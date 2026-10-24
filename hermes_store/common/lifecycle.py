"""Lifecycle-hook dispatch for committed session deletes."""

import logging
from typing import Callable, Optional

logger = logging.getLogger("hermes_state")

_SESSION_DELETE_HOOK: Optional[Callable[..., None]] = None


def set_session_delete_hook(hook: Optional[Callable[..., None]]) -> None:
    """Install the surface-owned ``on_session_delete`` dispatcher."""
    global _SESSION_DELETE_HOOK
    _SESSION_DELETE_HOOK = hook


def emit_session_deleted(db, deleted_ids, *, reason, primary=None, sessions_dir=None):
    """Fire ``on_session_delete`` after a committed delete or deliberate archive (#124511).

    Call right after the write transaction commits (before follow-up cleanup that can raise), with
    the ids it removed or, for ``reason="archive"``, hid. *primary* is the session the caller asked
    for; without it the first id stands in (bulk sweeps). ``deleted_ids`` rides along when more
    than one row went. Dispatch runs under the store's own profile home, so a process touching
    another profile's store (``sessions repair-profiles``) reaches THAT profile's plugins.
    Late-bound and fail-open: never breaks the delete.
    """
    ids = sorted({sid for sid in (deleted_ids or ()) if isinstance(sid, str) and sid})
    if not ids:
        return
    hook = _SESSION_DELETE_HOOK
    if hook is None:
        return
    try:
        hook(db, ids, reason=reason, primary=primary, sessions_dir=sessions_dir)
    except Exception:
        logger.warning("on_session_delete dispatch failed", exc_info=True)
