"""Cached Venice AI model catalog.

Venice publishes a richer ``/models`` payload than the OpenAI shape: context,
output cap, USD pricing, capabilities, reasoning-effort options, and model
traits all live under ``model_spec``. The catalog is public, so the picker can
read it before a key is configured.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from typing import Any

from hermes_cli.chat_catalog import chat_catalog_ids, catalog_item_is_generation
from hermes_cli.urllib_security import open_credentialed_url
from providers.base import _profile_user_agent

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.venice.ai/api/v1"
DEFAULT_MODEL = "deepseek-v4-1-flash-1017"
AUX_MODEL = "z-ai-glm-5-3-flash"
VISION_MODEL = "qwen-3-8-27b"
FALLBACK_MODELS = (
    DEFAULT_MODEL,
    "z-ai-glm-5-3",
    AUX_MODEL,
    "deepseek-v4-pro-0813",
    "kimi-k3",
    VISION_MODEL,
    "abliteration-abliterated-model-large-v2",
    "abliteration-abliterated-model-large-flash",
    "deepseek-v4-1-flash-1017-uncensored",
)

_CATALOG_TTL_SECONDS = 300.0
_CACHE_LOCK = threading.Lock()
_CATALOG: list[dict[str, Any]] | None = None
_CATALOG_AT = 0.0
_CATALOG_BASE = ""


def reset_cache() -> None:
    """Drop the in-process catalog cache. Used by tests and forced refreshes."""
    global _CATALOG, _CATALOG_AT, _CATALOG_BASE
    with _CACHE_LOCK:
        _CATALOG = None
        _CATALOG_AT = 0.0
        _CATALOG_BASE = ""


def _normalized_base(base_url: str | None) -> str:
    return (base_url or DEFAULT_BASE_URL).strip().rstrip("/")


def _cached(base_url: str, *, allow_stale: bool = False) -> list[dict[str, Any]] | None:
    with _CACHE_LOCK:
        if _CATALOG is None or _CATALOG_BASE != base_url:
            return None
        if allow_stale or time.monotonic() - _CATALOG_AT < _CATALOG_TTL_SECONDS:
            return _CATALOG
        return None


def fetch_catalog(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 8.0,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Return Venice's raw text-model catalog, cached for five minutes.

    Network failures return the last known catalog when one exists, else an
    empty list. Callers fall back to ``FALLBACK_MODELS``.
    """
    base = _normalized_base(base_url)
    if not force_refresh:
        cached = _cached(base)
        if cached is not None:
            return cached
    url = base + "/models"
    request = urllib.request.Request(url)
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", _profile_user_agent())
    try:
        with open_credentialed_url(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("catalog payload has no data list")
        models = [item for item in items if isinstance(item, dict) and item.get("id")]
        if models:
            global _CATALOG, _CATALOG_AT, _CATALOG_BASE
            with _CACHE_LOCK:
                _CATALOG = models
                _CATALOG_AT = time.monotonic()
                _CATALOG_BASE = base
            return models
    except Exception as exc:
        logger.debug("Venice catalog fetch failed for %s: %s", base, exc, exc_info=True)
    return _cached(base, allow_stale=True) or []


def catalog_items(base_url: str | None = None) -> list[dict[str, Any]]:
    """Cached text-model catalog without any network I/O.

    With no ``base_url`` this returns the last catalog fetched for any base, so
    profile hooks stay warm when the user points Venice at a proxy.
    """
    with _CACHE_LOCK:
        if _CATALOG is None:
            return []
        if base_url is not None and _CATALOG_BASE != _normalized_base(base_url):
            return []
        return list(_CATALOG)


def chat_models(models: list[dict[str, Any]] | None = None) -> list[str]:
    items = catalog_items() if models is None else models
    return chat_catalog_ids([item for item in items if not catalog_item_is_generation(item)])


def model_entry(model: str | None, base_url: str | None = None) -> dict[str, Any] | None:
    wanted = str(model or "").strip()
    if not wanted:
        return None
    items = catalog_items(base_url)
    for item in items:
        if item.get("id") == wanted:
            return item
    lowered = wanted.lower()
    for item in items:
        if str(item.get("id") or "").lower() == lowered:
            return item
    if "/" in wanted:
        bare = wanted.rsplit("/", 1)[-1].lower()
        for item in items:
            if str(item.get("id") or "").lower() == bare:
                return item
    return None


def _spec(entry: dict[str, Any] | None) -> dict[str, Any]:
    spec = entry.get("model_spec") if isinstance(entry, dict) else None
    return spec if isinstance(spec, dict) else {}


def _capabilities(entry: dict[str, Any] | None) -> dict[str, Any]:
    caps = _spec(entry).get("capabilities")
    return caps if isinstance(caps, dict) else {}


def traits(entry: dict[str, Any] | None) -> tuple[str, ...]:
    spec = _spec(entry)
    raw = spec.get("traits") or (entry.get("traits") if isinstance(entry, dict) else None) or ()
    return tuple(str(tag) for tag in raw if isinstance(tag, str) and tag.strip())


def trait_model(trait: str, base_url: str | None = None) -> str | None:
    for item in catalog_items(base_url):
        if trait in traits(item):
            return str(item.get("id") or "") or None
    return None


def context_length(model: str | None, base_url: str | None = None) -> int | None:
    entry = model_entry(model, base_url)
    if entry is None:
        return None
    value = entry.get("context_length") or _spec(entry).get("availableContextTokens")
    return value if isinstance(value, int) and value > 0 else None


def max_completion_tokens(model: str | None, base_url: str | None = None) -> int | None:
    entry = model_entry(model, base_url)
    value = _spec(entry).get("maxCompletionTokens") if entry else None
    return value if isinstance(value, int) and value > 0 else None


def reasoning_efforts(model: str | None, base_url: str | None = None) -> tuple[str, ...] | None:
    """Declared effort levels for a model, ``()`` when it takes none, None when cold."""
    entry = model_entry(model, base_url)
    if entry is None:
        return None
    caps = _capabilities(entry)
    if caps.get("supportsReasoningEffort") is not True:
        return () if "supportsReasoning" in caps else None
    options = caps.get("reasoningEffortOptions")
    if not isinstance(options, list):
        return None
    levels = tuple(str(level).strip().lower() for level in options if isinstance(level, str) and level.strip())
    return levels or None


def aux_model(*, vision: bool = False, base_url: str | None = None) -> str:
    if vision:
        return trait_model("default_vision", base_url) or _present_or(VISION_MODEL, base_url) or ""
    return _present_or(AUX_MODEL, base_url) or trait_model("default", base_url) or ""


def vision_model(base_url: str | None = None) -> str | None:
    return trait_model("default_vision", base_url) or _present_or(VISION_MODEL, base_url) or None


def _present_or(model: str, base_url: str | None) -> str | None:
    return model if model_entry(model, base_url) is not None else None
