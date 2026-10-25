"""Compatibility alias for :mod:`hermes_store.adapters.gateway` (Gateway-facing session state)."""

import hermes_state  # installs the adapter hooks
import sys

from hermes_store.adapters import gateway as _impl

sys.modules[__name__] = _impl
