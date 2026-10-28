"""Surface callbacks the host platform layer cannot import directly."""

from typing import Any, Callable, Optional, Protocol


class PlatformHooks(Protocol):
    def windows_hide_flags(self) -> int: ...

    def installed_package(self, name: str) -> Any: ...

    def env_for(self, spec: str, base_env: Any = None) -> Any: ...

    def venv_bin_dir(self, venv_dir: Any, *, windows: Optional[bool] = None) -> Any: ...

    def site_packages(self, venv_dir: Any) -> Any: ...

    def venv_python(self, venv_dir: Any, *, windows: Optional[bool] = None) -> Any: ...

    def retry_backoff(self, attempt: int, *, base_delay: float, max_delay: float) -> float: ...

    def split_key_path(self, key_path: str) -> list: ...

    def greedy_literal_match(self, mapping: dict, keys: list) -> Any: ...

    def require_readable_config_before_write(self, path: Any) -> Any: ...

    def redact_sensitive_text(self, text: str) -> str: ...

    def redacting_formatter(self) -> type: ...

    def is_managed(self) -> bool: ...

    def load_user_config_effective(self, path: Any) -> Any: ...

    def is_multiplex_active(self) -> bool: ...

    def spawner_is_dead(self, entry: Any) -> Optional[bool]: ...

    def process_start_time(self, pid: int) -> Any: ...

    def report_startup_progress(self, *args: Any, **kwargs: Any) -> Any: ...


_provider: Optional[Callable[[], PlatformHooks]] = None


def set_platform_hooks_provider(provider: Optional[Callable[[], PlatformHooks]]) -> None:
    global _provider
    _provider = provider


def platform_hooks() -> PlatformHooks:
    if _provider is None:
        # Entry points call platform functions (notably setup_logging) before the
        # root composition shim is imported. Import the shim here so the provider
        # exists on first use; the root-package edge is a migration allowance.
        import hermes_state  # health: allow LATE_IMPORT -- platform bootstrap runs before the composition shim
    if _provider is None:
        raise RuntimeError("platform hooks are not installed")
    return _provider()
