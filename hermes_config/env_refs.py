"""Environment-reference expansion for config values."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Optional

from hermes_config.values import _items_by_unique_name

logger = logging.getLogger(__name__)

ENV_REF_RE = re.compile(r"\${([^}]+)}")

SecretLookup = Callable[[str], Optional[str]]


def is_non_env_secret_ref(ref: str) -> bool:
    """True for a SecretRef body with a non-``env`` source (``bitwarden:FOO``, ``vault:...``)."""
    return ":" in ref and re.match(r"^[a-z][a-z0-9_-]*:", ref) is not None


def env_ref_var_name(ref: str) -> Optional[str]:
    """Env-var name a ``${...}`` body reads, or None for a non-env source / empty ``env:``."""
    ref = ref.strip()
    if ref.startswith("env:"):
        return ref[len("env:"):].strip() or None
    if is_non_env_secret_ref(ref):
        return None
    return ref


def _expand_match(m: re.Match, lookup: SecretLookup) -> str:
    """Expand one ``${VAR}`` (legacy bare name) or ``${env:VAR}`` (Cursor-style SecretRef).
    Other SecretRef sources (``file:``, ``bitwarden:``, ``vault:``...) are NOT resolved here:
    external backends inject their values into the environment at startup (the ``secrets:``
    block), so a config ref only ever needs the env shape. Unresolved refs stay verbatim so
    callers can detect them."""
    raw = m.group(0)
    inner = m.group(1).strip()
    name = env_ref_var_name(inner)
    if name is None:
        if not inner.startswith("env:") and is_non_env_secret_ref(inner):
            logger.warning(
                "Config ref %r uses source %r which is not resolvable in "
                "config.yaml — external secret sources inject env vars at "
                "startup, so reference the variable as ${env:NAME} instead",
                raw, inner.split(":", 1)[0])
        return raw  # non-env source, or empty ``${env:}``
    val = lookup(name)
    if val is not None:
        return val
    if inner.startswith("env:"):
        logger.warning(
            "Config ref %r: %s is not set (check ~/.hermes/.env); "
            "keeping the literal placeholder", raw, name)
    return raw


def expand_env_vars(obj: Any, lookup: SecretLookup) -> Any:
    """Recursively expand ``${VAR}`` / ``${env:VAR}`` in string values (keys/non-strings untouched)."""
    if isinstance(obj, str):
        return ENV_REF_RE.sub(lambda m: _expand_match(m, lookup), obj)
    if isinstance(obj, dict):
        return {k: expand_env_vars(v, lookup) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env_vars(item, lookup) for item in obj]
    return obj


def env_ref_snapshot(obj: Any, lookup: SecretLookup, snapshot: Optional[dict] = None) -> dict:
    """Map each env-sourced ``${...}`` ref in *obj* to its current value.
    Stored with cached ``load_config()`` results so a cache hit can detect that the expansion was
    made against a different environment (load before ``load_hermes_dotenv()``, in-process
    rotation) — file mtime/size alone cannot see either.

    See #58514.
    """
    if snapshot is None:
        snapshot = {}
    if isinstance(obj, str):
        for raw in ENV_REF_RE.findall(obj):
            name = env_ref_var_name(raw)
            if name is not None:
                snapshot[name] = lookup(name)
    elif isinstance(obj, dict):
        for value in obj.values():
            env_ref_snapshot(value, lookup, snapshot)
    elif isinstance(obj, list):
        for item in obj:
            env_ref_snapshot(item, lookup, snapshot)
    return snapshot


def preserve_env_ref_templates(
    current: Any, raw: Any, loaded_expanded: Any = None, *, lookup: SecretLookup,
) -> Any:
    """Restore raw ``${VAR}`` templates where the value is otherwise unchanged, so persisting a
    loaded (expanded) config never writes the plaintext secret back to ``config.yaml``."""
    if isinstance(current, str) and isinstance(raw, str) and ENV_REF_RE.search(raw):
        if current in (raw, loaded_expanded) or expand_env_vars(raw, lookup) == current:
            return raw
        return current

    if isinstance(current, dict) and isinstance(raw, dict):
        return {
            key: preserve_env_ref_templates(
                value, raw.get(key),
                loaded_expanded.get(key) if isinstance(loaded_expanded, dict) else None,
                lookup=lookup)
            for key, value in current.items()}

    if isinstance(current, list) and isinstance(raw, list):
        # Match named objects (e.g. custom_providers) by name so reordering keeps templates;
        # with duplicate names fall back to positional matching rather than shadowing an entry.
        current_by_name = _items_by_unique_name(current)
        raw_by_name = _items_by_unique_name(raw)
        loaded_by_name = _items_by_unique_name(loaded_expanded)
        if current_by_name is not None and raw_by_name is not None:
            return [
                preserve_env_ref_templates(
                    item, raw_by_name.get(item.get("name")),
                    loaded_by_name.get(item.get("name")) if loaded_by_name is not None else None,
                    lookup=lookup)
                for item in current]
        return [
            preserve_env_ref_templates(
                item,
                raw[index] if index < len(raw) else None,
                loaded_expanded[index]
                if isinstance(loaded_expanded, list) and index < len(loaded_expanded)
                else None,
                lookup=lookup)
            for index, item in enumerate(current)]

    return current
