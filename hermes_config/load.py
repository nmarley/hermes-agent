"""Read and write the user config with cache and runtime hooks injected by the caller."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from hermes_config.defaults import DEFAULT_CONFIG
from hermes_config.read_errors import (
    FailedConfigRead, _FIX_PERMS, _FIX_YAML, _backups_dir_display, _refuse_failed_read,
    _refuse_overwrite, _warn_config_parse_failure,
)
from hermes_config.values import _deep_merge
from hermes_platform.utils import atomic_roundtrip_yaml_save, fast_safe_load, file_signature

logger = logging.getLogger(__name__)


@dataclass
class ConfigState:
    """Mutable caches plus the runtime hooks a config read needs.

    ``hermes_cli.config`` builds one per call from its module globals so tests that clear or
    replace those globals keep working while the loader moves.
    """

    lock: Any
    raw_cache: dict
    load_cache: dict
    last_expanded: dict
    parse_failures: dict
    get_config_path: Callable[[], Path]
    ensure_home: Callable[[], None]
    worker_snapshot: Callable[[], Optional[dict]]
    managed_dir: Callable[[], Optional[Path]]
    managed_config: Callable[[], dict]
    normalize_managed: Callable[[dict], dict]
    canonicalize: Callable[[dict], dict]
    expand_env_vars: Callable[[Any], Any]
    env_ref_snapshot: Callable[[Any], dict]
    env_ref_lookup: Callable[[str], Optional[str]]
    apply_moa_presets: Callable[[dict, dict], None]
    backup_good: Callable[[Path], None]
    load_newest_good_backup: Callable[[Path], Optional[dict]]
    warn_parse_failure: Callable[..., None] = _warn_config_parse_failure
    open_fn: Callable[..., Any] = open
    fast_safe_load_fn: Callable[..., Any] = fast_safe_load


def _raw_config_cache_hit(state: ConfigState, path_key: str, cache_key: tuple[Any, ...]) -> Optional[dict[str, Any]]:
    """Pure lookup: the cached raw config for ``path_key`` if its signature equals ``cache_key``,
    else ``None``. Shared by the lock-free fast path and the locked re-check of
    ``_read_raw_config_impl`` so the predicate cannot drift between them."""
    cached = state.raw_cache.get(path_key)
    if cached is not None and cached[:len(cache_key)] == cache_key:
        return cached[len(cache_key)]
    return None


def _read_raw_config_impl(state: ConfigState, *, want_deepcopy: bool) -> dict[str, Any]:
    snapshot = state.worker_snapshot()
    if snapshot is not None:
        return snapshot

    # Lock-free fast path for cache hits — same shape as `_load_config_impl`. `state.raw_cache`
    # publishes each entry as ONE `(*sig, data)` tuple replaced wholesale, so a reader sees either
    # the complete old entry or the complete new one; `state.lock` only serializes the re-parse
    # and the writers (`save_config()` holds it across an atomic YAML write, which used to stall
    # every cached read for the duration). A lost race just falls through to the locked re-check.
    try:
        config_path = state.get_config_path()
        cache_key = file_signature(config_path.stat())
        hit = _raw_config_cache_hit(state, str(config_path), cache_key)
        if hit is not None:
            return copy.deepcopy(hit) if want_deepcopy else hit
    except Exception:
        logger.debug("raw config fast path skipped", exc_info=True)

    with state.lock:
        config_path = state.get_config_path()
        try:
            cache_key = file_signature(config_path.stat())
        except FileNotFoundError:
            return {}
        except OSError as e:
            return FailedConfigRead(error=e)

        path_key = str(config_path)
        hit = _raw_config_cache_hit(state, path_key, cache_key)
        if hit is not None:
            return copy.deepcopy(hit) if want_deepcopy else hit

        try:
            with state.open_fn(config_path, encoding="utf-8-sig") as f:
                data = state.fast_safe_load_fn(f) or {}
        except Exception as e:
            logger.debug("raw config read failed", exc_info=True)
            state.warn_parse_failure(config_path, e)
            return FailedConfigRead(error=e)

        if not isinstance(data, dict):
            return FailedConfigRead(error=TypeError(f"top-level YAML must be a mapping, got {type(data).__name__}"))
        state.parse_failures.pop(path_key, None)  # the file reads now (a transient error left the record)
        # The cache stores its own deepcopy. The readonly path returns THAT object (identity
        # invariant: later cache hits return the same dict); the mutable path returns the parse.
        cached_copy = copy.deepcopy(data)
        state.raw_cache[path_key] = (*cache_key, cached_copy)
        return data if want_deepcopy else cached_copy


def read_raw_config(state: ConfigState) -> dict[str, Any]:
    """Read config.yaml as-is (no defaults merged, no migration); ``{}`` if missing/unparseable.
    Cached on the file signature (mtime_ns, size, ino, ctime_ns); returns a deepcopy since callers mutate before ``save_config()``."""
    return _read_raw_config_impl(state, want_deepcopy=True)


def read_user_config_raw(state: ConfigState, config_path: Optional[Path] = None) -> dict[str, Any]:
    """Read a user ``config.yaml`` EXACTLY as written (no defaults/overlay/expansion, no cache).
    ONLY legal for write-back round-trips and raw-file diagnostics — behavioral reads must use
    load_config()/load_config_readonly()."""
    if config_path is None:
        config_path = state.get_config_path()
    try:
        with state.open_fn(config_path, encoding="utf-8-sig") as f:
            data = state.fast_safe_load_fn(f) or {}
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}


def read_raw_config_readonly(state: ConfigState) -> dict[str, Any]:
    """``read_raw_config()`` without the per-call deepcopy, for callers that ONLY READ.
    **Mutating the result corrupts the in-process cache for every subsequent caller.** Meant for
    per-turn policy checks that were paying a full config deepcopy 2-3x per agent turn."""
    return _read_raw_config_impl(state, want_deepcopy=False)


def require_readable_config_before_write(state: ConfigState, config_path: Optional[Path] = None) -> dict[str, Any]:
    """Refuse to replace an existing config.yaml that cannot be read or parsed; return the mapping.
    Guards two collapse-to-empty failure modes that would let a read-then-write caller silently
    wipe user overrides: an unreadable file (permissions / broken mount) and an unparseable or
    non-mapping root — bare-``except`` loaders treat both as ``{}``, so a subsequent write would
    replace the recoverable file with only the caller's partial dict. Fails closed."""
    if config_path is None:
        snapshot = state.worker_snapshot()
        if snapshot is not None:
            # A bypass worker's config IS its frozen snapshot; it never reads the profile file.
            return copy.deepcopy(snapshot)
        config_path = state.get_config_path()
    try:
        config_path.stat()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise _refuse_overwrite(config_path, "cannot be accessed", exc, _FIX_PERMS) from exc

    try:
        with state.open_fn(config_path, encoding="utf-8-sig") as f:
            loaded = state.fast_safe_load_fn(f)
    except OSError as exc:
        raise _refuse_overwrite(config_path, "cannot be read", exc, _FIX_PERMS) from exc
    except Exception as exc:
        state.warn_parse_failure(config_path, exc, fallback="refuse-write")
        raise _refuse_overwrite(
            config_path, "has a formatting error", exc, _FIX_YAML.format(backups=_backups_dir_display())) from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        exc = TypeError(f"top-level YAML must be a mapping, got {type(loaded).__name__}")
        state.warn_parse_failure(config_path, exc, fallback="refuse-write")
        raise _refuse_overwrite(
            config_path, f"must start with settings names, but its top level is a {type(loaded).__name__}",
            exc, _FIX_YAML.format(backups=_backups_dir_display())) from exc
    return loaded


def _omitted_config_paths(
    existing: dict[str, Any], proposed: dict[str, Any], prefix: tuple[str, ...] = (),
) -> list[str]:
    """Mapping paths that *proposed* would delete by omission from *existing*.

    The round-trip writer recurses through mappings, so the completeness check must recurse too:
    checking top-level key counts still lets a partial ``plugins: {...}`` payload erase sibling
    settings inside that section. Replacing a non-empty mapping with a scalar/list is likewise a
    deletion of that mapping's children and is reported at the mapping path.
    """
    omitted: list[str] = []
    for key, old_value in existing.items():
        path = (*prefix, str(key))
        if key not in proposed:
            omitted.append(".".join(path))
            continue
        new_value = proposed[key]
        if isinstance(old_value, dict):
            if isinstance(new_value, dict):
                omitted.extend(_omitted_config_paths(old_value, new_value, path))
            elif old_value:
                omitted.append(".".join(path))
    return omitted


def _write_config_state(
    state: ConfigState, config_path: Path, data: dict[str, Any], *, allow_omissions: bool,
    extra_content_on_create: Optional[str] = None,
) -> None:
    """Shared comment-preserving config writer; omission policy is selected by the public wrapper."""
    _refuse_failed_read(config_path, data)
    if not allow_omissions:
        existing = require_readable_config_before_write(state, config_path)
        omitted = _omitted_config_paths(existing, data)
        if omitted:
            shown = ", ".join(omitted[:12])
            if len(omitted) > 12:
                shown += f", +{len(omitted) - 12} more"
            exc = ValueError(f"omitted config paths: {shown}")
            raise _refuse_overwrite(
                config_path,
                "would lose settings omitted by this write",
                exc,
                "Pass the complete current config, or use atomic_config_replace() only when "
                "deletion by omission is deliberate.",
            ) from exc
    atomic_roundtrip_yaml_save(config_path, data, extra_content_on_create=extra_content_on_create)


def atomic_config_write(
    state: ConfigState, config_path: Path, data: dict[str, Any], *, extra_content_on_create: Optional[str] = None,
) -> None:
    """Persist config without allowing an incomplete mapping to delete existing settings.

    Values explicitly present in *data* may change, but every existing mapping path must remain.
    Use ``atomic_config_replace`` for a deliberate full-state replacement where omitted keys are
    meant to be deleted. Both paths retain the unreadable-file guard and ruamel comment preservation.
    """
    _write_config_state(
        state, config_path, data, allow_omissions=False, extra_content_on_create=extra_content_on_create)


def atomic_config_replace(
    state: ConfigState, config_path: Path, data: dict[str, Any], *, extra_content_on_create: Optional[str] = None,
) -> None:
    """Persist the complete desired config state; omitted mapping keys are deliberately deleted."""
    _write_config_state(
        state, config_path, data, allow_omissions=True, extra_content_on_create=extra_content_on_create)


def _load_config_cache_sig(state: ConfigState, config_path: Path) -> tuple[Optional[tuple[int, int, int, int]], Optional[tuple[int, ...]]]:
    """Return ``(user_sig, cache_sig)`` for ``state.load_cache``.
    The managed config file's signature is folded in ((0, 0, 0, 0) = none) so editing it invalidates
    the merged result. ``cache_sig`` is None only when neither file exists (nothing to cache on)."""
    try:
        st = config_path.stat()
        user_sig: Optional[tuple[int, int, int, int]] = file_signature(st)
    except FileNotFoundError:
        user_sig = None
    managed_dir = state.managed_dir()
    try:
        mst = (managed_dir / "config.yaml").stat() if managed_dir else None
        managed_sig = file_signature(mst) if mst else (0, 0, 0, 0)
    except OSError:
        managed_sig = (0, 0, 0, 0)
    if user_sig is None and managed_sig == (0, 0, 0, 0):
        return None, None
    return user_sig, (*(user_sig or (0, 0, 0, 0)), *managed_sig)


def _last_known_good_fallback(
    state: ConfigState, config_path: Path, path_key: str, cache_sig, exc: Exception,
) -> Optional[dict[str, Any]]:
    """Warn about a parse failure and return the last-known-good config, or None (-> defaults).
    A parse failure must not silently replace the effective config with defaults — that drops
    EVERY user override, including security-critical ``approvals.deny`` rules, when a gateway
    user mid-edits config.yaml into broken YAML. Keep serving the last good config until fixed."""
    lkg = state.last_expanded.get(path_key)
    fallback = "last-known-good"
    if lkg is None:
        # Fresh process (CLI restart, `hermes config get`): nothing loaded yet in this process, so
        # fall back to the newest byte-exact copy the last successful parse left in backups/config/.
        # It holds the raw file (``${VAR}`` templates intact), so it goes through the same
        # canonicalize -> expand -> managed-overlay pipeline as a normal load.
        raw_good = state.load_newest_good_backup(config_path)
        if raw_good is not None:
            merged_good = _deep_merge(copy.deepcopy(DEFAULT_CONFIG), raw_good)
            state.apply_moa_presets(merged_good, raw_good)
            normalized = state.canonicalize(merged_good)
            expanded_good = state.expand_env_vars(normalized)
            lkg, _ = _merge_managed_overlay(state, expanded_good)
            fallback = "last-known-good-backup"
    state.warn_parse_failure(
        config_path, exc, fallback=fallback if lkg is not None else "defaults")
    if lkg is None:
        return None
    # save_config() stores the pre-expansion dict (templates preserved); the load path stores the
    # expanded one. Expand defensively — idempotent when already expanded.
    lkg_copy = FailedConfigRead(state.expand_env_vars(copy.deepcopy(lkg)), error=exc)
    if cache_sig is not None:
        # Cache under the failed file's signature (empty env snapshot: always valid) so repeated
        # loads don't re-parse the fallback; fixing the file changes the signature and reloads
        # normally, and a read error is re-probed on every hit (_load_config_cache_hit).
        state.load_cache[path_key] = (*cache_sig, lkg_copy, {})
    return lkg_copy


def _merge_managed_overlay(state: ConfigState, expanded: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """Apply the managed-scope overlay; returns ``(merged, managed_config_or_falsy)``.
    Managed wins at the leaf and is applied AFTER user expansion so a user ``${VAR}`` cannot shadow
    a managed literal: managed values expand only against the process environment. This
    deliberately inverts the usual env-over-config precedence for the keys the managed layer pins
    (docs/design/managed-scope.md §4.1)."""
    managed_config = state.managed_config()
    if not managed_config:
        return expanded, managed_config
    managed_normalized = state.normalize_managed(managed_config)
    if isinstance(managed_normalized.get("model"), str):
        managed_normalized = dict(managed_normalized)
        managed_normalized["model"] = {"default": managed_normalized["model"]}
    return _deep_merge(expanded, state.expand_env_vars(managed_normalized)), managed_config


def _load_config_cache_hit(state: ConfigState, path_key: str, cache_sig: Any) -> Optional[dict[str, Any]]:
    """Lookup: the cached expanded config for ``path_key`` if its signature equals
    ``cache_sig`` AND every ``${VAR}`` it was expanded against still has the same value, else
    ``None``. Signatures matching is not enough: a load before load_hermes_dotenv() would otherwise
    pin unexpanded literals (e.g. auxiliary.<task>.api_key) for the process lifetime (#58514).
    Shared by the lock-free fast path and the locked re-check of ``_load_config_impl``."""
    cached = state.load_cache.get(path_key)
    if cached is None or cache_sig is None or cached[:8] != cache_sig:
        return None
    hit = cached[8]
    if isinstance(hit, FailedConfigRead) and isinstance(hit.read_error, OSError):
        # A read error (EMFILE/EIO/sharing violation) can clear without touching the file's
        # signature: serve the fallback only while the file still cannot be read.
        try:
            with state.open_fn(path_key, "rb") as f:
                f.read()
            return None
        except OSError:
            return hit
    env_snapshot = cached[9] if len(cached) > 9 else {}
    if all(state.env_ref_lookup(k) == v for k, v in env_snapshot.items()):
        return hit
    return None


def _load_config_impl(state: ConfigState, *, want_deepcopy: bool) -> dict[str, Any]:
    snapshot = state.worker_snapshot()
    if snapshot is not None:
        return _deep_merge(copy.deepcopy(DEFAULT_CONFIG), snapshot)

    # Lock-free fast path for cache hits — same publication contract as `_read_raw_config_impl`
    # above (whole-tuple replace, `state.lock` only serializes rebuilds and writers). A hit costs
    # ~0.024ms; behind a lock held by `save_config()` the same read measured 10010ms, and on a
    # gateway that stalls every inbound message's hook path. A lost race falls through to the lock.
    try:
        config_path = state.get_config_path()
        path_key = str(config_path)
        if path_key in state.load_cache:
            _, fast_sig = _load_config_cache_sig(state, config_path)
            hit = _load_config_cache_hit(state, path_key, fast_sig)
            if hit is not None:
                return copy.deepcopy(hit) if want_deepcopy else hit
    except Exception:
        # Any surprise here falls through to the locked path, which is the
        # original fully-defensive implementation.
        logger.debug("config fast path skipped", exc_info=True)

    with state.lock:
        state.ensure_home()
        config_path = state.get_config_path()
        path_key = str(config_path)

        user_sig, cache_sig = _load_config_cache_sig(state, config_path)

        hit = _load_config_cache_hit(state, path_key, cache_sig)
        if hit is not None:
            return copy.deepcopy(hit) if want_deepcopy else hit

        config = copy.deepcopy(DEFAULT_CONFIG)

        if user_sig is not None:
            try:
                with state.open_fn(config_path, encoding="utf-8-sig") as f:
                    user_config = state.fast_safe_load_fn(f) or {}
                state.parse_failures.pop(path_key, None)  # the file reads now (a transient error left the record)

                if "max_turns" in user_config:
                    agent_user_config = dict(user_config.get("agent") or {})
                    if agent_user_config.get("max_turns") is None:
                        agent_user_config["max_turns"] = user_config["max_turns"]
                    user_config["agent"] = agent_user_config
                    user_config.pop("max_turns", None)

                config = _deep_merge(config, user_config)
                state.apply_moa_presets(config, user_config)
                # A copy of the file that just parsed is what a FRESH process falls back to when the
                # next edit breaks the YAML (see _last_known_good_fallback). backup_config() skips
                # byte-identical repeats and keeps a bounded count, so steady-state loads cost one stat.
                state.backup_good(config_path)
            except Exception as e:
                logger.debug("config load failed", exc_info=True)
                lkg_copy = _last_known_good_fallback(state, config_path, path_key, cache_sig, e)
                if lkg_copy is not None:
                    return copy.deepcopy(lkg_copy) if want_deepcopy else lkg_copy
                # Defaults stand in for the unreadable file: never the next last-known-good,
                # never saveable, and cached like the LKG path.
                fallback = FailedConfigRead(
                    _merge_managed_overlay(state, state.expand_env_vars(state.canonicalize(config)))[0], error=e)
                if cache_sig is not None:
                    state.load_cache[path_key] = (*cache_sig, fallback, {})
                return copy.deepcopy(fallback) if want_deepcopy else fallback

        normalized = state.canonicalize(config)
        expanded, managed_config = _merge_managed_overlay(state, state.expand_env_vars(normalized))
        state.last_expanded[path_key] = copy.deepcopy(expanded)
        if cache_sig is not None:
            # The cache stores its own deepcopy so load_config() callers can mutate freely while
            # load_config_readonly() callers all see the same stable object. The env snapshot
            # records the values this expansion was made against so later loads detect drift.
            cached_copy = copy.deepcopy(expanded)
            env_snapshot = state.env_ref_snapshot(normalized)
            if managed_config:
                state.env_ref_snapshot(managed_config, env_snapshot)
            state.load_cache[path_key] = (*cache_sig, cached_copy, env_snapshot)
            # Readonly path returns the same object later calls will see (identity invariant).
            if not want_deepcopy:
                return cached_copy
        else:
            state.load_cache.pop(path_key, None)
        # First-load result is a fresh dict (not aliased to the cache); safe to return directly.
        return expanded


def load_config(state: ConfigState) -> dict[str, Any]:
    """Load the merged configuration (DEFAULT_CONFIG + config.yaml + managed scope, env-expanded).
    Cached on the file signature; returns a deepcopy since most call sites mutate the result.
    Read-only hot paths should use ``load_config_readonly()`` to skip the deepcopy."""
    return _load_config_impl(state, want_deepcopy=True)


def load_config_readonly(state: ConfigState) -> dict[str, Any]:
    """``load_config()`` without the defensive deepcopy (~half of the 265us cache-hit cost).
    **Mutating the returned dict (or any nested structure) corrupts the in-process cache for
    every subsequent caller** — only for code paths that never write to the result."""
    return _load_config_impl(state, want_deepcopy=False)


