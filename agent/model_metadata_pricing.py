"""Normalize ``/models`` rate cards into per-token strings.

Providers publish prices in incompatible shapes: flat per-token strings, nested
``$ / MTok`` buckets, or provider-specific metadata. This module owns the
normalization; ``agent.model_metadata`` only attaches the result to a cache entry.
"""

from __future__ import annotations

from typing import Any


def _iter_nested_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nested_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nested_dicts(item)


_PRICING_UNIT_DIVISORS = {
    "per_token": 1, "per_1k_tokens": 1_000, "per_thousand_tokens": 1_000,
    "per_1m_tokens": 1_000_000, "per_million_tokens": 1_000_000,
}
_PER_MILLION_QUOTE_MIN = 0.001
_TOKEN_RATE_FIELDS = ("prompt", "completion", "cache_read", "cache_write")


def _normalize_token_rates(pricing: dict[str, Any], unit: Any) -> dict[str, Any]:
    """Rescale token rates to per-token strings, the contract usage_pricing multiplies by 1e6."""
    rates: dict[str, float] = {}
    for key in _TOKEN_RATE_FIELDS:
        try:
            rates[key] = float(pricing[key])
        except (KeyError, TypeError, ValueError):
            continue
    divisor = _PRICING_UNIT_DIVISORS.get(str(unit or "").strip().lower())
    if divisor is None:
        divisor = 1_000_000 if any(v >= _PER_MILLION_QUOTE_MIN for v in rates.values()) else 1
    if divisor != 1:
        pricing.update({key: str(value / divisor) for key, value in rates.items()})
    return pricing


def _extract_pricing(payload: dict[str, Any]) -> dict[str, Any]:
    def _per_token(source: dict[str, Any], fields: dict[str, str], scale) -> dict[str, Any]:
        return {target: str(scale(float(source[key]))) for target, key in fields.items() if source.get(key) is not None}

    # Nested ``$ / MTok`` rate cards: Venice publishes model_spec.pricing as
    # ``{input: {usd}, output: {usd}, cache_input: {usd}, cache_write: {usd}}``.
    spec_pricing = (payload.get("model_spec") or {}).get("pricing") if isinstance(payload.get("model_spec"), dict) else None
    for rate_card in (spec_pricing, payload.get("pricing")):
        if not isinstance(rate_card, dict):
            continue
        nested: dict[str, float] = {}
        for target, key in (("prompt", "input"), ("completion", "output"), ("cache_read", "cache_input"), ("cache_write", "cache_write")):
            rate = rate_card.get(key)
            value = rate.get("usd") if isinstance(rate, dict) else None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                nested[target] = float(value)
        if nested:
            return _normalize_token_rates(nested, "per_1m_tokens")

    novita_fields = {"prompt": "input_token_price_per_m", "completion": "output_token_price_per_m"}
    if any(payload.get(k) is not None for k in novita_fields.values()):
        return _per_token(payload, novita_fields, lambda v: v / 10_000 / 1_000_000)
    # DeepInfra ships pricing under ``metadata.pricing`` in $/MTok.
    metadata = payload.get("metadata")
    deepinfra_pricing = metadata.get("pricing") if isinstance(metadata, dict) else None
    deepinfra_fields = {"prompt": "input_tokens", "completion": "output_tokens", "cache_read": "cache_read_tokens"}
    if isinstance(deepinfra_pricing, dict) and any(k in deepinfra_pricing for k in deepinfra_fields.values()):
        return _per_token(deepinfra_pricing, deepinfra_fields, lambda v: v / 1_000_000)
    alias_map = {
        "prompt": ("prompt", "input", "input_cost_per_token", "prompt_token_cost"),
        "completion": ("completion", "output", "output_cost_per_token", "completion_token_cost"),
        "request": ("request", "request_cost"),
        "cache_read": ("cache_read", "cached_prompt", "input_cache_read", "cache_read_cost_per_token"),
        "cache_write": ("cache_write", "cache_creation", "input_cache_write", "cache_write_cost_per_token"),
    }
    for mapping in _iter_nested_dicts(payload):
        normalized = {str(key).lower(): value for key, value in mapping.items()}
        pricing: dict[str, Any] = {}
        for target, aliases in alias_map.items():
            for alias in aliases:
                if alias in normalized and normalized[alias] not in {None, ""}:
                    pricing[target] = normalized[alias]
                    break
        if pricing:
            return _normalize_token_rates(pricing, normalized.get("unit"))
    return {}
