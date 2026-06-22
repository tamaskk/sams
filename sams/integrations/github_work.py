"""Run an agent on a GitHub repo via an ephemeral clone.

So agents can work on repos that aren't checked out locally: clone the repo into
a temp dir, let the local Claude Code agent make changes, push them to a new
branch, open a pull request, then delete the clone. Progress is streamed onto the
event bus as ``agent.log`` so it shows live in the Agent Logs feed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
from typing import Any

from .github_api import GitHubClient

log = logging.getLogger("sams.integrations.github_work")


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:32] or "task"


def clone_url(full_name: str, token: str | None) -> str:
    """An authenticated clone URL (token embedded) so private repos work."""
    return (f"https://x-access-token:{token}@github.com/{full_name}.git"
            if token else f"https://github.com/{full_name}.git")


async def _run(cmd: list[str], cwd: str | None, redact: str | None = None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    text = out.decode(errors="replace") if out else ""
    if redact:
        text = text.replace(redact, "***")
    return proc.returncode or 0, text


class GitHubWorker:
    def __init__(self, coder, github: GitHubClient, event_bus, space: str = "main.space") -> None:
        self.coder = coder
        self.github = github
        self.event_bus = event_bus
        self.space = space

    async def _log(self, message: str, level: str = "INFO", actor: str = "github") -> None:
        await self.event_bus.emit(
            "agent.log", {"agent": actor, "level": level, "message": message},
            actor=actor, space=self.space,
        )

    async def work(self, full_name: str, task: str, base: str | None = None) -> dict[str, Any]:
        token = self.github.token
        tmp = tempfile.mkdtemp(prefix="sams-repo-")
        try:
            await self._log(f"📥 Cloning {full_name} …")
            rc, out = await _run(["git", "clone", "--depth", "1", clone_url(full_name, token), tmp], None, redact=token)
            if rc != 0:
                await self._log(f"❌ Clone failed: {out.strip()[:300]}", level="ERROR")
                return {"ok": False, "reason": "clone failed"}

            base = base or await self.github.default_branch(full_name) or "main"
            branch = f"sams/{_slug(task)}-{os.urandom(2).hex()}"
            await _run(["git", "checkout", "-b", branch], tmp)
            await _run(["git", "config", "user.email", "sams-agent@users.noreply.github.com"], tmp)
            await _run(["git", "config", "user.name", "SAMS Agent"], tmp)

            if not self.coder.available:
                await self._log("❌ The `claude` CLI is not available — cannot edit code.", level="ERROR")
                return {"ok": False, "reason": "claude unavailable"}

            await self._log("🛠️ Agent working on the task …", actor="developer")
            prompt = (
                f"You are working inside a fresh clone of the GitHub repository '{full_name}'.\n\n"
                f"Task:\n{task}\n\n"
                "Make the necessary code changes directly in the files. Keep the change "
                "focused, correct, and consistent with the existing code."
            )

            async def on_event(line: str) -> None:
                await self.event_bus.emit(
                    "agent.log", {"agent": "developer", "level": "INFO", "message": line},
                    actor="developer", space=self.space,
                )

            result = await self.coder.run(tmp, prompt, on_event=on_event)

            rc, status = await _run(["git", "status", "--porcelain"], tmp)
            if not status.strip():
                await self._log("ℹ️ The agent produced no changes — nothing to push.")
                return {"ok": True, "changed": False, "summary": result.get("summary", "")}

            await _run(["git", "add", "-A"], tmp)
            await _run(["git", "commit", "-m", f"SAMS agent: {task[:72]}"], tmp)
            await self._log("⬆️ Pushing branch …")
            rc, out = await _run(["git", "push", "-u", "origin", branch], tmp, redact=token)
            if rc != 0:
                await self._log(f"❌ Push failed: {out.strip()[:300]}", level="ERROR")
                return {"ok": False, "reason": "push failed"}

            pr_url: str | None = None
            try:
                pr = await self.github.open_pr(
                    full_name, branch, base, f"SAMS: {task[:60]}",
                    f"Automated changes by a SAMS agent.\n\n**Task**\n{task}",
                )
                pr_url = pr.get("html_url")
                await self._log(f"✅ Opened pull request: {pr_url}", level="SUCCESS")
            except Exception as exc:  # noqa: BLE001
                await self._log(
                    f"✅ Pushed branch '{branch}'. Open a PR: "
                    f"https://github.com/{full_name}/pull/new/{branch}  ({exc})",
                    level="SUCCESS",
                )
            return {"ok": True, "changed": True, "branch": branch, "pr": pr_url}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            await self._log("🧹 Cleaned up the local clone.")
