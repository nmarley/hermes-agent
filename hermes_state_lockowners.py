"""Compatibility alias for :mod:`hermes_store.runtime.lockowners` (Write lock owners)."""

import sys

from hermes_store.runtime import lockowners as _impl

sys.modules[__name__] = _impl
