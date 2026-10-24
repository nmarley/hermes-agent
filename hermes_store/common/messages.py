"""Message-row probes and display predicates shared by the messages and compression mixins."""

from hermes_store.common.compression import MODEL_ONLY_DISPLAY_METADATA_KEY
from hermes_store.common.sql import _sql_json_extract

# ``display_metadata`` flag stamped on the user row a busy-queue accept writes (#111868/#121374
# accept-time durability). The in-memory queue drain re-places an unmarked row at the transcript
# end and deactivates this one; a backend restart discards the queue with nothing left to retire
# the accept-time row, so ``reopen_session`` deactivates still-marked rows (#125577) — the marker
# is exactly what distinguishes a never-drained accept row from a dispatched-then-interrupted
# turn's row (which #123532 deliberately keeps active).
QUEUED_PROMPT_METADATA_KEY = "_queued_prompt"


# Row probes shared by the messages / compression mixins.
_ENDED_ROW_SQL = "SELECT ended_at, end_reason FROM sessions WHERE id = ?"
_COMPRESSION_LOCK_ROW_SQL = "SELECT holder, expires_at FROM compression_locks WHERE session_id = ?"


def _ended_by_compression(row) -> bool:
    return row is not None and row["ended_at"] is not None and row["end_reason"] == "compression"

# Model-only rows never enter a display projection. Unqualified on purpose: inside a correlated
# subquery it binds to the innermost ``messages`` alias.
DISPLAY_VISIBLE_SQL = (
    f" AND COALESCE({_sql_json_extract('display_metadata', '$.' + MODEL_ONLY_DISPLAY_METADATA_KEY)}, 0) = 0")
