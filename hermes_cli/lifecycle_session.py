"""Dispatch ``on_session_delete`` for the store's lifecycle seam."""

import os

from hermes_cli.lifecycle import invoke_hook
from hermes_constants import (
    get_hermes_home, profile_name_for_home, reset_hermes_home_override, set_hermes_home_override,
)


def emit_session_deleted_event(db, ids, *, reason, primary=None, sessions_dir=None):
    """Dispatch under the store's own profile home, then restore the caller's scope."""
    home = os.path.dirname(os.path.abspath(os.fspath(db.db_path)))
    profile = profile_name_for_home(home)
    payload: dict = {"session_id": primary if primary in ids else ids[0], "reason": reason, "profile": profile}
    if len(ids) > 1:
        payload["deleted_ids"] = ids
    if sessions_dir is not None:
        payload["sessions_dir"] = str(sessions_dir)
    rebind = profile is not None and os.path.realpath(home) != os.path.realpath(get_hermes_home())
    token = set_hermes_home_override(home) if rebind else None
    try:
        invoke_hook("on_session_delete", **payload)
    finally:
        if token is not None:
            reset_hermes_home_override(token)
