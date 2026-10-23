"""Compatibility alias for :mod:`hermes_config.defaults`.

The implementation moved; replacing this module in ``sys.modules`` keeps the old import path
and monkeypatch seam pointing at the same module object as the new one.
"""

import sys

from hermes_config import defaults as _impl

sys.modules[__name__] = _impl
