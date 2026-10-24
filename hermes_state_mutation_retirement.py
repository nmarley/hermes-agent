"""Compatibility alias for :mod:`hermes_store.mutations.retirement` (Session retirement fences)."""

import sys

from hermes_store.mutations import retirement as _impl

sys.modules[__name__] = _impl
