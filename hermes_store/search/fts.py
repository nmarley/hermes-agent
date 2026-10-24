"""FTS schema, projections, and cross-process rebuild admission."""

import contextlib
import logging

from hermes_store.common.sql import _sql_json_extract
from hermes_store.locks import (
    _IS_WINDOWS,
    _acquire_db_flock,
    _acquire_msvcrt_lock,
    _clear_lock_holder_record,
    _describe_lock_holder,
    _read_lock_holder_record,
)

# Log-record parity with the origin module (caplog tests pin "hermes_state").
logger = logging.getLogger("hermes_state")

_FTS_REBUILD_LOCK_TIMEOUT_SECONDS = 120.0
_FTS_REBUILD_LOCK_POLL_SECONDS = 0.1


# FTS storage-layout version, tracked INDEPENDENTLY of SCHEMA_VERSION in the
# state_meta key ``fts_storage_version``. The main schema version advances
# freely on open (so future migrations always land); the FTS *layout* only
# reaches the current version when a DB is either born fresh or explicitly
# optimized via ``hermes sessions optimize-storage``. A legacy DB sits at
# layout 0 (marker absent) with a working inline index until the user opts in.
#   1 = v23 external-content layout with a tool-row-excluded trigram
#   2 = trigram also excludes structured tool_calls JSON
#   3 = messages_fts source aligned to a stable projection view
#       (``messages_fts_src``): always-truncate tool rows to the prefix, no
#       moving high-water boundary. The external-content source now reads
#       back EXACTLY what the triggers indexed, so the rank=1
#       'integrity-check' probe cannot drift from the stored index (the
#       recurring fts5 "checksum mismatch" / leaked-token failures).
FTS_STORAGE_VERSION = 3

# Tool results are often multi-megabyte machine payloads. The base FTS index
# stores only a bounded prefix of every tool row; tool rows are skipped by
# default in search, and explicit tool-only search uses a LIKE fallback over
# the full stored content, so no search capability is lost. The projection
# below is STABLE — it depends only on the row being written, never on
# mutable ``state_meta`` markers — which is what keeps the external-content
# integrity checker and the trigger 'delete'/'update' commands in agreement
# with the stored index forever.
FTS_TOOL_CONTENT_PREFIX_CHARS = 8_192


def _fts_indexed_content_sql(alias: str) -> str:
    return f"""CASE WHEN {alias}.role = 'tool'
         THEN substr(COALESCE({alias}.content, ''), 1, {FTS_TOOL_CONTENT_PREFIX_CHARS})
         ELSE {alias}.content END"""


_FTS_NEW_INDEXED_CONTENT_SQL = _fts_indexed_content_sql("new")
_FTS_OLD_INDEXED_CONTENT_SQL = _fts_indexed_content_sql("old")

# Cap on user-controlled FTS5 query input before sanitizer processing.
MAX_FTS5_QUERY_CHARS = 2_048


_FTS_TRIGGERS = ("messages_fts_insert", "messages_fts_delete", "messages_fts_update",
                 "messages_fts_trigram_insert", "messages_fts_trigram_delete", "messages_fts_trigram_update")


FTS_SQL = f"""
-- Stable projection the base word index reads and writes through: the view
-- computes EXACTLY what the triggers/backfill insert, so 'rebuild' and the
-- integrity checker always agree with the stored index.
CREATE VIEW IF NOT EXISTS messages_fts_src AS
    SELECT id,
           CASE WHEN role = 'tool'
                THEN substr(COALESCE(content, ''), 1, {FTS_TOOL_CONTENT_PREFIX_CHARS})
                ELSE content END AS content,
           tool_name, tool_calls
    FROM messages;

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    tool_name,
    tool_calls,
    content='messages_fts_src',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages
WHEN (new.id > COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                         WHERE key = 'fts_rebuild_high_water'), -1)
   OR new.id <= COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                          WHERE key = 'fts_rebuild_progress'), -1))
BEGIN
    INSERT INTO messages_fts(rowid, content, tool_name, tool_calls)
    VALUES (
        new.id,
        {_FTS_NEW_INDEXED_CONTENT_SQL},
        new.tool_name,
        new.tool_calls
    );
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages
WHEN (old.id > COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                         WHERE key = 'fts_rebuild_high_water'), -1)
   OR old.id <= COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                          WHERE key = 'fts_rebuild_progress'), -1))
BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, tool_name, tool_calls)
    VALUES (
        'delete',
        old.id,
        {_FTS_OLD_INDEXED_CONTENT_SQL},
        old.tool_name,
        old.tool_calls
    );
END;

-- UPDATE OF skips the trigger entirely for non-content column writes
-- (status/compacted/observed/etc.), which is stronger than the WHEN gate
-- alone and avoids FTS I/O saturation on large state.db (#68858 / #73639).
CREATE TRIGGER IF NOT EXISTS messages_fts_update
AFTER UPDATE OF content, tool_name, tool_calls, role ON messages
WHEN (old.content IS NOT new.content
    OR old.tool_name IS NOT new.tool_name
    OR old.tool_calls IS NOT new.tool_calls
    OR old.role IS NOT new.role)
   AND (old.id > COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                           WHERE key = 'fts_rebuild_high_water'), -1)
     OR old.id <= COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                            WHERE key = 'fts_rebuild_progress'), -1))
BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, tool_name, tool_calls)
    VALUES (
        'delete',
        old.id,
        {_FTS_OLD_INDEXED_CONTENT_SQL},
        old.tool_name,
        old.tool_calls
    );
    INSERT INTO messages_fts(rowid, content, tool_name, tool_calls)
    VALUES (
        new.id,
        {_FTS_NEW_INDEXED_CONTENT_SQL},
        new.tool_name,
        new.tool_calls
    );
END;
"""


# Trigram FTS5 table for CJK substring search.  The default unicode61
# tokenizer splits CJK characters into individual tokens, breaking phrase
# matching.  The trigram tokenizer creates overlapping 3-byte sequences so
# substring queries work natively for any script (CJK, Thai, etc.).
#
# The trigram index is the most expensive index in state.db (~2.6x the size
# of the text it covers). Tool output (~90% of message bytes, machine noise)
# and cron transcripts are excluded: the index reads through
# ``messages_fts_trigram_src``, a view that skips both classes. They stay
# fully stored in ``messages`` and searchable via the standard
# ``messages_fts`` index; they just don't get trigram (CJK substring)
# treatment. ``search_messages`` routes explicit tool/cron CJK searches to
# LIKE for the same reason. Structured ``tool_calls`` JSON likewise stays
# searchable through ``messages_fts``; excluding it here avoids indexing
# repetitive JSON syntax as trigrams (FTS_STORAGE_VERSION 2).
#
# Delegate-child (subagent) transcripts are excluded the same way (v30):
# on a fan-out-heavy install they were ~70% of all message bytes and
# ``session_search`` hides ``source='subagent'`` sessions anyway. A child
# is recognised by its source OR by the ``_delegate_from`` creation marker
# (children spawned under a gateway turn inherit the gateway's source).
# Compression/branch continuations of interactive sessions also carry
# ``parent_session_id`` but NOT the marker, so they stay trigram-indexed.
FTS_TRIGRAM_EXCLUDED_SOURCES = ("cron", "subagent")

def fts_trigram_session_sql(alias: str = "") -> str:
    """Predicate over a ``sessions`` row selecting sessions whose rows belong in
    the trigram index; ``alias`` qualifies every column for joins. Shared by the
    view, the sync triggers, and the deferred-backfill INSERT ... SELECTs so they
    can never disagree about the index boundary."""
    q = f"{alias}." if alias else ""
    return (
        f"{q}source NOT IN ("
        + ", ".join(f"'{src}'" for src in FTS_TRIGRAM_EXCLUDED_SOURCES)
        + f") AND {_sql_json_extract(q + 'model_config', '$._delegate_from')} IS NULL"
    )


FTS_TRIGRAM_SESSION_SQL = fts_trigram_session_sql()


FTS_TRIGRAM_SQL = f"""
CREATE VIEW IF NOT EXISTS messages_fts_trigram_src AS
    SELECT m.id, m.role, m.content, m.tool_name
    FROM messages AS m
    JOIN sessions AS s ON s.id = m.session_id
    WHERE m.role <> 'tool' AND {fts_trigram_session_sql('s')};

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts_trigram USING fts5(
    content,
    tool_name,
    content='messages_fts_trigram_src',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS messages_fts_trigram_insert AFTER INSERT ON messages
WHEN new.role <> 'tool'
   AND EXISTS (SELECT 1 FROM sessions
               WHERE id = new.session_id AND {FTS_TRIGRAM_SESSION_SQL})
   AND (new.id > COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                           WHERE key = 'fts_rebuild_high_water'), -1)
     OR new.id <= COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                            WHERE key = 'fts_rebuild_progress'), -1))
BEGIN
    INSERT INTO messages_fts_trigram(rowid, content, tool_name)
    VALUES (new.id, new.content, new.tool_name);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_trigram_delete AFTER DELETE ON messages
WHEN old.role <> 'tool'
   AND EXISTS (SELECT 1 FROM sessions
               WHERE id = old.session_id AND {FTS_TRIGRAM_SESSION_SQL})
   AND (old.id > COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                           WHERE key = 'fts_rebuild_high_water'), -1)
     OR old.id <= COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                            WHERE key = 'fts_rebuild_progress'), -1))
BEGIN
    INSERT INTO messages_fts_trigram(messages_fts_trigram, rowid, content, tool_name)
    VALUES ('delete', old.id, old.content, old.tool_name);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_trigram_update
AFTER UPDATE OF content, tool_name, role ON messages
WHEN (old.content IS NOT new.content
    OR old.tool_name IS NOT new.tool_name
    OR old.role IS NOT new.role)
   AND (old.id > COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                           WHERE key = 'fts_rebuild_high_water'), -1)
     OR old.id <= COALESCE((SELECT CAST(value AS INTEGER) FROM state_meta
                            WHERE key = 'fts_rebuild_progress'), -1))
BEGIN
    INSERT INTO messages_fts_trigram(messages_fts_trigram, rowid, content, tool_name)
    SELECT 'delete', old.id, old.content, old.tool_name
    WHERE old.role <> 'tool'
      AND EXISTS (SELECT 1 FROM sessions
                  WHERE id = old.session_id AND {FTS_TRIGRAM_SESSION_SQL});
    INSERT INTO messages_fts_trigram(rowid, content, tool_name)
    SELECT new.id, new.content, new.tool_name
    WHERE new.role <> 'tool'
      AND EXISTS (SELECT 1 FROM sessions
                  WHERE id = new.session_id AND {FTS_TRIGRAM_SESSION_SQL});
END;
"""

_FTS_CJK_TRIGGERS = ("messages_fts_cjk_insert", "messages_fts_cjk_delete", "messages_fts_cjk_update")

# Set when a tokenizer-less process dropped the cjk triggers to keep writes alive: the cjk index is missing rows
# and must not serve reads until `hermes sessions optimize-storage` rebuilds it on a capable host.
FTS_CJK_STALE_KEY = "fts_cjk_stale"

# Set when a base/trigram FTS index was detached after runtime corruption; startup must rebuild the complete
# index before reinstalling sync triggers (rows written while they were absent leave an unknown gap).
FTS_STALE_KEY = "fts_stale"

# Durable diagnostic for stale FTS recovery blocked across process restarts.
FTS_REBUILD_DEFERRAL_KEY = "fts_rebuild_deferral"


# ── Legacy (v22 / inline-content) FTS DDL ──────────────────────────────
# Used ONLY to keep an existing pre-v23 install's search working and its
# triggers repairable UNTIL the user opts into `hermes db optimize`. This is
# the exact inline shape v11..v22 shipped: each virtual table stores its own
# copy of ``content || tool_name || tool_calls`` and the trigram table indexes
# every row (including role='tool'). We never CREATE these on a fresh install —
# fresh installs are born on the v23 external-content schema above. These
# constants exist so a legacy DB is never accidentally handed the v23 DDL
# (which would create the external-content trigram source VIEW and leave the
# DB in a mixed, broken state). `optimize_fts_storage()` is what migrates a
# legacy DB to the v23 shape.
LEGACY_FTS_SQL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content
);

CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (
        new.id,
        COALESCE({_FTS_NEW_INDEXED_CONTENT_SQL}, '')
        || ' ' || COALESCE(new.tool_name, '') || ' ' || COALESCE(new.tool_calls, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
    DELETE FROM messages_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_update
AFTER UPDATE OF content, tool_name, tool_calls, role ON messages BEGIN
    DELETE FROM messages_fts WHERE rowid = old.id;
    INSERT INTO messages_fts(rowid, content) VALUES (
        new.id,
        COALESCE({_FTS_NEW_INDEXED_CONTENT_SQL}, '')
        || ' ' || COALESCE(new.tool_name, '') || ' ' || COALESCE(new.tool_calls, '')
    );
END;
"""


LEGACY_FTS_TRIGRAM_SQL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts_trigram USING fts5(
    content,
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS messages_fts_trigram_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts_trigram(rowid, content) VALUES (
        new.id,
        COALESCE({_FTS_NEW_INDEXED_CONTENT_SQL}, '')
        || ' ' || COALESCE(new.tool_name, '') || ' ' || COALESCE(new.tool_calls, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_trigram_delete AFTER DELETE ON messages BEGIN
    DELETE FROM messages_fts_trigram WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_trigram_update
AFTER UPDATE OF content, tool_name, tool_calls, role ON messages BEGIN
    DELETE FROM messages_fts_trigram WHERE rowid = old.id;
    INSERT INTO messages_fts_trigram(rowid, content) VALUES (
        new.id,
        COALESCE({_FTS_NEW_INDEXED_CONTENT_SQL}, '')
        || ' ' || COALESCE(new.tool_name, '') || ' ' || COALESCE(new.tool_calls, '')
    );
END;
"""


@contextlib.contextmanager
def fts_rebuild_admission(db_path, *, timeout_seconds=None):
    """Serialize full structural FTS rebuilds on *db_path* across processes.  Yields True when this process
    holds the authority, False when the bounded acquire timed out or the lock file could not be opened: the
    caller must NOT rebuild (fail closed; the stale breadcrumb guarantees a retry).  ``db_path`` None
    (in-memory) yields True.  In-process retries pass ``timeout_seconds=0`` so a live holder never stalls a
    long-lived writer; the orphan break still applies."""
    if db_path is None:
        yield True
        return
    timeout = _FTS_REBUILD_LOCK_TIMEOUT_SECONDS if timeout_seconds is None else max(float(timeout_seconds), 0.0)
    lock_path = f"{db_path}.fts_rebuild.lock"
    try:
        handle = open(lock_path, "a+b")
    except OSError as exc:
        # Fail closed like a timed-out acquire: an unopenable lock file means the FS is out of
        # space/inodes/descriptors and a sibling that opened earlier may still be rebuilding — yielding True
        # gave every process on a full disk a concurrent rebuild.  Deferring is free: the breadcrumb retries.
        logger.warning("Could not open FTS rebuild lock %s (%s) — deferring this rebuild "
                       "rather than running it without cross-process authority.", lock_path, exc)
        yield False
        return
    acquired = False
    try:
        if _IS_WINDOWS:
            acquired = _acquire_msvcrt_lock(lock_path, handle, timeout, _FTS_REBUILD_LOCK_POLL_SECONDS)
        else:
            acquired, handle = _acquire_db_flock(
                lock_path, handle, timeout, _FTS_REBUILD_LOCK_POLL_SECONDS, "FTS rebuild lock")
        if acquired is None:
            # Already logged with the real errno; "held by another process" would be a lie.
            acquired = False
        elif not acquired:
            record = None if _IS_WINDOWS else _read_lock_holder_record(handle)
            if timeout <= 0:
                # Non-blocking probe from an in-process retry: keep it quiet.
                logger.info("FTS rebuild lock %s is busy — deferring this retry "
                            "(the stale-FTS breadcrumb keeps it retryable). Recorded holder: %s.",
                            lock_path, _describe_lock_holder(record))
            else:
                logger.warning("FTS rebuild lock %s held by another process for more than %.0fs — deferring "
                               "this rebuild to avoid racing the holder (the stale-FTS breadcrumb keeps it "
                               "retryable). Recorded holder: %s.", lock_path, timeout, _describe_lock_holder(record))
        yield acquired
    finally:
        try:
            with contextlib.suppress(OSError):  # best-effort release
                if acquired and _IS_WINDOWS:
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                elif acquired:
                    import fcntl
                    _clear_lock_holder_record(handle)
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
