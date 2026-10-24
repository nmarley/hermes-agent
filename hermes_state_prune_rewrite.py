"""Compatibility alias for :mod:`hermes_store.compression.prune_rewrite` (Prune row rewrites)."""

import sys

from hermes_store.compression import prune_rewrite as _impl

sys.modules[__name__] = _impl
