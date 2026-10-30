"""Classic-CLI config loading: CLI defaults over the user YAML with env mirroring."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

from hermes_config.defaults import DEFAULT_SANDBOX_IMAGE as img
from hermes_config.env_refs import expand_env_vars
from hermes_config.paths import get_project_root
from hermes_config.values import _normalize_root_model_keys
from hermes_platform.constants import get_hermes_home
from hermes_platform.utils import fast_safe_load

logger = logging.getLogger("cli")

# terminal.<key> -> TERMINAL_<KEY> env var. Container-resource keys apply to docker,
# modal, daytona, vercel_sandbox and container plugin backends (ignored for local/ssh).
_TERMINAL_ENV_MAPPINGS = {
    key: f"TERMINAL_{key.upper()}"
    for key in (
        "degraded_mode", "cwd", "timeout", "home_mode", "lifetime_seconds", "docker_image",
        "docker_forward_env", "modal_image", "daytona_image", "vercel_runtime", "vercel_image",
        "ssh_host", "ssh_user", "ssh_port", "ssh_key", "container_cpu", "container_memory",
        "container_disk", "container_persistent", "docker_volumes", "docker_env", "docker_extra_args",
        "docker_shm_size", "docker_mount_cwd_to_workspace", "docker_network", "docker_run_as_host_user",
        "docker_snap_compat",
        "docker_persist_across_processes", "docker_shared_container_key", "docker_orphan_reaper",
        "sandbox_dir", "persistent_shell",
    )
}

_TERMINAL_ENV_MAPPINGS = {"env_type": "TERMINAL_ENV", **_TERMINAL_ENV_MAPPINGS, "sudo_password": "SUDO_PASSWORD"}

# Per-task auxiliary endpoint tuples (config key -> env var).
_AUXILIARY_TASK_ENV = {
    "vision": {
        "provider": "AUXILIARY_VISION_PROVIDER",
        "model": "AUXILIARY_VISION_MODEL",
        "base_url": "AUXILIARY_VISION_BASE_URL",
        "api_key": "AUXILIARY_VISION_API_KEY",
    },
    "approval": {
        "provider": "AUXILIARY_APPROVAL_PROVIDER",
        "model": "AUXILIARY_APPROVAL_MODEL",
        "base_url": "AUXILIARY_APPROVAL_BASE_URL",
        "api_key": "AUXILIARY_APPROVAL_API_KEY",
    },
}

_CWD_PLACEHOLDERS = (".", "auto", "cwd")


def _mirror_config_to_env(defaults, _file_has_terminal_config):
    """Project config.yaml values into the env vars the tool modules read (terminal/browser/auxiliary/security/sessions). Env always wins when already set."""
    terminal_config = defaults.get("terminal", {})

    # "backend" (documented) and legacy "env_type" are both accepted; "backend" wins.
    if "backend" in terminal_config:
        terminal_config["env_type"] = terminal_config["backend"]

    # Local backend: cwd is always os.getcwd(). Non-local: a placeholder is popped so
    # terminal_tool uses its per-backend default; an explicit path is kept.
    effective_backend = terminal_config.get("env_type", "local")
    if effective_backend == "local":
        terminal_config["cwd"] = os.getcwd()
        defaults["terminal"]["cwd"] = terminal_config["cwd"]
    elif terminal_config.get("cwd") in _CWD_PLACEHOLDERS:
        terminal_config.pop("cwd", None)

    # TERMINAL_CWD is force-exported (beats stale .env) except inside a gateway process,
    # whose config bridge already set it.
    _is_gateway = os.environ.get("_HERMES_GATEWAY") == "1"
    for config_key, env_var in _TERMINAL_ENV_MAPPINGS.items():
        if config_key not in terminal_config:
            continue
        val = terminal_config[config_key]
        if env_var == "TERMINAL_CWD":
            if not _is_gateway:
                os.environ[env_var] = str(val)
        elif _file_has_terminal_config or env_var not in os.environ:
            os.environ[env_var] = json.dumps(val) if isinstance(val, (list, dict)) else str(val)

    browser_config = defaults.get("browser", {})
    if "inactivity_timeout" in browser_config:
        os.environ["BROWSER_INACTIVITY_TIMEOUT"] = str(browser_config["inactivity_timeout"])

    # Only non-empty / non-"auto" auxiliary values are bridged so auto-detection still works.
    auxiliary_config = defaults.get("auxiliary", {})
    for task_key, env_map in _AUXILIARY_TASK_ENV.items():
        task_cfg = auxiliary_config.get(task_key, {})
        if not isinstance(task_cfg, dict):
            continue
        for field, env_var in env_map.items():
            val = str(task_cfg.get(field, "")).strip()
            if val and not (field == "provider" and val == "auto"):
                os.environ[env_var] = val

    security_config = defaults.get("security", {})
    if isinstance(security_config, dict):
        redact = security_config.get("redact_secrets")
        if redact is not None:
            os.environ["HERMES_REDACT_SECRETS"] = str(redact).lower()

    # Session-search index knobs (hermes_state reads the env carriers).
    sessions_config = defaults.get("sessions", {})
    if isinstance(sessions_config, dict):
        if "cjk_fts" in sessions_config:
            os.environ["HERMES_CJK_FTS"] = str(sessions_config["cjk_fts"])
        if "search_slow_ms" in sessions_config:
            os.environ["HERMES_SEARCH_SLOW_MS"] = str(sessions_config["search_slow_ms"])


def _cli_config_defaults():
    """Built-in defaults for every config key the CLI reads (the file overlays these)."""
    return {
        "model": {"default": "", "base_url": "", "provider": "auto"},
        "terminal": {
            "env_type": "local", "cwd": ".", "home_mode": "auto", "lifetime_seconds": 300,  # cwd "." -> os.getcwd()
            "docker_image": img, "docker_forward_env": [], "modal_image": img, "daytona_image": img, "docker_volumes": [],
            "docker_mount_cwd_to_workspace": False,  # opt-in only: sandbox isolation
            "docker_shared_container_key": "",
        },
        "browser": {
            "inactivity_timeout": 120, "record_sessions": False, "engine": "auto",  # auto (Chrome) | lightpanda | chrome
            "camofox": {"rewrite_loopback_urls": False, "loopback_host_alias": "host.docker.internal"},
        },
        # threshold: fraction of the model's context limit; min_tail: real user messages kept in the tail
        "compression": {"enabled": True, "threshold": 0.50, "min_tail_user_messages": 1},
        "agent": {
            "max_turns": 500, "verbose": False, "system_prompt": "", "prefill_messages_file": "",  # max_turns shared with subagents
            "reasoning_effort": "", "service_tier": "",
            "personalities": {},  # user overrides merged by name over hermes_cli.personality builtins
        },
        "display": {
            "compact": False,
            # /resume recap tuning and show_reasoning: keep in sync with hermes_cli/config.py DEFAULT_CONFIG
            "resume_display": "full", "resume_exchanges": 10, "resume_max_user_chars": 300,
            "resume_max_assistant_chars": 200, "resume_max_assistant_lines": 3, "resume_skip_tool_only": True,
            "show_reasoning": True, "reasoning_full": False, "streaming": True, "busy_input_mode": "interrupt",
            "cli_layout": "modern",
            "persistent_output": True, "persistent_output_max_lines": 200,
            # Also clear scrollback on redraw/resize recovery; off because users prefer history.
            "cli_rebuild_scrollback_on_redraw": False,
            "persist_prompts": True,  # one-line summary of resolved modal prompts into scrollback
            "skin": "default",
        },
        "code_execution": {"timeout": 300, "max_tool_calls": 50},
        "auxiliary": {"vision": {"provider": "auto", "model": "", "base_url": "", "api_key": ""}},
        # delegation: empty model/provider = inherit parent; api_key falls back to OPENAI_API_KEY
        "delegation": {"max_iterations": 45, "model": "", "provider": "", "base_url": "", "api_key": ""},
        "onboarding": {"seen": {}},  # first-touch hint flags (agent/onboarding.py), latched once shown
    }


def _merge_file_config(defaults: dict[str, Any], file_config: dict[str, Any]) -> None:
    """Overlay a parsed config file onto *defaults* in place (model normalization, deep merge, legacy keys)."""
    # model: string (new format) or dict (old format with default/base_url)
    if "model" in file_config:
        if isinstance(file_config["model"], str):
            defaults["model"]["default"] = file_config["model"]
        elif isinstance(file_config["model"], dict):
            defaults["model"].update(file_config["model"])
            # Promote model.model -> model.default (HermesCLI checks "default" first).
            if "model" in file_config["model"] and "default" not in file_config["model"]:
                defaults["model"]["default"] = file_config["model"]["model"]

    # Deep-merge dict sections, overwrite scalars; a None section keeps the defaults;
    # unknown keys (platform_toolsets, memory, ...) are carried over.
    for key, value in file_config.items():
        if key == "model":
            continue
        if isinstance(defaults.get(key), dict):
            if isinstance(value, dict):
                defaults[key].update(value)
            elif value is not None:
                defaults[key] = value
        else:
            defaults[key] = value

    # Legacy root-level max_turns -> agent.max_turns whenever the nested key is missing.
    agent_file_config = file_config.get("agent")
    if "max_turns" in file_config and not (
        isinstance(agent_file_config, dict) and agent_file_config.get("max_turns") is not None
    ):
        defaults["agent"]["max_turns"] = file_config["max_turns"]


def load_cli_config(
    *, home: Optional[Path] = None,
    managed_overlay: Optional[Callable[[dict], dict]] = None,
    mirror_env: bool = True,
) -> dict[str, Any]:
    """~/.hermes/config.yaml (else ./cli-config.yaml) over built-in defaults; env vars win.

    ``HERMES_IGNORE_USER_CONFIG=1`` skips the user config entirely (``.env`` still loads).
    """
    home = home or get_hermes_home()
    config_path = home / "config.yaml"
    if not config_path.exists() or os.environ.get("HERMES_IGNORE_USER_CONFIG") == "1":
        config_path = get_project_root() / "cli-config.yaml"

    defaults = _cli_config_defaults()

    # Only a file's terminal section may overwrite terminal env vars already set by .env.
    _file_has_terminal_config = False

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                file_config = _normalize_root_model_keys(fast_safe_load(f) or {})

            _file_has_terminal_config = "terminal" in file_config
            _merge_file_config(defaults, file_config)
        except Exception as e:
            logger.warning("Failed to load cli-config.yaml: %s", e, exc_info=True)

    # Expand ${ENV_VAR} references before bridging to env vars.
    defaults = expand_env_vars(defaults, os.environ.get)

    if managed_overlay is not None:
        defaults = managed_overlay(defaults)

    if mirror_env:
        _mirror_config_to_env(defaults, _file_has_terminal_config)

    return defaults
