"""CLI and gateway implementations of the store's repair hooks."""

from typing import Any, Optional

from gateway import message_timestamps, runtime_ownership
import gateway.status as gateway_status
import hermes_cli.config as hermes_config
from hermes_cli import sqlite_safe_read
import hermes_startup_watchdog as startup_watchdog


class CliRepairHooks:
    def offline_file_access(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_safe_read.offline_file_access(*args, **kwargs)

    def has_live_connection(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_safe_read.has_live_connection(*args, **kwargs)

    def connect_tracked(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_safe_read.connect_tracked(*args, **kwargs)

    def live_connection_error(self) -> type[BaseException]:
        return sqlite_safe_read.LiveConnectionError

    def cfg_get(self, *args: Any, **kwargs: Any) -> Any:
        return hermes_config.cfg_get(*args, **kwargs)

    def load_config_readonly(self) -> Any:
        return hermes_config.load_config_readonly()

    def profile_label_for_home(self, home: Any) -> Optional[str]:
        return gateway_status._profile_label_for_home(home)

    def read_gateway_lock_record(self, lock_path: Any = None) -> Optional[dict]:
        return gateway_status._read_gateway_lock_record(lock_path)

    def canonical_home(self, home: Any) -> Any:
        return runtime_ownership.canonical_home(home)

    def exclusive_maintenance(self, *args: Any, **kwargs: Any) -> Any:
        return runtime_ownership.exclusive_maintenance(*args, **kwargs)

    def ownership_conflict(self) -> type[BaseException]:
        return runtime_ownership.OwnershipConflict

    def live_runtime_owner(self, *args: Any, **kwargs: Any) -> Any:
        return runtime_ownership.live_runtime_owner(*args, **kwargs)

    def strip_leading_message_timestamps(self, content: str, tz: Any = None) -> Any:
        return message_timestamps.strip_leading_message_timestamps(content, tz)

    def report_startup_progress(self, *args: Any, **kwargs: Any) -> Any:
        return startup_watchdog.report_startup_progress(*args, **kwargs)


repair_hooks = CliRepairHooks()
