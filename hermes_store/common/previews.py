"""Session-preview SQL and display shaping."""

from typing import Any

from hermes_store.common.compression import (
    LEGACY_SUMMARY_PREFIX,
    SUMMARY_PREFIX,
    _MERGED_PRIOR_CONTEXT_HEADER,
    _MERGED_SUMMARY_DELIMITER,
    _SUMMARY_END_MARKER,
)
from hermes_store.common.skills import (
    AUTO_LOAD_SCAFFOLD_SQL_LIKE,
    SKILL_EXCERPT_JOINT,
    SKILL_SCAFFOLD_SQL_LIKE,
    describe_skill_invocation,
)
from hermes_store.common.sql import (
    _sql_after_marker,
    _sql_literal,
    _sql_ltrim_whitespace,
    _sql_starts_with,
    _sql_trim_whitespace,
)


# Session preview = head of the first user message (shown when a session has no title).  A /skill invocation
# embeds the whole skill body, so scaffolded rows take a wider excerpt (whole message under budget, else head +
# tail where the typed instruction lands) and ``_shape_preview`` recovers ``/work — fix ...`` from it.
_PREVIEW_HEAD_CHARS = 63
_PREVIEW_SCAFFOLD_WINDOW = 400
_PREVIEW_MAX_CHARS = 60


_PREVIEW_CONTENT_SQL = "REPLACE(REPLACE(m.content, X'0A', ' '), X'0D', ' ')"
# User-invoked and gateway auto-load scaffolds both get the head+tail excerpt window:
# the typed request sits at the tail (auto-load) or behind the instruction marker.
# No LIKE wildcards in either prefix, so no ESCAPE clause is needed.
_PREVIEW_SCAFFOLDED_SQL = (
    f"(m.content LIKE '{SKILL_SCAFFOLD_SQL_LIKE}'"
    f" OR m.content LIKE '{AUTO_LOAD_SCAFFOLD_SQL_LIKE}')")


# Match the whole introduction shared by current and legacy prefixes, so a message that merely starts with the
# bracketed label is not a compaction carrier.
_PREVIEW_LONG_FORM_PREFIX = SUMMARY_PREFIX.split("Do NOT answer", 1)[0]
_PREVIEW_SUMMARY_PREFIXES = (_PREVIEW_LONG_FORM_PREFIX, LEGACY_SUMMARY_PREFIX)
_PREVIEW_STANDALONE_SUMMARY_SQL = _sql_starts_with("m.content", _PREVIEW_SUMMARY_PREFIXES)
_PREVIEW_MERGED_AFTER_SQL = _sql_after_marker(_MERGED_SUMMARY_DELIMITER)
_PREVIEW_MERGED_SUMMARY_SQL = (f"(INSTR(m.content, {_sql_literal(_MERGED_SUMMARY_DELIMITER)}) > 0"
    f" AND {_sql_starts_with(_PREVIEW_MERGED_AFTER_SQL, _PREVIEW_SUMMARY_PREFIXES)})")
_PREVIEW_MERGED_PRIOR_SQL = _sql_trim_whitespace(
    f"SUBSTR(m.content, 1, INSTR(m.content, {_sql_literal(_MERGED_SUMMARY_DELIMITER)}) - 1)")
_PREVIEW_MERGED_PRIOR_LTRIMMED_SQL = _sql_ltrim_whitespace(_PREVIEW_MERGED_PRIOR_SQL)
_PREVIEW_MERGED_PRIOR_UNWRAPPED_SQL = (f"CASE WHEN SUBSTR({_PREVIEW_MERGED_PRIOR_LTRIMMED_SQL}, 1,"
    f" {len(_MERGED_PRIOR_CONTEXT_HEADER)}) = {_sql_literal(_MERGED_PRIOR_CONTEXT_HEADER)}"
    f" THEN {_sql_ltrim_whitespace(f'SUBSTR({_PREVIEW_MERGED_PRIOR_LTRIMMED_SQL}, {len(_MERGED_PRIOR_CONTEXT_HEADER) + 1})')}"
    f" ELSE {_PREVIEW_MERGED_PRIOR_SQL} END")
_PREVIEW_FORCE_USER_REMAINDER_SQL = _sql_after_marker(_SUMMARY_END_MARKER)

# Pure compaction rows are ineligible; force-user-leading and merged carriers only when authentic content survives.
# A display_kind="hidden" row is model-facing scaffolding the gateway never paints; the preview must not paint it either.
_PREVIEW_ELIGIBLE_SQL = (f"(COALESCE(m.display_kind, '') <> 'hidden'"
    f" AND ((NOT {_PREVIEW_STANDALONE_SUMMARY_SQL} AND NOT {_PREVIEW_MERGED_SUMMARY_SQL})"
    f" OR ({_PREVIEW_STANDALONE_SUMMARY_SQL} AND INSTR(m.content, {_sql_literal(_SUMMARY_END_MARKER)}) > 0"
    f" AND LENGTH({_sql_trim_whitespace(_PREVIEW_FORCE_USER_REMAINDER_SQL)}) > 0)"
    f" OR ({_PREVIEW_MERGED_SUMMARY_SQL}"
    f" AND LENGTH({_sql_trim_whitespace(_PREVIEW_MERGED_PRIOR_UNWRAPPED_SQL)}) > 0)))")

# ``_preview_raw`` SELECT for every listing query (scaffolded rows: head + tail around SKILL_EXCERPT_JOINT).
_PREVIEW_RAW_SELECT = (
    f"CASE WHEN {_PREVIEW_STANDALONE_SUMMARY_SQL} THEN {_PREVIEW_FORCE_USER_REMAINDER_SQL}"
    f" WHEN {_PREVIEW_MERGED_SUMMARY_SQL} THEN {_PREVIEW_MERGED_PRIOR_UNWRAPPED_SQL}"
    f" WHEN {_PREVIEW_SCAFFOLDED_SQL} AND LENGTH(m.content) > {_PREVIEW_SCAFFOLD_WINDOW * 2}"
    f" THEN SUBSTR({_PREVIEW_CONTENT_SQL}, 1, {_PREVIEW_SCAFFOLD_WINDOW}) || '{SKILL_EXCERPT_JOINT}'"
    f" || SUBSTR({_PREVIEW_CONTENT_SQL}, -{_PREVIEW_SCAFFOLD_WINDOW})"
    f" WHEN {_PREVIEW_SCAFFOLDED_SQL} THEN SUBSTR({_PREVIEW_CONTENT_SQL}, 1, {_PREVIEW_SCAFFOLD_WINDOW * 2})"
    f" ELSE SUBSTR({_PREVIEW_CONTENT_SQL}, 1, {_PREVIEW_HEAD_CHARS}) END")


def _shape_preview(raw: Any) -> str:
    """Turn a ``_preview_raw`` column into the short preview callers show."""
    text = str(raw or "").strip()
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    described = describe_skill_invocation(text)
    text = described if described is not None else text.split(SKILL_EXCERPT_JOINT)[0]
    return text[:_PREVIEW_MAX_CHARS] + "..." if len(text) > _PREVIEW_MAX_CHARS else text


def _sql_preview_raw(session_id_expr: str = "s.id") -> str:
    """Correlated ``_preview_raw`` column: the first eligible user message of *session_id_expr*.
    ``INDEXED BY`` walks the session in timestamp order and stops at the first eligible row; with planner
    stats older than idx_messages_session_id, SQLite otherwise reads and sorts the whole session (#119403)."""
    return (f"COALESCE((SELECT {_PREVIEW_RAW_SELECT} FROM messages m INDEXED BY idx_messages_session"
        f" WHERE m.session_id = {session_id_expr} AND m.role = 'user' AND m.content IS NOT NULL"
        f" AND {_PREVIEW_ELIGIBLE_SQL} ORDER BY m.timestamp, m.id LIMIT 1), '') AS _preview_raw")
