"""Compatibility shim for the state facade: the implementation lives in ``hermes_store.api``.

``SessionDB`` is re-exported explicitly because the frozen old-updater surface resolves names
statically from this file. Replacing ``sys.modules`` makes the old and new import paths one
module object, so existing patch seams keep working during the migration.
"""

import sys

from hermes_store import api as _api
from hermes_store.api import SessionDB

__all__ = ["SessionDB"]


def _load_config_readonly():
    from hermes_cli.config import load_config_readonly
    return load_config_readonly()


def _install_agent_turn_hooks():
    from agent.agent_runtime_helpers import repair_message_sequence
    from agent.compaction_display import project_compaction_message_for_display
    from agent.context_compressor import split_user_originated_turn, user_originated_turn_view
    _api.set_turn_view_hooks(
        split_user_originated_turn=split_user_originated_turn,
        user_originated_turn_view=user_originated_turn_view,
        repair_message_sequence=repair_message_sequence,
        project_compaction_message_for_display=project_compaction_message_for_display,
    )


def _dispatch_session_delete(db, ids, **kwargs):
    from hermes_cli.lifecycle_session import emit_session_deleted_event
    emit_session_deleted_event(db, ids, **kwargs)


_api.set_config_loader(_load_config_readonly)
_api.set_session_delete_hook(_dispatch_session_delete)
_install_agent_turn_hooks()

sys.modules[__name__] = _api
