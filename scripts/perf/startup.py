"""Cold-start latency for the Ink TUI.

Launches the built TUI in a fresh PTY with an isolated HOME and HERMES_HOME,
waits for the startup trace, and reports the phases from the shared perf log.
Invoked through the perf harness:

    scripts/run-in-hermes-env python3 scripts/perf/run.py startup --runs 5 --build
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.perf import metrics as perf
from scripts.perf import tui_process

PHASES = {
    "module_eval": ("startup.module_eval_ms", "Node boot to the first TUI module"),
    "gateway_spawn": ("startup.gateway_spawn_ms", "Node boot to gateway bootstrap"),
    "first_frame": ("startup.first_paint_ms", "Node boot to the first Ink frame"),
    "gateway_ready": ("startup.gateway_ready_ms", "Node boot to gateway ready"),
    "session_ready": ("startup.session_ready_ms", "Node boot to the first ready session"),
}

_IMPORT_TIME = re.compile(r"^import time:\s+(\d+)\s+\|\s+(\d+)\s+\|", re.MULTILINE)


def parse_importtime(stderr: str) -> list[int]:
    """Per-module self times (microseconds) from ``python -X importtime``."""
    return [int(match.group(1)) for match in _IMPORT_TIME.finditer(stderr)]


def _install_state() -> Path | None:
    from hermes_constants import get_default_hermes_root
    from pm.environments import install_key, owning_home_root

    owner = owning_home_root(_PROJECT_ROOT) or get_default_hermes_root()
    state = owner / "installs" / install_key(_PROJECT_ROOT)
    return state if state.is_dir() else None


def _committed_python() -> Path | None:
    state = _install_state()
    if state is None:
        return None
    try:
        facts = json.loads((state / "facts.json").read_text(encoding="utf-8-sig"))
        venv = Path(facts["packages"]["venv"]["environment"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return python if python.exists() else None


def _link_install_state(hermes_home: Path) -> None:
    """Point the isolated home at this checkout's committed dependency generation.

    The TUI's gateway bootstrap activates PM's committed environment before it
    imports Hermes. A temp HERMES_HOME has no install state, so link the real
    state in; the app's config and sessions still live in the temp home.
    """
    state = _install_state()
    if state is None:
        print(
            f"warning: no committed dependency state for {_PROJECT_ROOT}; "
            "the gateway bootstrap may fail",
            file=sys.stderr,
        )
        return
    installs = hermes_home / "installs"
    installs.mkdir(parents=True, exist_ok=True)
    link = installs / state.name
    if not link.exists():
        link.symlink_to(state, target_is_directory=True)


def _clean_env(home: Path, log: Path) -> dict[str, str]:
    """A hermetic child environment: no inherited Hermes or credential state."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("HERMES_")
        and not key.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIALS"))
        and key not in {"NODE_OPTIONS", "NODE_PATH", "PYTHONHOME"}
    }
    env.update(
        {
            "HOME": str(home),
            "HERMES_HOME": str(home / ".hermes"),
            "HERMES_DEV_PERF": "1",
            "HERMES_DEV_PERF_LOG": str(log),
            "HERMES_DEV_PERF_MS": "0",
            "HERMES_PYTHON": sys.executable,
            "HERMES_PYTHON_SRC_ROOT": str(_PROJECT_ROOT),
            "PYTHONPATH": str(_PROJECT_ROOT),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "TERM": env.get("TERM", "xterm-256color"),
        }
    )
    return env


def _startup_rows(path: Path, since_ms: int) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in tui_process.read_jsonl(path, since_ms=since_ms):
        if row.get("src") != "startup":
            continue
        phase = row.get("phase")
        if isinstance(phase, str) and phase not in rows:
            rows[phase] = row
    return rows


def metrics_from_rows(rows: dict[str, dict[str, Any]]) -> dict[str, perf.Metric]:
    metrics: dict[str, perf.Metric] = {}
    for phase, (name, note) in PHASES.items():
        row = rows.get(phase)
        uptime = row.get("uptimeMs") if row else None
        if isinstance(uptime, (int, float)) and not isinstance(uptime, bool):
            metrics[name] = perf.Metric(
                name=name, unit="ms", samples=(float(uptime),), note=note
            )
    return metrics


def cli_import_metrics(timeout: float = 120.0) -> dict[str, perf.Metric]:
    """Cold interpreter import cost for the classic CLI entry point."""
    python = _committed_python()
    if python is None:
        print(
            "cli import probe: no committed dependency environment; run `hermes pm repair`",
            file=sys.stderr,
        )
        return {}
    with tempfile.TemporaryDirectory(prefix="hermes-perf-import-") as tmp:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("HERMES_") and key not in {"PYTHONHOME", "PYTHONPATH"}
        }
        env["HERMES_HOME"] = tmp
        env["PYTHONPATH"] = str(_PROJECT_ROOT)
        started = time.monotonic()
        try:
            result = subprocess.run(
                [str(python), "-X", "importtime", "-c", "import hermes_cli.main"],
                cwd=_PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print(f"CLI import probe timed out after {timeout:.0f}s", file=sys.stderr)
            return {}
        elapsed_ms = (time.monotonic() - started) * 1000
        if result.returncode != 0:
            print(result.stderr[-2000:], file=sys.stderr)
            return {}
        self_us = parse_importtime(result.stderr)
        metrics = {
            "startup.cli_import_ms": perf.Metric(
                name="startup.cli_import_ms",
                unit="ms",
                samples=(elapsed_ms,),
                note="interpreter start through import hermes_cli.main",
            )
        }
        if self_us:
            metrics["startup.cli_import_self_ms"] = perf.Metric(
                name="startup.cli_import_self_ms",
                unit="ms",
                samples=(sum(self_us) / 1000.0,),
                note="sum of per-module self time",
            )
            metrics["startup.cli_import_hot_modules"] = perf.Metric(
                name="startup.cli_import_hot_modules",
                unit="count",
                samples=(float(sum(1 for micros in self_us if micros >= 1000)),),
                note="modules with at least 1ms self time",
            )
        return metrics


def add_import_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="seconds to wait for the import probe")


def run_import_once(args: argparse.Namespace) -> tuple[dict[str, perf.Metric], str]:
    metrics = cli_import_metrics(timeout=args.timeout)
    if not metrics:
        return {}, "cli import probe produced no metrics"
    wall = metrics["startup.cli_import_ms"].value()
    detail = f"import hermes_cli.main: {wall:.0f}ms wall"
    self_metric = metrics.get("startup.cli_import_self_ms")
    hot_metric = metrics.get("startup.cli_import_hot_modules")
    if self_metric is not None and hot_metric is not None:
        detail += f", {self_metric.value():.0f}ms self, {hot_metric.value():.0f} hot modules"
    return metrics, detail


def _detail(
    rows: dict[str, dict[str, Any]], log: Path, home: Path, *, keep_home: bool
) -> str:
    lines = ["cold start phases (ms since Node process start):"]
    for phase, (_, label) in PHASES.items():
        row = rows.get(phase)
        value = row.get("uptimeMs") if row else None
        shown = f"{value:>8}" if isinstance(value, (int, float)) else f"{'missing':>8}"
        lines.append(f"  {phase:<14} {shown}  {label}")
    missing = [phase for phase in PHASES if phase not in rows]
    if missing:
        lines.append(f"  missing: {', '.join(missing)}")
    lines.append(f"  perf log: {log}")
    if keep_home:
        lines.append(f"  home kept: {home}")
    return "\n".join(lines)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="seconds to wait for the first session info")
    parser.add_argument("--cols", type=int, default=120)
    parser.add_argument("--rows", type=int, default=40)
    parser.add_argument("--tui-dir", default=str(tui_process.DEFAULT_TUI_DIR))
    parser.add_argument("--keep-home", action="store_true",
                        help="keep the temp HOME and HERMES_HOME for inspection")


def run_once(args: argparse.Namespace) -> tuple[dict[str, perf.Metric], str]:
    """Launch one cold TUI and return its startup phases."""
    from tests.fakes.fake_llm_provider import FakeLLMServer, write_hermes_home

    root = Path(tempfile.mkdtemp(prefix="hermes-perf-startup-"))
    home = root / "home"
    log = root / "perf.log"
    try:
        home.mkdir(parents=True, exist_ok=True)
        with FakeLLMServer() as server:
            write_hermes_home(home / ".hermes", server.base_url)
            _link_install_state(home / ".hermes")
            env = _clean_env(home, log)
            since_ms = int(time.time() * 1000)
            pid, fd = tui_process.spawn(
                Path(args.tui_dir), env, cols=args.cols, rows=args.rows
            )
            rows: dict[str, dict[str, Any]] = {}
            try:
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    tui_process.drain(fd, 0.02)
                    rows = _startup_rows(log, since_ms)
                    if "session_ready" in rows:
                        break
                if not rows:
                    time.sleep(0.2)
                    rows = _startup_rows(log, since_ms)
            finally:
                tui_process.stop(pid, fd)
                tui_process.stop_gateway(home / ".hermes")
        return metrics_from_rows(rows), _detail(
            rows, log, home, keep_home=args.keep_home
        )
    finally:
        if not args.keep_home:
            shutil.rmtree(root, ignore_errors=True)
