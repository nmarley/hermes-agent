"""Compatibility alias for :mod:`hermes_store.mutations.compress` (Compression mutation)."""

import sys

from hermes_store.mutations import compress as _impl

sys.modules[__name__] = _impl
