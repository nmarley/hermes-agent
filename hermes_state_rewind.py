"""Compatibility alias for :mod:`hermes_store.compression.rewind` (Carrier-aware rewind)."""

import hermes_state  # installs the compression hooks
import sys

from hermes_store.compression import rewind as _impl

sys.modules[__name__] = _impl
