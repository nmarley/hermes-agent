from __future__ import annotations

import json

import pytest

from scripts.perf import budget, metrics


def test_percentile_nearest_rank() -> None:
    assert metrics.percentile([1, 2, 3, 4], 0.5) == 3
    assert metrics.percentile([1, 2, 3, 4], 0.95) == 4
    assert metrics.percentile([], 0.5) == 0.0
    with pytest.raises(ValueError):
        metrics.percentile([1], 0)


def test_metric_reports_stats_and_budget_verdict() -> None:
    metric = metrics.Metric(
        name="frame_ms", unit="ms", samples=(10, 20, 30), budget=25, gate="warn"
    )
    assert metric.count == 3
    assert metric.value() == 30
    assert metric.verdict() == "warn"


def test_blocking_metric_fails_a_breached_budget() -> None:
    metric = metrics.Metric(
        name="frame_ms", unit="ms", samples=(10, 20, 30), budget=25, gate="blocking"
    )
    assert metric.verdict() == "fail"


def test_higher_is_better_metric_passes_above_budget() -> None:
    metric = metrics.Metric(
        name="fps",
        unit="fps",
        samples=(60,),
        direction="higher",
        budget=50,
        gate="blocking",
    )
    assert metric.verdict() == "pass"


def test_report_round_trip_preserves_aggregates() -> None:
    report = metrics.Report(
        suite="demo",
        runs=2,
        metrics={"frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(10, 20, 30))},
    )
    loaded = metrics.Report.from_dict(json.loads(json.dumps(report.to_dict())))
    original = report.metrics["frame_ms"]
    restored = loaded.metrics["frame_ms"]
    assert restored.count == original.count
    assert restored.value() == original.value()
    assert restored.stat("p50") == original.stat("p50")
    assert restored.verdict() == original.verdict()


def test_merge_metrics_concatenates_samples_across_runs() -> None:
    first = {"frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(1.0,))}
    second = {"frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(2.0, 3.0))}
    merged = metrics.merge_metrics([first, second])
    assert merged["frame_ms"].samples == (1.0, 2.0, 3.0)
    assert merged["frame_ms"].count == 3


def test_merge_metrics_rejects_a_shape_change() -> None:
    first = {"frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(1.0,))}
    second = {"frame_ms": metrics.Metric(name="frame_ms", unit="s", samples=(2.0,))}
    with pytest.raises(ValueError):
        metrics.merge_metrics([first, second])


def test_evaluate_flags_budget_and_regression() -> None:
    baseline = {
        "schema_version": 1,
        "tolerance_pct": 10.0,
        "suites": {
            "demo": {
                "frame_ms": {
                    "unit": "ms",
                    "direction": "lower",
                    "gate": "blocking",
                    "comparison": "p95",
                    "budget": 10.0,
                    "current": 5.0,
                }
            }
        },
    }
    report = metrics.Report(
        suite="demo",
        metrics={"frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(12.0,))},
    )
    evaluated, findings = budget.evaluate(report, baseline)
    assert evaluated.metrics["frame_ms"].budget == 10.0
    assert {(finding.kind, finding.severity) for finding in findings} == {
        ("budget", "fail"),
        ("regression", "fail"),
    }


def test_evaluate_flags_a_missing_blocking_metric() -> None:
    baseline = {
        "schema_version": 1,
        "suites": {"demo": {"tool.count": {"gate": "blocking"}}},
    }
    report = metrics.Report(suite="demo", metrics={})
    _, findings = budget.evaluate(report, baseline)
    assert findings == [
        budget.Finding("tool.count", "fail", "missing", "the suite did not report this metric")
    ]


def test_update_baseline_preserves_policy_and_sets_current() -> None:
    baseline = {
        "schema_version": 1,
        "tolerance_pct": 10.0,
        "suites": {"demo": {"frame_ms": {"gate": "blocking", "budget": 16.0}}},
    }
    report = metrics.Report(
        suite="demo",
        metrics={
            "frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(12.0,)),
            "new_metric": metrics.Metric(name="new_metric", unit="count", samples=(3.0,)),
        },
    )
    updated = budget.update_baseline(report, baseline)
    entry = updated["suites"]["demo"]["frame_ms"]
    assert entry["gate"] == "blocking"
    assert entry["budget"] == 16.0
    assert entry["current"] == 12.0
    assert updated["suites"]["demo"]["new_metric"]["gate"] == "info"


def test_load_baseline_rejects_an_unknown_schema(tmp_path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(SystemExit):
        budget.load_baseline(path)


def test_format_table_includes_the_verdict() -> None:
    report = metrics.Report(
        suite="demo",
        metrics={
            "frame_ms": metrics.Metric(
                name="frame_ms", unit="ms", samples=(12.0,), budget=16.0, gate="warn"
            )
        },
    )
    table = metrics.format_table(report)
    assert "frame_ms" in table
    assert "pass" in table


def test_format_diff_marks_an_improvement() -> None:
    before = metrics.Report(
        suite="demo",
        metrics={"frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(20.0,))},
    )
    after = metrics.Report(
        suite="demo",
        metrics={"frame_ms": metrics.Metric(name="frame_ms", unit="ms", samples=(10.0,))},
    )
    assert "better" in metrics.format_diff(before, after)


def _frame(ts: float, duration: float = 12.0, *, flickers=None, backpressure: bool = False):
    return {
        "ts": ts,
        "durationMs": duration,
        "phases": {
            "renderer": 5.0,
            "yoga": 2.0,
            "diff": 1.0,
            "optimize": 0.5,
            "write": 1.0,
            "commit": 0.5,
            "patches": 10,
            "optimizedPatches": 8,
            "writeBytes": 100,
            "prevFrameDrainMs": 0.0,
            "yogaVisited": 50,
            "yogaMeasured": 20,
            "yogaCacheHits": 30,
            "yogaLive": 40,
            "backpressure": backpressure,
        },
        "flickers": flickers or [],
    }


def test_tui_frames_converts_rows_to_metrics() -> None:
    from scripts.perf import tui_frames

    data = {
        "frame": [
            _frame(1000),
            _frame(1016, 18.0, flickers=[{"reason": "resize"}], backpressure=True),
        ],
        "react": [{"id": "AppView", "actualMs": 3.0}],
    }
    result = tui_frames.metrics_from_data(data)
    assert result["tui.frame.duration_ms"].samples == (12.0, 18.0)
    assert result["tui.frame.gap_ms"].samples == (16.0,)
    assert result["tui.react.appview_ms"].samples == (3.0,)
    assert result["tui.flickers"].value() == 1.0
    assert result["tui.backpressure_frames"].value() == 1.0
    assert result["tui.fps"].value() == pytest.approx(125.0)


def test_tui_frames_returns_nothing_without_rows() -> None:
    from scripts.perf import tui_frames

    assert tui_frames.metrics_from_data({"frame": [], "react": []}) == {}
