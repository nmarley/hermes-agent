"""Pure config value helpers: nested access, deep merge, default stripping, and turn limits."""

from __future__ import annotations

import copy
import logging
import sys
from typing import Any, Optional

from hermes_config.defaults import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


def cfg_get(cfg: Optional[dict[str, Any]], *keys: str, default: Any = None) -> Any:
    """Traverse nested dict keys safely, returning ``default`` on any miss.
    Explicit ``None`` values are returned as-is (``dict.get`` semantics: ``default`` only when the
    key is absent). Named ``cfg_get`` to avoid shadowing the ubiquitous ``cfg_path`` local."""
    if not isinstance(cfg, dict):
        return default
    node: Any = cfg
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*: dict-over-dict recurses (so overriding one leaf
    keeps sibling defaults), and ``None`` over a dict section is ignored.

    An empty section key in config.yaml (``terminal:`` with no value) parses as YAML ``None``; treating that
    as an override would replace the entire default dict with ``None`` and crash every downstream consumer
    that expects a mapping (#58277).
    """
    result = base.copy()
    for key, value in override.items():
        over_dict = isinstance(result.get(key), dict)
        if over_dict and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif not (over_dict and value is None):
            result[key] = value
    return result


def _merge_partial_save(raw: dict, override: dict) -> dict:
    """Merge *override* over *raw* for partial ``save_config`` writes.
    Omitted top-level sections are preserved; shared dict sections deep-merge so one nested key
    can change without dropping siblings on disk. Key REMOVALS are not supported here —
    migrations go through ``_persist_migration`` with a full ``read_raw_config()`` dict."""
    result = copy.deepcopy(override)
    for key, value in raw.items():
        if key not in result:
            result[key] = copy.deepcopy(value)
        elif isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(value, result[key])
    return result


def _strip_dotted_keys(cfg: dict, dotted_keys: set) -> tuple[dict, set]:
    """Remove dotted leaf keys from *cfg* in place -> ``(cfg, keys_actually_present)``.
    ``save_config`` drops managed-scope leaves this way so a bulk write never persists a user
    value that would lose to the managed layer on the next load."""
    stripped: set = set()
    for dotted in dotted_keys:
        *parents, leaf = dotted.split(".")
        node = cfg_get(cfg, *parents)
        if isinstance(node, dict) and leaf in node:
            del node[leaf]
            stripped.add(dotted)
    return cfg, stripped


def _items_by_unique_name(items):
    """Return a name-indexed dict only when all items have unique string names."""
    if not isinstance(items, list):
        return None
    indexed = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            return None
        name = item["name"]
        if name in indexed:
            return None
        indexed[name] = item
    return indexed


def _explicit_config_paths(config: dict[str, Any]) -> set[tuple[str, ...]]:
    """Leaf paths explicitly present in a RAW (un-normalized) config, so values injected by
    normalisation are never mistaken for user-set ones. Feeds ``_strip_default_values``."""
    paths: set[tuple[str, ...]] = set()

    def _walk(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                _walk(child, path + (key,))
        elif path:
            paths.add(path)

    _walk(config, ())
    return paths


def _strip_default_values(
    config: dict[str, Any], defaults: dict[str, Any] = DEFAULT_CONFIG,
    preserve_keys: Optional[set[tuple[str, ...]]] = None) -> dict[str, Any]:
    """Return *config* without keys whose values match *defaults*.
    Paths in *preserve_keys* (explicitly present in the user's raw config) are always kept even
    when equal to the default. Dicts whose every child is stripped are removed entirely so
    default-only subtrees never bloat ``config.yaml``."""
    preserve_keys = {("_config_version",)} | set(preserve_keys or ())
    # None is a valid authored value, not a signal to remove the node.
    dropped = object()

    def _strip(value: Any, default: Any, path: tuple[str, ...]) -> Any:
        if path in preserve_keys:
            return copy.deepcopy(value)
        if isinstance(value, dict) and value:
            default_dict = default if isinstance(default, dict) else {}
            stripped = {k: _strip(v, default_dict.get(k), path + (k,)) for k, v in value.items()}
            return {k: v for k, v in stripped.items() if v is not dropped} or dropped
        return dropped if value == default else copy.deepcopy(value)

    stripped = _strip(config, defaults, ())
    return {} if stripped is dropped else stripped


def split_model_config_default(raw_default: Any) -> tuple[str, str]:
    """Canonicalize ``model.default``/``model.model`` -> ``(model, provider)``; a dict value pairs
    the model string with the provider it must be routed through."""
    if isinstance(raw_default, dict):
        provider = str(raw_default.get("provider") or "").strip()
        model = raw_default.get("model") or raw_default.get("default")
        return (str(model or "").strip(), provider)
    return (str(raw_default or "").strip(), "")


def _normalize_max_turns_config(config: dict[str, Any]) -> dict[str, Any]:
    """Move legacy root-level ``max_turns`` under ``agent``; the schema default is injected only
    when the user set max_turns somewhere (so save_config can otherwise omit it)."""
    config = dict(config)
    agent_config = dict(config.get("agent") or {})
    if "max_turns" in config and "max_turns" not in agent_config:
        agent_config["max_turns"] = config["max_turns"]
    if agent_config or "agent" in config:  # a sparse save must not grow an `agent: {}` section
        config["agent"] = agent_config
    config.pop("max_turns", None)
    return config


# Sentinel for an unlimited turn budget. ``sys.maxsize`` survives the str->int round-trip through
# the HERMES_MAX_ITERATIONS env bridge, works in every ``<``/``>=``/``max - used`` comparison in
# the iteration budget without an "unlimited" special case, and is unreachable in practice.
TURN_LIMIT_UNLIMITED = sys.maxsize

# Spellings that mean "no limit" (compared lowercased, whitespace-stripped).
_UNLIMITED_SPELLINGS = frozenset({
    "none", "null", "unlimited", "infinite", "infinity", "inf", "∞", "-1", "0"})


def resolve_turn_limit(raw: Any, default: int = TURN_LIMIT_UNLIMITED) -> int:
    """Normalize a raw ``agent.max_turns`` value into an int iteration cap (always >= 1)."""
    # bool is a subclass of int; reject explicitly so True/False don't become 1/0.
    if raw is None or isinstance(raw, bool):
        return default
    if isinstance(raw, (int, float)):
        n = int(raw)
    elif isinstance(raw, str):
        s = raw.strip().lower()
        if not s:
            return default
        if s in _UNLIMITED_SPELLINGS:
            return TURN_LIMIT_UNLIMITED
        try:
            n = int(s)
        except ValueError:
            try:
                n = int(float(s))
            except ValueError:
                logger.debug("resolve_turn_limit: unparseable value %r → default %d", raw, default)
                return default
    else:
        # Unknown type (list, dict, …) — don't crash the agent over a bad config.
        logger.debug("resolve_turn_limit: unsupported type %s (%r) → default %d", type(raw).__name__, raw, default)
        return default
    return TURN_LIMIT_UNLIMITED if n <= 0 else n
