"""Keyboard echo and first-open latency for the Ink TUI.

Runs a real TUI in an isolated home, types a rare character, and measures the
time until it appears on the emulated screen. Opens the model and session
pickers once each and measures their first-open latency. Repeat-key scrolling
stays in the tui-frames suite, which runs against a populated transcript.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.perf import metrics as perf
from scripts.perf import tui_process, tui_session
from tests.e2e.core.terminal._vt import Screen

PROBE = "§"
BACKSPACE = b"\x7f"
CLEAR = b"\x15"
ENTER = b"\r"
ESCAPE = b"\x1b"

MODEL_TITLE = "Select provider (step 1/3)"
SESSIONS_TITLE = "Sessions"


class Harness:
    """The PTY plus the emulated screen it feeds."""

    def __init__(self, session: tui_session.TuiSession, screen: Screen) -> None:
        self.session = session
        self.screen = screen

    def pump(self, timeout: float = 0.01) -> bytes:
        return self.session.drain(timeout)

    def text(self) -> str:
        rows = self.screen.display() if self.screen.alt_active else self.screen.transcript()
        return "\n".join(rows)

    def write(self, data: bytes) -> None:
        os.write(self.session.fd, data)

    def wait_for(self, needle: str, timeout: float) -> float | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump(0.005)
            if needle in self.text():
                return time.monotonic()
        return None

    def wait_absent(self, needle: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump(0.005)
            if needle not in self.text():
                return True
        return False

    def clear(self) -> None:
        self.write(CLEAR)
        self.pump(0.05)
        if PROBE in self.text():
            self.write(BACKSPACE * 64)
            self.pump(0.1)


def _echo_samples(harness: Harness, samples: int, timeout: float) -> list[float]:
    # One warmup pass so the first measurement is not the focus/typography settle.
    harness.clear()
    harness.write(PROBE.encode())
    harness.wait_for(PROBE, timeout)
    harness.write(BACKSPACE)
    harness.wait_absent(PROBE, timeout)

    latencies: list[float] = []
    for _ in range(samples):
        harness.clear()
        started = time.monotonic()
        harness.write(PROBE.encode())
        seen = harness.wait_for(PROBE, timeout)
        if seen is None:
            break
        latencies.append((seen - started) * 1000.0)
        harness.write(BACKSPACE)
        harness.wait_absent(PROBE, timeout)
    return latencies


def _picker_open(
    harness: Harness, command: str, title: str, timeout: float
) -> float | None:
    harness.clear()
    harness.write(command.encode())
    harness.pump(0.05)
    started = time.monotonic()
    harness.write(ENTER)
    seen = harness.wait_for(title, timeout)
    latency = None if seen is None else (seen - started) * 1000.0
    harness.write(ESCAPE)
    harness.wait_absent(title, 2.0)
    harness.clear()
    return latency


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--samples", type=int, default=10,
                        help="echo samples per run (default 10)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="seconds to wait for one screen change")
    parser.add_argument("--cols", type=int, default=120)
    parser.add_argument("--rows", type=int, default=40)
    parser.add_argument("--tui-dir", default=str(tui_process.DEFAULT_TUI_DIR))
    parser.add_argument("--keep-home", action="store_true",
                        help="keep the temp HOME and HERMES_HOME for inspection")


def run_once(args: argparse.Namespace) -> tuple[dict[str, perf.Metric], str]:
    """Measure echo, first picker opens, and key-to-frame latency."""
    screen = Screen(args.rows, args.cols)
    session = tui_session.launch(
        args, wait_for="session_ready", timeout=args.timeout, screen=screen
    )
    try:
        harness = Harness(session, screen)
        metrics: dict[str, perf.Metric] = {}

        echo = _echo_samples(harness, args.samples, args.timeout)
        if echo:
            metrics["input.echo_ms"] = perf.Metric(
                name="input.echo_ms", unit="ms", samples=tuple(echo),
                note="key write to the echoed cell",
            )

        model_open = _picker_open(harness, "/model", MODEL_TITLE, args.timeout)
        if model_open is not None:
            metrics["input.model_picker_open_ms"] = perf.Metric(
                name="input.model_picker_open_ms", unit="ms", samples=(model_open,),
                note="Enter on /model to the provider stage",
            )

        sessions_open = _picker_open(harness, "/sessions", SESSIONS_TITLE, args.timeout)
        if sessions_open is not None:
            metrics["input.session_picker_open_ms"] = perf.Metric(
                name="input.session_picker_open_ms", unit="ms", samples=(sessions_open,),
                note="Enter on /sessions to the overlay title",
            )

        lines = [f"screen: {args.cols}x{args.rows}"]
        lines.append(
            f"echo: {len(echo)} samples"
            + (
                f", p50 {perf.percentile(echo, 0.50):.1f}ms, "
                f"p95 {perf.percentile(echo, 0.95):.1f}ms"
                if echo else " (missing)"
            )
        )
        lines.append(
            "model picker: "
            + (f"{model_open:.0f}ms" if model_open is not None else "missing")
        )
        lines.append(
            "session picker: "
            + (f"{sessions_open:.0f}ms" if sessions_open is not None else "missing")
        )
        lines.append(f"perf log: {session.log}")
        if args.keep_home:
            lines.append(f"home kept: {session.home}")

        return metrics, "\n".join(lines)
    finally:
        session.close()
