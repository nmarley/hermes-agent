"""Stable message INSERT shape and column list shared by writers and repair."""

import re

_INSERT_MESSAGE_SQL = """INSERT INTO messages (session_id, role, content, tool_call_id,
                   tool_calls, tool_name, effect_disposition, timestamp, token_count, finish_reason,
                   reasoning, reasoning_content, reasoning_details, codex_reasoning_items,
                   codex_message_items, platform_message_id, observed, _compressed_summary, active, api_content, display_kind,
                   display_metadata, display_identity, message_uid, absorbed_message_uids, tool_call_uids,
                   tool_call_uid)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

_MESSAGE_WRITE_COLUMNS = tuple(
    re.findall(r"\w+", _INSERT_MESSAGE_SQL.split("(", 1)[1].split(")", 1)[0])
)
