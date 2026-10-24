"""Compatibility alias for :mod:`hermes_store.compression.session` (Compression lineage and locks)."""

import sys

from hermes_store.compression import session as _impl

sys.modules[__name__] = _impl
