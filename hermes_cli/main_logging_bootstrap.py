"""Early config bridge and file logging for the CLI entry point.

Runs at import time in ``hermes_cli.main`` before argparse, so failures during
dispatch reach the same log files every other surface writes.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Optional, Sequence

from hermes_cli.config import get_hermes_home, is_managed
from hermes_platform.logging import setup_logging

logger = logging.getLogger(__name__)


def _load_early_config() -> Optional[Mapping[str, Any]]:
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return None
    try:
        from hermes_cli.config_effective import load_user_config_effective
        return load_user_config_effective(config_path)
    except Exception:
        logger.debug("early config read failed", exc_info=True)
        return None


def _mode_for(argv: Sequence[str]) -> str:
    command = next((arg for arg in argv if not arg.startswith("-")), "")
    return "gui" if command in {"dashboard", "serve", "gui", "desktop"} else "cli"


def bootstrap_early_logging(argv: Sequence[str]) -> bool:
    """Bridge config into the environment, start file logging, return force_ipv4."""
    config = None
    force_ipv4 = False
    try:
        config = _load_early_config()
        if config:
            if "HERMES_REDACT_SECRETS" not in os.environ:
                security = config.get("security", {})
                if isinstance(security, dict):
                    redact = security.get("redact_secrets")
                    if redact is not None:
                        os.environ["HERMES_REDACT_SECRETS"] = str(redact).lower()
            network = config.get("network", {})
            if isinstance(network, dict) and network.get("force_ipv4"):
                force_ipv4 = True
    except Exception:
        logger.debug("early config bridge failed", exc_info=True)
        config = None
        force_ipv4 = False
    try:
        setup_logging(mode=_mode_for(argv), config=config, managed=is_managed())
    except Exception:
        logger.debug("early logging setup failed", exc_info=True)
    return force_ipv4
