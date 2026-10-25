"""Compatibility alias for :mod:`hermes_store.adapters.terminal` (Terminal tombstones)."""

import hermes_state  # installs the adapter hooks
import sys

from hermes_store.adapters import terminal as _impl

sys.modules[__name__] = _impl
