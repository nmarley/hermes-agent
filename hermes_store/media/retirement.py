"""Durable media retirement candidates survive transcript deletion and failed cleanup."""
import hashlib
import json

from hermes_store.keys import prefix_range

PREFIX = 'gateway.media.retired.v1.'
SPILLOVER_PREFIX = 'gateway.spillover.retired.v1.'


def retire_media(conn, payload, request_id=''):
    from hermes_store.api import media_hooks
    h = media_hooks()
    references = [*h.admission_media_references(payload), *h.hosted_document_references(request_id, payload),
                  *payload.get('api_turn_v1', {}).get('media', [])]
    for reference in references:
        key = PREFIX + hashlib.sha256(reference['path'].encode()).hexdigest()
        conn.execute('INSERT OR IGNORE INTO state_meta(key,value) VALUES(?,?)',
                     (key, json.dumps(reference)))


def retire_spillover(conn, session_ids):
    """Record the spillover archives the doomed sessions' messages point at, inside the delete
    transaction (the pointers vanish with the rows), as durable candidates (#126351)."""
    from hermes_store.api import media_hooks
    from hermes_store.common.sql import _id_chunks, _placeholders
    h = media_hooks()
    for chunk in _id_chunks(list(session_ids)):
        for content, api_content in conn.execute(
                f"SELECT content, api_content FROM messages WHERE session_id IN ({_placeholders(chunk)})"
                f" AND {h.spillover_sql_filter()}", chunk).fetchall():
            conn.executemany('INSERT OR IGNORE INTO state_meta(key,value) VALUES(?,?)',
                             [(SPILLOVER_PREFIX + n, json.dumps(n)) for n in h.spillover_names_in_text(content, api_content)])


def collect_retired_spillover(db):
    """Unlink retired archives no surviving message references (a branch/compression sibling sharing
    the pointer keeps it until it dies too). Unknown reference set: keep files and candidates."""
    from hermes_store.api import media_hooks
    with db._read_ctx() as conn:
        rows = conn.execute('SELECT key,value FROM state_meta WHERE key>=? AND key<?',
                            prefix_range(SPILLOVER_PREFIX)).fetchall()
    spill_dir = db.db_path.parent / 'cache' / 'spillover'
    if not rows or (referenced := media_hooks().referenced_spillover_names(spill_dir)) is None:
        return
    done = []
    for key, raw in rows:
        try:
            if (name := json.loads(raw)) not in referenced:
                (spill_dir / name).unlink(missing_ok=True)
        except OSError:
            continue  # stays a candidate for the next delete/prune pass
        done.append((key,))
    db._execute_write(lambda conn: conn.executemany('DELETE FROM state_meta WHERE key=?', done))


def collect_retired_media(db):
    """Release retired candidates no admission or retained transcript row owns; drop collected keys.
    Synchronous SQLite plus one messages pass: async callers must run it off the event loop."""
    from hermes_store.api import media_hooks
    collect_retired_spillover(db)
    with db._read_ctx() as conn:
        # Primary-key range, not LIKE: the common no-candidate case costs one index probe.
        rows = conn.execute('SELECT key,value FROM state_meta WHERE key>=? AND key<?',
                            prefix_range(PREFIX)).fetchall()
    if rows:
        media_hooks().release_unheld_media(db, [json.loads(row['value']) for row in rows])
        from pathlib import Path
        gone = [(row['key'],) for row in rows if not Path(json.loads(row['value'])['path']).exists()]
        if gone:
            db._execute_write(lambda conn: conn.executemany('DELETE FROM state_meta WHERE key=?', gone))
