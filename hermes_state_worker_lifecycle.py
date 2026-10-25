"""Compatibility alias for :mod:`hermes_store.runtime.worker_lifecycle` (Worker lifecycle)."""

import sys

from hermes_store.runtime import worker_lifecycle as _impl

sys.modules[__name__] = _impl
