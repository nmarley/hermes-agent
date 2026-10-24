"""Pure message sanitization helpers shared by the agent and the store."""

from __future__ import annotations

import re
from typing import Any

# Lone surrogates are invalid UTF-8 and crash json.dumps in the OpenAI SDK.
_SURROGATE_RE = re.compile(r'[\ud800-\udfff]')


def _sanitize_surrogates(text: str) -> str:
    """Replace lone surrogate code points with U+FFFD; no-op when none present."""
    if text.isascii():
        return text
    return _SURROGATE_RE.sub('\ufffd', text)


def _tc_field(tc: Any, key: str) -> Any:
    """Read ``key`` from a tool-call entry that may be a dict or an SDK object."""
    return tc.get(key) if isinstance(tc, dict) else getattr(tc, key, None)


def coalesce_tool_call_id(tc: Any) -> str:
    """Effective call id of a tool_call entry (dict or object); ``""`` when none."""
    for raw in (_tc_field(tc, "call_id"), _tc_field(tc, "id")):
        value = raw.strip() if isinstance(raw, str) else ""
        if value:
            return value.split("|", 1)[0].strip() or value
    return ""


def _expand_tool_id_variants(values: tuple[Any, ...]) -> frozenset[str]:
    """Every wire spelling of one tool-call identifier."""
    variants: set[str] = set()
    for raw in values:
        value = raw.strip() if isinstance(raw, str) else ""
        if value:
            variants.add(value)
            variants.update(p for p in (part.strip() for part in value.split("|")) if p)
    return frozenset(variants)


def tool_call_id_variants(tc: Any) -> frozenset[str]:
    """Return all pairing-id variants carried by a tool-call entry."""
    return _expand_tool_id_variants(tuple(_tc_field(tc, k) for k in ("call_id", "id", "response_item_id")))


def tool_result_id_variants(tool_call_id: Any) -> frozenset[str]:
    """Return all matching variants for a role=tool ``tool_call_id``."""
    return _expand_tool_id_variants((tool_call_id,))


def _scrub_surrogates(value: Any) -> Any:
    """Lone surrogates make sqlite3 raise UnicodeEncodeError and abort the whole write."""
    return _sanitize_surrogates(value) if isinstance(value, str) else value
