"""Compare a perf report with the checked-in baseline.

The baseline owns budgets, gates, and current values; suites only report raw
samples. Run directly for a one-off check:

    python -m scripts.perf.budget --check report.json
    python -m scripts.perf.budget --update report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.perf.metrics import Report, format_table

DEFAULT_BASELINE = Path(__file__).with_name("baseline.json")


@dataclass(frozen=True)
class Finding:
    metric: str
    severity: str
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "metric": self.metric,
            "severity": self.severity,
            "kind": self.kind,
            "message": self.message,
        }


def load_baseline(path: Path = DEFAULT_BASELINE) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SystemExit(f"baseline not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"baseline is not valid JSON: {path}: {exc}") from None
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise SystemExit(f"baseline has an unsupported schema: {path}")
    return data


def _entries(baseline: Mapping[str, Any], suite: str) -> Mapping[str, Any]:
    suites = baseline.get("suites")
    if not isinstance(suites, Mapping):
        return {}
    entries = suites.get(suite)
    return entries if isinstance(entries, Mapping) else {}


def _apply_policy(metric, entry: Mapping[str, Any]):
    return replace(
        metric,
        unit=str(entry.get("unit", metric.unit)),
        direction=str(entry.get("direction", metric.direction)),
        gate=str(entry.get("gate", metric.gate)),
        budget=entry.get("budget", metric.budget),
        comparison=str(entry.get("comparison", metric.comparison)),
    )


def _budget_finding(metric) -> Finding | None:
    budget = metric.budget
    if budget is None or metric.gate == "info" or metric.count == 0:
        return None
    current = metric.value()
    passed = current <= budget if metric.direction == "lower" else current >= budget
    if passed:
        return None
    relation = "exceeds" if metric.direction == "lower" else "is below"
    severity = "fail" if metric.gate == "blocking" else "warn"
    return Finding(
        metric.name,
        severity,
        "budget",
        f"{current:.2f} {metric.unit} {relation} budget {budget:.2f}",
    )


def _regression_finding(
    metric, entry: Mapping[str, Any], tolerance_pct: float
) -> Finding | None:
    baseline_value = entry.get("current")
    if not isinstance(baseline_value, (int, float)) or isinstance(baseline_value, bool):
        return None
    if metric.gate == "info" or metric.count == 0 or baseline_value == 0:
        return None
    allowed = (
        baseline_value * (1 + tolerance_pct / 100)
        if metric.direction == "lower"
        else baseline_value * (1 - tolerance_pct / 100)
    )
    current = metric.value()
    regressed = current > allowed if metric.direction == "lower" else current < allowed
    if not regressed:
        return None
    change = (current / baseline_value - 1) * 100
    severity = "fail" if metric.gate == "blocking" else "warn"
    return Finding(
        metric.name,
        severity,
        "regression",
        f"{current:.2f} {metric.unit} is {change:+.1f}% vs baseline "
        f"{baseline_value:.2f} (tolerance {tolerance_pct:.1f}%)",
    )


def evaluate(
    report: Report,
    baseline: Mapping[str, Any],
    *,
    tolerance_pct: float | None = None,
) -> tuple[Report, list[Finding]]:
    """Apply the baseline policy to a report and return findings."""
    entries = _entries(baseline, report.suite)
    tolerance = float(
        baseline.get("tolerance_pct", 10.0) if tolerance_pct is None else tolerance_pct
    )
    metrics = dict(report.metrics)
    findings: list[Finding] = []
    for name, entry in entries.items():
        if not isinstance(entry, Mapping):
            continue
        metric = metrics.get(name)
        if metric is None:
            severity = "fail" if entry.get("gate") == "blocking" else "warn"
            findings.append(
                Finding(name, severity, "missing", "the suite did not report this metric")
            )
            continue
        metric = _apply_policy(metric, entry)
        metrics[name] = metric
        for finding in (
            _budget_finding(metric),
            _regression_finding(metric, entry, tolerance),
        ):
            if finding is not None:
                findings.append(finding)
    return replace(report, metrics=metrics), findings


def update_baseline(report: Report, baseline: Mapping[str, Any]) -> dict[str, Any]:
    """Write the report's current values into the baseline, preserving policy."""
    data = json.loads(json.dumps(baseline))
    suites = data.setdefault("suites", {})
    if not isinstance(suites, dict):
        raise SystemExit("baseline 'suites' must be an object")
    entries = suites.setdefault(report.suite, {})
    if not isinstance(entries, dict):
        raise SystemExit(f"baseline suite {report.suite!r} must be an object")
    for name, metric in sorted(report.metrics.items()):
        if metric.count == 0:
            continue
        entry = entries.setdefault(name, {})
        entry["unit"] = metric.unit
        entry["direction"] = metric.direction
        entry["comparison"] = metric.comparison
        entry["current"] = round(metric.value(), 4)
        entry.setdefault("gate", "info")
        entry.setdefault("budget", None)
    data["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return data


def write_baseline(data: Mapping[str, Any], path: Path = DEFAULT_BASELINE) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_report(path: Path) -> Report:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SystemExit(f"report not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"report is not valid JSON: {path}: {exc}") from None
    if not isinstance(raw, dict):
        raise SystemExit(f"report must be a JSON object: {path}")
    return Report.from_dict(raw)


def _print_findings(report: Report, findings: list[Finding]) -> None:
    if not findings:
        print(f"perf budget: {report.suite}: all checks passed")
        return
    print(f"perf budget: {report.suite}")
    for finding in findings:
        print(f"{finding.severity.upper():<5} {finding.kind:<10} {finding.metric}: {finding.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", metavar="REPORT", help="check one report JSON")
    action.add_argument("--update", metavar="REPORT", help="write current values into the baseline")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="baseline path")
    parser.add_argument("--tolerance", type=float, default=None, help="regression tolerance percent")
    parser.add_argument("--json", action="store_true", help="emit machine-readable findings")
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline)
    baseline = load_baseline(baseline_path)

    if args.update:
        report = _load_report(Path(args.update))
        updated = update_baseline(report, baseline)
        write_baseline(updated, baseline_path)
        print(f"updated {baseline_path} from {args.update} ({len(report.metrics)} metrics)")
        return 0

    report = _load_report(Path(args.check))
    evaluated, findings = evaluate(report, baseline, tolerance_pct=args.tolerance)
    failed = any(finding.severity == "fail" for finding in findings)
    if args.json:
        payload = {
            "suite": evaluated.suite,
            "findings": [finding.to_dict() for finding in findings],
            "report": evaluated.to_dict(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_findings(evaluated, findings)
        print()
        print(format_table(evaluated))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
