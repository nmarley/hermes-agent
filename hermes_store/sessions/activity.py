"""Session activity provenance and description helpers shared by the agent and store."""

from __future__ import annotations

from enum import Enum
from typing import Optional

ACTIVITY_DESCRIPTION_MAX = 120
SESSION_ACTIVITY_HEARTBEAT_MIN_INTERVAL_SECONDS = 60.0


class ActivityProvenance(str, Enum):
    """Where a durable/in-memory activity stamp came from."""

    UNKNOWN = "unknown"
    AGENT_COMPRESSION = "agent.compression"
    AGENT_COMPRESSION_TIMEOUT = "agent.compression_timeout"
    AGENT_COMPRESSION_COOLDOWN = "agent.compression_cooldown"
    AGENT_COMPRESSION_TURNHOLD = "agent.compression_turnhold"


TERMINAL_COMPRESSION_PROVENANCES = frozenset(
    {
        ActivityProvenance.AGENT_COMPRESSION_TIMEOUT,
        ActivityProvenance.AGENT_COMPRESSION_COOLDOWN,
        ActivityProvenance.AGENT_COMPRESSION_TURNHOLD,
    }
)


def is_terminal_compression_provenance(provenance: Optional[ActivityProvenance | str]) -> bool:
    """True when this stamp ends a compression phase and must bypass the persist rate limit."""
    return normalize_activity_provenance(provenance) in TERMINAL_COMPRESSION_PROVENANCES


def bound_activity_description(description: Optional[str]) -> str:
    """Clamp free-form activity text to the shared description budget."""
    text = (description or "").strip()
    return text if len(text) <= ACTIVITY_DESCRIPTION_MAX else text[: ACTIVITY_DESCRIPTION_MAX - 1] + "…"


def normalize_activity_provenance(provenance: Optional[ActivityProvenance | str]) -> ActivityProvenance:
    """Return a known provenance, or ``UNKNOWN`` when unset/unrecognized."""
    if isinstance(provenance, ActivityProvenance):
        return provenance
    try:
        return ActivityProvenance((provenance or "").strip())
    except ValueError:
        return ActivityProvenance.UNKNOWN
