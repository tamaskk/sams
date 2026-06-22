"""The real-time WebSocket stream (spec 11.2).

The client subscribes to a space's event stream and receives an initial scene
snapshot followed by live event/state deltas. Clients may also send commands
(``agent:new``, ``task:create``, ``gate:approve``, ``workflow:run``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from ..core.events import Event

log = logging.getLogger("sams.api.ws")


async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    platform = websocket.app.state.platform
    space = websocket.query_params.get("space", platform.default_space)

    # Initial snapshot so the client can render immediately.
    await websocket.send_json({
        "type": "snapshot",
        "space": space,
        "scene": platform.spatial.scene(space),
        "agents": platform.list_agents(space),
        "tasks": [c.to_dict() for c in platform.kanban.all()],
        "status": platform.status(),
    })

    queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)

    async def forward(event: Event) -> None:
        if event.space and event.space != space:
            return
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:  # slow client: drop oldest
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    sub = platform.event_bus.subscribe("*", forward, name=f"ws:{id(websocket)}")

    async def sender() -> None:
        while True:
            event = await queue.get()
            await websocket.send_json({"type": "event", "event": event.model_dump_event()})

    async def receiver() -> None:
        while True:
            msg = await websocket.receive_json()
            await _dispatch(platform, space, msg)

    send_task = asyncio.create_task(sender())
    recv_task = asyncio.create_task(receiver())
    try:
        await asyncio.wait({send_task, recv_task}, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        recv_task.cancel()
        await sub.cancel()


async def _dispatch(platform, space: str, msg: dict[str, Any]) -> None:
    if msg.get("type") != "command":
        return
    command = msg.get("command")
    args = msg.get("args", {})
    try:
        if command == "agent:new":
            ref = args.get("ref")
            if ref and (manifest := platform.agent_registry.get(ref)):
                await platform.spawn_agent(manifest)
        elif command == "task:create":
            await platform.kanban.create(
                args["title"], column=args.get("column", "To Do"),
                labels=args.get("labels", []), assignee=args.get("assignee"),
                actor="human:operator",
            )
        elif command == "task:assign":
            await platform.submit_task(
                args["title"], capability=args.get("capability"),
                assignee=args.get("assignee"), inputs=args.get("inputs", {}),
            )
        elif command == "gate:approve":
            await platform.approve_gate(args["gate_id"], args.get("approver", "human:lead"))
        elif command == "workflow:run":
            await platform.run_workflow(args["id"], args.get("payload", {}))
        elif command == "primitive:add":
            await platform.spatial.add_primitive(space, args["type"], args.get("name"), args.get("position"))
    except Exception:  # noqa: BLE001
        log.exception("ws command %s failed", command)
