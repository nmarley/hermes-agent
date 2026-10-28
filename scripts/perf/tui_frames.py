"""Drive the Hermes TUI under HERMES_DEV_PERF and summarize the frame pipeline.

Invoked through the perf harness so every suite shares one report shape:

    scripts/run-in-hermes-env python3 scripts/perf/run.py tui-frames --runs 3

Defaults: picks the session with the most messages, holds PageUp for 8s at
~30 Hz (matching xterm key-repeat), and summarizes the perf log on exit.

The TUI build must exist. Pass --build to run.py, or run `npm run build` in
ui-tui first. This module launches `node dist/entry.js` directly with
HERMES_TUI_RESUME set so it bypasses the hermes_cli wrapper. Repeatable timing
matters more than the CLI's session-picker flow.

Environment overrides:
  HERMES_PERF_LOG     (default ~/.hermes/perf.log)
  HERMES_PERF_NODE    (default node from $PATH)
  HERMES_TUI_DIR      (default: <repo>/ui-tui)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.perf import metrics as perf
from scripts.perf import tui_process
try:
    from hermes_constants import get_hermes_home
except ImportError:
    def get_hermes_home() -> Path:  # type: ignore[misc]
        val = (os.environ.get("HERMES_HOME") or "").strip()
        return Path(val) if val else Path.home() / ".hermes"

DEFAULT_LOG = Path(os.environ.get("HERMES_PERF_LOG", str(get_hermes_home() / "perf.log")))
DEFAULT_STATE_DB = get_hermes_home() / "state.db"

# Keystroke escape sequences.  Matches what xterm/VT220 send when the
# terminal has bracketed-paste disabled and the key-repeat handler fires.
KEYS = {
    "page_up": b"\x1b[5~",
    "page_down": b"\x1b[6~",
    "wheel_up": b"\x1b[M`!!",      # mouse wheel up (SGR-less) - best-effort
    "shift_up": b"\x1b[1;2A",
    "shift_down": b"\x1b[1;2B",
}


def pick_longest_session(db: Path) -> str:
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT id FROM sessions s ORDER BY "
        "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) DESC LIMIT 1"
    ).fetchone()
    if not row:
        sys.exit(f"no sessions in {db}")
    return row[0]


def hold_key(fd: int, seq: bytes, seconds: float, rate_hz: int) -> int:
    """Write `seq` to fd at ~rate_hz for `seconds`. Returns keystrokes sent."""
    interval = 1.0 / max(1, rate_hz)
    end = time.monotonic() + seconds
    sent = 0
    while time.monotonic() < end:
        try:
            os.write(fd, seq)
            sent += 1
        except OSError:
            break
        # Drain stdout to keep the PTY buffer flowing; ignore content.
        tui_process.drain(fd, 0)
        time.sleep(interval)
    return sent


def summarize(log: Path, since_ts_ms: int) -> dict[str, Any]:
    """Parse perf.log, keep only events newer than since_ts_ms, return stats."""
    react_events: list[dict[str, Any]] = []
    frame_events: list[dict[str, Any]] = []
    if not log.exists():
        return {"error": f"no log at {log}", "react": [], "frame": []}
    for line in log.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(row.get("ts", 0)) < since_ts_ms:
            continue
        src = row.get("src")
        if src == "react":
            react_events.append(row)
        elif src == "frame":
            frame_events.append(row)

    return {
        "react": react_events,
        "frame": frame_events,
    }


pct = perf.percentile


def format_report(data: dict[str, Any]) -> str:
    react = data.get("react") or []
    frames = data.get("frame") or []
    out = []

    out.append("═══ React Profiler ═══")
    if not react:
        out.append("  (no react events - HERMES_DEV_PERF wired? threshold too high?)")
    else:
        by_id: dict[str, list[float]] = {}
        for r in react:
            by_id.setdefault(r["id"], []).append(r["actualMs"])
        out.append(f"  {'pane':<14} {'count':>6} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}")
        for pid, ms in sorted(by_id.items(), key=lambda kv: -pct(kv[1], 0.99)):
            out.append(
                f"  {pid:<14} {len(ms):>6} {pct(ms,0.50):>8.2f} {pct(ms,0.95):>8.2f} "
                f"{pct(ms,0.99):>8.2f} {max(ms):>8.2f}"
            )

    out.append("")
    out.append("═══ Ink pipeline ═══")
    if not frames:
        out.append("  (no frame events - onFrame wiring broken?)")
    else:
        dur = [f["durationMs"] for f in frames]
        phases_present = any(f.get("phases") for f in frames)
        out.append(f"  frames captured: {len(frames)}")
        out.append(
            f"  durationMs  p50={pct(dur,0.50):.2f}  p95={pct(dur,0.95):.2f}  "
            f"p99={pct(dur,0.99):.2f}  max={max(dur):.2f}"
        )
        # Effective FPS during the run: frames / elapsed seconds.
        ts = sorted(f["ts"] for f in frames)
        if len(ts) >= 2:
            elapsed_s = (ts[-1] - ts[0]) / 1000.0
            fps = len(frames) / elapsed_s if elapsed_s > 0 else float("inf")
            out.append(f"  throughput: {len(frames)} frames / {elapsed_s:.2f}s = {fps:.1f} fps")

        if phases_present:
            fields = ["yoga", "renderer", "diff", "optimize", "write", "commit"]
            out.append("")
            out.append(f"  {'phase':<10} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}   (ms)")
            for field in fields:
                vals = [f["phases"][field] for f in frames if f.get("phases")]
                if vals:
                    out.append(
                        f"  {field:<10} {pct(vals,0.50):>8.2f} {pct(vals,0.95):>8.2f} "
                        f"{pct(vals,0.99):>8.2f} {max(vals):>8.2f}"
                    )
            # Derived: sum of phases vs durationMs (reveals hidden time).
            sum_ps = [
                sum(f["phases"][k] for k in fields)
                for f in frames if f.get("phases")
            ]
            if sum_ps:
                dur_match = [f["durationMs"] for f in frames if f.get("phases")]
                deltas = [d - s for d, s in zip(dur_match, sum_ps)]
                out.append(
                    f"  {'dur-Σphases':<10} {pct(deltas,0.50):>8.2f} {pct(deltas,0.95):>8.2f} "
                    f"{pct(deltas,0.99):>8.2f} {max(deltas):>8.2f}   (unaccounted-for time)"
                )

            # Yoga counters
            visited = [f["phases"]["yogaVisited"] for f in frames if f.get("phases")]
            measured = [f["phases"]["yogaMeasured"] for f in frames if f.get("phases")]
            cache_hits = [f["phases"]["yogaCacheHits"] for f in frames if f.get("phases")]
            live = [f["phases"]["yogaLive"] for f in frames if f.get("phases")]
            out.append("")
            out.append("  Yoga counters (per frame):")
            for name, vals in (
                ("visited", visited),
                ("measured", measured),
                ("cacheHits", cache_hits),
                ("live", live),
            ):
                if vals:
                    out.append(f"    {name:<11} p50={pct(vals,0.5):.0f}  p99={pct(vals,0.99):.0f}  max={max(vals)}")

            # Patch counts - proxy for "how much changed each frame"
            patches = [f["phases"]["patches"] for f in frames if f.get("phases")]
            if patches:
                out.append(
                    f"  patches     p50={pct(patches,0.5):.0f}  p99={pct(patches,0.99):.0f}  "
                    f"max={max(patches)}  total={sum(patches)}"
                )
            optimized = [
                f["phases"].get("optimizedPatches", 0)
                for f in frames if f.get("phases")
            ]
            if any(optimized):
                out.append(
                    f"  optimized   p50={pct(optimized,0.5):.0f}  p99={pct(optimized,0.99):.0f}  "
                    f"max={max(optimized)}  total={sum(optimized)}"
                    f"  (ratio: {sum(optimized)/max(1,sum(patches)):.2f})"
                )

            # Write bytes + drain telemetry - the outer-terminal bottleneck gauge.
            bytes_written = [
                f["phases"].get("writeBytes", 0)
                for f in frames if f.get("phases")
            ]
            if any(bytes_written):
                total_b = sum(bytes_written)
                kb = total_b / 1024
                out.append(
                    f"  writeBytes  p50={pct(bytes_written,0.5):.0f}B  p99={pct(bytes_written,0.99):.0f}B  "
                    f"max={max(bytes_written)}B  total={kb:.1f}KB"
                )
            drains = [
                f["phases"].get("prevFrameDrainMs", 0)
                for f in frames if f.get("phases")
            ]
            if any(d > 0 for d in drains):
                nonzero = [d for d in drains if d > 0]
                out.append(
                    f"  drainMs     p50={pct(nonzero,0.5):.2f}  p95={pct(nonzero,0.95):.2f}  "
                    f"p99={pct(nonzero,0.99):.2f}  max={max(nonzero):.2f}   (terminal flush latency)"
                )
            backpressure = sum(1 for f in frames if f.get("phases", {}).get("backpressure"))
            if backpressure:
                out.append(
                    f"  backpressure: {backpressure}/{len(frames)} frames "
                    f"({100*backpressure/len(frames):.0f}%)   (Node stdout buffer full - terminal slow)"
                )

        # Flickers
        flicker_frames = [f for f in frames if f.get("flickers")]
        if flicker_frames:
            out.append("")
            out.append(f"  ⚠ flickers detected in {len(flicker_frames)} frames")
            reasons: dict[str, int] = {}
            for f in flicker_frames:
                for fl in f["flickers"]:
                    reasons[fl["reason"]] = reasons.get(fl["reason"], 0) + 1
            for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
                out.append(f"    {reason}: {n}")

    return "\n".join(out)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "unknown"


def metrics_from_data(data: dict[str, Any]) -> dict[str, perf.Metric]:
    """Turn raw perf-log rows into the shared metric shape."""
    frames = data.get("frame") or []
    react = data.get("react") or []
    if not frames and not react:
        return {}
    out: dict[str, perf.Metric] = {}

    def add(name: str, values: list[float], unit: str, *, direction: str = "lower",
            comparison: str = "p95", note: str = "") -> None:
        out[name] = perf.Metric(
            name=name,
            unit=unit,
            samples=tuple(float(value) for value in values),
            direction=direction,
            comparison=comparison,
            note=note,
        )

    def phases(key: str) -> list[float]:
        return [
            float(frame["phases"][key])
            for frame in frames
            if frame.get("phases") and key in frame["phases"]
        ]

    add("tui.frame.duration_ms", [float(f["durationMs"]) for f in frames if "durationMs" in f],
        "ms", note="full frame, renderer through terminal write")
    for key, name in (
        ("renderer", "tui.frame.renderer_ms"),
        ("yoga", "tui.frame.yoga_ms"),
        ("diff", "tui.frame.diff_ms"),
        ("optimize", "tui.frame.optimize_ms"),
        ("write", "tui.frame.write_ms"),
        ("commit", "tui.frame.commit_ms"),
    ):
        add(name, phases(key), "ms")
    add("tui.frame.patches", phases("patches"), "count")
    add("tui.frame.optimized_patches", phases("optimizedPatches"), "count")
    add("tui.frame.write_bytes", phases("writeBytes"), "bytes")
    add("tui.frame.drain_ms", phases("prevFrameDrainMs"), "ms", note="previous frame's terminal flush")
    add("tui.yoga.visited", phases("yogaVisited"), "count")
    add("tui.yoga.measured", phases("yogaMeasured"), "count")
    add("tui.yoga.cache_hits", phases("yogaCacheHits"), "count")
    add("tui.yoga.live", phases("yogaLive"), "count", comparison="max",
        note="live Yoga nodes; growth is a leak")

    stamps = sorted(float(frame["ts"]) for frame in frames if "ts" in frame)
    if len(stamps) >= 2:
        gaps = [stamps[i] - stamps[i - 1] for i in range(1, len(stamps))]
        add("tui.frame.gap_ms", gaps, "ms", note="idle gap between frames")
        elapsed_s = (stamps[-1] - stamps[0]) / 1000.0
        add("tui.fps", [len(stamps) / elapsed_s if elapsed_s > 0 else 0.0], "fps",
            direction="higher", comparison="p50")

    add("tui.frames", [float(len(frames))], "count", note="frames in the sample window")
    add("tui.flickers", [float(sum(1 for frame in frames if frame.get("flickers")))], "count")
    add(
        "tui.backpressure_frames",
        [float(sum(1 for frame in frames if frame.get("phases", {}).get("backpressure")))],
        "count",
    )

    by_pane: dict[str, list[float]] = {}
    for row in react:
        by_pane.setdefault(_slug(str(row.get("id", "unknown"))), []).append(
            float(row.get("actualMs", 0.0))
        )
    for pane, values in by_pane.items():
        add(f"tui.react.{pane}_ms", values, "ms", note="React commit")

    return out


def run_once(args: argparse.Namespace) -> tuple[dict[str, perf.Metric], str]:
    """Run one scripted TUI session and return metrics plus the detailed report."""
    tui_dir = Path(args.tui_dir).resolve()

    sid = args.session or pick_longest_session(DEFAULT_STATE_DB)
    print(f"session: {sid}", file=sys.stderr)
    print(
        f"hold: {args.hold} x {args.rate}Hz for {args.seconds}s "
        f"after {args.warmup}s warmup",
        file=sys.stderr,
    )
    print(f"terminal: {args.cols}x{args.rows}", file=sys.stderr)

    log = Path(args.log)
    if not args.keep_log and log.exists():
        log.unlink()

    since_ms = int(time.time() * 1000)

    env = os.environ.copy()
    env["HERMES_DEV_PERF"] = "1"
    env["HERMES_DEV_PERF_MS"] = str(args.threshold_ms)
    env["HERMES_DEV_PERF_LOG"] = str(log)
    env["HERMES_TUI_RESUME"] = sid
    env["COLUMNS"] = str(args.cols)
    env["LINES"] = str(args.rows)
    env["TERM"] = env.get("TERM", "xterm-256color")

    pid, fd = tui_process.spawn(
        tui_dir,
        env,
        cols=args.cols,
        rows=args.rows,
        extra_flags=tuple(getattr(args, "extra_flags", [])),
    )

    try:
        print(f"pid: {pid}  fd: {fd}", file=sys.stderr)
        print(f"warmup {args.warmup}s (drain startup output)", file=sys.stderr)
        tui_process.drain(fd, args.warmup)

        print(f"holding {args.hold}", file=sys.stderr)
        sent = hold_key(fd, KEYS[args.hold], args.seconds, args.rate)
        print(f"sent {sent} keystrokes", file=sys.stderr)

        tui_process.drain(fd, 0.5)
    finally:
        tui_process.stop(pid, fd)

    time.sleep(0.2)
    data = summarize(log, since_ms)
    return metrics_from_data(data), format_report(data)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session", help="session id to resume (default: longest in db)")
    parser.add_argument("--hold", default="page_up", choices=sorted(KEYS), help="key to hold")
    parser.add_argument("--seconds", type=float, default=8.0, help="how long to hold the key")
    parser.add_argument("--rate", type=int, default=30, help="keystrokes per second")
    parser.add_argument("--warmup", type=float, default=3.0,
                        help="seconds to wait after launch before input")
    parser.add_argument("--threshold-ms", type=float, default=0.0,
                        help="HERMES_DEV_PERF_MS (0 captures every frame)")
    parser.add_argument("--cols", type=int, default=120)
    parser.add_argument("--rows", type=int, default=40)
    parser.add_argument("--keep-log", action="store_true", help="keep the previous perf log")
    parser.add_argument("--tui-dir", default=str(tui_process.DEFAULT_TUI_DIR))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--loop", action="store_true",
                        help="watch sources, rebuild, rerun, and diff against the previous run")
    parser.add_argument("--extra-flag", dest="extra_flags", action="append", default=[],
                        help="pass through to node dist/entry.js (repeatable)")


def loop(args: argparse.Namespace) -> int:
    """Watch sources, rebuild, rerun, and diff against the previous run."""
    tui_dir = Path(args.tui_dir).resolve()
    src_root = tui_dir / "src"
    pkg_root = tui_dir / "packages" / "hermes-ink" / "src"

    def collect_mtimes() -> dict[str, float]:
        mtimes: dict[str, float] = {}
        for root in (src_root, pkg_root):
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.suffix in {".ts", ".tsx"} and "__tests__" not in str(path):
                    try:
                        mtimes[str(path)] = path.stat().st_mtime
                    except OSError:
                        pass
        return mtimes

    previous: perf.Report | None = None
    previous_mtimes = collect_mtimes()
    iteration = 0

    print(f"loop mode: watching {src_root} + {pkg_root} for *.ts(x) changes", file=sys.stderr)
    print("edit any TS file, the harness rebuilds and reruns automatically", file=sys.stderr)
    print("Ctrl+C to stop\n", file=sys.stderr)

    try:
        while True:
            iteration += 1
            print(f"\niteration {iteration} at {time.strftime('%H:%M:%S')}", file=sys.stderr)
            if iteration > 1:
                print("rebuilding...", file=sys.stderr)
                if not tui_process.build(tui_dir):
                    print("waiting for source changes to retry...", file=sys.stderr)
                    previous_mtimes = wait_for_change(previous_mtimes, collect_mtimes)
                    continue
                print("build ok", file=sys.stderr)

            started = time.monotonic()
            metrics, detail = run_once(args)
            report = perf.Report(
                suite="tui-frames",
                metrics=metrics,
                runs=1,
                duration_s=time.monotonic() - started,
            )
            print(detail, file=sys.stderr)
            if previous is not None:
                print(perf.format_diff(previous, report), file=sys.stderr)
            previous = report
            print("\nwaiting for source changes...", file=sys.stderr)
            previous_mtimes = wait_for_change(previous_mtimes, collect_mtimes)
    except KeyboardInterrupt:
        print("\nloop stopped", file=sys.stderr)
        return 0


def wait_for_change(prev: dict[str, float], collect) -> dict[str, float]:
    """Poll every 1s until a watched file's mtime changes. Debounced 500ms."""
    while True:
        time.sleep(1)
        current = collect()

        changed = [
            path for path, mtime in current.items() if prev.get(path) != mtime
        ]

        if changed:
            print(f"  ↻ {len(changed)} file(s) changed:")
            for path in changed[:5]:
                print(f"    {path}")
            # Debounce - editor save bursts can take ~500ms to settle
            time.sleep(0.5)
            return collect()
