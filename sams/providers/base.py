"""The provider contract and factory.

The factory maps a manifest's ``model`` binding (provider + name) to a concrete
provider instance, honoring the platform's default provider for offline/dev runs.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..sdk.agent import Completion

if TYPE_CHECKING:
    from ..config.models import SamsConfig
    from ..sdk.agent import Agent
    from ..sdk.manifest import AgentManifest

log = logging.getLogger("sams.providers")


class LLMProvider(ABC):
    """A bound LLM. Implementations call Claude / GPT / Gemini / a local model."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        *,
        agent: "Agent",
        system: str,
        prompt: str,
        context: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Completion: ...


class ProviderFactory:
    """Builds providers and resolves which provider an agent should use."""

    def __init__(self, config: "SamsConfig") -> None:
        self.config = config
        self._cache: dict[str, LLMProvider] = {}

    def _build(self, provider_name: str, model: str) -> LLMProvider:
        key = f"{provider_name}:{model}"
        if key in self._cache:
            return self._cache[key]

        provider: LLMProvider
        if provider_name == "mock":
            from .mock import MockProvider

            provider = MockProvider(model=model)
        elif provider_name == "anthropic":
            from .anthropic import AnthropicProvider

            pc = self.config.platform.providers.get("anthropic")
            provider = AnthropicProvider(
                model=model, api_key=(pc.api_key if pc else None)
            )
        elif provider_name in ("openai", "google", "local"):
            from .extra import GenericHTTPProvider

            pc = self.config.platform.providers.get(provider_name)
            provider = GenericHTTPProvider(
                provider_name=provider_name,
                model=model,
                api_key=(pc.api_key if pc else None),
                base_url=(pc.base_url if pc else None),
            )
        else:
            log.warning("unknown provider %s; falling back to mock", provider_name)
            from .mock import MockProvider

            provider = MockProvider(model=model)
        self._cache[key] = provider
        return provider

    def provider_for(self, manifest: "AgentManifest") -> LLMProvider:
        binding = manifest.spec.model
        provider_name = binding.provider
        model = binding.name
        # In offline/dev runs, force every agent onto the default provider so the
        # platform works with no API keys. (`defaultProvider: mock` by default.)
        default = self.config.platform.defaultProvider
        if default == "mock":
            return self._build("mock", model)
        return self._build(provider_name, model)
