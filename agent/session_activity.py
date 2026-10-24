"""Shared session activity observation contract: timestamp + bounded description/provenance, observation
only (notification, timeout, kill and retry policy live elsewhere). Provenance is a small closed enum of
*noun* sources; the default agent clock stamps ``unknown`` unless a writer passes ``provenance=``."""

from __future__ import annotations

import sys
import time
from contextlib import suppress
from enum import Enum
from typing import Any, Mapping, Optional

from agent.i18n import t
from hermes_store.sessions.activity import (
    ACTIVITY_DESCRIPTION_MAX, SESSION_ACTIVITY_HEARTBEAT_MIN_INTERVAL_SECONDS, ActivityProvenance,
    TERMINAL_COMPRESSION_PROVENANCES,
    bound_activity_description, is_terminal_compression_provenance, normalize_activity_provenance,
)

def format_iteration_progress(api_call_count: Any, max_iterations: Any) -> str:
    """``iteration N/M`` for user-facing status lines, or ``iteration N`` when the cap is unbounded.

    ``AIAgent.max_iterations`` defaults to ``sys.maxsize`` (unlimited), so printing the pair verbatim
    shows ``iteration 3/9223372036854775807`` in busy acks, heartbeats and timeout diagnostics (#102806).
    """
    try:
        cap = int(max_iterations)
    except (TypeError, ValueError):
        cap = sys.maxsize
    if cap >= sys.maxsize:
        return t("display.iteration_progress.unbounded", n=api_call_count)
    return t("display.iteration_progress.bounded", n=api_call_count, max=cap)


def reset_session_activity_persist_window(agent: Any) -> None:
    """Clear the persist rate-limit so the next stamp writes through (terminal compression labels must not stick on mid-compress text)."""
    with suppress(Exception):
        agent._session_activity_last_persist_mono = 0.0


def build_activity_snapshot(
    *,
    last_activity_at: Optional[float],
    last_activity_description: Optional[str],
    last_activity_provenance: Optional[ActivityProvenance | str] = None,
    now: Optional[float] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Build the shared activity snapshot (plus optional caller extras)."""
    when = float(last_activity_at) if last_activity_at is not None else None
    clock = float(now if now is not None else time.time())
    desc = bound_activity_description(last_activity_description)
    prov = normalize_activity_provenance(last_activity_provenance).value
    return {
        "last_activity_at": when,
        "last_activity_description": desc,
        "last_activity_provenance": prov,
        "seconds_since_activity": round(clock - when, 1) if when is not None else None,
        # Short aliases used by existing gateway/delegate readers.
        "last_activity_ts": when, "last_activity_desc": desc, "description": desc, "provenance": prov,
        **(extra or {}),
    }


class AwakeIdleMeter:
    """Removes host sleep from a polling watchdog's idle readings.

    Idle time is measured on the wall clock, which keeps running while the host sleeps, so a laptop
    that sleeps 15 minutes mid-turn wakes up "idle" for 15 minutes and the first poll after resume
    kills a turn that never had a chance to run. ``time.monotonic()`` pauses during sleep on macOS
    (``mach_absolute_time``) and Linux (``CLOCK_MONOTONIC``), so the two clocks drift apart by the
    time spent asleep. Call :meth:`measure` once per poll with the wall-clock idle seconds.
    """

    def __init__(self) -> None:
        self._wall, self._mono = time.time(), time.monotonic()
        self._asleep_s = 0.0

    def measure(self, idle_s: float) -> float:
        """Return *idle_s* minus the sleep observed since the agent's last activity."""
        wall, mono = time.time(), time.monotonic()
        slept_s = max(0.0, (wall - self._wall) - (mono - self._mono))
        # Activity since the previous sample (it is younger than the sampling interval) makes all
        # earlier credit predate it. A rarely sampled meter (stale-agent eviction samples only
        # when a message arrives) would otherwise keep charging old sleep against new idle time.
        if idle_s < wall - self._wall:
            self._asleep_s = 0.0
        self._asleep_s += slept_s
        self._wall, self._mono = wall, mono
        # The idle sample may predate sleep observed by these clock reads. Keep that new
        # credit until the next poll; only older credit can be trimmed by renewed activity.
        self._asleep_s = max(0.0, min(self._asleep_s, idle_s + slept_s))
        return max(0.0, idle_s - self._asleep_s)
