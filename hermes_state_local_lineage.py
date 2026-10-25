"""Compatibility alias for :mod:`hermes_store.repair.local_lineage` (Local physical lineage)."""

import hermes_state  # installs the repair hooks
import sys

from hermes_store.repair import local_lineage as _impl

sys.modules[__name__] = _impl
