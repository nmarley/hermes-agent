"""Compatibility alias for :mod:`hermes_store.compression.worker_compression` (Worker compression operations)."""

import hermes_state  # installs the compression hooks
import sys

from hermes_store.compression import worker_compression as _impl

sys.modules[__name__] = _impl
