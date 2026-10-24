"""Compatibility alias for :mod:`hermes_store.mutations.reset` (Session reset mutation)."""

import sys

from hermes_store.mutations import reset as _impl

sys.modules[__name__] = _impl
