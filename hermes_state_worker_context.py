"""Compatibility alias for :mod:`hermes_store.runtime.worker_context` (Worker constructor context)."""

import sys

from hermes_store.runtime import worker_context as _impl

sys.modules[__name__] = _impl
