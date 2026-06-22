"""The Kanban pipeline controller.

Turns the role-columns into an automated pipeline: moving a card into an agent's
column dispatches that agent to work on it (scoped to the card's project folder
and carrying the prior stages' outputs). The **Deployer** column is a human
validation gate — the deploy only runs after the human accepts, even in
Development Mode.

    To Do → (idle)
    Planner / Designer / Developer / Reviewer / Tester → the agent works
    Deployer → await human Validate/Accept → then deploy/commit
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .coding import ClaudeCodeRunner
from .core.retry import RetryOptions, async_retry
from .integrations.github_api import GitHubClient
from .integrations.github_work import _run as _git_run, _slug, clone_url
from .orchestrator.models import Task

if TYPE_CHECKING:
    from .core.event_bus import EventBus
    from .kanban.board import KanbanBoard
    from .orchestrator.orchestrator import Orchestrator
    from .security.gate import SecurityGate

log = logging.getLogger("sams.pipeline")

# The full pipeline order. A card auto-advances through it as each stage finishes,
# until the Deployer (which waits for the human's validation).
PIPELINE = ["To Do", "Planner", "Designer", "Developer", "Reviewer", "Tester", "Deployer"]

# Column -> (agent id, capability) for the auto-working stages.
STAGE_ROLES: dict[str, tuple[str, str]] = {
    "Planner": ("planner", "plan.spec"),
    "Designer": ("designer", "design.wireframe"),
    "Developer": ("developer", "code.write"),
    "Reviewer": ("reviewer", "code.review"),
    "Tester": ("tester", "qa.test.run"),
}
DEPLOY_COLUMN = "Deployer"
COMMITTED_COLUMN = "Committed"  # terminal parking column at the right end

# Each stage runs the local Claude Code CLI in the card's project with a
# role-specific prompt — so every stage does *real* work on the actual project.
STAGE_PROMPTS: dict[str, str] = {
    "Planner": (
        "Act as the Planner. Read the relevant parts of this project and produce a concise, concrete "
        "implementation plan for the task: the steps, which files likely need to change, and any risks. "
        "Do NOT modify any files — output the plan only."
    ),
    "Designer": (
        "Act as the Designer. Inspect the relevant UI/markup/styles in this project and give specific "
        "design and UX guidance for the task: layout, spacing, copy, components, and concrete style "
        "values to use. Do NOT modify any files — output the design notes only."
    ),
    "Developer": (
        "Implement the task by editing the code in this project, using the prior plan/design notes below "
        "as guidance. Make the minimal necessary edits directly to the project files. "
        "Do not start or run the dev server."
    ),
    "Reviewer": (
        "Act as the code Reviewer. Run `git diff` to see the recent changes and review them for "
        "correctness, bugs, security, and standards relevant to the task. Output concise findings and "
        "whether it is good to ship. Do NOT modify any files."
    ),
    "Tester": (
        "Act as the Tester. Run the project's tests if present (e.g. `npm test`, `pytest`) or otherwise "
        "do a quick build/smoke check (e.g. `npm run build`). Report exactly what you ran and the "
        "results. Do NOT modify any source files."
    ),
}

# Pause between auto-advanced stages so the progression is watchable.
STAGE_DELAY = 0.6


class PipelineController:
    def __init__(
        self,
        event_bus: "EventBus",
        kanban: "KanbanBoard",
        orchestrator: "Orchestrator",
        gate: "SecurityGate",
        *,
        space: str = "main.space",
        storage_path: str | Path | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.kanban = kanban
        self.orchestrator = orchestrator
        self.gate = gate
        self.space = space
        self.coder = ClaudeCodeRunner()
        self._running: dict[str, asyncio.Task] = {}
        # User-editable per-stage prompt overrides (persisted across restarts).
        self._prompts_path = Path(storage_path) if storage_path else None
        self._prompt_overrides: dict[str, str] = {}
        self._load_prompts()
        # GitHub-repo projects (project == "github:owner/name") get a per-card
        # ephemeral clone that the stages edit; pushed as a PR at the deploy gate.
        self._github = GitHubClient()
        self._gh_dirs: dict[str, str] = {}
        self._gh_base: dict[str, str] = {}
        self._gh_branch: dict[str, str] = {}

    def wire(self) -> None:
        self.event_bus.subscribe("kanban.card.moved", self._on_card_moved, name="pipeline:moved")

    def rearm_pending(self) -> None:
        """After a restart, mark Deployer cards 'ready' so the Commit button shows."""
        for card in self.kanban.all():
            if card.status == DEPLOY_COLUMN and card.stage_status not in ("committing", "committed"):
                card.stage_status = "ready"

    async def _on_card_moved(self, event) -> None:
        card_id = event.payload.get("card_id")
        to = event.payload.get("to")
        card = self.kanban.get(card_id) if card_id else None
        if card is None:
            return
        # A manual (human) move stops/redirects any in-flight work for this card —
        # drag to "To Do" to stop it, or drag back to an earlier stage to restart.
        # Pipeline auto-advance moves (actor "pipeline") must NOT cancel themselves.
        if event.actor != "pipeline":
            await self._cancel(card_id)
        if to in STAGE_ROLES:
            self._start(card_id, self._run_stage(card_id, to))
        elif to == DEPLOY_COLUMN:
            # No approval gate — the work is already done; the card just waits for a
            # human to press Commit (see commit()).
            card.stage_status = "ready"
            card.gate_id = None
            await self._emit_update(card_id, {"stage": DEPLOY_COLUMN, "status": "ready"})
        elif to == COMMITTED_COLUMN:
            card.gate_id = None
            # A manual drag here marks it committed; commit() drives its own status.
            if event.actor != "pipeline":
                card.stage_status = "committed"
                await self._emit_update(card_id, {"stage": COMMITTED_COLUMN, "status": "committed"})
        elif to == "To Do":
            card.stage_status = "idle"
            card.gate_id = None
            self._cleanup_gh(card_id)  # discard the working clone when stopped
            await self._emit_update(card_id, {"stage": "To Do", "status": "stopped"})

    def _start(self, card_id: str, coro) -> None:
        self._running[card_id] = asyncio.create_task(coro)

    async def _cancel(self, card_id: str) -> None:
        task = self._running.pop(card_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    # --- GitHub-repo project working clones ---------------------------------
    async def _glog(self, message: str, level: str = "INFO", actor: str = "github") -> None:
        await self.event_bus.emit(
            "agent.log", {"agent": actor, "level": level, "message": message},
            actor=actor, space=self.space,
        )

    async def _resolve_dir(self, card_id: str, card) -> tuple[str | None, str | None]:
        """Resolve a card's project to (local_dir, github_full_name|None).

        For a ``github:owner/name`` project, ensure a per-card clone exists on a
        ``sams/<card>`` branch and return that directory so the stages edit it.
        """
        p = card.project or ""
        if not p.startswith("github:"):
            return (p or None), None
        full = p[len("github:"):]
        existing = self._gh_dirs.get(card_id)
        if existing and os.path.isdir(existing):
            return existing, full
        token = self._github.token
        await self._glog(f"📥 Cloning {full} …")
        try:
            base = await self._github.default_branch(full)
        except Exception:  # noqa: BLE001
            base = None
        dest = tempfile.mkdtemp(prefix=f"sams-{_slug(card_id)}-")
        rc, out = await _git_run(["git", "clone", "--depth", "1", clone_url(full, token), dest], None, redact=token)
        if rc != 0:
            await self._glog(f"❌ Clone failed: {out.strip()[:200]}", level="ERROR")
            shutil.rmtree(dest, ignore_errors=True)
            return None, full
        branch = f"sams/{_slug(card_id)}-{os.urandom(2).hex()}"
        await _git_run(["git", "checkout", "-b", branch], dest)
        await _git_run(["git", "config", "user.email", "sams-agent@users.noreply.github.com"], dest)
        await _git_run(["git", "config", "user.name", "SAMS Agent"], dest)
        self._gh_dirs[card_id] = dest
        self._gh_base[card_id] = base or "main"
        self._gh_branch[card_id] = branch
        return dest, full

    def _cleanup_gh(self, card_id: str) -> None:
        d = self._gh_dirs.pop(card_id, None)
        self._gh_base.pop(card_id, None)
        self._gh_branch.pop(card_id, None)
        if d:
            shutil.rmtree(d, ignore_errors=True)

    # --- an agent works a stage ---------------------------------------------
    async def _run_stage(self, card_id: str, column: str) -> None:
        card = self.kanban.get(card_id)
        if card is None:
            return
        role, capability = STAGE_ROLES[column]
        card.stage_status = "working"
        card.gate_id = None
        await self._emit_update(card_id, {"stage": column, "agent": role, "status": "working"})

        # Real work via the local Claude Code CLI when a project is set; otherwise
        # fall back to the model-backed agent (mock when offline). A GitHub-repo
        # project resolves to a per-card clone the stages edit.
        project_dir, gh_repo = await self._resolve_dir(card_id, card)
        if self.coder.available and project_dir:
            label = gh_repo or Path(project_dir).name
            await self._emit_agent_state(role, "working", f"{column.lower()} · {label}")

            async def on_event(line: str, _role=role, _col=column) -> None:
                await self.event_bus.emit(
                    "agent.log",
                    {"agent": _role, "level": "INFO", "message": f"[{_col}] {line}"},
                    actor=_role, space=self.space,
                )

            retry_cfg = (
                RetryOptions.from_dict(card.retry_options) if card.retry_options
                else RetryOptions(max_attempts=1)
            )
            _attempt_num = [0]

            async def _coder_attempt() -> dict:
                _attempt_num[0] += 1
                if _attempt_num[0] > 1:
                    await on_event(f"🔄 Retry {_attempt_num[0]}/{retry_cfg.max_attempts}…")
                r = await self.coder.run(
                    project_dir, self._stage_prompt(column, card), on_event=on_event
                )
                if not r.get("ok"):
                    raise RuntimeError(r.get("reason") or r.get("summary") or "run failed")
                return r

            try:
                result = await async_retry(_coder_attempt, retry_cfg)
            except asyncio.CancelledError:
                await self._emit_agent_state(role, "idle", "")  # stage stopped — release the robot
                raise
            except RuntimeError as exc:
                result = {"ok": False, "reason": str(exc), "changed": []}
            await self._emit_agent_state(role, "idle", "")
            output = self._format_result(column, result)
            changed = result.get("changed") or []
            await self.event_bus.emit(
                "project.edited",
                {"card_id": card_id, "project": card.project, "stage": column,
                 "ok": result.get("ok"), "changed": changed,
                 "summary": (result.get("summary") or result.get("reason") or "")[:300]},
                space=self.space,
            )
            if not result.get("ok"):
                card.outputs[column] = output
                card.stage_status = "error"
                await self._emit_update(card_id, {"stage": column, "status": "error"})
                return  # a real failure (CLI/auth) — stop so the human can look
        else:
            prior = "\n".join(f"- {stage}: {out}" for stage, out in card.outputs.items())
            task = Task(
                title=card.title, capability=capability, assignee=role, card_id=card_id,
                inputs={"description": card.description, "project": card.project,
                        "prior_stages": prior or "(none)", "stage": column},
                space=self.space,
            )
            completed = await self.orchestrator.assign_and_run(task)
            if completed.status != "complete":
                card.stage_status = "error"
                await self._emit_update(card_id, {"stage": column, "status": "error"})
                return
            output = _summarize(completed.result)
            if card.project and not self.coder.available:
                output += "  ⚠️ real work skipped — `claude` CLI not found (or SAMS_AUTOEDIT=0)."

        card.outputs[column] = output
        card.stage_status = "done"
        await self._emit_update(card_id, {"stage": column, "status": "done"})

        # Auto-advance to the next stage — the card flows through the whole
        # pipeline until it reaches the Deployer's human validation gate.
        idx = PIPELINE.index(column) if column in PIPELINE else -1
        if 0 <= idx < len(PIPELINE) - 1 and self.kanban.get(card_id) is not None:
            await asyncio.sleep(STAGE_DELAY)
            # Only advance if it hasn't been moved elsewhere in the meantime.
            if self.kanban.get(card_id).status == column:
                await self.kanban.move(card_id, PIPELINE[idx + 1], actor="pipeline")

    # --- the human Commit step (no approval gate) ---------------------------
    async def commit(self, card_id: str) -> None:
        """On Commit: move the card straight to the 'Committed' column, then run the
        commit (github push + PR, or deploy) there. No approval gate."""
        card = self.kanban.get(card_id)
        if card is None:
            return
        card.gate_id = None
        # Move to Committed immediately so it lands there the moment you click.
        await self.kanban.move(card_id, COMMITTED_COLUMN, actor="pipeline")
        card = self.kanban.get(card_id)
        if card is None:
            return
        card.stage_status = "committing"
        await self._emit_update(card_id, {"stage": COMMITTED_COLUMN, "status": "committing"})
        if (card.project or "").startswith("github:"):
            await self._finalize_github(card_id, card)
        else:
            await self._commit_local(card_id, card)
        card.stage_status = "committed"
        await self._emit_update(card_id, {"stage": COMMITTED_COLUMN, "status": "committed"})

    async def _commit_local(self, card_id: str, card) -> None:
        """A real git commit (+ push) of the agents' changes in a local project."""
        proj = card.project

        async def glog(msg: str, level: str = "INFO") -> None:
            await self.event_bus.emit("agent.log", {"agent": "deployer", "level": level, "message": msg},
                                      actor="deployer", space=self.space)

        if not proj or not os.path.isdir(proj):
            card.outputs[COMMITTED_COLUMN] = "⚠️ no project folder to commit."
            await glog("No project folder to commit.", level="ERROR")
            return
        rc, _ = await _git_run(["git", "rev-parse", "--is-inside-work-tree"], proj)
        if rc != 0:
            await glog(f"📦 Initializing a git repo in {os.path.basename(proj.rstrip('/'))} …")
            await _git_run(["git", "init"], proj)
        rc, dirty = await _git_run(["git", "status", "--porcelain"], proj)
        if not dirty.strip():
            card.outputs[COMMITTED_COLUMN] = "No changes to commit."
            await glog("No changes to commit.")
            return
        n = len([ln for ln in dirty.splitlines() if ln.strip()])
        await glog(f"📝 Committing {n} changed file(s) …")
        await _git_run(["git", "add", "-A"], proj)
        await _git_run(["git", "-c", "user.email=sams-agent@users.noreply.github.com",
                        "-c", "user.name=SAMS Agent", "commit", "-m", f"SAMS: {card.title[:72]}"], proj)
        # Push if there's a remote (use the GitHub token for github https remotes).
        rc, remote_url = await _git_run(["git", "remote", "get-url", "origin"], proj)
        remote_url = remote_url.strip()
        if not remote_url:
            card.outputs[COMMITTED_COLUMN] = f"committed locally ({n} file(s)) — no remote to push to."
            await glog(f"✅ Committed locally ({n} file(s)). No 'origin' remote — not pushed.", level="SUCCESS")
            return
        rc, branch = await _git_run(["git", "rev-parse", "--abbrev-ref", "HEAD"], proj)
        branch = branch.strip() or "main"
        token = self._github.token
        await glog("⬆️ Pushing …")
        if remote_url.startswith("https://github.com/") and token:
            auth = remote_url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/", 1)
            rc, out = await _git_run(["git", "push", auth, branch], proj, redact=token)
        else:
            rc, out = await _git_run(["git", "push", "origin", branch], proj, redact=token)
        if rc == 0:
            card.outputs[COMMITTED_COLUMN] = f"committed & pushed ({n} file(s)) to {branch}."
            await glog(f"✅ Committed & pushed {n} file(s) to {branch}.", level="SUCCESS")
        else:
            card.outputs[COMMITTED_COLUMN] = f"committed ({n} file(s)); push failed: {out.strip()[:160]}"
            await glog(f"⚠️ Committed locally, but push failed: {out.strip()[:200]}", level="ERROR")

    async def _finalize_github(self, card_id: str, card) -> None:
        """Commit the per-card clone, push a branch and open a PR, then clean up."""
        full = (card.project or "")[len("github:"):]
        token = self._github.token
        d = self._gh_dirs.get(card_id)
        if not d or not os.path.isdir(d):
            # The clone was ephemeral and lost on restart — re-clone and regenerate
            # the change from the task + prior stage notes so Accept still works.
            await self._glog("Working clone was lost on restart — re-cloning and regenerating the change…", actor="deployer")
            d, _ = await self._resolve_dir(card_id, card)
            if not d:
                card.outputs[DEPLOY_COLUMN] = "⚠️ could not clone the repo to deploy."
                await self._glog("Could not clone the repo to deploy.", level="ERROR", actor="deployer")
                return
            if self.coder.available:
                async def on_event(line: str) -> None:
                    await self.event_bus.emit(
                        "agent.log", {"agent": "developer", "level": "INFO", "message": f"[Developer] {line}"},
                        actor="developer", space=self.space,
                    )
                await self.coder.run(d, self._stage_prompt("Developer", card), on_event=on_event)
        _, dirty = await _git_run(["git", "status", "--porcelain"], d)
        if not dirty.strip():
            card.outputs[DEPLOY_COLUMN] = "No changes to push."
            await self._glog("No changes to push.", actor="deployer")
            self._cleanup_gh(card_id)
            return
        branch = self._gh_branch.get(card_id) or f"sams/{_slug(card_id)}"
        await _git_run(["git", "add", "-A"], d)
        await _git_run(["git", "commit", "-m", f"SAMS: {card.title[:72]}"], d)
        await self._glog("⬆️ Pushing branch …", actor="deployer")
        rc, out = await _git_run(["git", "push", "-u", "origin", branch], d, redact=token)
        if rc != 0:
            card.outputs[DEPLOY_COLUMN] = f"⚠️ push failed: {out.strip()[:200]}"
            await self._glog(f"❌ Push failed: {out.strip()[:200]}", level="ERROR", actor="deployer")
            return
        base = self._gh_base.get(card_id) or "main"
        pr_url: str | None = None
        try:
            pr = await self._github.open_pr(
                full, branch, base, f"SAMS: {card.title[:60]}",
                f"Automated changes by the SAMS pipeline.\n\n{card.description or ''}",
            )
            pr_url = pr.get("html_url")
        except Exception as exc:  # noqa: BLE001
            await self._glog(f"Pushed branch '{branch}' (PR not auto-created: {exc})",
                             level="SUCCESS", actor="deployer")
        if pr_url:
            await self._glog(f"✅ Opened pull request: {pr_url}", level="SUCCESS", actor="deployer")
            card.outputs[DEPLOY_COLUMN] = f"PR opened: {pr_url}"
        else:
            card.outputs[DEPLOY_COLUMN] = f"Pushed branch {branch} — open a PR on GitHub."
        self._cleanup_gh(card_id)

    # --- editable per-stage prompts -----------------------------------------
    def _load_prompts(self) -> None:
        if not self._prompts_path or not self._prompts_path.exists():
            return
        try:
            data = json.loads(self._prompts_path.read_text())
            self._prompt_overrides = {k: v for k, v in data.items() if k in STAGE_PROMPTS and isinstance(v, str)}
        except (json.JSONDecodeError, OSError):
            pass

    def _save_prompts(self) -> None:
        if not self._prompts_path:
            return
        try:
            self._prompts_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._prompts_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._prompt_overrides, indent=2))
            tmp.replace(self._prompts_path)
        except OSError:
            pass

    def stage_prompt_text(self, column: str) -> str:
        return self._prompt_overrides.get(column) or STAGE_PROMPTS.get(column, "")

    def stage_prompts(self) -> dict[str, dict]:
        return {
            col: {"default": STAGE_PROMPTS[col],
                  "prompt": self._prompt_overrides.get(col, STAGE_PROMPTS[col]),
                  "overridden": col in self._prompt_overrides}
            for col in STAGE_PROMPTS
        }

    def set_stage_prompt(self, column: str, text: str | None) -> None:
        if column not in STAGE_PROMPTS:
            return
        if not text or not text.strip() or text.strip() == STAGE_PROMPTS[column].strip():
            self._prompt_overrides.pop(column, None)  # back to default
        else:
            self._prompt_overrides[column] = text
        self._save_prompts()

    def _stage_prompt(self, column: str, card) -> str:
        parts = [self.stage_prompt_text(column), "", f"Task: {card.title}"]
        if card.description:
            parts.append(f"Details: {card.description}")
        if getattr(card, "image", None):
            parts.append(f"\nA reference image for this task is attached at: {card.image}\n"
                         "Use the Read tool to open and view it for visual context before you work.")
        # The Developer benefits from the plan/design produced by earlier stages.
        if column == "Developer" and card.outputs:
            prior = "\n\n".join(f"[{stage}]\n{out}" for stage, out in card.outputs.items())
            parts.append(f"\nPrior stage notes:\n{prior}")
        return "\n".join(parts)

    @staticmethod
    def _format_result(column: str, result: dict) -> str:
        if not result.get("ok"):
            return f"⚠️ {column} failed: {result.get('reason') or (result.get('summary') or '')[:200]}"
        changed = result.get("changed")
        head = ""
        if changed:
            head = f"✏️ changed {len(changed)} file(s): " + ", ".join(changed[:10]) + "\n\n"
        body = (result.get("summary") or "").strip()[:800]
        cost = result.get("cost")
        return head + body + (f"\n\n(~${cost:.4f})" if cost else "")

    async def _emit_agent_state(self, agent_id: str, state: str, task_label: str) -> None:
        await self.event_bus.emit(
            "agent.state.changed",
            {"agent": agent_id, "state": state,
             "telemetry": {"current_task": task_label} if task_label else {}},
            actor=agent_id, space=self.space,
        )

    async def _emit_update(self, card_id: str, extra: dict | None = None) -> None:
        card = self.kanban.get(card_id)
        await self.event_bus.emit(
            "kanban.card.stage", {"card_id": card_id, "stage_status": card.stage_status if card else None,
                                  **(extra or {})},
            space=self.space,
        )


def _summarize(result) -> str:
    if isinstance(result, dict):
        return str(result.get("summary") or result.get("artifact") or result)[:400]
    return str(result)[:400]
