"""Default configuration data for Hermes Agent: DEFAULT_CONFIG and OPTIONAL_ENV_VARS.

Pure-data leaf module. Comments are the user-facing docs of config.yaml. The literal is split
across ``defaults_config_core`` and ``defaults_config_surface`` to keep each module under the
code-health file cap; the merged dict preserves the original top-level key order.
"""

from hermes_config.defaults_config_core import DEFAULT_CONFIG_CORE
from hermes_config.defaults_config_surface import DEFAULT_CONFIG_SURFACE
from hermes_config.defaults_env_vars import OPTIONAL_ENV_VARS
from hermes_config.defaults_shared import (
    DEFAULT_SANDBOX_IMAGE, DEFAULT_VERCEL_IMAGE, LEGACY_SANDBOX_IMAGE, LEGACY_SANDBOX_IMAGES,
    LEGACY_VERCEL_RUNTIME, _aux,
)

DEFAULT_CONFIG = {**DEFAULT_CONFIG_CORE, **DEFAULT_CONFIG_SURFACE}
