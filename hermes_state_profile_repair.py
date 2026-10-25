"""Compatibility alias for :mod:`hermes_store.repair.profile_repair` (Cross-profile repair)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import profile_repair as _impl

sys.modules[__name__] = _impl
