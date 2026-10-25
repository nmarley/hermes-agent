"""CLI implementations of the store's storage hooks."""

from typing import Any

import utils
from agent import session_client_env
from hermes_cli import backup, config as hermes_config, sqlite_runtime, sqlite_safe_read


class CliStorageHooks:
    def atomic_json_write(self, *args: Any, **kwargs: Any) -> Any:
        return utils.atomic_json_write(*args, **kwargs)

    def connect_tracked(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_safe_read.connect_tracked(*args, **kwargs)

    def has_live_connection(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_safe_read.has_live_connection(*args, **kwargs)

    def read_header_bytes_preopen(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_safe_read.read_header_bytes_preopen(*args, **kwargs)

    def is_zeroed_sqlite_file(self, *args: Any, **kwargs: Any) -> Any:
        return backup.is_zeroed_sqlite_file(*args, **kwargs)

    def is_sqlite_wal_reset_vulnerable(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_runtime.is_sqlite_wal_reset_vulnerable(*args, **kwargs)

    def load_config_readonly(self) -> Any:
        return hermes_config.load_config_readonly()

    def cfg_get(self, *args: Any, **kwargs: Any) -> Any:
        return hermes_config.cfg_get(*args, **kwargs)

    def detect_install_method(self, *args: Any, **kwargs: Any) -> Any:
        return hermes_config.detect_install_method(*args, **kwargs)

    def get_project_root(self, *args: Any, **kwargs: Any) -> Any:
        return hermes_config.get_project_root(*args, **kwargs)

    def recommended_update_command_for_method(self, *args: Any, **kwargs: Any) -> Any:
        return hermes_config.recommended_update_command_for_method(*args, **kwargs)

    def retry_matches(self, *args: Any, **kwargs: Any) -> Any:
        return session_client_env.retry_matches(*args, **kwargs)


storage_hooks = CliStorageHooks()
