"""Compatibility alias for :mod:`hermes_store.repair.repair` (Repair and backup)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import repair as _impl

sys.modules[__name__] = _impl
