"""Idle redraw and CPU cost for a ready TUI session."""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import psutil

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.perf import metrics as perf
from scripts.perf import tui_process, tui_session


def _cadence(stamps: list[float]) -> str:
    """Name the trigger from the median gap between a pane's commits."""
    if len(stamps) < 2:
        return "react"
    gaps = sorted(stamps[i] - stamps[i - 1] for i in range(1, len(stamps)))
    median = gaps[len(gaps) // 2]
    if 800 <= median <= 1200:
        return "clock"
    if 80 <= median <= 300:
        return "animation"
    if 4000 <= median <= 6000:
        return "poll"
    return "react"


def classify_frames(
    frames: list[dict[str, Any]], react: list[dict[str, Any]]
) -> Counter[str]:
    """Attribute each idle frame to a React pane and its timer cadence."""
    commits = sorted(
        ((float(row["ts"]), str(row.get("id", "?"))) for row in react if "ts" in row),
        key=lambda pair: pair[0],
    )
    counts: Counter[str] = Counter()
    by_pane: dict[str, list[float]] = {}
    for frame in frames:
        phases = frame.get("phases") or {}
        if not phases.get("patches"):
            counts["noop"] += 1
            continue
        frame_ts = float(frame.get("ts", 0))
        nearest = min(commits, key=lambda pair: abs(pair[0] - frame_ts), default=None)
        if nearest is not None and abs(nearest[0] - frame_ts) <= 25.0:
            by_pane.setdefault(nearest[1], []).append(frame_ts)
        else:
            counts["render"] += 1
    for pane, stamps in by_pane.items():
        counts[f"{_cadence(stamps)}:{pane}"] += len(stamps)
    return counts


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seconds", type=float, default=60.0,
                        help="idle window in seconds (default 60)")
    parser.add_argument("--settle", type=float, default=2.0,
                        help="seconds to let the session settle before sampling")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="seconds to wait for the ready session")
    parser.add_argument("--cols", type=int, default=120)
    parser.add_argument("--rows", type=int, default=40)
    parser.add_argument("--tui-dir", default=str(tui_process.DEFAULT_TUI_DIR))
    parser.add_argument("--keep-home", action="store_true",
                        help="keep the temp HOME and HERMES_HOME for inspection")


def run_once(args: argparse.Namespace) -> tuple[dict[str, perf.Metric], str]:
    """Sample frames and CPU for a ready TUI with no input."""
    session = tui_session.launch(args, wait_for="session_ready", timeout=args.timeout)
    try:
        time.sleep(args.settle)
        started_ms = int(time.time() * 1000)
        tui_proc = psutil.Process(session.pid)
        gateway_pid = tui_process.read_gateway_pid(session.hermes_home)
        gateway_proc = psutil.Process(gateway_pid) if gateway_pid else None
        tui_proc.cpu_percent(interval=None)
        if gateway_proc is not None:
            gateway_proc.cpu_percent(interval=None)

        tui_cpu: list[float] = []
        backend_cpu: list[float] = []
        deadline = time.monotonic() + args.seconds
        next_sample = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            session.drain(0.05)
            if time.monotonic() < next_sample:
                continue
            try:
                tui_cpu.append(tui_proc.cpu_percent(interval=None))
            except psutil.Error:
                break
            if gateway_proc is not None:
                try:
                    backend_cpu.append(gateway_proc.cpu_percent(interval=None))
                except psutil.Error:
                    gateway_proc = None
            next_sample += 1.0
        session.drain(0.2)

        rows = session.rows()
        frames = [
            row
            for row in rows
            if row.get("src") == "frame" and float(row.get("ts", 0)) >= started_ms
        ]
        react = [
            row
            for row in rows
            if row.get("src") == "react" and float(row.get("ts", 0)) >= started_ms
        ]
        classes = classify_frames(frames, react)

        metrics: dict[str, perf.Metric] = {
            "idle.frames": perf.Metric(
                name="idle.frames", unit="count", samples=(float(len(frames)),),
                note="frames rendered in the idle window",
            )
        }
        clock_frames = sum(count for name, count in classes.items() if name.startswith("clock:"))
        metrics["idle.clock_frames"] = perf.Metric(
            name="idle.clock_frames", unit="count", samples=(float(clock_frames),),
            note="frames driven by a ~1s clock",
        )
        metrics["idle.active_frames"] = perf.Metric(
            name="idle.active_frames", unit="count",
            samples=(float(len(frames) - clock_frames),),
            note="idle frames not driven by the clock",
        )
        if tui_cpu:
            metrics["idle.cpu_pct"] = perf.Metric(
                name="idle.cpu_pct", unit="%", samples=tuple(tui_cpu),
                note="TUI process CPU",
            )
        if backend_cpu:
            metrics["idle.backend_cpu_pct"] = perf.Metric(
                name="idle.backend_cpu_pct", unit="%", samples=tuple(backend_cpu),
                note="gateway process CPU",
            )

        lines = [
            f"idle window: {args.seconds:.0f}s after {args.settle:.0f}s settle",
            f"frames: {len(frames)} ({clock_frames} clock-driven)",
        ]
        for name, count in classes.most_common():
            lines.append(f"  {name}: {count}")
        if tui_cpu:
            lines.append(f"TUI CPU: max {max(tui_cpu):.2f}%")
        if backend_cpu:
            lines.append(f"gateway CPU: max {max(backend_cpu):.2f}%")
        lines.append(f"perf log: {session.log}")
        if args.keep_home:
            lines.append(f"home kept: {session.home}")
        return metrics, "\n".join(lines)
    finally:
        session.close()
