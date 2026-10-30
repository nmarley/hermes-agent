"""Classic-CLI config loading: prefill messages, reasoning/service-tier parsing, terminal env mirroring, CLI defaults + user YAML merge and the logging/display bootstrap.

Split out of ``cli.py``; ``cli`` re-exports every public name and moved bodies late-bind
cli-level names through ``from cli import ...`` at call time so facade monkeypatch seams hold.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any
from hermes_config.cli import (
    _AUXILIARY_TASK_ENV, _CWD_PLACEHOLDERS, _TERMINAL_ENV_MAPPINGS,
    _cli_config_defaults, _merge_file_config, _mirror_config_to_env,
    load_cli_config as _load_cli_config,
)

# Log-record parity with the origin module.
logger = logging.getLogger("cli")


def _cli():
    """Late import of the ``cli`` facade: mutable CLI module state (and its test seams) lives there."""
    import cli

    return cli


def _load_prefill_messages(file_path: str, base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load prefill messages (JSON array) from *file_path*; missing/empty -> [].

    Relative paths resolve against *base_dir*, defaulting to the CLI's hermes home.
    """
    if not file_path:
        return []
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = (base_dir or _cli()._hermes_home) / path
    if not path.exists():
        logger.warning("Prefill messages file not found: %s", path)
        return []
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("Prefill messages file must contain a JSON array: %s", path)
            return []
        return data
    except Exception as e:
        logger.warning("Failed to load prefill messages from %s: %s", path, e)
        return []


def _resolve_prefill_messages_file(config: dict[str, Any]) -> str:
    """Prefill file path: env, then top-level ``prefill_messages_file``, then legacy ``agent.*``."""
    from agent.session_client_env import session_env
    agent_cfg = config.get("agent", {})
    return (
        session_env("HERMES_PREFILL_MESSAGES_FILE").strip()
        or str(config.get("prefill_messages_file", "") or "").strip()
        or (str(agent_cfg.get("prefill_messages_file", "") or "").strip() if isinstance(agent_cfg, dict) else "")
    )


def _parse_reasoning_config(effort) -> dict | None:
    """Parse a reasoning effort level (string or YAML bool; ``false``/``off`` = disabled)."""
    from hermes_constants import parse_reasoning_effort
    result = parse_reasoning_effort(effort)
    if effort and str(effort).strip() and result is None:
        logger.warning("Unknown reasoning_effort '%s', using default (medium)", effort)
    return result


def _parse_service_tier_config(raw: str) -> str | None:
    """Parse a persisted fast-mode preference: None, "priority", "ultrafast", "auto", or "cold"."""
    from agent.fast_mode import NORMAL_TIER_WORDS, parse_service_tier

    tier = parse_service_tier(raw)
    if tier is None and str(raw or "").strip().lower() not in NORMAL_TIER_WORDS:
        logger.warning("Unknown service_tier '%s', ignoring", raw)
    return tier


def load_cli_config() -> dict[str, Any]:
    """Load the CLI config over built-in defaults, managed overlay last."""
    from hermes_cli import managed_scope

    return _load_cli_config(
        home=_cli()._hermes_home,
        managed_overlay=managed_scope.apply_managed_overlay,
    )


def _init_logging_and_display_from_config() -> None:
    """Best-effort startup side effects: logging, config warnings, skin, display knobs."""
    from importlib import import_module as _im

    def _display(key, default):
        return _cli().CLI_CONFIG.get("display", {}).get(key, default)

    for step in (
        lambda: _im("hermes_platform.logging").setup_logging(mode="cli"),
        lambda: _im("hermes_cli.config").print_config_warnings(),
        lambda: _im("hermes_cli.skin_engine").init_skin_from_config(_cli().CLI_CONFIG),
        lambda: _im("agent.display").set_tool_preview_max_len(int(_display("tool_preview_length", 0) or 0)),
        lambda: _im("agent.display").set_friendly_tool_labels(bool(_display("friendly_tool_labels", True))),
    ):
        try:
            step()
        except Exception:
            pass
