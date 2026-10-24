"""Compatibility alias for :mod:`hermes_store.mutations.branch` (Session branching)."""

import sys

from hermes_store.mutations import branch as _impl

sys.modules[__name__] = _impl
