"""Compatibility alias for :mod:`hermes_store.repair.local_migration` (Legacy local migration)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import local_migration as _impl

sys.modules[__name__] = _impl
