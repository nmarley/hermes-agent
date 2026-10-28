#!/usr/bin/env python3
"""Performance harness entry point.

Run a suite and emit one report shape:

    scripts/run-in-hermes-env python3 scripts/perf/run.py tui-frames --runs 3
    scripts/run-in-hermes-env python3 scripts/perf/run.py tui-frames --json --save report.json

Budgets live in scripts/perf/baseline.json and are checked separately:

    scripts/run-in-hermes-env python3 scripts/perf/budget.py --check report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.perf import idle
from scripts.perf import input as keyboard
from scripts.perf import metrics as perf
from scripts.perf import startup, tui_frames, tui_process


@dataclass(frozen=True)
class Suite:
    name: str
    description: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run_once: Callable[[argparse.Namespace], tuple[dict[str, perf.Metric], str | None]]
    needs_tui: bool = False


SUITES: dict[str, Suite] = {
    "cli-import": Suite(
        name="cli-import",
        description="cold interpreter import cost for the classic CLI",
        add_arguments=startup.add_import_arguments,
        run_once=startup.run_import_once,
    ),
    "idle": Suite(
        name="idle",
        description="frames and CPU while a ready TUI sits idle",
        add_arguments=idle.add_arguments,
        run_once=idle.run_once,
        needs_tui=True,
    ),
    "input": Suite(
        name="input",
        description="keyboard echo and first picker-open latency",
        add_arguments=keyboard.add_arguments,
        run_once=keyboard.run_once,
        needs_tui=True,
    ),
    "startup": Suite(
        name="startup",
        description="cold start to first frame, gateway ready, and session ready",
        add_arguments=startup.add_arguments,
        run_once=startup.run_once,
        needs_tui=True,
    ),
    "tui-frames": Suite(
        name="tui-frames",
        description="frame and React timings from a scripted TUI scroll run",
        add_arguments=tui_frames.add_arguments,
        run_once=tui_frames.run_once,
        needs_tui=True,
    ),
}


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--runs", type=int, default=1, help="repeat the suite N times (default 1)")
    common.add_argument("--json", action="store_true", help="write the report as JSON to stdout")
    common.add_argument("--save", metavar="PATH", help="write the JSON report to PATH")
    common.add_argument("--compare", metavar="PATH", help="diff against a previous JSON report")
    common.add_argument("--build", action="store_true", help="build the TUI before running")

    parser = argparse.ArgumentParser(
        prog="perf",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="suite", required=True)
    for suite in SUITES.values():
        subparser = subparsers.add_parser(
            suite.name,
            parents=[common],
            help=suite.description,
            description=suite.description,
        )
        suite.add_arguments(subparser)
    return parser


def _read_report(path: Path) -> perf.Report:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SystemExit(f"report not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"report is not valid JSON: {path}: {exc}") from None
    if not isinstance(raw, Mapping):
        raise SystemExit(f"report must be a JSON object: {path}")
    return perf.Report.from_dict(raw)


def _write_report(path: Path, report: perf.Report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(perf.render_json(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    suite = SUITES[args.suite]
    if args.build and not suite.needs_tui:
        parser.error(f"--build is only meaningful for suites that need the TUI ({args.suite} does not)")

    if suite.needs_tui:
        tui_process.ensure_built(Path(args.tui_dir), build_first=args.build)
    if getattr(args, "loop", False):
        return tui_frames.loop(args)

    started = time.monotonic()
    metric_sets: list[dict[str, perf.Metric]] = []
    detail: str | None = None
    for index in range(args.runs):
        if args.runs > 1:
            print(f"run {index + 1}/{args.runs}", file=sys.stderr)
        metrics, detail = suite.run_once(args)
        metric_sets.append(metrics)

    report = perf.Report(
        suite=args.suite,
        metrics=perf.merge_metrics(metric_sets),
        runs=args.runs,
        duration_s=time.monotonic() - started,
        meta={"tui_dir": str(Path(args.tui_dir).resolve())} if suite.needs_tui else {},
    )

    if detail and not args.json:
        print(detail, file=sys.stderr)

    if args.save:
        _write_report(Path(args.save), report)
        print(f"saved: {args.save}", file=sys.stderr)

    if args.compare:
        previous = _read_report(Path(args.compare))
        print(perf.format_diff(previous, report), file=sys.stderr if args.json else sys.stdout)

    if args.json:
        print(perf.render_json(report), end="")
    else:
        print(perf.format_table(report))

    return 2 if not report.metrics else 0


if __name__ == "__main__":
    raise SystemExit(main())
