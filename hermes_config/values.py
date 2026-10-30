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


def coerce_provider_id(value: Any) -> str:
    """Provider identity fields are strings."""
    if value is None:
        return ""
    return str(value).strip()


def _normalize_root_model_keys(config: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize the ``model`` section at the single load/save chokepoint.
    Root-level ``provider``/``base_url``/``context_length`` (older layouts) are moved under
    ``model`` only when the corresponding ``model.*`` key is empty — never overriding. ``api_base``
    (the OpenAI-SDK/LiteLLM name users reach for) is an alias for ``base_url``; the runtime reads
    only ``model.base_url``. A dict-valued ``default``/``model``/``name`` is flattened so no reader
    sees a nested dict, and the id is canonicalized to ``default``.

    Also aliases ``api_base`` → ``base_url`` (issue #8919). ``api_base`` is the intuitive name OpenAI-SDK /
    LiteLLM users reach for, and ``hermes config set`` blindly accepts any dotted key — so
    ``model.api_base`` got written, confirmed, and then silently ignored by the runtime resolver (which
    reads only ``model.base_url``), causing requests to fall back to OpenRouter. We migrate the alias to the
    canonical key (fallback-only — never override an explicit ``base_url``) and drop the alias so it can't
    confuse later loads.
    Finally, canonicalizes the model-id key to ``model.default`` (issue #34500). The runtime resolver and
    ~14 other readers select the chat model via ``model.default``; ``model.model`` was already aliased
    inline at some sites but ``model.name`` was not, so a custom-provider config like ``model: {name: <id>,
    provider: <custom>}`` resolved to an empty model and the API request went out with ``model=`` (HTTP 400
    from OpenAI-compatible backends) — while display paths (``hermes status``/``dump``) read ``name`` and
    *showed* the model, making the failure silent. Normalizing here (the single load/save chokepoint) means
    every reader, present and future, sees a populated ``default`` and the stale alias is migrated out of
    config.yaml on the next save. Precedence: ``default`` > ``model`` > ``name`` (never overrides an
    explicit ``default``, so existing configs are unaffected).
    """
    model_in = config.get("model")
    model_provider = model_in.get("provider") if isinstance(model_in, dict) else None
    needs_model_work = (model_provider is not None and not isinstance(model_provider, str)) or (
        isinstance(model_in, dict) and (
            model_in.get("api_base")
            or model_in.get("model") or model_in.get("name")
            or any(isinstance(model_in.get(k), dict) for k in ("default", "model", "name"))))
    has_root = any(config.get(k) for k in ("provider", "base_url", "context_length", "api_base"))
    if not has_root and not needs_model_work:
        return config

    config = dict(config)
    model = config.get("model")
    model = dict(model) if isinstance(model, dict) else {"default": model} if model else {}
    config["model"] = model

    # Flatten ``{provider: <p>, model: <m>}``. The nested provider wins over the merged default
    # ``"auto"`` (which runtime resolution treats as authoritative) but never over a configured one.
    for _key in ("default", "model", "name"):
        _val = model.get(_key)
        if isinstance(_val, dict):
            _nested_model = _val.get("model") or _val.get("default")
            _nested_provider = str(_val.get("provider") or "").strip()
            model[_key] = str(_nested_model or "").strip()
            if _nested_provider:
                _outer_provider = str(model.get("provider") or "").strip()
                if not _outer_provider or _outer_provider == "auto":
                    model["provider"] = _nested_provider

    for key in ("provider", "base_url", "context_length"):
        root_val = config.get(key)
        if root_val and not model.get(key):
            model[key] = root_val
        config.pop(key, None)

    # Provider identity is a string (#117345): an unquoted YAML scalar (``provider: 2``)
    # loads as int, and downstream readers call ``(provider or "").strip()`` — a gateway
    # turn dies before the agent runs. Normalize at the load/save chokepoint so every
    # reader (and the next save, which rewrites config.yaml) heals the persisted value.
    # Guard on presence: coerce_provider_id(None) is "" — injecting an empty key into
    # provider-less configs would add churn to config.yaml on the next save.
    if model.get("provider") is not None:
        model["provider"] = coerce_provider_id(model.get("provider"))

    for alias_val in (config.get("api_base"), model.get("api_base")):
        if alias_val and not model.get("base_url"):
            model["base_url"] = alias_val
    config.pop("api_base", None)
    model.pop("api_base", None)

    # ``model``/``name`` are last-resort aliases (in that order), then dropped.
    alias = model.get("model") or model.get("name")
    if not model.get("default") and alias:
        model["default"] = alias
    if model.get("default"):
        model.pop("model", None)
        model.pop("name", None)

    return config


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


def _canonicalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """The load/save normalization pipeline: max_turns relocation, then model-section canon."""
    return _normalize_root_model_keys(_normalize_max_turns_config(config))


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
