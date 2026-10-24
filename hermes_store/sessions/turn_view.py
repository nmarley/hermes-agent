"""Surface-injected turn projection and sequence repair hooks for the store."""

from __future__ import annotations

from typing import Any, Callable, Optional

_SPLIT_TURN: Optional[Callable[[Any], Any]] = None
_USER_VIEW: Optional[Callable[[Any], Any]] = None
_REPAIR_SEQUENCE: Optional[Callable[[Any, list], int]] = None
_PROJECT_COMPACTION: Optional[Callable[[Any], Any]] = None


def set_turn_view_hooks(
    *,
    split_user_originated_turn: Optional[Callable[[Any], Any]] = None,
    user_originated_turn_view: Optional[Callable[[Any], Any]] = None,
    repair_message_sequence: Optional[Callable[[Any, list], int]] = None,
    project_compaction_message_for_display: Optional[Callable[[Any], Any]] = None,
) -> None:
    """Install the surface-owned turn projections."""
    global _SPLIT_TURN, _USER_VIEW, _REPAIR_SEQUENCE, _PROJECT_COMPACTION
    if split_user_originated_turn is not None:
        _SPLIT_TURN = split_user_originated_turn
    if user_originated_turn_view is not None:
        _USER_VIEW = user_originated_turn_view
    if repair_message_sequence is not None:
        _REPAIR_SEQUENCE = repair_message_sequence
    if project_compaction_message_for_display is not None:
        _PROJECT_COMPACTION = project_compaction_message_for_display


def split_user_originated_turn(message: Any):
    fn = _SPLIT_TURN
    if fn is None:
        return None, message if isinstance(message, dict) else None
    return fn(message)


def user_originated_turn_view(message: Any):
    fn = _USER_VIEW
    return fn(message) if fn is not None else (message if isinstance(message, dict) else None)


def repair_message_sequence(agent: Any, messages: list) -> int:
    fn = _REPAIR_SEQUENCE
    return fn(agent, messages) if fn is not None else 0


def project_compaction_message_for_display(message: Any):
    fn = _PROJECT_COMPACTION
    return fn(message) if fn is not None else (message.copy() if isinstance(message, dict) else None)
