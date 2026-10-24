"""Gateway implementations of the store's compression hooks."""

from typing import Any, Optional

from agent.context_compressor import (
    ContextCompressor,
    history_before_user_originated_turn, retryable_user_text, split_user_originated_turn,
    user_originated_turn_view,
)
from agent.message_content import flatten_message_text
from agent.session_persistence import _durable_content, _is_ephemeral_scaffolding
from gateway.session_policy import created_surface


class GatewayCompressionHooks:
    def __init__(self, worker_automation_state_types: Any) -> None:
        self._worker_automation_state_types = worker_automation_state_types

    def created_surface(self, value: Any) -> Optional[str]:
        return created_surface(value)

    def user_originated_turn_view(self, message: Any) -> Any:
        return user_originated_turn_view(message)

    def history_before_user_originated_turn(self, messages: list, index: int) -> tuple[list, Any]:
        return history_before_user_originated_turn(messages, index)

    def retryable_user_text(self, message: Any) -> Any:
        return retryable_user_text(message)

    def split_user_originated_turn(self, message: Any) -> tuple[Any, Any]:
        return split_user_originated_turn(message)

    def is_ephemeral_scaffolding(self, message: Any) -> bool:
        return _is_ephemeral_scaffolding(message)

    def durable_content(self, content: Any) -> Any:
        return _durable_content(content)

    def flatten_message_text(self, content: Any) -> str:
        return flatten_message_text(content)

    def worker_automation_state_types(self) -> tuple[tuple[str, Any], ...]:
        return self._worker_automation_state_types()

    def is_context_summary_content(self, content: Any) -> bool:
        return ContextCompressor._is_context_summary_content(content)
