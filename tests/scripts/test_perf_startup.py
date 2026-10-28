from __future__ import annotations

from scripts.perf import startup


def test_parse_importtime_reads_self_times() -> None:
    stderr = (
        "import time: self [us] | cumulative | imported package\n"
        "import time:       396 |        396 |   _io\n"
        "import time:      1200 |       1596 | _abc\n"
        "import time:         0 |       1596 | abc\n"
    )
    assert startup.parse_importtime(stderr) == [396, 1200, 0]


def test_metrics_from_rows_maps_phases() -> None:
    rows = {
        "module_eval": {"phase": "module_eval", "uptimeMs": 120},
        "first_frame": {"phase": "first_frame", "uptimeMs": 450},
        "gateway_ready": {"phase": "gateway_ready", "uptimeMs": 1400},
        "session_ready": {"phase": "session_ready", "uptimeMs": 1900},
    }
    metrics = startup.metrics_from_rows(rows)
    assert metrics["startup.module_eval_ms"].value() == 120
    assert metrics["startup.first_paint_ms"].value() == 450
    assert metrics["startup.gateway_ready_ms"].value() == 1400
    assert metrics["startup.session_ready_ms"].value() == 1900
    assert "startup.gateway_spawn_ms" not in metrics


def test_metrics_from_rows_ignores_boolean_and_missing_values() -> None:
    rows = {"first_frame": {"uptimeMs": True}, "gateway_ready": {}}
    assert startup.metrics_from_rows(rows) == {}


def test_clean_env_isolates_hermes_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HERMES_HOME", "/real/hermes")
    monkeypatch.setenv("HERMES_TUI_RESUME", "sid")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    monkeypatch.setenv("SAFE_SETTING", "kept")

    home = tmp_path / "home"
    log = tmp_path / "perf.log"
    env = startup._clean_env(home, log)

    assert env["HERMES_HOME"] == str(home / ".hermes")
    assert "HERMES_TUI_RESUME" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["SAFE_SETTING"] == "kept"
    assert env["HERMES_DEV_PERF"] == "1"
    assert env["HERMES_DEV_PERF_LOG"] == str(log)
