"""Injected scratch hooks drive registered-process liveness."""

from __future__ import annotations

import json

from hermes_platform import scratch


class FakeHooks:
    def __init__(self, *, live: set[int], dead_spawners: set[int]):
        self.live = live
        self.dead_spawners = dead_spawners

    def spawner_is_dead(self, entry):
        return entry.get("pid") in self.dead_spawners

    def is_live_process(self, pid, stamp):
        return pid in self.live


def test_registered_live_pids_uses_injected_hooks(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "spawn-ledger.json").write_text("[]", encoding="utf-8")
    (home / "processes.json").write_text(
        json.dumps([
            {"pid": 111, "host_start_time": "stamp-live", "pid_scope": "host"},
            {"pid": 222, "host_start_time": "stamp-dead", "pid_scope": "host"},
            {"pid": 333, "host_start_time": "stamp-orphan", "pid_scope": "host", "purpose": "mcp-helper"},
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        scratch, "_hooks_provider",
        lambda: FakeHooks(live={111, 333}, dead_spawners={333}),
    )
    monkeypatch.setattr("hermes_platform.constants.get_default_hermes_root", lambda home=None: home)

    assert scratch._registered_live_pids(home) == {111}
