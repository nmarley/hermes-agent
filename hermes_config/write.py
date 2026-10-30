"""Persist the merged config with defaults stripped and managed keys protected."""

from __future__ import annotations

import copy
from typing import Any, Optional

from hermes_config.defaults import DEFAULT_CONFIG
from hermes_config.env_refs import preserve_env_ref_templates
from hermes_config.load import ConfigState, atomic_config_replace, require_readable_config_before_write
from hermes_config.read_errors import _refuse_failed_read
from hermes_config.values import _explicit_config_paths, _strip_default_values

_SECURITY_COMMENT = """
# ── Security ──────────────────────────────────────────────────────────
# Secret redaction is ON by default — strings that look like API keys,
# tokens, and passwords are masked in tool output, logs, and chat
# responses before the model or user ever sees them. Set redact_secrets
# to false to disable (e.g. when developing the redactor itself).
#
# security:
#   redact_secrets: true
"""

_FALLBACK_COMMENT = """
# ── Fallback Model ────────────────────────────────────────────────────
# Automatic provider failover when primary is unavailable.
# Uncomment and configure to enable. Triggers on rate limits (429),
# overload (529), service errors (503), or connection failures.
#
# Supported providers:
#   openrouter   (OPENROUTER_API_KEY)  — routes to any model
#   openai-codex (OAuth — hermes auth) — OpenAI Codex
#   nous         (OAuth — hermes auth) — Nous Portal
#   zai          (ZAI_API_KEY)         — Z.AI / GLM
#   kimi-coding  (KIMI_API_KEY)        — Kimi / Moonshot
#   kimi-coding-cn (KIMI_CN_API_KEY)   — Kimi / Moonshot (China)
#   minimax      (MINIMAX_API_KEY)     — MiniMax
#   minimax-cn   (MINIMAX_CN_API_KEY)  — MiniMax (China)
#   bedrock      (AWS IAM / boto3)     — AWS Bedrock (Converse API)
#
# For custom OpenAI-compatible endpoints, add base_url and key_env.
#
# fallback_model:
#   provider: openrouter
#   model: anthropic/claude-sonnet-4
"""


def _commented_sections_for_save(normalized: dict[str, Any]) -> Optional[str]:
    """Commented-out example blocks for features that are off/unconfigured."""
    parts = []
    if (normalized.get("security") or {}).get("redact_secrets") is None:
        parts.append(_SECURITY_COMMENT)
    fb = normalized.get("fallback_model", {})
    fb_entries = fb if isinstance(fb, list) else [fb]
    if not any(isinstance(e, dict) and e.get("provider") and e.get("model") for e in fb_entries):
        parts.append(_FALLBACK_COMMENT)
    return "".join(parts) or None


def save_config(
    state: ConfigState, config: dict[str, Any], *, strip_defaults: bool = True,
    preserve_keys: Optional[set[tuple[str, ...]]] = None, merge_existing: bool = False,
):
    """Save configuration to ~/.hermes/config.yaml.
    Schema defaults are not written unless the user explicitly set them (the path exists in the
    raw config before normalisation), so config.yaml is never contaminated with defaults that
    would hide future default changes. ``merge_existing`` deep-merges the on-disk raw config
    under *config* so partial callers cannot drop sections they omitted."""
    with state.lock:
        if state.is_managed():
            state.managed_error("save configuration")
            return

        config_path = state.get_config_path()
        _refuse_failed_read(config_path, config)
        config = state.strip_managed_keys(config)

        state.ensure_home()
        # Explicit user paths come from the RAW dict BEFORE normalisation (which may inject
        # agent.max_turns) so _strip_default_values keeps exactly what the user set. The
        # fail-closed read is the single authority here: ``read_raw_config()`` is cached and
        # swallows transient stat/open errors into ``{}``, and a ``{}`` at this point makes the
        # strip pass drop every user section whose value matches a default (#113301).
        _raw_for_paths = require_readable_config_before_write(state, config_path)
        config = state.rebase_for_save(config, _raw_for_paths, merge_existing)

        current_normalized = state.canonicalize(config)
        normalized = current_normalized
        if _raw_for_paths:
            normalized = preserve_env_ref_templates(
                normalized, state.canonicalize(_raw_for_paths),
                state.last_expanded.get(str(config_path)), lookup=state.env_ref_lookup)

        if strip_defaults:
            # ``_strip_default_values`` always preserves ``_config_version`` itself.
            effective_preserve_keys = _explicit_config_paths(_raw_for_paths) | set(preserve_keys or ())
            normalized = _strip_default_values(normalized, DEFAULT_CONFIG, preserve_keys=effective_preserve_keys)

        atomic_config_replace(
            state, config_path, normalized, extra_content_on_create=_commented_sections_for_save(normalized))
        state.secure_file(config_path)
        state.raw_cache.pop(str(config_path), None)
        state.last_expanded[str(config_path)] = copy.deepcopy(current_normalized)
    state.record_saved(_raw_for_paths, current_normalized)
