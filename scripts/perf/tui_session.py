"""One isolated, ready TUI session for the interactive perf suites.

The session owns a fake provider, a temp HOME/HERMES_HOME, the Node PTY child,
and the detached gateway it starts. Closing it stops all three and removes the
temp tree unless --keep-home was passed.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.perf import hermetic, tui_process


@dataclass
class TuiSession:
    root: Path
    home: Path
    hermes_home: Path
    log: Path
    env: dict[str, str]
    pid: int
    fd: int
    since_ms: int
    keep_home: bool
    server: Any
    screen: Any = None

    def drain(self, timeout: float = 0.02) -> bytes:
        data = tui_process.drain(self.fd, timeout)
        if data and self.screen is not None:
            self.screen.feed(data)
        return data

    def rows(self) -> list[dict[str, Any]]:
        return tui_process.read_jsonl(self.log, since_ms=self.since_ms)

    def startup_rows(self) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for row in self.rows():
            if row.get("src") != "startup":
                continue
            phase = row.get("phase")
            if isinstance(phase, str) and phase not in rows:
                rows[phase] = row
        return rows

    def wait_for_phase(self, phase: str, timeout: float) -> dict[str, dict[str, Any]]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.drain()
            rows = self.startup_rows()
            if phase in rows:
                return rows
        return self.startup_rows()

    def close(self) -> None:
        tui_process.stop(self.pid, self.fd)
        tui_process.stop_gateway(self.hermes_home)
        try:
            self.server.stop()
        finally:
            if not self.keep_home:
                shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> TuiSession:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def launch(
    args: argparse.Namespace,
    *,
    wait_for: str = "session_ready",
    timeout: float = 30.0,
    screen: Any = None,
) -> TuiSession:
    """Start a TUI in an isolated home and wait for one startup phase."""
    from tests.fakes.fake_llm_provider import FakeLLMServer, write_hermes_home

    root = Path(tempfile.mkdtemp(prefix="hermes-perf-tui-"))
    home = root / "home"
    home.mkdir(parents=True, exist_ok=True)
    log = root / "perf.log"
    server = FakeLLMServer()
    pid = fd = None
    try:
        server.start()
        write_hermes_home(home / ".hermes", server.base_url)
        hermetic.link_install_state(home / ".hermes")
        env = hermetic.clean_env(home, log)
        since_ms = int(time.time() * 1000)
        pid, fd = tui_process.spawn(
            Path(args.tui_dir), env, cols=args.cols, rows=args.rows
        )
        session = TuiSession(
            root=root,
            home=home,
            hermes_home=home / ".hermes",
            log=log,
            env=env,
            pid=pid,
            fd=fd,
            since_ms=since_ms,
            keep_home=bool(getattr(args, "keep_home", False)),
            server=server,
            screen=screen,
        )
        if wait_for:
            session.wait_for_phase(wait_for, timeout)
        return session
    except BaseException:
        if pid is not None and fd is not None:
            tui_process.stop(pid, fd)
        tui_process.stop_gateway(home / ".hermes")
        server.stop()
        shutil.rmtree(root, ignore_errors=True)
        raise
