"""Compatibility alias for :mod:`hermes_store.mutations.binding` (History control bindings)."""

import sys

from hermes_store.mutations import binding as _impl

sys.modules[__name__] = _impl
