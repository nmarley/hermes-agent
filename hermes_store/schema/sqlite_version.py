"""Pure SQLite version predicates with no host or surface dependencies."""

WAL_RESET_FIXED_VERSION = (3, 51, 3)


def _version_tuple(parts) -> tuple[int, int, int]:
    values = [int(part) for part in parts]
    values.extend([0] * (3 - len(values)))
    return tuple(values[:3])


def is_sqlite_wal_reset_vulnerable(version_info: tuple[int, ...]) -> bool:
    """Return whether *version_info* contains SQLite's WAL-reset bug."""
    info = _version_tuple(version_info)
    return not (
        info < (3, 7, 0)
        or info >= WAL_RESET_FIXED_VERSION
        or (3, 50, 7) <= info < (3, 51, 0)
        or (3, 44, 6) <= info < (3, 45, 0))
