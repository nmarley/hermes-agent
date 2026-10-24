"""Shared store constants outside the schema and FTS policy modules."""

# Auto-maintenance VACUUMs only above this freelist fraction; below it a rewrite costs more I/O than it returns.
# Auto-maintenance only VACUUMs when at least this fraction of the database file is reclaimable (``PRAGMA
# freelist_count / PRAGMA page_count``). Below it a full rewrite costs more I/O than it returns — pruning a
# handful of small sessions on a dense multi-GB state.db should never rewrite the whole file to reclaim a
# few MB (#54189). Composes with ``min_vacuum_interval_days``.
AUTO_VACUUM_MIN_FREELIST_RATIO = 0.25
