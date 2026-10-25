"""Compatibility alias for :mod:`hermes_store.repair.coverage` (Held-row coverage)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import coverage as _impl

sys.modules[__name__] = _impl
