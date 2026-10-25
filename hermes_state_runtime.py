"""Compatibility alias for :mod:`hermes_store.runtime.transactions` (Runtime transactions)."""

import sys

from hermes_store.runtime import transactions as _impl

sys.modules[__name__] = _impl
