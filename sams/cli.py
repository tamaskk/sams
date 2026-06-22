"""The ``sams`` CLI — mirrors the control-plane API (spec 15).

``sams up`` starts the platform (FastAPI + WebSocket). Stateful commands talk to a
running instance over REST; offline commands (validate, init) work without one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__

app = typer.Typer(help="SAMS — Spatial Agentic Management System", no_args_is_help=True)
agent_app = typer.Typer(help="Manage agents")
flow_app = typer.Typer(help="Manage workflows")
task_app = typer.Typer(help="Manage Kanban tasks")
events_app = typer.Typer(help="Inspect the event stream")
app.add_typer(agent_app, name="agent")
app.add_typer(flow_app, name="flow")
app.add_typer(task_app, name="task")
app.add_typer(events_app, name="events")

console = Console()
API = os.environ.get("SAMS_API", "http://127.0.0.1:8787")


def _api(method: str, path: str, **kwargs):
    import httpx

    try:
        resp = httpx.request(method, f"{API}/api/v1{path}", timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        console.print(f"[red]Could not reach SAMS at {API}. Is `sams up` running?[/red]")
        raise typer.Exit(1)


# --------------------------------------------------------------------------- #
# Instance
# --------------------------------------------------------------------------- #
@app.command()
def version() -> None:
    """Print the SAMS version."""
    console.print(f"SAMS v{__version__}")


@app.command()
def init() -> None:
    """Scaffold config files + directories in the current workspace."""
    for d in ["agents/builtin", "agents/custom", "workflows", "configs", "assets", "packs"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    console.print("[green]Workspace scaffolded.[/green] Edit configs/ then run `sams up`.")


@app.command()
def up(
    host: str = "127.0.0.1",
    port: int = 8787,
    mode: str = typer.Option(None, help="development | standard | strict"),
    autonomous: bool = typer.Option(False, help="alias for --mode development (full autonomy)"),
) -> None:
    """Start the platform (API + WebSocket + UI)."""
    import uvicorn

    if autonomous:
        mode = "development"
    if mode:
        os.environ["SAMS_MODE"] = mode
    os.environ.setdefault("SAMS_WORKSPACE", ".")
    console.print(f"[bold]SAMS[/bold] starting on http://{host}:{port}  ·  mode={mode or 'config'}")
    uvicorn.run("sams.api.app:app", host=host, port=port, log_level="info")


@app.command()
def status() -> None:
    """Show platform health + Development Mode posture."""
    data = _api("GET", "/status")
    posture = data.get("posture", {})
    console.print(
        f"[bold]SAMS v{data['version']}[/bold] · {data['mode']} · {data['agents_online']} Agents Online · "
        f"Gates: {posture.get('gates')} · Permissions: {posture.get('permissions')} · "
        f"Confirmations: {posture.get('confirmations')}"
    )


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #
@agent_app.command("list")
def agent_list() -> None:
    """List agents and states."""
    agents = _api("GET", "/agents")
    table = Table("Name", "ID", "Role", "State", "Model", "Approves")
    for a in agents:
        table.add_row(a["name"], a["agent_id"], a["role"], a["state"],
                      a["model"]["name"], "✅" if a["permissions"]["approve"] else "—")
    console.print(table)


@agent_app.command("validate")
def agent_validate(manifest: str) -> None:
    """Validate an agent manifest without registering it."""
    from .sdk.manifest import load_manifest

    try:
        m = load_manifest(manifest)
        console.print(f"[green]OK[/green] {m.id} ({m.name}) — caps: {', '.join(m.capabilities)}")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Invalid:[/red] {exc}")
        raise typer.Exit(1)


@agent_app.command("add")
def agent_add(manifest: str) -> None:
    """Register an agent from a manifest (spawns it on the running instance)."""
    doc = Path(manifest).read_text()
    import yaml

    _api("POST", "/agents", json={"manifest_doc": yaml.safe_load(doc)})
    console.print(f"[green]Added[/green] {manifest}")


@agent_app.command("spawn")
def agent_spawn(agent_id: str) -> None:
    """Spawn a built-in agent by id."""
    _api("POST", "/agents", json={"ref": agent_id})
    console.print(f"[green]Spawned[/green] {agent_id}")


@agent_app.command("despawn")
def agent_despawn(agent_id: str) -> None:
    """Despawn an agent (graceful drain)."""
    _api("DELETE", f"/agents/{agent_id}")
    console.print(f"[yellow]Despawned[/yellow] {agent_id}")


# --------------------------------------------------------------------------- #
# Workflows
# --------------------------------------------------------------------------- #
@flow_app.command("list")
def flow_list() -> None:
    table = Table("ID", "Name", "Trigger", "Steps")
    for w in _api("GET", "/workflows"):
        table.add_row(w["id"], w["name"], str(w["trigger"]), str(w["steps"]))
    console.print(table)


@flow_app.command("validate")
def flow_validate(file: str) -> None:
    from .orchestrator.workflows import load_workflow

    try:
        defn = load_workflow(file)
        console.print(f"[green]OK[/green] {defn.id} — {len(defn.steps)} steps")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Invalid:[/red] {exc}")
        raise typer.Exit(1)


@flow_app.command("run")
def flow_run(workflow_id: str, payload: str = typer.Option("{}", help="JSON trigger payload")) -> None:
    run = _api("POST", f"/workflows/{workflow_id}/run", json={"payload": json.loads(payload)})
    console.print(f"[bold]{run['workflow']}[/bold] → {run['status']}")
    for s in run["steps"]:
        console.print(f"  {s['id']:18} {s['status']}")


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
@task_app.command("list")
def task_list(status: str = typer.Option(None, help="filter by column")) -> None:
    params = {"status": status} if status else {}
    table = Table("ID", "Title", "Status", "Assignee", "Priority")
    for c in _api("GET", "/tasks", params=params):
        table.add_row(c["id"], c["title"][:40], c["status"], c["assignee"] or "—", c["priority"])
    console.print(table)


@task_app.command("create")
def task_create(title: str, label: list[str] = typer.Option([]), column: str = "To Do") -> None:
    c = _api("POST", "/tasks", json={"title": title, "labels": label, "column": column})
    console.print(f"[green]Created[/green] {c['id']} — {c['title']}")


@task_app.command("move")
def task_move(card_id: str, to: str) -> None:
    c = _api("PATCH", f"/tasks/{card_id}", json={"to": to})
    console.print(f"[green]Moved[/green] {c['id']} → {c['status']}")


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
@events_app.command("tail")
def events_tail(type: str = typer.Option(None, help="filter by topic/type"), limit: int = 30) -> None:
    params = {"limit": limit}
    if type:
        params["type"] = type
    for e in _api("GET", "/events", params=params):
        console.print(f"[dim]{e['ts']}[/dim] [cyan]{e['type']:28}[/cyan] actor={e.get('actor')}")


if __name__ == "__main__":
    app()
