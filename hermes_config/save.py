"""Persist individual config values into HERMES_HOME/config.yaml."""

import logging
import os

from hermes_platform import constants as _constants
from hermes_platform import utils as _utils

logger = logging.getLogger(__name__)


def save_config_value(key_path: str, value: any) -> bool:
    """Persist dot-separated ``key_path`` = value into HERMES_HOME/config.yaml; True on success.

    Never the repo's cli-config.yaml: no config reader loads it, so the value would vanish.
    """
    config_path = _constants.get_config_path()

    try:
        _constants.mkdir_under_hermes_home(config_path.parent)
        _utils.atomic_roundtrip_yaml_update(config_path, key_path, value)
        try:  # owner-only: config files contain API keys
            os.chmod(config_path, 0o600)
        except (OSError, NotImplementedError):
            pass
        return True
    except Exception as e:
        logger.error("Failed to save config: %s", e)
        return False
