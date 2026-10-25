"""Compatibility alias for :mod:`hermes_platform.utils`."""

import sys

from hermes_platform import utils as _impl
from hermes_platform.utils import (
    atomic_json_write, atomic_roundtrip_yaml_update, atomic_yaml_write, env_var_enabled,
    fast_safe_load,
)

sys.modules[__name__] = _impl
