"""Filesystem identity helpers for the state store."""

import os


def stat_db_file_identity(path) -> tuple[int, int] | None:
    """``(st_dev, st_ino)`` for *path*, or None.  st_ino=0 (Windows, some network FS) would false-positive
    every replaced-file check, so it counts as unknown."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_dev, st.st_ino) if st.st_dev and st.st_ino else None
