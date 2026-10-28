"""Isolated home and dependency-environment helpers for the perf suites.

The TUI suites must never read the operator's Hermes state, but the gateway
bootstrap still needs this checkout's committed dependency generation. A temp
HERMES_HOME has no install state, so the temp home links the real state in
while config, sessions, and logs stay isolated.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def install_state() -> Path | None:
    from hermes_constants import get_default_hermes_root
    from pm.environments import install_key, owning_home_root

    owner = owning_home_root(PROJECT_ROOT) or get_default_hermes_root()
    state = owner / "installs" / install_key(PROJECT_ROOT)
    return state if state.is_dir() else None


def committed_python() -> Path | None:
    state = install_state()
    if state is None:
        return None
    try:
        facts = json.loads((state / "facts.json").read_text(encoding="utf-8-sig"))
        venv = Path(facts["packages"]["venv"]["environment"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return python if python.exists() else None


def link_install_state(hermes_home: Path) -> None:
    """Point the isolated home at this checkout's committed dependency generation."""
    state = install_state()
    if state is None:
        print(
            f"warning: no committed dependency state for {PROJECT_ROOT}; "
            "the gateway bootstrap may fail",
            file=sys.stderr,
        )
        return
    installs = hermes_home / "installs"
    installs.mkdir(parents=True, exist_ok=True)
    link = installs / state.name
    if not link.exists():
        link.symlink_to(state, target_is_directory=True)


def clean_env(home: Path, log: Path) -> dict[str, str]:
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
            "HERMES_PYTHON_SRC_ROOT": str(PROJECT_ROOT),
            "PYTHONPATH": str(PROJECT_ROOT),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "TERM": env.get("TERM", "xterm-256color"),
        }
    )
    return env
