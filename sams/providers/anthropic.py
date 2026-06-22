"""Anthropic (Claude) provider adapter.

Calls the Messages API over HTTP. Manifest model names from the catalog
(``claude-opus-4`` / ``claude-sonnet-4`` / ``claude-haiku-4``) are mapped to
current API model ids. Used when ``defaultProvider`` is not ``mock`` and an
``ANTHROPIC_API_KEY`` is present.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..sdk.agent import Agent, Completion
from .base import LLMProvider

log = logging.getLogger("sams.providers.anthropic")

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# Map catalog model names -> current API model ids.
MODEL_MAP = {
    "claude-opus-4": "claude-opus-4-8",
    "claude-sonnet-4": "claude-sonnet-4-6",
    "claude-haiku-4": "claude-haiku-4-5-20251001",
}


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4", api_key: str | None = None) -> None:
        self.model = MODEL_MAP.get(model, model)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    async def complete(
        self,
        *,
        agent: Agent,
        system: str,
        prompt: str,
        context: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Completion:
        if not self.api_key:
            raise RuntimeError(
                "anthropic provider selected but ANTHROPIC_API_KEY is unset. "
                "Set defaultProvider: mock in sams.yaml to run offline."
            )
        params = params or {}
        sys_text = system
        if context:
            sys_text = f"{system}\n\n# Context\n{context}"

        payload = {
            "model": self.model,
            "max_tokens": int(params.get("max_tokens", 4096)),
            "temperature": float(params.get("temperature", 0.4)),
            "system": sys_text,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        usage = data.get("usage", {})
        return Completion(
            text=text,
            markdown=text,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
        )
