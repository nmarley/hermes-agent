"""Compatibility alias for :mod:`hermes_config.backups`."""

import sys

from hermes_config import backups as _impl

sys.modules[__name__] = _impl
