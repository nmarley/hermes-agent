"""Cross-process lock-file helpers shared by repair and FTS rebuild admission."""

import contextlib
import errno
import json
import logging
import os
import sys
import time

from hermes_store.pidns import persistent_record_pidns_checkable, pid_namespace_id

# Log-record parity with the origin module (caplog tests pin "hermes_state").
logger = logging.getLogger("hermes_state")


# flock rides the open file DESCRIPTION, so a forked child inherits the lock and can outlive
# the process that recorded itself as holder. Contenders therefore record pid + start time
# under the lock and break it only when that holder is provably dead; anything indeterminate
# defers (fail closed). The FTS rebuild admission and the schema-repair lock both use these
# helpers.
_IS_WINDOWS = sys.platform == "win32"
# Post-break re-acquire budget: the fresh inode is contended only by live processes — never the full timeout.
_LOCK_BREAK_REACQUIRE_SECONDS = 5.0

# "Another process holds the lock": flock → EWOULDBLOCK/EAGAIN, msvcrt.locking → EACCES (EDEADLK when its retry
# gives up).  Anything else (ESTALE, ENOTSUP, ENOLCK, EIO) is a persistent failure polling cannot fix.
_LOCK_CONTENTION_ERRNOS = {errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK, errno.EDEADLK}


def is_advisory_lock_contention(exc: BaseException) -> bool:
    """True when *exc* means another process holds the lock; on any other ``OSError`` fail closed at once."""
    return isinstance(exc, BlockingIOError) or (isinstance(exc, OSError) and exc.errno in _LOCK_CONTENTION_ERRNOS)


def _proc_start_ticks(pid: int):
    """Kernel start time of *pid* (field 22 of ``/proc/<pid>/stat``; with the PID it identifies a process
    uniquely).  None off Linux or on any failure — callers must treat None as unknowable and FAIL CLOSED."""
    try:
        # comm (field 2) may contain spaces/parens; split after the LAST ')'.
        with open(f"/proc/{pid}/stat", "rb") as fh:
            return int(fh.read().rsplit(b")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _read_lock_holder_record(handle):
    """Best-effort parse of the holder metadata JSON in a lock file."""
    try:
        handle.seek(0)
        raw = handle.read(4096)
        record = json.loads(raw.decode("utf-8", "replace")) if raw else None
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return record if isinstance(record, dict) else None


def _rewrite_lock_file(handle, payload: bytes) -> None:
    """Best-effort truncate-and-write of *payload* at offset 0."""
    with contextlib.suppress(OSError, ValueError):
        handle.seek(0)
        handle.truncate()
        if payload:
            handle.write(payload)
        handle.flush()


def _write_lock_holder_record(handle) -> None:
    """Record this process as holder (best effort) so timed-out contenders can tell an orphaned-fd holder
    from a live wedged one.

    Written under the flock so contenders that time out can tell an orphaned-fd holder (recorded process
    dead, flock inherited by a forked child — issue #100108) from a live wedged holder.  ``pidns``: see
    ``hermes_state_pidns``.
    """
    record = {"pid": os.getpid(), "pidns": pid_namespace_id(),
              "start_ticks": _proc_start_ticks(os.getpid()), "acquired_at": time.time()}
    _rewrite_lock_file(handle, json.dumps(record, sort_keys=True).encode("utf-8"))


def _clear_lock_holder_record(handle) -> None:
    """Erase holder metadata before a normal release: a surviving record means ABNORMAL exit (break allowed)."""
    _rewrite_lock_file(handle, b"")


def _lock_holder_provably_dead(record) -> bool:
    """True ONLY when the recorded holder is provably dead or PID-recycled.  Anything indeterminate
    (no/malformed record, PID owned by another user, /proc unavailable, foreign PID namespace)
    is False: FAIL CLOSED and defer.  Unstamped records keep probing: see ``hermes_state_pidns``."""
    try:
        pid = int(record["pid"])
    except (KeyError, TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if not persistent_record_pidns_checkable(record.get("pidns")):
        return False  # foreign namespace: a local reading is not proof — defer
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False  # PermissionError et al.: PID exists (or unknowable) — closed
    recorded_ticks = record.get("start_ticks")
    if recorded_ticks is None:
        return False
    current_ticks = _proc_start_ticks(pid)
    return current_ticks is not None and current_ticks != recorded_ticks  # different start time: PID recycled


def _acquire_db_flock(lock_path, handle, timeout_seconds, poll_seconds, description):
    """Bounded POSIX flock acquire with orphaned-holder break.  Returns ``(acquired, handle)``; *handle* may
    have been re-opened and the caller closes whichever comes back.  *acquired*: True, False (a holder kept
    the lock past the deadline) or None (non-contention ``OSError``, already logged: treat as not acquired
    without the held-by-another-process warning).  ``flock`` rides the open file DESCRIPTION, which ``fork()``
    duplicates, so a holder that forks then dies leaves the lock held forever; when the acquirer is provably
    dead the file is unlinked and retaken on a fresh inode (the orphan's flock excludes nobody).  Every
    acquire verifies its inode still names *lock_path*, so a racer on a dead inode retries.

    A holder that forks (multiprocessing worker, daemonized helper) and then dies leaves the flock held by a
    child that will never release it — the kernel's holder-death release never triggers, and every contender
    defers forever. Indeterminate liveness always defers (fail closed). See #100108.
    """
    import fcntl
    deadline = time.monotonic() + timeout_seconds
    broke_lock = False
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            if not is_advisory_lock_contention(exc):
                logger.warning("Could not acquire %s %s (%s) — deferring rather than "
                               "waiting out the %.0fs holder timeout on a non-contention error.",
                               description, lock_path, exc, timeout_seconds)
                return None, handle
            if time.monotonic() < deadline:
                time.sleep(poll_seconds)
                continue
            if broke_lock:
                return False, handle
            record = _read_lock_holder_record(handle)
            if not _lock_holder_provably_dead(record):
                return False, handle
            logger.warning("%s %s is held by an orphaned file descriptor (recorded holder pid %s is dead — a "
                           "forked child inherited the lock fd); breaking the stale lock and retaking it on a "
                           "fresh file.", description, lock_path, (record or {}).get("pid"))
            try:
                os.unlink(lock_path)
                handle.close()
                handle = open(lock_path, "a+b")
            except OSError as exc:
                logger.warning("Could not break stale %s %s (%s) — deferring.", description, lock_path, exc)
                return False, handle
            broke_lock = True
            deadline = time.monotonic() + _LOCK_BREAK_REACQUIRE_SECONDS
            continue
        # A breaker may have replaced the file while we waited; a lock on a dead inode excludes nobody.
        try:
            fd_stat, path_stat = os.fstat(handle.fileno()), os.stat(lock_path)
            same_file = fd_stat.st_dev == path_stat.st_dev and fd_stat.st_ino == path_stat.st_ino
        except OSError:
            same_file = False
        if same_file:
            _write_lock_holder_record(handle)
            return True, handle
        try:
            handle.close()
            handle = open(lock_path, "a+b")
        except OSError:
            return False, handle
        if time.monotonic() >= deadline:
            return False, handle


def _describe_lock_holder(record) -> str:
    """Human-readable holder identity for deferral warnings."""
    if not isinstance(record, dict) or "pid" not in record:
        return "unknown (no holder record; pre-fix writer or non-Hermes)"
    age = ""
    with contextlib.suppress(TypeError, ValueError):
        if record.get("acquired_at") is not None:
            age = f", acquired {time.time() - float(record['acquired_at']):.0f}s ago"
    return f"pid {record.get('pid')}{age}"


def _acquire_msvcrt_lock(lock_path, handle, timeout, poll_seconds):
    """Windows counterpart of ``_acquire_db_flock`` (no orphan break); same True / False / None contract."""
    import msvcrt
    deadline = time.monotonic() + timeout
    while True:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except (BlockingIOError, OSError) as exc:
            if not is_advisory_lock_contention(exc):
                logger.warning("Could not acquire FTS rebuild lock %s (%s) — deferring on a non-contention error.",
                               lock_path, exc)
                return None
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_seconds)
