"""Compatibility alias for :mod:`hermes_store.repair.reconcile` (Schema drift reconciliation)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import reconcile as _impl

sys.modules[__name__] = _impl
