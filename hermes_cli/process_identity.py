"""Compatibility alias for :mod:`hermes_platform.process`."""

import sys

from hermes_platform import process as _impl

sys.modules[__name__] = _impl
