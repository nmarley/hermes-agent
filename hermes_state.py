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


def _load_mutation_hooks():
    from gateway.mutation_hooks import mutation_hooks
    return mutation_hooks


def _load_compression_hooks():
    from gateway.compression_hooks import GatewayCompressionHooks
    from hermes_cli.goals import GoalState
    from hermes_cli.heartbeat import HeartbeatState
    from hermes_cli.loops import LoopState

    return GatewayCompressionHooks(
        lambda: (('goal', GoalState), ('heartbeat', HeartbeatState), ('loop', LoopState)))


def _load_repair_hooks():
    from hermes_cli.repair_hooks import repair_hooks
    return repair_hooks


def _load_runtime_hooks():
    from hermes_cli.runtime_hooks import runtime_hooks
    return runtime_hooks


def _load_media_hooks():
    from hermes_cli.media_hooks import media_hooks
    return media_hooks


def _load_adapter_hooks():
    from hermes_cli.adapter_hooks import adapter_hooks
    return adapter_hooks


def _load_storage_hooks():
    from hermes_cli.storage_hooks import storage_hooks
    return storage_hooks


def _load_platform_hooks():
    from hermes_cli.platform_hooks import platform_hooks
    return platform_hooks


_api.set_config_loader(_load_config_readonly)
_api.set_session_delete_hook(_dispatch_session_delete)
_api.set_mutation_hooks_provider(_load_mutation_hooks)
_api.set_compression_hooks_provider(_load_compression_hooks)
_api.set_repair_hooks_provider(_load_repair_hooks)
_api.set_runtime_hooks_provider(_load_runtime_hooks)
_api.set_media_hooks_provider(_load_media_hooks)
_api.set_adapter_hooks_provider(_load_adapter_hooks)
_api.set_storage_hooks_provider(_load_storage_hooks)
from hermes_platform.hooks import set_platform_hooks_provider
from hermes_platform.logging import set_redactor_provider
from hermes_platform.time import set_timezone_source_provider
set_platform_hooks_provider(_load_platform_hooks)
set_redactor_provider(_load_platform_hooks)
set_timezone_source_provider(_load_platform_hooks)
_install_agent_turn_hooks()

sys.modules[__name__] = _api
