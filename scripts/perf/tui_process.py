"""Shared PTY launch, log parsing, and build helpers for the TUI perf suites."""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TUI_DIR = Path(os.environ.get("HERMES_TUI_DIR") or str(_PROJECT_ROOT / "ui-tui"))
DEFAULT_NODE = os.environ.get("HERMES_PERF_NODE", "node")


def entry(tui_dir: Path) -> Path:
    return Path(tui_dir).resolve() / "dist" / "entry.js"


def build(tui_dir: Path) -> bool:
    """Build the TUI bundle; return False after printing the captured failure."""
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=tui_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("TUI build timed out after 600s", file=sys.stderr)
        return False
    if result.returncode == 0:
        return True
    print("TUI build failed:", file=sys.stderr)
    print(result.stdout[-2000:], file=sys.stderr)
    print(result.stderr[-2000:], file=sys.stderr)
    return False


def ensure_built(tui_dir: Path, *, build_first: bool) -> None:
    if build_first and not build(tui_dir):
        raise SystemExit("TUI build failed")
    path = entry(tui_dir)
    if not path.exists():
        raise SystemExit(
            f"{path} is missing; pass --build or run `npm run build` in {tui_dir} first"
        )


def spawn(
    tui_dir: Path,
    env: dict[str, str],
    *,
    cols: int = 120,
    rows: int = 40,
    extra_flags: tuple[str, ...] = (),
) -> tuple[int, int]:
    """Launch the built TUI in a fresh PTY; return (pid, fd)."""
    import pty  # windows-footgun: ok - the TUI suites are POSIX-only by design

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(_PROJECT_ROOT)
        os.execvpe(DEFAULT_NODE, [DEFAULT_NODE, str(entry(tui_dir)), *extra_flags], env)

    import fcntl
    import struct
    import termios

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    return pid, fd


def drain(fd: int, timeout: float) -> bytes:
    """Read whatever's available from fd within `timeout`, then return."""
    chunks = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], max(0.0, end - time.monotonic()))
        if not ready:
            break
        try:
            data = os.read(fd, 4096)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


def _signal_child(pid: int, sig: int) -> None:
    """Signal the TUI child, and its group once it owns one.

    pty.fork() setsids in the child, but the parent can observe the child's
    pre-setsid group; killpg on that value would target the harness itself.
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    try:
        if pgid == pid:
            os.killpg(pgid, sig)  # windows-footgun: ok - POSIX-only PTY harness
        else:
            os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def stop(pid: int, fd: int, *, grace: float = 1.0) -> None:
    """Terminate the TUI child, then reap and close the PTY. Never blocks forever."""
    _signal_child(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    reaped = False
    while time.monotonic() < deadline:
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            reaped = True
            break
        if done == pid:
            reaped = True
            break
        time.sleep(0.05)
    if not reaped:
        _signal_child(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                done, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                reaped = True
                break
            if done == pid:
                reaped = True
                break
            time.sleep(0.05)
    if not reaped:
        print(f"warning: TUI child {pid} did not exit", file=sys.stderr)
    try:
        os.close(fd)
    except OSError:
        pass


def stop_gateway(hermes_home: Path, *, grace: float = 2.0) -> None:
    """Stop the detached gateway a measured TUI launch started for its profile."""
    try:
        payload = json.loads((hermes_home / "gateway.pid").read_text(encoding="utf-8-sig"))
        pid = int(payload["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if not psutil.pid_exists(pid):
            return
        time.sleep(0.05)
    try:
        os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    except (ProcessLookupError, PermissionError):
        pass


def read_jsonl(path: Path, *, since_ms: int = 0) -> list[dict[str, Any]]:
    """Read best-effort JSONL rows newer than `since_ms`, skipping torn lines."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and int(row.get("ts", 0)) >= since_ms:
            rows.append(row)
    return rows
