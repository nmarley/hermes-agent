"""Compatibility alias for :mod:`hermes_store.adapters.todo` (Todo result lookup)."""

import hermes_state  # installs the adapter hooks
import sys

from hermes_store.adapters import todo as _impl

sys.modules[__name__] = _impl
