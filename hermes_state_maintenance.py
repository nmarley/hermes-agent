"""Compatibility alias for :mod:`hermes_store.repair.maintenance` (Retention and maintenance)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import maintenance as _impl

sys.modules[__name__] = _impl
