"""Routed ``sessions.*`` settings for the profile whose state.db this process touches."""

import os
from typing import Any

from hermes_platform.constants import get_hermes_home_override
from hermes_store.common.config import load_config_snapshot


def routed_sessions_setting(key: str, env_var: str) -> Any:
    """``sessions.<key>`` for the profile whose state.db this process is touching.

    ``gateway/run.py`` bridges the LAUNCH profile's ``sessions.*`` into ``env_var`` (the cross-process
    carrier CLI/cron children read). Under a multiplexer a routed turn runs with a HERMES_HOME override
    and that env slot holds the default profile's value, so a served profile with different
    ``sessions.*`` settings must read its own config.yaml. Unscoped: the env bridge, as before.
    Returns ``None`` when neither source sets the key.
    """
    if get_hermes_home_override():
        try:
            config = load_config_snapshot()
            if config is None:
                return None
            return (config.get("sessions") or {}).get(key)
        except Exception:
            return None
    return os.environ.get(env_var)
