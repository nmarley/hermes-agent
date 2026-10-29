"""Early CLI logging bootstrap: config bridge, mode selection, and force_ipv4."""

from __future__ import annotations

import os

from hermes_cli import main_logging_bootstrap as bootstrap


def _write_config(home):
    (home / "config.yaml").write_text(
        "security:\n"
        "  redact_secrets: false\n"
        "network:\n"
        "  force_ipv4: true\n"
        "logging:\n"
        "  level: DEBUG\n",
        encoding="utf-8",
    )


def test_bridges_config_and_selects_cli_mode(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    _write_config(home)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_REDACT_SECRETS", raising=False)
    calls = []
    monkeypatch.setattr(bootstrap, "setup_logging", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(bootstrap, "is_managed", lambda: True)

    force_ipv4 = bootstrap.bootstrap_early_logging(["status"])

    assert force_ipv4 is True
    assert os.environ["HERMES_REDACT_SECRETS"] == "false"
    assert calls[0]["mode"] == "cli"
    assert calls[0]["config"]["network"]["force_ipv4"] is True
    assert calls[0]["managed"] is True


def test_dashboard_uses_gui_mode_and_missing_config_stays_default(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_REDACT_SECRETS", raising=False)
    calls = []
    monkeypatch.setattr(bootstrap, "setup_logging", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(bootstrap, "is_managed", lambda: False)

    force_ipv4 = bootstrap.bootstrap_early_logging(["serve"])

    assert force_ipv4 is False
    assert calls[0]["mode"] == "gui"
    assert calls[0]["config"] is None
    assert "HERMES_REDACT_SECRETS" not in os.environ
