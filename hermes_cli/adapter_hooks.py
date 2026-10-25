"""CLI implementations of the store's domain-adapter hooks."""

from typing import Any

from agent import turn_context
from hermes_cli import dashboard_procs
from tools import todo_tool


class CliAdapterHooks:
    def reanchor_current_turn_user_idx(self, messages: list, user_message: Any) -> int:
        return turn_context.reanchor_current_turn_user_idx(messages, user_message)

    def max_todo_result_chars(self) -> int:
        return todo_tool.MAX_TODO_RESULT_CHARS

    def is_ephemeral_port_zero_backend(self, argv: list) -> bool:
        return dashboard_procs._is_ephemeral_port_zero_backend(argv)


adapter_hooks = CliAdapterHooks()
