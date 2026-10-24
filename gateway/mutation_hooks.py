"""Gateway implementations of the store's mutation hooks."""

from typing import Any, Optional

from agent.context_compressor import split_user_originated_turn
from gateway.config import Platform
from gateway.session import SessionEntry, SessionSource, build_session_key
from gateway.session_identity import parse_authenticated_subject
from gateway.session_lifecycle import _now


class GatewayMutationHooks:
    def parse_authenticated_subject(self, subject: str) -> Optional[tuple[str, str, str]]:
        return parse_authenticated_subject(subject)

    def branch_session(self, *, session_id: str, principal_id: str, origin_profile: Optional[str],
                       route_profile: Optional[str]) -> tuple[str, Any, Any]:
        source = SessionSource(Platform.LOCAL, session_id, user_id=principal_id, chat_type='dm',
                               profile=origin_profile)
        route = build_session_key(source, profile=route_profile)
        now = _now()
        entry = SessionEntry(route, session_id, now, now, origin=source, platform=Platform.LOCAL)
        return route, entry, now

    def reset_entry(self, previous_entry: Any, child_id: str) -> tuple[Any, Any]:
        previous = SessionEntry.from_dict(previous_entry)
        now = _now()
        entry = SessionEntry(previous.session_key, child_id, now, now,
                             origin=previous.origin, platform=previous.platform,
                             chat_type=previous.chat_type, display_name=previous.display_name,
                             is_fresh_reset=True)
        return entry, now

    def split_user_originated_turn(self, message: Any) -> tuple[Any, Any]:
        return split_user_originated_turn(message)


mutation_hooks = GatewayMutationHooks()
