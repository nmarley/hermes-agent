"""SQL builders and binding helpers shared by the state store."""

import json
import logging
from typing import Any

logger = logging.getLogger("hermes_state")


def escape_like(text: str) -> str:
    """Escape LIKE wildcards (``%``, ``_``) so derived text matches literally; pair with ``ESCAPE '\\'``.
    ``_`` is common in branch names/titles/paths and a substring match must not silently widen."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


_SQL_WHITESPACE = "CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32)"


def _sql_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"



def _sql_json_extract(expression: str, path: str) -> str:
    """Build a non-throwing JSON marker lookup for a JSON TEXT column."""

    safe_json = (
        f"(CASE WHEN json_valid({expression}) "
        f"THEN {expression} ELSE json_object() END)"
    )
    return f"json_extract({safe_json}, {_sql_literal(path)})"


def _sql_ltrim_whitespace(expression: str) -> str:
    return f"LTRIM({expression}, {_SQL_WHITESPACE})"


def _sql_trim_whitespace(expression: str) -> str:
    return f"TRIM({expression}, {_SQL_WHITESPACE})"


def _sql_starts_with(expression: str, prefixes: tuple[str, ...]) -> str:
    trimmed = _sql_ltrim_whitespace(expression)
    return "(" + " OR ".join(f"SUBSTR({trimmed}, 1, {len(p)}) = {_sql_literal(p)}" for p in prefixes) + ")"


def _sql_after_marker(marker: str) -> str:
    """``m.content`` after the first occurrence of *marker*."""
    return f"SUBSTR(m.content, INSTR(m.content, {_sql_literal(marker)}) + {len(marker)})"


# Match the whole introduction shared by current and legacy prefixes, so a message that merely starts with the


def _placeholders(items) -> str:
    """``?,?,?`` for one bound parameter per element of *items* (a sequence or an int count)."""
    return ",".join("?" for _ in range(items if isinstance(items, int) else len(items)))


# Ids per ``IN (?,...)`` list: SQLite caps bound parameters at SQLITE_MAX_VARIABLE_NUMBER (999 on builds
# < 3.32, 32766 after); a bulk prune of a cron-heavy store bound tens of thousands of ids into one list and
# died with "too many SQL variables". Every IN-list over session ids goes through ``_id_chunks``.
_SQL_IN_CHUNK = 900


def _id_chunks(ids, size: int = _SQL_IN_CHUNK):
    """Yield *ids* (any iterable) as lists of at most *size* elements."""
    ids = list(ids)
    for start in range(0, len(ids), size):
        yield ids[start:start + size]


def _json_or(raw: Any, fallback: Any, warning: str) -> Any:
    """``json.loads(raw)``; on failure log *warning* and return *fallback*."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(warning)
        return fallback
