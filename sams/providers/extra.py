"""OpenAI / Google / local provider adapters.

A thin OpenAI-compatible chat-completions client covers OpenAI, many local
servers (Ollama/vLLM expose an OpenAI-compatible endpoint), and is a reasonable
default for Gemini via a compatible proxy. Falls back to the mock provider when
no endpoint/key is configured so the platform never hard-fails in dev.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..sdk.agent import Agent, Completion
from .base import LLMProvider
from .mock import MockProvider

log = logging.getLogger("sams.providers.extra")

DEFAULT_BASE = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "local": "http://localhost:11434/v1",  # Ollama default
}
ENV_KEY = {"openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY", "local": "LOCAL_API_KEY"}


class GenericHTTPProvider(LLMProvider):
    """OpenAI-compatible chat-completions client."""

    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.name = provider_name
        self.model = model
        self.base_url = (base_url or DEFAULT_BASE.get(provider_name, "")).rstrip("/")
        self.api_key = api_key or os.environ.get(ENV_KEY.get(provider_name, ""), "")
        self._fallback = MockProvider(model=model)

    async def complete(
        self,
        *,
        agent: Agent,
        system: str,
        prompt: str,
        context: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Completion:
        if not self.base_url or (self.name != "local" and not self.api_key):
            log.warning("%s not configured; using mock fallback", self.name)
            return await self._fallback.complete(
                agent=agent, system=system, prompt=prompt, context=context, params=params
            )
        params = params or {}
        messages = [{"role": "system", "content": system}]
        if context:
            messages.append({"role": "system", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(params.get("temperature", 0.4)),
            "max_tokens": int(params.get("max_tokens", 4096)),
        }
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return Completion(
            text=choice,
            markdown=choice,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )
