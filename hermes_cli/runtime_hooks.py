"""CLI implementations of the store's runtime hooks."""

from typing import Any, Optional

from gateway import session_policy
from hermes_cli import sqlite_safe_read


class CliRuntimeHooks:
    def connect_tracked(self, *args: Any, **kwargs: Any) -> Any:
        return sqlite_safe_read.connect_tracked(*args, **kwargs)

    def created_surface(self, value: Any) -> Optional[str]:
        return session_policy.created_surface(value)


runtime_hooks = CliRuntimeHooks()
