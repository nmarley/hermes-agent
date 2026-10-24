"""Compatibility alias for :mod:`hermes_store.mutations.prepared` (Prepared mutation snapshots)."""

import sys

from hermes_store.mutations import prepared as _impl

sys.modules[__name__] = _impl
