"""Config and install paths shared by the config, store, and CLI layers."""

from pathlib import Path

from hermes_platform.constants import get_config_path, get_env_path

__all__ = ["get_config_path", "get_env_path", "get_project_root"]


def get_project_root() -> Path:
    """Return the repository or installed package root."""
    return Path(__file__).resolve().parents[1]
