"""Session lineage, source, and recency SQL predicates."""

from hermes_store.common.sql import _placeholders, _sql_json_extract
from hermes_store.common.time import EPOCH_MAX, EPOCH_MIN


# ── Session lineage predicates ({a} = sessions alias) ───────────────────────

# /branch child (kept visible, never cascade-deleted): stable marker OR legacy end_reason heuristic.
_BRANCH_CHILD_SQL = (f"{_sql_json_extract('{a}.model_config', '$._branched_from')} IS NOT NULL"
    " OR EXISTS (SELECT 1 FROM sessions p            WHERE p.id = {a}.parent_session_id"
    "            AND p.end_reason = 'branched'            AND {a}.started_at >= p.ended_at)")
_COMPRESSION_CHILD_SQL = ("EXISTS (SELECT 1 FROM sessions p        WHERE p.id = {a}.parent_session_id"
    "        AND p.end_reason = 'compression')")

# 'session_switch' creates no child row today, but pre-marker DBs hold legacy reset children whose parent
# ended that way.  Must stay identical to the recovery fence in find_latest_gateway_session_for_peer.
_RESET_END_REASONS = ("session_reset", "session_switch", "idle", "daily", "suspended", "resume_pending_expired")
_RESET_END_REASONS_SQL = ", ".join(f"'{reason}'" for reason in _RESET_END_REASONS)
# Deliberate conversation boundaries: the reset set plus CLI /new, which ends the predecessor as
# 'new_session' (hermes_cli/cli_session_mixin.py) without a reset child row.  A compression rotation must
# never heal one of these (#106459); tools/session_search_tool.py derives its fresh-reset set from it.
_BOUNDARY_END_REASONS = frozenset(_RESET_END_REASONS) | {"new_session"}

# Accidental end reasons recovery treats as resumable (website/docs/developer-guide/gateway-session-lifecycle.md); single source of truth for
# recovery SQL and SessionDB.RECOVERABLE_END_REASONS.  superseded_by_resume = sentinel-parked runtime replaced
# by a fresh session.resume; startup_orphan_reap = dead-gateway sweep, same class as ws_orphan_reap but kept
# distinct for forensics.
_RECOVERABLE_END_REASONS = ("agent_close", "ws_orphan_reap", "superseded_by_resume", "startup_orphan_reap")
# Startup sweep of rows orphaned by a dead gateway process (#65194): the in-process ws-orphan grace timer
# died with the process, so the row was closed at the next boot instead.
_RECOVERABLE_END_REASONS_SQL = ", ".join(f"'{reason}'" for reason in _RECOVERABLE_END_REASONS)

# End reasons written by AUTOMATIC cleanup (shutdown, orphan reapers, idle/LRU eviction), not a deliberate
# conversation boundary: "some runtime went away", so a writer that can prove liveness (e.g. a compression
# rotation holding the lease) may clear it.  Recoverable set plus the TUI gateway's automatic reasons.
# Superset of the recoverable set: those are already resumable accidents; the extra TUI reasons are the same
# accident class but were historically only known to tui_gateway's _AUTOMATIC_SESSION_END_REASONS. See
# #88197.
_AUTOMATIC_END_REASONS = frozenset(_RECOVERABLE_END_REASONS) | {
    "tui_shutdown", "ws_disconnect", "idle_timeout", "lru_evict"}


def is_automatic_end_reason(reason) -> bool:
    """True when *reason* is an automatic-cleanup end stamp; compression-liveness sites must call this.

    Single owner of the "accidental vs deliberate end" predicate — every compression-liveness site must call
    this instead of re-implementing the reason taxonomy (#88197, never-patch-predicates).
    """
    return isinstance(reason, str) and reason in _AUTOMATIC_END_REASONS


def _legacy_reset_child_sql(alias: str, reasons_sql: str) -> str:
    """Pre-marker reset-continuation heuristic: child rides its parent's exact non-empty routing key and the
    parent ended at a reset boundary.  Shared by ``_RESET_CHILD_SQL`` and ``reopen_session()`` so the two
    cannot drift; ``reasons_sql`` is a literal or placeholder list."""
    return (f"EXISTS (SELECT 1 FROM sessions p            WHERE p.id = {alias}.parent_session_id"
        f"            AND p.end_reason IN ({reasons_sql})            AND {alias}.session_key IS NOT NULL"
        f"            AND {alias}.session_key != ''            AND {alias}.session_key = p.session_key)")


def _non_continuation_child_sql(child: str = "", parent: str = "?") -> str:
    """``  AND ...`` clauses rejecting children that are NOT compression continuations of *parent*
    (branch/delegate/reset forks, tool sessions).  Markers are bound to the parent id: continuations
    inherit ``model_config`` verbatim, so a marker naming another row is inherited, not a fork.
    ``child`` is the column prefix (``""``, ``"c."``); single owner so prune and compression agree."""
    return "".join(
        f"  AND COALESCE({_sql_json_extract(f'{child}model_config', f'$.{marker}')}, '') != {parent}\n"
        for marker in ("_branched_from", "_delegate_from", "_reset_from")
    ) + f"  AND COALESCE({child}source, '') != 'tool'\n"


# A reset starts a separate user-visible conversation though rows keep parent_session_id for lineage.
# Stable marker, or the same-key fallback for pre-marker rows (exact key keeps subagent children out).
_RESET_CHILD_SQL = (f"{_sql_json_extract('{a}.model_config', '$._reset_from')} IS NOT NULL"
    " OR " + _legacy_reset_child_sql("{a}", _RESET_END_REASONS_SQL))

# Picker-visible rows: roots + branch/reset children (not subagent runs or compression continuations).
_LISTABLE_CHILD_SQL = (f"(s.parent_session_id IS NULL OR {_BRANCH_CHILD_SQL.format(a='s')}"
    f" OR {_RESET_CHILD_SQL.format(a='s')})")


def _ephemeral_child_sql(alias: str = "s") -> str:
    """Subagent runs, not branch, reset, or compression children."""
    return (f"({alias}.parent_session_id IS NOT NULL AND NOT ({_BRANCH_CHILD_SQL.format(a=alias)})"
        f" AND NOT ({_COMPRESSION_CHILD_SQL.format(a=alias)}) AND NOT ({_RESET_CHILD_SQL.format(a=alias)}))")


_SQL_IN_WINDOW = f"BETWEEN {EPOCH_MIN!r} AND {EPOCH_MAX!r}"


def _sql_in_window(expr: str) -> str:
    """*expr* when it is inside the ``coerce_epoch`` window, else NULL."""
    return f"(SELECT _win.v FROM (SELECT {expr} AS v) _win WHERE _win.v {_SQL_IN_WINDOW})"


def _sql_freshest_of(activity: str, session_id_expr: str, started: str) -> str:
    """Freshest of *activity* and the latest message timestamp for *session_id_expr*, else *started*.
    Heartbeats are rate-limited (~60s) so ``last_activity_at`` can lag a newer message; never use it alone.
    Cells outside the ``coerce_epoch`` window (garbage doubles salvaged from a damaged page, TEXT) are
    skipped, fallback included, or one bad row pins the session's recency to ``5e+246`` (#91536); a
    session with no trusted cell at all is NULL."""
    # Pinned for the same reason as _sql_preview_raw (#119403).
    msg_max = (f"(SELECT MAX(_act_m.timestamp) FROM messages _act_m INDEXED BY idx_messages_session"
        f" WHERE _act_m.session_id = {session_id_expr}"
        f" AND _act_m.timestamp {_SQL_IN_WINDOW})")
    return (f"COALESCE((SELECT MAX(_act_v.v) FROM (SELECT {activity} AS v UNION ALL SELECT {msg_max}) _act_v"
        f" WHERE _act_v.v {_SQL_IN_WINDOW}), {_sql_in_window(started)})")


def _sql_session_last_active(alias: str = "s") -> str:
    """Session recency expression for a ``sessions {alias}`` row."""
    return _sql_freshest_of(f"{alias}.last_activity_at", f"{alias}.id", f"{alias}.started_at")


def _sql_session_last_active_by_id(session_id_expr: str) -> str:
    """Same freshest-of expression keyed by a session-id SQL expression."""
    return _sql_freshest_of(
        f"(SELECT last_activity_at FROM sessions _act_s WHERE _act_s.id = {session_id_expr})", session_id_expr,
        f"(SELECT started_at FROM sessions _act_s WHERE _act_s.id = {session_id_expr})")


# A first prompt is durable in ``session_admissions`` from admission on, while its transcript row lands
# only at turn start; a restart in between leaves the admission ``unknown`` and the session at 0
# messages. Only a session with neither messages nor an admission is an empty launch stub.
_NOT_A_LAUNCH_STUB_SQL = (
    "(s.message_count > 0 OR EXISTS (SELECT 1 FROM session_admissions a WHERE a.target_session_id = s.id))")


def launch_stub_filter_sql(db) -> str:
    """``sessions s`` predicate that drops empty launch stubs (the CLI crashed or a resume failed before
    the first turn). A read-only open does not migrate, so a store from before the runtime tables may
    lack ``session_admissions``; messages alone decide there."""
    if db._read_all("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'session_admissions'"):
        return _NOT_A_LAUNCH_STUB_SQL
    return "s.message_count > 0"


def _source_match_clause(sources, local_created_sources=None) -> tuple[str, list]:
    """``sessions s`` source predicate. With ``local_created_sources``, a ``source='local'`` row
    matches only when ``created_source`` is one of those surfaces; the placeholder ``'unknown'``
    is not a surface and stays unmatched until an upsert stamps the real creator."""
    labels = list(sources or [])
    if not labels:
        return "", []
    surfaces = list(local_created_sources or ())
    if not surfaces:
        return f"s.source IN ({_placeholders(labels)})", labels
    non_local = [item for item in labels if item != "local"]
    local_sql = f"(s.source = 'local' AND s.created_source IN ({_placeholders(surfaces)}))"
    if not non_local:
        return local_sql, list(surfaces)
    return (
        f"(s.source IN ({_placeholders(non_local)}) OR {local_sql})",
        [*non_local, *surfaces],
    )
