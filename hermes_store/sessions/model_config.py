"""Tolerant ``sessions.model_config`` decoding."""

from __future__ import annotations

import json
from typing import Any


def parse_model_config(raw: Any) -> dict[str, Any]:
    """JSON text or dict -> dict copy; anything else -> {}."""
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return dict(raw) if isinstance(raw, dict) else {}
