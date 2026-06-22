"""REST control-plane routes (spec 11.1)."""

from __future__ import annotations

import asyncio
import json as _json
import os
import re as _re
import signal
import subprocess
from pathlib import Path
from typing import Any

import httpx

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..integrations.clickup import ClickUpClient
from ..integrations.github_api import GitHubClient
from ..integrations.github_work import GitHubWorker
from ..integrations.vercel import VercelDeployer
from ..sdk.manifest import AgentManifest, load_manifest

router = APIRouter()
_clickup = ClickUpClient()
_github = GitHubClient()


def _platform(request: Request):
    return request.app.state.platform


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    return _platform(request).status()


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #
class SpawnAgentBody(BaseModel):
    manifest: str | None = None  # path to a manifest file
    manifest_doc: dict[str, Any] | None = None  # inline manifest
    ref: str | None = None  # built-in agent id
    instances: int = 1


@router.get("/agents")
async def list_agents(request: Request, space: str | None = None) -> list[dict[str, Any]]:
    return _platform(request).list_agents(space)


@router.post("/agents")
async def spawn_agent(request: Request, body: SpawnAgentBody) -> dict[str, Any]:
    p = _platform(request)
    if body.manifest_doc:
        manifest = AgentManifest.from_dict(body.manifest_doc)
    elif body.manifest:
        manifest = load_manifest(Path(p.config.workspace_root) / body.manifest)
    elif body.ref:
        manifest = p.agent_registry.get(body.ref)
        if manifest is None:
            raise HTTPException(404, f"unknown agent ref {body.ref}")
    else:
        raise HTTPException(400, "provide manifest, manifest_doc, or ref")
    agent = await p.spawn_agent(manifest)
    return {"agent_id": agent.id, "name": agent.name, "spawned": True}


class SpawnTypeBody(BaseModel):
    ref: str


@router.post("/agents/spawn")
async def spawn_type(request: Request, body: SpawnTypeBody) -> dict[str, Any]:
    """Spawn an (additional) instance of an agent type — used by drag-to-spawn."""
    try:
        agent = await _platform(request).spawn_type(body.ref)
    except KeyError:
        raise HTTPException(404, f"unknown agent type {body.ref}")
    return {"agent_id": agent.id, "name": agent.name, "spawned": True}


@router.get("/agents/{agent_id}")
async def get_agent(request: Request, agent_id: str) -> dict[str, Any]:
    p = _platform(request)
    summary = next((a for a in p.list_agents() if a["agent_id"] == agent_id), None)
    if summary is None:
        raise HTTPException(404, f"no agent {agent_id}")
    # Enrich with the full manifest (systemPrompt, capabilities, tools, model,
    # permissions, memory, routing…) so the inspector can show everything.
    inst = next((a for a in p.runtime.instances() if a.id == agent_id), None)
    if inst is not None:
        doc = inst.manifest.to_dict()
        summary = {**summary, "metadata": doc.get("metadata", {}), "spec": doc.get("spec", {})}
    # If this agent drives a pipeline stage, include its (editable) stage prompt —
    # this is what actually controls what the agent does in the Kanban pipeline.
    base = agent_id.rsplit("-", 1)[0] if (agent_id.rsplit("-", 1)[-1].isdigit()) else agent_id
    column = base.capitalize()
    stages = p.pipeline.stage_prompts()
    if column in stages:
        summary["stage"] = {"column": column, **stages[column]}
    return summary


@router.get("/pipeline/prompts")
async def pipeline_prompts(request: Request) -> dict[str, Any]:
    return {"prompts": _platform(request).pipeline.stage_prompts()}


class StagePromptBody(BaseModel):
    column: str
    prompt: str | None = None


@router.patch("/pipeline/prompts")
async def set_pipeline_prompt(request: Request, body: StagePromptBody) -> dict[str, Any]:
    p = _platform(request)
    stages = p.pipeline.stage_prompts()
    if body.column not in stages:
        raise HTTPException(404, f"no pipeline stage {body.column}")
    p.pipeline.set_stage_prompt(body.column, body.prompt)
    await p.event_bus.emit(
        "agent.log",
        {"agent": "pipeline", "level": "INFO", "message": f"⚙️ {body.column} stage prompt updated"},
        actor="pipeline", space=p.default_space,
    )
    return p.pipeline.stage_prompts()[body.column]


class AgentPatchBody(BaseModel):
    systemPrompt: str | None = None
    role: str | None = None
    seniority: str | None = None
    description: str | None = None
    model_name: str | None = None
    model_provider: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    capabilities: list[str] | None = None
    tools: list[str] | None = None


@router.patch("/agents/{agent_id}")
async def patch_agent(request: Request, agent_id: str, body: AgentPatchBody) -> dict[str, Any]:
    """Edit a live agent's profile (prompt, model, capabilities, tools…). Applies
    in-place so it takes effect immediately, and persists to the manifest file when
    editing a base role (so it survives a restart)."""
    p = _platform(request)
    inst = next((a for a in p.runtime.instances() if a.id == agent_id), None)
    if inst is None:
        raise HTTPException(404, f"no agent {agent_id}")
    spec = inst.manifest.spec
    meta = inst.manifest.metadata
    if body.systemPrompt is not None: spec.systemPrompt = body.systemPrompt
    if body.role is not None: spec.role = body.role
    if body.seniority is not None: spec.seniority = body.seniority
    if body.description is not None: meta.description = body.description
    if body.model_provider is not None: spec.model.provider = body.model_provider
    if body.model_name is not None: spec.model.name = body.model_name
    if body.temperature is not None or body.max_tokens is not None:
        params = dict(spec.model.params or {})
        if body.temperature is not None: params["temperature"] = body.temperature
        if body.max_tokens is not None: params["max_tokens"] = body.max_tokens
        spec.model.params = params
    if body.capabilities is not None: spec.capabilities = [c.strip() for c in body.capabilities if c.strip()]
    if body.tools is not None: spec.tools = [t.strip() for t in body.tools if t.strip()]

    # Persist to the source manifest only for a base role (filename == id), so
    # editing a spawned instance (e.g. planner-2) never clobbers the base file.
    persisted = False
    src = getattr(inst.manifest, "source", None)
    if src and Path(src).name.replace(".agent.yaml", "").replace(".yaml", "") == agent_id:
        try:
            import yaml as _yaml
            Path(src).write_text(_yaml.safe_dump(inst.manifest.to_dict(), sort_keys=False, allow_unicode=True))
            persisted = True
        except Exception:  # noqa: BLE001
            pass

    await p.event_bus.emit(
        "agent.log",
        {"agent": agent_id, "level": "INFO",
         "message": f"⚙️ profile updated{' (saved to manifest)' if persisted else ' (until restart)'}"},
        actor=agent_id, space=p.default_space,
    )
    return await get_agent(request, agent_id)


class AssignBody(BaseModel):
    title: str
    capability: str | None = None
    inputs: dict[str, Any] = {}
    requires_gate: bool = False
    gate_approvers: list[str] = []


@router.post("/agents/{agent_id}/assign")
async def assign_task(request: Request, agent_id: str, body: AssignBody) -> dict[str, Any]:
    task = await _platform(request).submit_task(
        body.title, capability=body.capability, assignee=agent_id, inputs=body.inputs,
        requires_gate=body.requires_gate, gate_approvers=body.gate_approvers,
    )
    return task.to_dict()


@router.delete("/agents/{agent_id}")
async def despawn_agent(request: Request, agent_id: str) -> dict[str, Any]:
    await _platform(request).despawn_agent(agent_id)
    return {"agent_id": agent_id, "despawned": True}


# --------------------------------------------------------------------------- #
# Spaces / primitives
# --------------------------------------------------------------------------- #
@router.get("/spaces")
async def list_spaces(request: Request) -> list[dict[str, Any]]:
    p = _platform(request)
    return [{"id": sid, "agents": len(sp.agents), "primitives": len(sp.primitives)}
            for sid, sp in p.spatial.spaces.items()]


@router.get("/spaces/{space_id}/scene")
async def get_scene(request: Request, space_id: str) -> dict[str, Any]:
    scene = _platform(request).spatial.scene(space_id)
    if not scene:
        raise HTTPException(404, f"no space {space_id}")
    return scene


class PrimitiveBody(BaseModel):
    type: str
    name: str | None = None
    position: list[float] | None = None


@router.post("/spaces/{space_id}/primitives")
async def add_primitive(request: Request, space_id: str, body: PrimitiveBody) -> dict[str, Any]:
    prim = await _platform(request).spatial.add_primitive(space_id, body.type, body.name, body.position)
    return prim.to_dict()


# --------------------------------------------------------------------------- #
# Tasks (Kanban cards)
# --------------------------------------------------------------------------- #
class CardBody(BaseModel):
    title: str
    column: str = "To Do"
    labels: list[str] = []
    assignee: str | None = None
    priority: str = "Medium"
    description: str = ""
    project: str | None = None
    image_data: str | None = None  # data URL (data:image/png;base64,…)
    image_name: str | None = None
    retry_options: dict[str, Any] | None = None  # {max_attempts, initial_delay, backoff_multiplier}


def _image_ext(name: str | None, header: str) -> str:
    if name and "." in name:
        return "." + name.rsplit(".", 1)[-1].lower()[:5]
    for fmt, ext in (("png", ".png"), ("jpeg", ".jpg"), ("jpg", ".jpg"), ("webp", ".webp"), ("gif", ".gif")):
        if fmt in header:
            return ext
    return ".png"


class CardPatch(BaseModel):
    to: str | None = None  # move to column / skill stage
    progress: float | None = None
    assignee: str | None = None
    label: str | None = None  # add a single label
    title: str | None = None
    description: str | None = None
    project: str | None = None
    priority: str | None = None
    labels: list[str] | None = None  # replace all labels
    milestone: str | None = None


@router.get("/tasks")
async def list_tasks(request: Request, status: str | None = None) -> list[dict[str, Any]]:
    board = _platform(request).kanban
    cards = board.all() if not status else board.by_column().get(status, [])
    return [c.to_dict() for c in cards]


@router.post("/tasks")
async def create_task(request: Request, body: CardBody) -> dict[str, Any]:
    p = _platform(request)
    card = await p.kanban.create(
        body.title, column=body.column, labels=body.labels,
        assignee=body.assignee, priority=body.priority, description=body.description,
        project=body.project, actor="human:operator",
    )
    if body.image_data:
        try:
            import base64
            header, _, b64 = body.image_data.partition(",")
            raw = base64.b64decode(b64 or header)
            d = Path(p.config.workspace_root) / ".sams" / "state" / "task-images"
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{card.id}{_image_ext(body.image_name, header)}"
            path.write_bytes(raw)
            card.image = str(path)
            p.kanban.persist()
        except Exception:  # noqa: BLE001
            pass
    if body.retry_options:
        card.retry_options = body.retry_options
        p.kanban.persist()
    return card.to_dict()


@router.get("/tasks/{card_id}/image")
async def task_image(request: Request, card_id: str):
    from fastapi.responses import FileResponse
    card = _platform(request).kanban.get(card_id)
    if card is None or not card.image or not Path(card.image).exists():
        raise HTTPException(404, "no image for this task")
    return FileResponse(card.image)


@router.patch("/tasks/{card_id}")
async def patch_task(request: Request, card_id: str, body: CardPatch) -> dict[str, Any]:
    board = _platform(request).kanban
    if board.get(card_id) is None:
        raise HTTPException(404, f"no card {card_id}")
    op = "human:operator"
    if body.to:
        await board.move(card_id, body.to, actor=op)
    if body.label:
        await board.label(card_id, body.label, actor=op)
    # Full-field edit (from the edit modal).
    await board.edit(
        card_id, title=body.title, description=body.description, project=body.project,
        priority=body.priority, labels=body.labels, assignee=body.assignee,
        milestone=body.milestone, actor=op,
    )
    if body.progress is not None:
        await board.update(card_id, progress=body.progress, actor=op)
    return board.get(card_id).to_dict()


@router.delete("/tasks/{card_id}")
async def delete_task(request: Request, card_id: str) -> dict[str, Any]:
    ok = await _platform(request).kanban.delete(card_id, actor="human:operator")
    if not ok:
        raise HTTPException(404, f"no card {card_id}")
    return {"card_id": card_id, "deleted": True}


@router.post("/tasks/{card_id}/accept")
async def accept_task(request: Request, card_id: str) -> dict[str, Any]:
    """Human validation: accept a card awaiting deploy -> the deployer runs."""
    p = _platform(request)
    card = p.kanban.get(card_id)
    if card is None:
        raise HTTPException(404, f"no card {card_id}")
    if not card.gate_id:
        return {"ok": False, "reason": "card is not awaiting validation"}
    await p.gate.approve(card.gate_id, "human:operator")
    return {"ok": True, "card_id": card_id, "accepted": True}


@router.post("/tasks/{card_id}/commit")
async def commit_task(request: Request, card_id: str) -> dict[str, Any]:
    """Commit a finished card (Deployer) — runs the commit/deploy, then moves it to
    the 'Committed' column. No approval gate (the work is already done)."""
    p = _platform(request)
    if p.kanban.get(card_id) is None:
        raise HTTPException(404, f"no card {card_id}")
    asyncio.create_task(p.pipeline.commit(card_id))
    return {"ok": True, "card_id": card_id, "committing": True}


class RejectTaskBody(BaseModel):
    comment: str = ""


@router.post("/tasks/{card_id}/reject")
async def reject_task_validation(request: Request, card_id: str, body: RejectTaskBody) -> dict[str, Any]:
    p = _platform(request)
    card = p.kanban.get(card_id)
    if card is None:
        raise HTTPException(404, f"no card {card_id}")
    if not card.gate_id:
        return {"ok": False, "reason": "card is not awaiting validation"}
    await p.gate.reject(card.gate_id, "human:operator", body.comment)
    return {"ok": True, "card_id": card_id, "rejected": True}


# --------------------------------------------------------------------------- #
# Workflows
# --------------------------------------------------------------------------- #
@router.get("/workflows")
async def list_workflows(request: Request) -> list[dict[str, Any]]:
    return [{"id": w.id, "name": w.name, "trigger": w.trigger.get("on"), "steps": len(w.steps)}
            for w in _platform(request).orchestrator.workflows()]


class WorkflowRunBody(BaseModel):
    payload: dict[str, Any] = {}


@router.post("/workflows/{workflow_id}/run")
async def run_workflow(request: Request, workflow_id: str, body: WorkflowRunBody) -> dict[str, Any]:
    try:
        run = await _platform(request).run_workflow(workflow_id, body.payload)
    except KeyError:
        raise HTTPException(404, f"no workflow {workflow_id}")
    return run.to_dict()


@router.get("/runs")
async def list_runs(request: Request) -> list[dict[str, Any]]:
    return [r.to_dict() for r in _platform(request).orchestrator.runs()]


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
@router.get("/events")
async def list_events(request: Request, topic: str | None = None, actor: str | None = None,
                      type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    events = await _platform(request).event_bus.history(topic=topic, actor=actor, type=type, limit=limit)
    return [e.model_dump_event() for e in events]


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #
@router.get("/gates")
async def list_gates(request: Request) -> list[dict[str, Any]]:
    return [g.to_dict() for g in _platform(request).gate.all()]


class GateApproveBody(BaseModel):
    approver: str = "human:lead"


@router.post("/gates/{gate_id}/approve")
async def approve_gate(request: Request, gate_id: str, body: GateApproveBody) -> dict[str, Any]:
    try:
        req = await _platform(request).approve_gate(gate_id, body.approver)
    except KeyError:
        raise HTTPException(404, f"no gate {gate_id}")
    return req.to_dict()


class GateRejectBody(BaseModel):
    approver: str = "human:lead"
    comment: str = ""


@router.post("/gates/{gate_id}/reject")
async def reject_gate(request: Request, gate_id: str, body: GateRejectBody) -> dict[str, Any]:
    req = await _platform(request).gate.reject(gate_id, body.approver, body.comment)
    return req.to_dict()


# --------------------------------------------------------------------------- #
# Chat / messaging / AI Assistant (spec 7.16)
# --------------------------------------------------------------------------- #
@router.get("/threads")
async def list_threads(request: Request) -> list[dict[str, Any]]:
    return [t.to_dict() for t in _platform(request).chat.threads()]


@router.get("/threads/{thread_id}")
async def get_thread(request: Request, thread_id: str) -> dict[str, Any]:
    t = _platform(request).chat.get_thread(thread_id)
    if t is None:
        raise HTTPException(404, f"no thread {thread_id}")
    return {**t.to_dict(), "messages": [m.to_dict() for m in t.messages]}


class MessageBody(BaseModel):
    body: str
    author_type: str = "human"
    author_id: str = "human:operator"
    mentions: list[str] = []
    context_refs: list[str] = []


@router.post("/threads/{thread_id}/messages")
async def post_message(request: Request, thread_id: str, body: MessageBody) -> dict[str, Any]:
    msg = await _platform(request).chat.post(
        thread_id, author_type=body.author_type, author_id=body.author_id,
        body=body.body, mentions=body.mentions, context_refs=body.context_refs,
    )
    return msg.to_dict()


class AssistantBody(BaseModel):
    prompt: str
    context_refs: list[str] = []
    anchor: dict[str, Any] | None = None


@router.post("/assistant/ask")
async def assistant_ask(request: Request, body: AssistantBody) -> dict[str, Any]:
    return await _platform(request).chat.assistant_ask(
        body.prompt, context_refs=body.context_refs, anchor=body.anchor
    )


# --------------------------------------------------------------------------- #
# Filesystem browser (Explorer) — scoped to the user's home directory.
# --------------------------------------------------------------------------- #
_FS_ROOT = Path.home()
_TEXT_MAX = 200_000


def _safe_path(raw: str | None) -> Path:
    base = (Path(raw).expanduser() if raw else (_FS_ROOT / "Desktop")).resolve()
    if base != _FS_ROOT and _FS_ROOT not in base.parents:
        raise HTTPException(403, "path is outside the allowed root")
    return base


@router.get("/fs")
async def fs_list(request: Request, path: str | None = None) -> dict[str, Any]:
    base = _safe_path(path)
    if not base.exists() or not base.is_dir():
        raise HTTPException(404, "not a directory")
    entries: list[dict[str, Any]] = []
    for p in sorted(base.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if p.name.startswith("."):
            continue
        try:
            is_dir = p.is_dir()
            entries.append({
                "name": p.name, "path": str(p), "type": "dir" if is_dir else "file",
                "size": (None if is_dir else p.stat().st_size),
            })
        except OSError:
            continue
    return {"path": str(base), "parent": str(base.parent), "entries": entries}


@router.get("/fs/read")
async def fs_read(request: Request, path: str) -> dict[str, Any]:
    p = _safe_path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "not a file")
    if p.stat().st_size > _TEXT_MAX:
        return {"path": str(p), "content": f"(file too large to preview: {p.stat().st_size} bytes)", "truncated": True}
    try:
        return {"path": str(p), "content": p.read_text(errors="replace"), "truncated": False}
    except (UnicodeDecodeError, OSError):
        return {"path": str(p), "content": "(binary file — preview unavailable)", "truncated": True}


# --------------------------------------------------------------------------- #
# Run a project ("Start" button next to each folder)
# --------------------------------------------------------------------------- #
_RUNNING: dict[int, dict[str, Any]] = {}
_PROCS: dict[int, subprocess.Popen] = {}


def _detect_start(path: Path) -> tuple[str, str] | None:
    """Detect how to start a project from the files in its directory."""
    if (path / "package.json").exists():
        try:
            scripts = _json.loads((path / "package.json").read_text()).get("scripts", {})
        except Exception:  # noqa: BLE001
            scripts = {}
        for s in ("dev", "start", "serve"):
            if s in scripts:
                return (f"npm run {s}", f"npm:{s}")
        return ("npm install && npm start", "npm")
    if (path / "docker-compose.yml").exists() or (path / "docker-compose.yaml").exists():
        return ("docker compose up", "docker")
    if (path / "manage.py").exists():
        return ("python3 manage.py runserver", "django")
    for f in ("main.py", "app.py", "run.py"):
        if (path / f).exists():
            return (f"python3 {f}", "python")
    if (path / "Cargo.toml").exists():
        return ("cargo run", "cargo")
    if (path / "go.mod").exists():
        return ("go run .", "go")
    if (path / "Makefile").exists():
        return ("make", "make")
    if (path / "start.sh").exists():
        return ("bash start.sh", "script")
    return None


class StartProjectBody(BaseModel):
    path: str


@router.post("/projects/start")
async def start_project(request: Request, body: StartProjectBody) -> dict[str, Any]:
    path = _safe_path(body.path)
    if not path.is_dir():
        raise HTTPException(404, "not a directory")
    detected = _detect_start(path)
    if detected is None:
        return {"started": False, "reason": "no recognizable start command", "path": str(path)}
    command, kind = detected

    logdir = Path(_platform(request).config.workspace_root) / ".sams" / "projects"
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / f"{path.name}.log"
    fh = open(logfile, "a")
    fh.write(f"\n$ {command}  (cwd={path})\n")
    fh.flush()
    proc = subprocess.Popen(
        command, shell=True, cwd=str(path), stdout=fh, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    info = {"pid": proc.pid, "name": path.name, "path": str(path), "command": command,
            "kind": kind, "log": str(logfile)}
    _RUNNING[proc.pid] = info
    _PROCS[proc.pid] = proc
    await _platform(request).event_bus.emit(
        "project.started", info, space=_platform(request).default_space
    )
    return {"started": True, **info}


def _alive(pid: int) -> bool:
    # For our own children, poll() reaps the process if it exited (avoids a
    # zombie reading as "alive" forever). Otherwise fall back to a signal probe.
    proc = _PROCS.get(pid)
    if proc is not None:
        return proc.poll() is None
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


async def _terminate(pid: int) -> None:
    """Kill a project's whole process group: SIGTERM, then SIGKILL if needed."""
    try:
        pgid = os.getpgid(pid)
    except OSError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        pass
    await asyncio.sleep(0.4)
    if _alive(pid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass
    proc = _PROCS.get(pid)
    if proc is not None:
        proc.poll()  # reap


@router.get("/projects/running")
async def running_projects(request: Request) -> list[dict[str, Any]]:
    # Keep entries (so logs stay readable after exit), capped to the last 50.
    while len(_RUNNING) > 50:
        _RUNNING.pop(next(iter(_RUNNING)))
    return [{**info, "alive": _alive(pid)} for pid, info in _RUNNING.items()]


@router.get("/projects/log")
async def project_log(request: Request, pid: int, lines: int = 600) -> dict[str, Any]:
    info = _RUNNING.get(pid)
    if info is None:
        raise HTTPException(404, "not a tracked process")
    p = Path(info["log"])
    content = ""
    if p.exists():
        content = "\n".join(p.read_text(errors="replace").splitlines()[-lines:])
    return {"pid": pid, "name": info["name"], "command": info["command"],
            "alive": _alive(pid), "content": content}


class StopProjectBody(BaseModel):
    pid: int


@router.post("/projects/stop")
async def stop_project(request: Request, body: StopProjectBody) -> dict[str, Any]:
    info = _RUNNING.get(body.pid)
    if info is None:
        raise HTTPException(404, "not a tracked process")
    await _terminate(body.pid)
    still = _alive(body.pid)
    await _platform(request).event_bus.emit(
        "project.stopped", {"pid": body.pid, "name": info["name"]},
        space=_platform(request).default_space,
    )
    return {"stopped": not still, "pid": body.pid, "alive": still}


# --------------------------------------------------------------------------- #
# ClickUp integration (Source Control panel) — "my tasks"
# --------------------------------------------------------------------------- #
@router.get("/integrations/clickup/status")
async def clickup_status(request: Request) -> dict[str, Any]:
    return {"configured": _clickup.configured}


@router.get("/integrations/clickup/tasks")
async def clickup_tasks(request: Request) -> dict[str, Any]:
    if not _clickup.configured:
        return {"configured": False, "tasks": [],
                "hint": "Set CLICKUP_API_TOKEN (ClickUp → Settings → Apps → API Token, pk_…) before `sams up`."}
    try:
        return await _clickup.assigned_tasks()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"ClickUp error: {exc}")


@router.get("/integrations/github/status")
async def github_status(request: Request) -> dict[str, Any]:
    return {"configured": _github.configured}


@router.get("/integrations/github/repos")
async def github_repos(request: Request) -> dict[str, Any]:
    if not _github.configured:
        return {"configured": False, "repos": [],
                "hint": "Set GITHUB_TOKEN (GitHub → Settings → Developer settings → "
                        "Personal access tokens, read access to repositories) before `sams up`. "
                        "Or set GITHUB_USERNAME to list public repos."}
    try:
        return await _github.repos()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


@router.get("/integrations/github/tree")
async def github_tree(request: Request, repo: str, ref: str | None = None) -> dict[str, Any]:
    if not _github.configured:
        raise HTTPException(400, "GitHub is not configured (set GITHUB_TOKEN).")
    try:
        return await _github.tree(repo, ref)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


@router.get("/integrations/github/file")
async def github_file(request: Request, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
    if not _github.configured:
        raise HTTPException(400, "GitHub is not configured (set GITHUB_TOKEN).")
    try:
        return await _github.file_content(repo, path, ref)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


@router.get("/integrations/github/pulls")
async def github_pulls(request: Request, state: str = "open") -> dict[str, Any]:
    if not _github.configured:
        return {"configured": False, "pulls": [],
                "hint": "Set GITHUB_TOKEN before `sams up`."}
    try:
        return await _github.my_pulls(state)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


@router.get("/integrations/github/pull")
async def github_pull(request: Request, repo: str, number: int) -> dict[str, Any]:
    if not _github.configured:
        raise HTTPException(400, "GitHub is not configured.")
    try:
        return await _github.pull_detail(repo, number)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


@router.get("/integrations/github/pull/files")
async def github_pull_files(request: Request, repo: str, number: int) -> dict[str, Any]:
    if not _github.configured:
        raise HTTPException(400, "GitHub is not configured.")
    try:
        return await _github.pull_files(repo, number)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


class PullMergeBody(BaseModel):
    repo: str
    number: int
    method: str = "merge"


@router.post("/integrations/github/pull/merge")
async def github_pull_merge(request: Request, body: PullMergeBody) -> dict[str, Any]:
    if not _github.token:
        raise HTTPException(400, "A GITHUB_TOKEN with write access is required to merge.")
    try:
        return await _github.merge_pull(body.repo, body.number, body.method)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


class PullCloseBody(BaseModel):
    repo: str
    number: int


@router.post("/integrations/github/pull/close")
async def github_pull_close(request: Request, body: PullCloseBody) -> dict[str, Any]:
    if not _github.token:
        raise HTTPException(400, "A GITHUB_TOKEN with write access is required.")
    try:
        return await _github.close_pull(body.repo, body.number)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


@router.post("/integrations/github/pull/ready")
async def github_pull_ready(request: Request, body: PullCloseBody) -> dict[str, Any]:
    if not _github.token:
        raise HTTPException(400, "A GITHUB_TOKEN with write access is required.")
    try:
        return await _github.ready_pull(body.repo, body.number)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"GitHub error: {exc}")


class GitHubWorkBody(BaseModel):
    repo: str
    task: str
    base: str | None = None


@router.get("/integrations/vercel/status")
async def vercel_status(request: Request) -> dict[str, Any]:
    return {"configured": bool(os.environ.get("VERCEL_TOKEN"))}


class VercelDeployBody(BaseModel):
    target: str
    prod: bool = True
    subdir: str | None = None


@router.post("/integrations/vercel/deploy")
async def vercel_deploy(request: Request, body: VercelDeployBody) -> dict[str, Any]:
    """Deploy a local path or a github:owner/name repo to Vercel (streams to Agent Logs)."""
    if not os.environ.get("VERCEL_TOKEN"):
        raise HTTPException(400, "Set VERCEL_TOKEN (Vercel → Settings → Tokens) before `sams up`.")
    if not body.target:
        raise HTTPException(400, "target is required")
    # Local paths are scoped to the home dir (same as the /fs browser); github
    # targets are cloned to a temp dir, so they're inherently sandboxed.
    if not body.target.startswith("github:"):
        _safe_path(body.target)
    p = _platform(request)
    dep = VercelDeployer(p.event_bus, space=p.default_space)
    asyncio.create_task(dep.deploy_target(body.target, _github.token, body.prod, body.subdir))
    return {"started": True, "target": body.target, "prod": body.prod, "subdir": body.subdir}


@router.post("/integrations/github/work")
async def github_work(request: Request, body: GitHubWorkBody) -> dict[str, Any]:
    """Clone the repo, let an agent make the change, push a branch + open a PR, clean up."""
    if not _github.configured:
        raise HTTPException(400, "GitHub is not configured (set GITHUB_TOKEN).")
    if not body.repo or not body.task.strip():
        raise HTTPException(400, "repo and task are required")
    if not _github.token:
        raise HTTPException(400, "A GITHUB_TOKEN with write access is required to push changes.")
    p = _platform(request)
    worker = GitHubWorker(p.pipeline.coder, _github, p.event_bus, space=p.default_space)
    # Runs in the background; progress streams via agent.log events (Agent Logs).
    asyncio.create_task(worker.work(body.repo, body.task, body.base))
    return {"started": True, "repo": body.repo}


# --------------------------------------------------------------------------- #
# AI Ideas Generator
# --------------------------------------------------------------------------- #
_ANTHROPIC_MESSAGES = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class IdeasGenerateBody(BaseModel):
    project: str = ""
    categories: list[str] = []
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.7
    count: int = 5


@router.post("/ideas/generate")
async def generate_ideas(request: Request, body: IdeasGenerateBody) -> dict[str, Any]:
    # Uses the LOCAL `claude` CLI (no API key) — same engine as the pipeline.
    coder = _platform(request).pipeline.coder
    if not getattr(coder, "installed", False):
        raise HTTPException(
            400,
            "The local `claude` CLI was not found. Install Claude Code (and run `claude login`).",
        )

    project_name = body.project.rstrip("/").split("/")[-1] if body.project else ""
    project_ctx = f'"{project_name}"' if project_name else "a software project"
    cats = ", ".join(body.categories) if body.categories else "general improvements"

    prompt = (
        "You are a creative product and engineering strategist generating concrete, actionable "
        "improvement ideas for software projects.\n\n"
        f"Generate exactly {body.count} improvement ideas for {project_ctx}.\n"
        f"Focus on these categories: {cats}.\n\n"
        'Return ONLY valid JSON — no markdown fences, no prose. Shape: '
        '{"ideas": [{"title": "...", "description": "...", "category": "...", "impact": "High|Medium|Low"}]}\n'
        "Rules:\n"
        "- title: 5-8 words, specific and punchy\n"
        "- description: 2-3 sentences, concrete and actionable, not generic\n"
        "- category: must be one of the requested categories (use the exact label)\n"
        "- impact: exactly one of High, Medium, or Low"
    )

    try:
        text = await coder.ask(prompt, model=body.model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"claude error: {exc}")

    try:
        result = _json.loads(text)
    except _json.JSONDecodeError:
        m = _re.search(r"\{.*\}", text, _re.DOTALL)
        if not m:
            raise HTTPException(502, "AI returned a non-JSON response")
        try:
            result = _json.loads(m.group())
        except _json.JSONDecodeError:
            raise HTTPException(502, "Failed to parse the AI response as JSON")

    ideas = result.get("ideas", [])
    return {"ideas": ideas, "model": body.model, "project": body.project}


# --------------------------------------------------------------------------- #
# Observability (spec 16)
# --------------------------------------------------------------------------- #
@router.get("/metrics")
async def metrics(request: Request) -> dict[str, Any]:
    p = _platform(request)
    agents = p.list_agents()
    by_state: dict[str, int] = {}
    for a in agents:
        by_state[a["state"]] = by_state.get(a["state"], 0) + 1
    recent = await p.event_bus.history(limit=500)
    by_topic: dict[str, int] = {}
    for e in recent:
        by_topic[e.topic] = by_topic.get(e.topic, 0) + 1
    return {
        "agents_online": len(agents),
        "agents_by_state": by_state,
        "events_total": getattr(p.event_bus, "event_count", 0),
        "events_by_topic": by_topic,
        "tasks": len(p.orchestrator.tasks()),
        "workflow_runs": len(p.orchestrator.runs()),
        "pending_gates": len(p.gate.pending()),
        "vault": await p.vault.stats(),
        "posture": p.permissions.posture(),
    }
