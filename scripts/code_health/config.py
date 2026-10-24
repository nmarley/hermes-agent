"""Targets, file scope and the rule table: the one place a rule's id, scope and fix text live.

A rule's ``fix`` is the text the agent reads at the moment it trips the rule, so it names the
repo-specific remedy rather than restating the rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch

# Master switch, honoured everywhere the ratchet runs (CI, `scripts/check`, the git hooks). It is
# read from main, never from the branch under test, so a PR cannot relax its own check: CI reads
# the merge commit's first parent; local runs read `origin/main` (falling back to the merge-base).
# A flip reaches an open PR on its next CI run (a re-run reuses the old merge commit). "blocking": findings fail;
# "advisory": findings print, the run passes; "off": the ratchet is skipped. Flip it with a
# one-line commit to main; a single rule can instead be demoted with ``blocking=False`` below.
ENFORCEMENT = "blocking"

# Per-unit targets. A unit already over its target keeps its own current value as its cap
# (measured on the base revision) and may only go down; new units must meet the target.
TARGETS = {
    "CC": 20,  # cyclomatic complexity per function (ruff C901 numbers for Python)
    "FUNC_LINES": 300,
    "NESTING": 6,  # nested control-flow blocks inside one function
    "FILE_LINES": 2000,
}

METRIC_FIX = {
    "CC": "split it: extract phases into named helpers, or replace a branch ladder with a"
    " dict/table -> handler",
    "FUNC_LINES": "extract phases into named helpers, or into a domain subpackage when the"
    " phase is a real boundary",
    "NESTING": "return early, or extract the inner block into a helper",
    "FILE_LINES": "extract a domain subpackage or a public API; a new `<stem>_<topic>.py`"
    " sibling is not a boundary. Move existing code (it keeps its cap; see root AGENTS.md), or"
    " put new tests in a new test file; new behaviour never goes into a facade",
    "MEASURE": "the file must parse and measure (a file that cannot be measured cannot be"
    " judged); fix the syntax, or report the measurer bug",
}

PY_EXCLUDE = ("website/*", "*/node_modules/*", "node_modules/*")
TS_EXCLUDE = PY_EXCLUDE + ("*.d.ts", "*/dist/*", "*/build/*", "*/generated/*", "*.generated.ts")
TESTS = ("tests/*", "*/tests/*", "tests-js/*", "*/conftest.py")
# One-shot processes that serve a single profile (CI/release scripts, skill scripts run as a
# child with a scoped env, installers): the profile-scope rules don't apply to them.
SINGLE_PROFILE = TESTS + ("scripts/*", "skills/*", "optional-skills/*", "evals/*", "setup.py")

# Import-graph contract. A package may import only the packages named here, plus itself.
# The table is the target DAG, not a snapshot: existing violations are grandfathered by the
# base revision, and new ones fail. Surfaces may import inward; core may not import a surface.
ALL_PACKAGES = "*"
ROOT_PACKAGE = "<root>"
PACKAGE_LAYERS: dict[str, frozenset[str]] = {
    # Root modules are being retired. They are a graph node so a move out of the root keeps
    # its late-import credit, but they are allowed to import anything while they exist.
    ROOT_PACKAGE: frozenset({ALL_PACKAGES}),
    "hermes_types": frozenset(),
    # Foundational host layer: every package may import it. The root compatibility shims stay
    # importable until their callers move; `ROOT_MODULE` still stops new root files.
    "hermes_platform": frozenset({"hermes_types", ROOT_PACKAGE}),
    "hermes_config": frozenset({"hermes_types", "hermes_platform"}),
    "hermes_providers": frozenset({"hermes_types", "hermes_config", "hermes_platform"}),
    # Root compatibility shims stay importable until their callers move; `ROOT_MODULE` still
    # stops new root files.
    "hermes_store": frozenset({
        "hermes_types", "hermes_config", "hermes_platform", ROOT_PACKAGE,
    }),
    "hermes_plugins": frozenset({
        "hermes_types", "hermes_config", "hermes_providers", "hermes_platform",
    }),
    "pm": frozenset({"hermes_types", "hermes_platform"}),
    "tools": frozenset({"hermes_types", "hermes_config", "hermes_store", "hermes_platform"}),
    "agent": frozenset({
        "hermes_types", "hermes_config", "hermes_providers", "hermes_store",
        "hermes_plugins", "tools", "hermes_platform",
    }),
    "gateway": frozenset({
        "hermes_types", "hermes_config", "hermes_providers", "hermes_store",
        "hermes_plugins", "agent", "tools", "hermes_platform",
    }),
    "cron": frozenset({
        "hermes_types", "hermes_config", "hermes_store", "agent", "gateway", "hermes_platform",
    }),
    # In-tree plugin implementations sit at the edge: they may reach inward, never into a
    # surface. A new platform adapter goes under gateway/platforms/, not here.
    "plugins": frozenset({
        "hermes_types", "hermes_config", "hermes_providers", "hermes_store",
        "hermes_plugins", "agent", "tools", "gateway", "hermes_platform",
    }),
    "hermes_cli": frozenset({ALL_PACKAGES}),
    "tui_gateway": frozenset({ALL_PACKAGES}),
    "acp_adapter": frozenset({ALL_PACKAGES}),
}

# Modules that moved packages without changing their public names. The graph compares a base
# import of the old path as the new module, so a pure move is not new debt. A head import of
# the old path still counts as new: the move is only free for code that follows it.
MOVED_MODULES: dict[str, str] = {
    "hermes_cli.config_defaults": "hermes_config.defaults",
    "hermes_dir_acl": "hermes_platform.fs",
    "hermes_state_errors": "hermes_store.errors",
    "hermes_state_guard": "hermes_store.guard",
    "hermes_state_health": "hermes_store.health",
    "hermes_state_ids": "hermes_store.ids",
    "hermes_state_keys": "hermes_store.keys",
    "hermes_state_lockguard": "hermes_store.lockguard",
    "hermes_state_pidns": "hermes_store.pidns",
    "hermes_state_user_copy": "hermes_store.user_copy",
}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    fix: str
    source: str  # "ruff" | "ast" | "regex"
    exclude: tuple[str, ...] = TESTS
    blocking: bool = True
    include: tuple[str, ...] = ()  # when set, the rule applies only to these paths
    pattern_id: str = ""  # regex rules: id in scripts/ci/profile_scope_patterns.json


# Heuristic rules print as warnings until a frozen replay (`python -m scripts.code_health.replay`)
# shows most of their hits on merged PRs are real problems; flip a rule to blocking with that
# evidence in the PR. Reviewers' samples put these between ~12% and ~60% precision.
WARN_UNTIL_REPLAYED = False

RULES: tuple[Rule, ...] = (
    # Swallowed exceptions: the top statically-catchable bug cause in the fix sample.
    Rule("S110", "try/except/pass", "log it or narrow the except; a silent pass hides the"
         " failure the next bug report is about", "ruff"),
    # ruff (pinned, --ignore-noqa) passes a handler that re-raises or logs the traceback; a
    # message-only log such as `logger.warning("...: %s", e)` still counts as swallowed.
    Rule("BLE001", "blind `except Exception`", "catch the exceptions this code can actually"
         " raise; a deliberate catch-all boundary must re-raise or log the traceback"
         " (`logger.exception(...)` or `exc_info=True`; `logger.warning(..., e)` is not enough)."
         " `# noqa` is ignored here: waive with `# health: allow BLE001 -- <why>`", "ruff"),
    Rule("E722", "bare `except:`", "catch a named exception (bare except also swallows"
         " KeyboardInterrupt/SystemExit)", "ruff"),
    # Correctness basics.
    # tui_gateway method modules get the server's names injected (`bind_module(globals(), ...)`).
    Rule("F821", "undefined name", "import or define it", "ruff", exclude=("tui_gateway/*",)),
    Rule("F823", "local used before assignment", "assign before use or declare global",
         "ruff", exclude=()),
    Rule("F811", "redefinition of unused name", "remove the shadowed definition", "ruff",
         exclude=()),
    Rule("F841", "unused local variable", "delete it or use it", "ruff", exclude=()),
    Rule("RUF006", "dangling asyncio task", "keep a reference to the task (it can be garbage"
         " collected mid-run) and handle its exception", "ruff"),
    # Hangs.
    Rule("ASYNC230", "blocking open() in async def", "`await asyncio.to_thread(...)`", "ruff"),
    Rule("ASYNC240", "blocking path call in async def", "`await asyncio.to_thread(...)`",
         "ruff"),
    Rule("S113", "HTTP request without timeout", "pass `timeout=`", "ruff"),
    Rule("HX006", "subprocess/urlopen without timeout", "pass `timeout=`; an asyncio"
         " `proc.communicate()` goes inside `asyncio.wait_for(..., timeout=...)` (a child or"
         " socket that never answers hangs forever); after `proc.kill()` reap with `proc.wait()`,"
         " never a bare `communicate()` (it blocks while a grandchild holds the pipe)", "ast"),
    Rule("HX007", "sync config I/O inside async def", "`await asyncio.to_thread(load_config)`"
         " or read it before entering the event loop", "ast"),
    Rule("HX008", "asyncio.get_event_loop()", "`asyncio.get_running_loop()` inside a"
         " coroutine; `asyncio.run()` at an entry point", "ast"),
    Rule("HX009", "isinstance(r, Exception) on gather results", "check `BaseException`:"
         " `gather(return_exceptions=True)` also returns CancelledError", "ast"),
    # Profile scope (one process serves many profiles).
    Rule("HX001", "hardcoded Hermes home", "`get_hermes_home()` for paths,"
         " `display_hermes_home()` for user-facing text (`hermes_constants`); a path that"
         " deliberately lives under the user's home, not the profile (e.g. the profiles root),"
         " takes `# health: allow HX001 -- <why>`", "ast",
         blocking=WARN_UNTIL_REPLAYED,
         exclude=SINGLE_PROFILE + ("hermes_constants.py",)),
    Rule("HX002", "new HERMES_* environment variable", "behavioural settings go in"
         " config.yaml, secrets through the secret scope; `.env` is for credentials only",
         "ast", exclude=SINGLE_PROFILE),
    Rule("HX004", "UnscopedSecretError falls back to os.getenv", "bind the owning profile's"
         " secret scope at the spawn site; never read the launch profile's environment",
         "ast", exclude=SINGLE_PROFILE),
    Rule("HX005", "home/config/env captured at import time", "resolve it at call time"
         " (`get_hermes_home()`, `load_config()`) or key the slot by `hermes_home_key()`;"
         " module constants hold the launch profile's value", "ast",
         exclude=SINGLE_PROFILE),
    Rule("HX012", "raw threading.Thread", "`spawn_context_thread(...)` so the thread keeps"
         " the caller's profile scope (ContextVars do not cross a bare Thread)", "ast",
         blocking=WARN_UNTIL_REPLAYED,
         exclude=SINGLE_PROFILE),
    Rule("PS-P05", "child env built from os.environ", "`served_profile_child_env()`; the"
         " child otherwise inherits the launch profile's home and secrets", "regex",
         exclude=SINGLE_PROFILE, blocking=WARN_UNTIL_REPLAYED, pattern_id="P05"),
    Rule("PS-P06", "raw platform credential getenv", "read it through the profile's secret"
         " scope (`get_secret`)", "regex", exclude=SINGLE_PROFILE,
         blocking=WARN_UNTIL_REPLAYED, pattern_id="P06"),
    # Process identity.
    Rule("HX003", "process identity from argv substrings", "use"
         " `gateway.status.looks_like_gateway_command_line` /"
         " `hermes_cli.update_cmd._hermes_holder_subcommand` and match full cmdlines", "ast",
         blocking=WARN_UNTIL_REPLAYED),
    # Config truthiness.
    Rule("HX010", "bool() of a config/env string", "`bool(\"false\")` is True. Is it set?"
         " `os.getenv(\"X\") is not None` (or `!= \"\"` to treat empty as unset). A boolean"
         " flag? `is_truthy_value(...)`, which is False for any non-flag string such as a key",
         "ast", blocking=WARN_UNTIL_REPLAYED),
    # Structure.
    Rule("HX011", "if/elif ladder on one name", "use a dict/table -> handler (`_SLASH_DISPATCH`"
         " is the shape)", "ast", exclude=()),
    # Import graph. The graph is global, not per file: see scripts/code_health/imports.py.
    Rule("LAYER_VIOLATION", "forbidden package dependency", "move the shared code into a"
         " lower layer (`hermes_types`, `hermes_config`, `hermes_providers`, `hermes_store`)"
         " or inject it; a core package must not import a surface", "ast", exclude=()),
    Rule("IMPORT_CYCLE", "new package dependency cycle", "break the cycle by extracting the"
         " shared concern into a lower layer; a cycle means an API boundary is in the wrong"
         " place", "ast", exclude=()),
    Rule("LATE_IMPORT", "new function-level cross-package import", "import at module top"
         " level; a late import hides the dependency and defers the failure to call time",
         "ast", exclude=()),
    Rule("ROOT_MODULE", "new top-level Python module", "move it into the owning package;"
         " the repository root is entry points and compatibility shims only", "ast",
         exclude=()),
    # Tests: a fixed delay is a race against the runner's load (the usual flake).
    Rule("HX013", "wall-clock sleep in a test", "wait for the condition, not the clock: an"
         " Event the code under test sets (`threading.Event` / `asyncio.Event`, `.wait(timeout=)`),"
         " or poll with `tests.waiting.wait_until(predicate, timeout=...)` (`async_wait_until` in a"
         " coroutine; a poll loop's interval under a deadline or a `range(n)` bound passes); a stand-in that must hang"
         " blocks on an Event the test sets at teardown."
         " `sleep(0)` to yield is fine. A delay that IS the behaviour under test takes"
         " `# health: allow HX013 -- <why>`", "ast", include=TESTS, exclude=()),
)

RULES_BY_ID = {rule.id: rule for rule in RULES}
RUFF_CODES = tuple(rule.id for rule in RULES if rule.source == "ruff")
ALLOW_SYNTAX = "# health: allow <RULE> -- <why>"


def _matches(path: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch(path, glob) for glob in globs)


def rule_applies(rule: Rule, path: str) -> bool:
    if rule.include and not _matches(path, rule.include):
        return False
    return not _matches(path, rule.exclude)


def in_scope(path: str) -> str | None:
    """Language of a tracked path the engine measures, or None."""
    if path.endswith(".py"):
        return None if _matches(path, PY_EXCLUDE) else "py"
    if path.endswith((".ts", ".tsx", ".mts", ".cts")):
        return None if _matches(path, TS_EXCLUDE) else "ts"
    return None
