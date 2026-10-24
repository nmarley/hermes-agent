"""Compatibility alias for :mod:`hermes_store.mutations.actions` (Mutation action dispatch)."""

import sys

from hermes_store.mutations import actions as _impl

sys.modules[__name__] = _impl
