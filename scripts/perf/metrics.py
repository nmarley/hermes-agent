"""Metric primitives, report rendering, and JSON serialization for scripts/perf.

A suite returns Metric objects holding raw samples. The report layer computes
the distribution once, so every suite, budget check, and A/B diff speaks the
same shape. No I/O beyond JSON text, which keeps the harness easy to test.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
_STAT_KEYS = ("count", "min", "p50", "p95", "p99", "max", "mean", "value")
_COMPARISONS = frozenset({"p50", "p95", "p99", "max"})
_DIRECTIONS = frozenset({"lower", "higher"})
_GATES = frozenset({"blocking", "warn", "info"})


def percentile(samples: Iterable[float], p: float) -> float:
    """Nearest-rank percentile, matching the profile-tui report's convention."""
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    if not 0.0 < p <= 1.0:
        raise ValueError(f"percentile must be in (0, 1], got {p!r}")
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 4)


def _finite(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class Metric:
    """One measured quantity, either as raw samples or as a loaded aggregate.

    ``stats`` carries the aggregate when a report is read back from JSON. Live
    suites populate ``samples`` instead, and every statistic is computed once.
    """

    name: str
    unit: str
    samples: tuple[float, ...] = ()
    direction: str = "lower"
    gate: str = "info"
    budget: float | None = None
    comparison: str = "p95"
    note: str = ""
    stats: Mapping[str, float] | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.direction not in _DIRECTIONS:
            raise ValueError(f"direction must be one of {sorted(_DIRECTIONS)}, got {self.direction!r}")
        if self.gate not in _GATES:
            raise ValueError(f"gate must be one of {sorted(_GATES)}, got {self.gate!r}")
        if self.comparison not in _COMPARISONS:
            raise ValueError(f"comparison must be one of {sorted(_COMPARISONS)}, got {self.comparison!r}")
        if self.budget is not None:
            _finite(self.budget, label=f"{self.name} budget")
        for sample in self.samples:
            _finite(sample, label=f"{self.name} sample")
        if self.stats is not None:
            for key, value in self.stats.items():
                _finite(value, label=f"{self.name} stat {key!r}")

    @property
    def count(self) -> int:
        if self.stats is not None:
            return int(self.stats.get("count", 0))
        return len(self.samples)

    @property
    def minimum(self) -> float:
        if self.stats is not None:
            return float(self.stats.get("min", 0.0))
        return min(self.samples) if self.samples else 0.0

    @property
    def maximum(self) -> float:
        if self.stats is not None:
            return float(self.stats.get("max", 0.0))
        return max(self.samples) if self.samples else 0.0

    @property
    def mean(self) -> float:
        if self.stats is not None:
            return float(self.stats.get("mean", 0.0))
        return sum(self.samples) / len(self.samples) if self.samples else 0.0

    def stat(self, name: str) -> float:
        if name == "value":
            return self.stat(self.comparison)
        if self.stats is not None:
            return float(self.stats.get(name, 0.0))
        if name == "max":
            return self.maximum
        return percentile(self.samples, {"p50": 0.50, "p95": 0.95, "p99": 0.99}[name])

    def value(self) -> float:
        return self.stat(self.comparison)

    def verdict(self) -> str:
        if self.count == 0:
            return "missing"
        if self.budget is None or self.gate == "info":
            return "n/a"
        current = self.value()
        passed = current <= self.budget if self.direction == "lower" else current >= self.budget
        if passed:
            return "pass"
        return "fail" if self.gate == "blocking" else "warn"

    def to_dict(self) -> dict[str, Any]:
        present = self.count > 0
        return {
            "unit": self.unit,
            "direction": self.direction,
            "gate": self.gate,
            "budget": _round(self.budget),
            "comparison": self.comparison,
            "count": self.count,
            "min": _round(self.minimum) if present else None,
            "p50": _round(self.stat("p50")) if present else None,
            "p95": _round(self.stat("p95")) if present else None,
            "p99": _round(self.stat("p99")) if present else None,
            "max": _round(self.maximum) if present else None,
            "mean": _round(self.mean) if present else None,
            "value": _round(self.value()) if present else None,
            "verdict": self.verdict(),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any]) -> Metric:
        stats = {
            key: float(data[key])
            for key in _STAT_KEYS
            if isinstance(data.get(key), (int, float)) and not isinstance(data.get(key), bool)
        }
        return cls(
            name=name,
            unit=str(data.get("unit", "")),
            samples=(),
            direction=str(data.get("direction", "lower")),
            gate=str(data.get("gate", "info")),
            budget=data.get("budget"),
            comparison=str(data.get("comparison", "p95")),
            note=str(data.get("note", "")),
            stats=stats,
        )


@dataclass
class Report:
    suite: str
    metrics: dict[str, Metric] = field(default_factory=dict)
    runs: int = 1
    duration_s: float = 0.0
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "suite": self.suite,
            "runs": self.runs,
            "duration_s": round(self.duration_s, 3),
            "created_at": self.created_at,
            "metrics": {name: metric.to_dict() for name, metric in sorted(self.metrics.items())},
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Report:
        raw_metrics = data.get("metrics")
        metrics = {
            str(name): Metric.from_dict(str(name), entry)
            for name, entry in (raw_metrics.items() if isinstance(raw_metrics, Mapping) else ())
            if isinstance(entry, Mapping)
        }
        return cls(
            suite=str(data.get("suite", "")),
            metrics=metrics,
            runs=int(data.get("runs", 1)),
            duration_s=float(data.get("duration_s", 0.0)),
            created_at=str(data.get("created_at", "")),
            meta=dict(data.get("meta") or {}),
        )


def merge_metrics(metric_sets: Iterable[Mapping[str, Metric]]) -> dict[str, Metric]:
    """Concatenate samples across runs; every run must agree on the metric shape."""
    merged: dict[str, Metric] = {}
    for metric_set in metric_sets:
        for name, metric in metric_set.items():
            existing = merged.get(name)
            if existing is None:
                merged[name] = metric
                continue
            signature = (existing.unit, existing.direction, existing.gate,
                         existing.budget, existing.comparison, existing.note)
            other = (metric.unit, metric.direction, metric.gate,
                     metric.budget, metric.comparison, metric.note)
            if signature != other:
                raise ValueError(f"metric {name!r} changed shape between runs")
            merged[name] = replace(existing, samples=existing.samples + metric.samples)
    return merged


def _number(value: float | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:.1f}"
    return f"{value:.2f}"


def format_table(report: Report) -> str:
    lines = [
        f"{report.suite}: {report.runs} run(s) in {report.duration_s:.2f}s",
        "",
        f"{'metric':<38} {'unit':<6} {'n':>7} {'p50':>9} {'p95':>9} {'p99':>9} "
        f"{'max':>9} {'budget':>9}  verdict",
        "-" * 105,
    ]
    for name, metric in sorted(report.metrics.items()):
        present = metric.count > 0
        lines.append(
            f"{name:<38} {metric.unit or '-':<6} {metric.count:>7} "
            f"{_number(metric.stat('p50') if present else None):>9} "
            f"{_number(metric.stat('p95') if present else None):>9} "
            f"{_number(metric.stat('p99') if present else None):>9} "
            f"{_number(metric.maximum if present else None):>9} "
            f"{_number(metric.budget):>9}  {metric.verdict()}"
        )
    if not report.metrics:
        lines.append("(no metrics reported)")
    return "\n".join(lines)


def _change(direction: str, delta: float) -> str:
    if delta == 0:
        return "same"
    improved = delta < 0 if direction == "lower" else delta > 0
    return "better" if improved else "worse"


def format_diff(before: Report, after: Report) -> str:
    names = sorted(set(before.metrics) | set(after.metrics))
    lines = [
        f"A/B diff: {before.suite} -> {after.suite}",
        "",
        f"{'metric':<38} {'before':>11} {'after':>11} {'delta':>11} {'pct':>9}  change",
        "-" * 94,
    ]
    for name in names:
        left = before.metrics.get(name)
        right = after.metrics.get(name)
        left_value = left.value() if left is not None and left.count else None
        right_value = right.value() if right is not None and right.count else None
        direction = (right or left).direction
        if left_value is None or right_value is None:
            delta_text = pct_text = "-"
            change = "-"
        else:
            delta = right_value - left_value
            pct_text = f"{(right_value / left_value - 1) * 100:+.1f}%" if left_value else "n/a"
            delta_text = f"{delta:+.2f}"
            change = _change(direction, delta)
        lines.append(
            f"{name:<38} {_number(left_value):>11} {_number(right_value):>11} "
            f"{delta_text:>11} {pct_text:>9}  {change}"
        )
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
