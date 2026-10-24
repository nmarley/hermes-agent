"""Injected config snapshot reader for store modules during the platform split."""

from typing import Callable, Optional

_CONFIG_LOADER: Optional[Callable[[], dict]] = None


def set_config_loader(loader: Optional[Callable[[], dict]]) -> None:
    """Install the config reader. The root shim owns the surface import; the store does not."""
    global _CONFIG_LOADER
    _CONFIG_LOADER = loader


def load_config_snapshot() -> Optional[dict]:
    """The current config snapshot, or None when no loader is installed."""
    loader = _CONFIG_LOADER
    return loader() if loader is not None else None
