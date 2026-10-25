"""Compatibility alias for :mod:`hermes_store.repair.portability` (Export and import)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import portability as _impl

sys.modules[__name__] = _impl
