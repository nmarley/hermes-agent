"""Compatibility alias for :mod:`hermes_store.sqlite`."""

import sys

from hermes_store import sqlite as _impl
from hermes_store.sqlite import (
    add_column_if_missing,
    open_db,
    transaction,
    write_txn,
)

sys.modules[__name__] = _impl
