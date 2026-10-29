"""CLI implementations of the host platform hooks."""

from typing import Any, Optional

from agent import retry_utils
from agent import secret_scope
import gateway.status as gateway_status
import hermes_cli._subprocess_compat as subprocess_compat
import hermes_cli.config as hermes_config
from hermes_cli import config_effective
from hermes_cli import process_identity
from hermes_platform import startup_watchdog
import pm
import pm.environments as pm_environments
from agent import redact


class CliPlatformHooks:
    def windows_hide_flags(self) -> int:
        return subprocess_compat.windows_hide_flags()

    def installed_package(self, name: str) -> Any:
        return pm.installed_package(name)

    def env_for(self, spec: str, base_env: Any = None) -> Any:
        return pm.env_for(spec, base_env=base_env)

    def venv_bin_dir(self, venv_dir: Any, *, windows: Optional[bool] = None) -> Any:
        return pm_environments.venv_bin_dir(venv_dir, windows=windows)

    def site_packages(self, venv_dir: Any) -> Any:
        return pm_environments.site_packages(venv_dir)

    def venv_python(self, venv_dir: Any, *, windows: Optional[bool] = None) -> Any:
        return pm_environments.venv_python(venv_dir, windows=windows)

    def retry_backoff(self, attempt: int, *, base_delay: float, max_delay: float) -> float:
        return retry_utils.jittered_backoff(attempt, base_delay=base_delay, max_delay=max_delay)

    def split_key_path(self, key_path: str) -> list:
        return hermes_config._split_key_path(key_path)

    def greedy_literal_match(self, mapping: dict, keys: list) -> Any:
        return hermes_config._greedy_literal_match(mapping, keys)

    def require_readable_config_before_write(self, path: Any) -> Any:
        return hermes_config.require_readable_config_before_write(path)

    def redact_sensitive_text(self, text: str) -> str:
        return redact.redact_sensitive_text(text)

    def redacting_formatter(self) -> type:
        return redact.RedactingFormatter

    def is_managed(self) -> bool:
        return hermes_config.is_managed()

    def load_user_config_effective(self, path: Any) -> Any:
        return config_effective.load_user_config_effective(path)

    def is_multiplex_active(self) -> bool:
        return secret_scope.is_multiplex_active()

    def spawner_is_dead(self, entry: Any) -> Optional[bool]:
        return process_identity.spawner_is_dead(entry)

    def is_live_process(self, pid: int, stamp: Any) -> bool:
        return gateway_status.get_process_start_time(pid) == stamp

    def report_startup_progress(self, *args: Any, **kwargs: Any) -> Any:
        return startup_watchdog.report_startup_progress(*args, **kwargs)


platform_hooks = CliPlatformHooks()
