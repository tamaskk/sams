"""Vercel deployment — deploy a directory (a local project or a GitHub clone) to
Vercel via the Vercel CLI, streaming output onto the event bus (Agent Logs).

Needs VERCEL_TOKEN (Vercel → Account Settings → Tokens). Uses the `vercel` CLI if
on PATH, otherwise falls back to `npx vercel`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
from typing import Any

from .github_work import _run as _git_run, clone_url

log = logging.getLogger("sams.integrations.vercel")

_URL_RE = re.compile(r"https://[^\s]+\.vercel\.app")


class VercelDeployer:
    def __init__(self, event_bus, space: str = "main.space") -> None:
        self.event_bus = event_bus
        self.space = space

    @property
    def token(self) -> str | None:
        return os.environ.get("VERCEL_TOKEN")

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _cli(self) -> list[str]:
        return ["vercel"] if shutil.which("vercel") else ["npx", "--yes", "vercel@latest"]

    async def _log(self, message: str, level: str = "INFO", actor: str = "deployer") -> None:
        await self.event_bus.emit(
            "agent.log", {"agent": actor, "level": level, "message": message},
            actor=actor, space=self.space,
        )

    async def _run_streamed(self, cmd: list[str], cwd: str, token: str, capture_url: bool = False) -> tuple[int, str | None, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=cwd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            await self._log("❌ Neither `vercel` nor `npx` was found — install with `npm i -g vercel`.", level="ERROR")
            return 127, None, ""
        url: str | None = None
        lines: list[str] = []
        assert proc.stdout is not None
        async for raw in proc.stdout:
            text = raw.decode(errors="replace").rstrip()
            if not text:
                continue
            red = text.replace(token, "***")
            await self._log(red)
            lines.append(red)
            if capture_url:
                m = _URL_RE.search(text)
                if m:
                    url = m.group(0)
        await proc.wait()
        return (proc.returncode or 0), url, "\n".join(lines)

    async def deploy(self, directory: str, prod: bool = True) -> dict[str, Any]:
        """Build + deploy on Vercel. Vercel builds first and only promotes a
        successful build to production (a failed build is reported and never goes
        live), so this is "build, then deploy" — done in Vercel's environment, which
        has the right Node version + system env vars (local `vercel build` can't,
        e.g. when the local Node version isn't one Vercel supports)."""
        token = self.token
        if not token:
            await self._log("❌ VERCEL_TOKEN is not set.", level="ERROR")
            return {"ok": False, "reason": "no token"}
        if not os.path.isdir(directory):
            await self._log(f"❌ Directory not found: {directory}", level="ERROR")
            return {"ok": False, "reason": "no dir"}
        cli = self._cli()
        env = "production" if prod else "preview"
        name = os.path.basename(directory.rstrip("/")) or directory
        prod_flag = ["--prod"] if prod else []

        await self._log(f"▲ Building & deploying {name} on Vercel ({env}) …")
        rc, url, _ = await self._run_streamed(
            cli + ["deploy", "--yes", "--token", token] + prod_flag, directory, token, capture_url=True)
        if rc == 0:
            await self._log(f"✅ Deployed: {url or '(URL in the log above)'}", level="SUCCESS")
            return {"ok": True, "url": url}
        await self._log(f"❌ Build/deploy failed (exit {rc}) — production not updated.", level="ERROR")
        return {"ok": False, "url": url, "code": rc}

    @staticmethod
    def _join_subdir(base: str, subdir: str | None) -> str | None:
        """Join a subfolder onto base, refusing anything that escapes base."""
        if not subdir:
            return base
        sub = subdir.strip().strip("/")
        if not sub:
            return base
        full = os.path.realpath(os.path.join(base, sub))
        rbase = os.path.realpath(base)
        if full != rbase and not full.startswith(rbase + os.sep):
            return None
        return full

    async def deploy_target(self, target: str, github_token: str | None = None,
                            prod: bool = True, subdir: str | None = None) -> dict[str, Any]:
        """Deploy a local path or a ``github:owner/name`` repo, optionally only a
        subfolder (``subdir``) of it — for monorepos."""
        if target.startswith("github:"):
            full = target[len("github:"):]
            base = tempfile.mkdtemp(prefix="sams-vercel-")
            # Clone into a repo-named dir so the Vercel CLI uses the repo (or, with
            # a subdir, the subfolder) name as the project — not a random temp name.
            dest = os.path.join(base, full.split("/")[-1])
            try:
                await self._log(f"📥 Cloning {full} …")
                rc, out = await _git_run(["git", "clone", "--depth", "1", clone_url(full, github_token), dest], None, redact=github_token)
                if rc != 0:
                    await self._log(f"❌ Clone failed: {out.strip()[:200]}", level="ERROR")
                    return {"ok": False, "reason": "clone failed"}
                eff = self._join_subdir(dest, subdir)
                if eff is None:
                    await self._log("❌ Invalid folder path.", level="ERROR")
                    return {"ok": False, "reason": "bad subdir"}
                if not os.path.isdir(eff):
                    await self._log(f"❌ Folder not found in the repo: {subdir}", level="ERROR")
                    return {"ok": False, "reason": "no subdir"}
                if subdir:
                    await self._log(f"📁 Deploying subfolder: {subdir}")
                return await self.deploy(eff, prod)
            finally:
                shutil.rmtree(base, ignore_errors=True)
                await self._log("🧹 Cleaned up the clone.")
        eff = self._join_subdir(target, subdir)
        if eff is None:
            await self._log("❌ Invalid folder path.", level="ERROR")
            return {"ok": False, "reason": "bad subdir"}
        return await self.deploy(eff, prod)
