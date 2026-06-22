"""Real code edits via the local Claude Code CLI.

Instead of an API key, SAMS drives the user's installed ``claude`` CLI headlessly
in the card's project directory, so the Developer stage makes **actual edits to
the real project files** using the user's existing Claude auth. The dev server
hot-reloads and the change is visible immediately.

    claude -p "<task>" --permission-mode bypassPermissions --output-format json

Disabled with ``SAMS_AUTOEDIT=0``; model overridable with ``SAMS_CLAUDE_MODEL``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import tempfile
from pathlib import Path
from typing import Any

from .core.retry import RetryOptions, async_retry

log = logging.getLogger("sams.coding")


def _model_alias(model: str | None) -> str:
    """Map a model name/id to a `claude` CLI alias the CLI reliably accepts."""
    m = (model or "").lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    return "sonnet"


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    """Kill the subprocess and any children (it runs in its own session)."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


async def _emit(on_event, line: str) -> None:
    if on_event is not None and line:
        try:
            await on_event(line)
        except Exception:  # noqa: BLE001
            pass


def _fmt_tool(name: str, inp: dict) -> str:
    """Turn a Claude Code tool call into a short, human-readable activity line."""
    def base(p):
        return str(p).rsplit("/", 1)[-1] if p else ""
    if name in ("Edit", "MultiEdit"):
        return f"✏️ editing {base(inp.get('file_path'))}"
    if name == "Write":
        return f"📝 writing {base(inp.get('file_path'))}"
    if name == "Read":
        return f"📖 reading {base(inp.get('file_path'))}"
    if name == "Bash":
        return f"🔧 $ {str(inp.get('command', '')).strip()[:90]}"
    if name in ("Grep", "Glob"):
        return f"🔍 searching {inp.get('pattern') or inp.get('query') or ''}"
    if name == "TodoWrite":
        return "📋 planning the steps…"
    if name in ("WebFetch", "WebSearch"):
        return f"🌐 {name}: {inp.get('url') or inp.get('query') or ''}"
    return f"🔧 {name}"


class ClaudeCodeRunner:
    def __init__(self, model: str | None = None, timeout: float = 900.0) -> None:
        self.bin = shutil.which("claude")
        self.model = model or os.environ.get("SAMS_CLAUDE_MODEL", "sonnet")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return self.bin is not None and os.environ.get("SAMS_AUTOEDIT", "1") == "1"

    @property
    def installed(self) -> bool:
        return self.bin is not None

    async def ask(self, prompt: str, *, model: str | None = None, timeout: float = 120.0,
                  retry: RetryOptions | None = None) -> str:
        """One-shot Q&A via the local `claude` CLI (no file editing). Returns the text.

        Automatically retried on transient failures. Pass retry=RetryOptions(max_attempts=1)
        to disable retries, or customise max_attempts/initial_delay/backoff_multiplier.
        """
        if self.bin is None:
            raise RuntimeError("the `claude` CLI was not found on PATH")
        opts = retry if retry is not None else RetryOptions()
        cmd = [self.bin, "-p", prompt, "--output-format", "text", "--model", _model_alias(model or self.model)]

        async def _attempt() -> str:
            cwd = tempfile.mkdtemp(prefix="sams-ask-")
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, cwd=cwd, start_new_session=True,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                try:
                    out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                except asyncio.TimeoutError:
                    _kill_group(proc)
                    raise RuntimeError("claude timed out")
                if proc.returncode != 0:
                    raise RuntimeError((err or b"").decode(errors="replace").strip()[-300:] or "claude exited with an error")
                return (out or b"").decode(errors="replace").strip()
            finally:
                shutil.rmtree(cwd, ignore_errors=True)

        return await async_retry(_attempt, opts)

    async def run(self, project_dir: str, prompt: str, on_event=None) -> dict[str, Any]:
        """Run the local Claude Code headlessly in ``project_dir`` with ``prompt``.

        Streams Claude's activity (reads, edits, commands, messages) via ``on_event``
        — an async callback receiving a short human-readable line per step — so the
        UI can show a live feed instead of an opaque "working…".

        Returns ``{ok, summary, changed, cost}`` where ``changed`` is the list of
        files git reports as modified during the run (``None`` if not a git repo).
        """
        if not self.bin:
            return {"ok": False, "reason": "the `claude` CLI was not found on PATH", "changed": []}
        root = Path(project_dir).expanduser().resolve()
        if not root.is_dir():
            return {"ok": False, "reason": f"project directory not found: {project_dir}", "changed": []}

        before = await self._git_dirty(root)
        cmd = [self.bin, "-p", prompt, "--permission-mode", "bypassPermissions",
               "--output-format", "stream-json", "--verbose"]
        if self.model:
            cmd += ["--model", self.model]
        log.info("claude run in %s: %s", root, prompt[:80])

        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(root),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=2 ** 20,
            start_new_session=True,  # own process group so we can kill the whole tree
        )
        summary, is_error, cost = "", False, None
        assert proc.stdout is not None
        try:
            while True:
                raw = await asyncio.wait_for(proc.stdout.readline(), self.timeout)
                if not raw:
                    break
                try:
                    ev = json.loads(raw.decode(errors="replace"))
                except json.JSONDecodeError:
                    continue
                etype = ev.get("type")
                if etype == "assistant":
                    for block in ev.get("message", {}).get("content", []):
                        if block.get("type") == "text" and block.get("text", "").strip():
                            await _emit(on_event, "💬 " + block["text"].strip()[:200])
                        elif block.get("type") == "tool_use":
                            await _emit(on_event, _fmt_tool(block.get("name", ""), block.get("input", {})))
                elif etype == "result":
                    summary = ev.get("result", "") or summary
                    is_error = bool(ev.get("is_error", False))
                    cost = ev.get("total_cost_usd")
        except asyncio.TimeoutError:
            _kill_group(proc)
            return {"ok": False, "reason": "claude timed out", "changed": []}
        except asyncio.CancelledError:
            # The stage was cancelled (e.g. the card was dragged away) — stop Claude.
            _kill_group(proc)
            raise
        await proc.wait()
        if not summary and proc.returncode != 0:
            is_error = True
            err = (await proc.stderr.read()).decode(errors="replace") if proc.stderr else ""
            summary = err[-400:] or "claude exited with an error"

        after = await self._git_dirty(root)
        changed = None if (before is None or after is None) else sorted(after - before)
        return {"ok": not is_error, "summary": summary.strip(), "changed": changed, "cost": cost}

    async def _git_dirty(self, root: Path) -> set[str] | None:
        """Filenames git reports as changed/untracked, or None if not a git repo."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain", cwd=str(root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), 15)
            if proc.returncode != 0:
                return None
            return {line[3:] for line in out.decode(errors="replace").splitlines() if len(line) > 3}
        except Exception:  # noqa: BLE001
            return None
