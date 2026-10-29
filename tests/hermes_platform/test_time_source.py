"""Injected timezone source controls environment and config resolution."""

from __future__ import annotations

import pytest

import hermes_platform.time as hermes_time


class FakeSource:
    def __init__(self, *, multiplex: bool, timezone_name: str):
        self.multiplex = multiplex
        self.timezone_name = timezone_name

    def is_multiplex_active(self) -> bool:
        return self.multiplex

    def load_user_config_effective(self, path):
        return {"timezone": self.timezone_name}


@pytest.fixture(autouse=True)
def _reset_timezone_cache():
    hermes_time.reset_cache()
    yield
    hermes_time.reset_cache()


def test_source_supplies_configured_timezone(monkeypatch):
    monkeypatch.delenv("HERMES_TIMEZONE", raising=False)
    monkeypatch.setattr(
        hermes_time, "_source_provider",
        lambda: FakeSource(multiplex=False, timezone_name="Asia/Tokyo"),
    )

    assert hermes_time.get_timezone_name() == "Asia/Tokyo"
    assert str(hermes_time.get_timezone()) == "Asia/Tokyo"


def test_multiplex_source_ignores_process_env(monkeypatch):
    monkeypatch.setenv("HERMES_TIMEZONE", "America/New_York")
    monkeypatch.setattr(
        hermes_time, "_source_provider",
        lambda: FakeSource(multiplex=True, timezone_name="Asia/Tokyo"),
    )

    assert hermes_time.get_timezone_name() == "Asia/Tokyo"
    assert str(hermes_time.get_timezone()) == "Asia/Tokyo"
