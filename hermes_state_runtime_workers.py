"""Compatibility alias for :mod:`hermes_store.runtime.workers` (Runtime worker lineage)."""

import sys

from hermes_store.runtime import workers as _impl

sys.modules[__name__] = _impl
