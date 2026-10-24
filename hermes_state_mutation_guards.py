"""Compatibility alias for :mod:`hermes_store.mutations.guards` (Mutation guards)."""

import sys

from hermes_store.mutations import guards as _impl

sys.modules[__name__] = _impl
