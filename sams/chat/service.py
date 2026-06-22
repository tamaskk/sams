"""The chat service: threads, routing, and the context-aware AI Assistant.

Routing follows spec 7.16: a human message that is **addressed** (`@agent`) goes
to that agent; **anchored** messages go to the artifact's agents; **unaddressed**
messages are routed by capability to the best-fit agent. Agents ground replies on
attached ``context_refs`` (Vault files) so "Ask AI" answers about *this* artifact.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .models import Message, Thread

if TYPE_CHECKING:
    from ..core.event_bus import EventBus
    from ..runtime.runner import AgentRuntime
    from ..sdk.registry import CapabilityRegistry
    from ..vault.store import Vault

log = logging.getLogger("sams.chat")


class ChatService:
    def __init__(
        self,
        event_bus: "EventBus",
        runtime: "AgentRuntime",
        vault: "Vault",
        capabilities: "CapabilityRegistry",
        *,
        space: str = "main.space",
    ) -> None:
        self.event_bus = event_bus
        self.runtime = runtime
        self.vault = vault
        self.capabilities = capabilities
        self.space = space
        self._threads: dict[str, Thread] = {}

    # --- threads -------------------------------------------------------------
    def threads(self) -> list[Thread]:
        return list(self._threads.values())

    def get_thread(self, thread_id: str) -> Thread | None:
        return self._threads.get(thread_id)

    def create_thread(self, *, anchor: dict[str, Any] | None = None, title: str = "",
                      participants: list[str] | None = None) -> Thread:
        thread = Thread(
            anchor=anchor or {"type": "global", "id": "global"},
            title=title,
            participants=participants or [],
        )
        self._threads[thread.id] = thread
        return thread

    def thread_for_anchor(self, anchor: dict[str, Any]) -> Thread:
        for t in self._threads.values():
            if t.anchor.get("type") == anchor.get("type") and t.anchor.get("id") == anchor.get("id"):
                return t
        return self.create_thread(anchor=anchor, title=anchor.get("id", "Thread"))

    # --- posting -------------------------------------------------------------
    async def post(
        self,
        thread_id: str,
        *,
        author_type: str,
        author_id: str,
        body: str,
        mentions: list[str] | None = None,
        context_refs: list[str] | None = None,
        actions: list[dict[str, Any]] | None = None,
        reply: bool = True,
    ) -> Message:
        thread = self._threads.get(thread_id) or self.create_thread()
        msg = Message(
            thread_id=thread.id,
            anchor=thread.anchor,
            author={"type": author_type, "id": author_id},
            body=body,
            mentions=mentions or [],
            context_refs=context_refs or [],
            actions=actions or [],
        )
        thread.messages.append(msg)
        thread.updated_at = msg.ts
        if author_id not in thread.participants:
            thread.participants.append(author_id)

        await self.event_bus.emit(
            "chat.message.posted",
            {"thread_id": thread.id, "author": author_id, "body": body[:240], "mentions": msg.mentions},
            actor=author_id, space=self.space,
        )
        if author_type == "agent":
            await self.event_bus.emit(
                "agent.message", {"thread_id": thread.id, "from": author_id, "body": body[:240]},
                actor=author_id, space=self.space,
            )
        # Persist conversation to long-term memory (spec 7.16 "History & memory").
        await self.vault.memory.write(
            f"[thread {thread.id}] {author_id}: {body}",
            agent=author_id, scope="space", space=self.space,
        )

        # Route a reply for human-authored messages.
        if reply and author_type == "human":
            responder = self._route(thread, msg)
            if responder:
                asyncio.create_task(self._reply(thread, responder))
        return msg

    # --- routing (spec 7.16) -------------------------------------------------
    def _route(self, thread: Thread, msg: Message) -> str | None:
        spawned = {a.id for a in self.runtime.instances()}
        # 1. addressed — first mentioned agent that is online
        for m in msg.mentions:
            aid = m.lstrip("@").removeprefix("agent:")
            if aid in spawned:
                return aid
        # 2. anchored — an agent attached to the artifact
        anchor_id = thread.anchor.get("id", "")
        for p in thread.participants:
            if p in spawned:
                return p
        # 3. unaddressed — best-fit by capability (content.write / research.summarize)
        for cap in ("content.write", "research.summarize", "plan.spec"):
            providers = self.capabilities.providers_of(cap) & spawned
            if providers:
                return sorted(providers)[0]
        return next(iter(spawned), None)

    async def _reply(self, thread: Thread, responder_id: str) -> None:
        agent = self.runtime.get(responder_id)
        if agent is None:
            return
        # Ground the reply on attached context (last message's refs).
        last = thread.messages[-1]
        ctx_text = ""
        for ref in last.context_refs:
            try:
                ctx_text += f"\n# {ref}\n" + (await self.vault.read(ref))[:2000]
            except Exception:  # noqa: BLE001
                pass
        history = "\n".join(f"{m.author['id']}: {m.body}" for m in thread.messages[-6:])
        try:
            completion = await agent.think(
                f"Conversation so far:\n{history}\n\nReply helpfully and concisely as {agent.name}.",
                context=ctx_text or None,
            )
            await self.post(
                thread.id, author_type="agent", author_id=responder_id,
                body=completion.text[:1200], reply=False,
            )
        except Exception:  # noqa: BLE001
            log.exception("chat reply failed for %s", responder_id)

    # --- the "Ask AI" assistant ---------------------------------------------
    async def assistant_ask(
        self, prompt: str, *, context_refs: list[str] | None = None,
        anchor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Context-aware assistant: answer + optionally propose actions (spec 7.16)."""
        thread = self.thread_for_anchor(anchor or {"type": "global", "id": "assistant"})
        await self.post(
            thread.id, author_type="human", author_id="human:operator",
            body=prompt, context_refs=context_refs or [], reply=False,
        )
        responder = self._route(thread, thread.messages[-1]) or "atlas"
        agent = self.runtime.get(responder)
        if agent is None:
            return {"answer": "(no agent available)", "thread_id": thread.id}
        ctx_text = ""
        for ref in (context_refs or []):
            try:
                ctx_text += f"\n# {ref}\n" + (await self.vault.read(ref))[:2000]
            except Exception:  # noqa: BLE001
                pass
        completion = await agent.think(prompt, context=ctx_text or None)
        msg = await self.post(
            thread.id, author_type="agent", author_id=responder,
            body=completion.text[:1500], reply=False,
        )
        return {"answer": completion.text, "thread_id": thread.id, "by": responder,
                "message_id": msg.id}
