"""Compatibility alias for :mod:`hermes_store.runtime.readpool` (Read connection pool)."""

import sys

from hermes_store.runtime import readpool as _impl

sys.modules[__name__] = _impl
