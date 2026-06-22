"""Integration + unit tests for SAMS.

Covers the critical paths: the Event Bus contract, the catalog + manifest schema,
Development Mode + the Security Gate, deny-by-default permissions, end-to-end task
execution, workflow triggering, capability routing, the custom code-backed agent,
and the chat assistant.
"""

from __future__ import annotations

import asyncio

import pytest

from sams.catalog.loader import load_builtin_manifests
from sams.config.loader import load_config
from sams.core.event_bus import InMemoryEventBus
from sams.orchestrator.models import Task
from sams.security.permissions import PermissionDenied, PermissionEngine

from .conftest import wait_for


# --------------------------------------------------------------------------- #
# Event Bus
# --------------------------------------------------------------------------- #
async def test_event_bus_pubsub_ordering_and_idempotency():
    bus = InMemoryEventBus()
    await bus.start()
    got: list[str] = []

    async def handler(e):
        got.append(e.id)

    bus.subscribe("agent.*", handler, name="t")
    await bus.emit("agent.spawned", {"id": "x"}, idempotency_key="k1")
    await bus.emit("agent.spawned", {"id": "x"}, idempotency_key="k1")  # dupe
    await bus.emit("agent.state.changed", {"state": "idle"})
    await wait_for(lambda: len(got) >= 2)
    assert len(got) == 2  # duplicate deduped
    hist = await bus.history(topic="agent")
    assert [e.type for e in hist] == ["agent.spawned", "agent.spawned", "agent.state.changed"]
    await bus.stop()


# --------------------------------------------------------------------------- #
# Catalog & manifest schema
# --------------------------------------------------------------------------- #
def test_catalog_has_36_agents_with_separation_of_duties():
    manifests = load_builtin_manifests(".")
    assert len(manifests) == 36
    ids = [m.id for m in manifests]
    assert len(ids) == len(set(ids)), "agent ids must be unique"
    approvers = sorted(m.id for m in manifests if m.can_approve)
    assert approvers == ["aegis", "hex"], "only Hex and Aegis approve by default (5.14)"
    for m in manifests:
        assert m.capabilities, f"{m.id} declares no capabilities"


# --------------------------------------------------------------------------- #
# Development Mode + Security Gate
# --------------------------------------------------------------------------- #
def test_dev_mode_posture():
    cfg = load_config(".", environment="dev", mode="development")
    perms = PermissionEngine(cfg)
    assert perms.dev_mode and perms.grant_all and perms.auto_approve
    assert perms.posture()["gates"] == "auto"


def test_dev_mode_scoped_to_dev_only():
    # Development Mode must never widen to prod (12.6).
    cfg = load_config(".", environment="prod", mode="development")
    perms = PermissionEngine(cfg)
    assert not perms.dev_mode
    assert not perms.auto_approve


def test_deny_by_default_in_standard_mode():
    cfg = load_config(".", environment="staging", mode="standard")
    perms = PermissionEngine(cfg)
    opus = next(m for m in load_builtin_manifests(".") if m.id == "opus")
    # opus has fs.read but not deploy.run
    assert perms.can_use_tool(opus, "fs.read")
    with pytest.raises(PermissionDenied):
        perms.check_tool(opus, "deploy.run")


async def test_gate_auto_approves_in_dev(platform):
    req = await platform.gate.request(kind="approval", summary="x", approvers=["human:lead"],
                                      produced_by="opus")
    assert req.status == "approved"
    assert req.decisions.get("auto:dev-mode") == "approve"


# --------------------------------------------------------------------------- #
# End-to-end task + routing
# --------------------------------------------------------------------------- #
async def test_task_completes_end_to_end(platform):
    task = await platform.submit_task("Build the event system", capability="code.write")
    assert await wait_for(lambda: task.status in ("complete", "error"))
    assert task.status == "complete"
    assert "artifact" in task.result
    assert await platform.vault.exists(task.result["artifact"])


async def test_default_roster_is_six_roles(platform):
    ids = {a["agent_id"] for a in platform.list_agents()}
    assert ids == {"planner", "designer", "developer", "reviewer", "tester", "deployer"}


async def test_capability_routing_picks_a_provider(platform):
    # qa.test.run is provided by the Tester role in the default fleet.
    task = Task(title="Run tests", capability="qa.test.run", space=platform.default_space)
    completed = await platform.orchestrator.assign_and_run(task)
    assert completed.status == "complete"


async def test_spawn_type_creates_instance_and_despawn_removes_it(platform):
    before = {a["agent_id"] for a in platform.list_agents()}
    inst = await platform.spawn_type("developer")
    assert inst.id == "developer-2"
    assert platform.runtime.get("developer-2") is not None
    await platform.despawn_agent("developer-2")
    assert platform.runtime.get("developer-2") is None
    assert {a["agent_id"] for a in platform.list_agents()} == before


async def test_separation_of_duties_blocks_self_approval(platform):
    req = await platform.gate.request(kind="approval", summary="x", approvers=["hex"],
                                      produced_by="hex")
    # In dev mode it auto-approves; force a manual check of the rule itself:
    assert platform.permissions.self_approval_blocked_for("hex", "hex")
    assert not platform.permissions.self_approval_blocked_for("aegis", "hex")


# --------------------------------------------------------------------------- #
# Workflows
# --------------------------------------------------------------------------- #
async def test_code_review_workflow_triggers_and_completes(platform):
    before = len(platform.orchestrator.runs())
    await platform.github.on_inbound("pull_request.opened", {"pr": 128})
    assert await wait_for(lambda: len(platform.orchestrator.runs()) > before)
    run = platform.orchestrator.runs()[-1]
    assert await wait_for(lambda: run.status in ("complete", "error"))
    assert run.status == "complete"
    assert [s.status for s in run.steps] == ["complete"] * 4


# --------------------------------------------------------------------------- #
# Extensibility: the custom code-backed agent
# --------------------------------------------------------------------------- #
async def test_custom_agent_new_capability(platform):
    # seo-agent ships in agents/custom but isn't in the default roster — spawn it.
    await platform.spawn_agent(platform.agent_registry.get("seo-agent"))
    seo = platform.runtime.get("seo-agent")
    assert seo is not None and seo.has_handler_for("content.seo_audit")
    task = Task(title="Audit", capability="content.seo_audit", assignee="seo-agent",
                inputs={"url": "https://example.com"}, space=platform.default_space)
    completed = await platform.orchestrator.assign_and_run(task)
    assert completed.status == "complete"
    assert completed.result["issues"] >= 0


# --------------------------------------------------------------------------- #
# Chat / AI Assistant
# --------------------------------------------------------------------------- #
async def test_assistant_answers_and_persists_thread(platform):
    result = await platform.chat.assistant_ask("What is the plan?")
    assert result["answer"]
    thread = platform.chat.get_thread(result["thread_id"])
    assert thread is not None and len(thread.messages) >= 2  # question + answer


async def test_addressed_message_routes_to_named_agent(platform):
    thread = platform.chat.create_thread(title="review")
    await platform.chat.post(thread.id, author_type="human", author_id="human:tamas",
                             body="@reviewer please review", mentions=["@reviewer"])
    assert await wait_for(lambda: any(m.author["id"] == "reviewer" for m in thread.messages))
