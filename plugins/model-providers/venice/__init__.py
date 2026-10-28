"""Venice AI provider profile.

Venice is an OpenAI-compatible, API-key inference API. Its public ``/models``
catalog carries the capabilities Hermes needs, so the profile reads that
catalog instead of hardcoding a model table that rots.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agent.reasoning_effort import clamp_effort, requested_effort
from providers import register_provider
from providers.base import ProviderProfile

from . import catalog
from .billing import fetch_venice_account_usage

if TYPE_CHECKING:
    from agent.account_usage import AccountUsageSnapshot


class VeniceProfile(ProviderProfile):
    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        items = catalog.fetch_catalog(
            api_key=api_key, base_url=base_url, timeout=timeout
        )
        models = catalog.chat_models(items)
        return models or None

    def resolve_aux_model(self, *, vision: bool = False) -> str:
        return catalog.aux_model(vision=vision)

    def default_vision_model(self) -> str | None:
        return catalog.vision_model()

    def get_model_context_length(self, model: str) -> int | None:
        return catalog.context_length(model)

    def get_max_tokens(self, model: str | None) -> int | None:
        return catalog.max_completion_tokens(model)

    def supported_reasoning_efforts(
        self, model: str | None
    ) -> tuple[str, ...] | None:
        return catalog.reasoning_efforts(model)

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        efforts = catalog.reasoning_efforts(model)
        if not efforts:
            return {}, {}
        disabled = isinstance(reasoning_config, dict) and (
            reasoning_config.get("enabled") is False
            or str(reasoning_config.get("effort") or "").strip().lower() == "none"
        )
        if disabled:
            return ({}, {"reasoning_effort": "none"}) if "none" in efforts else ({}, {})
        effort = requested_effort(reasoning_config)
        if effort is None:
            return {}, {}
        clamped = clamp_effort(effort, efforts)
        return ({}, {"reasoning_effort": clamped}) if clamped in efforts else ({}, {})

    def fetch_account_usage(
        self, *, base_url: str | None = None, api_key: str | None = None
    ) -> AccountUsageSnapshot | None:
        return fetch_venice_account_usage(base_url=base_url, api_key=api_key)


register_provider(
    VeniceProfile(
        name="venice",
        aliases=("venice-ai", "veniceai"),
        display_name="Venice AI",
        description="Venice AI (private, OpenAI-compatible inference)",
        signup_url="https://venice.ai/settings/api",
        env_vars=("VENICE_API_KEY", "VENICE_BASE_URL"),
        base_url=catalog.DEFAULT_BASE_URL,
        auth_type="api_key",
        api_mode="chat_completions",
        supports_streaming=True,
        supports_prompt_cache_key=False,
        supports_vision_tool_messages=True,
        fallback_models=catalog.FALLBACK_MODELS,
        default_aux_model=catalog.AUX_MODEL,
    )
)
