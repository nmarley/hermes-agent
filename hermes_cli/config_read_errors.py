"""Compatibility alias for :mod:`hermes_config.read_errors`."""

import sys

from hermes_config import read_errors as _impl

sys.modules[__name__] = _impl
