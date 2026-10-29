# State and Utility Splits

## Purpose

This plan is the detailed follow-up to `docs/plans/PLAN-architecture-reset.md`. It covers the
work that cannot be done by moving whole modules:

- the 51 `hermes_state_*` modules still at the repository root;
- the cross-cutting utilities still at the root: `hermes_constants`, `hermes_logging`,
  `hermes_time`, `hermes_constants_scratch`, `hermes_constants_scratch_stuck`, `utils`, and
  `hermes_yaml`.

The earlier attempts proved the pattern: a module is movable only when its entire dependency
closure fits the target layer. Moving a coupled module whole creates a new cycle, and the
code-health ratchet rejects it. Split first, then move.

This is a design and sequencing document. It is not a progress tracker. Check git history for
what has landed.

## Current state

Baseline commit at plan creation: `8b7262cba3` (`Move low-level state modules into hermes_store`).

- Root Python files: 71.
- `hermes_store` exists with `__init__.py` and eight low-level modules:
  `errors`, `guard`, `health`, `ids`, `keys`, `lockguard`, `pidns`, `user_copy`.
- Root `hermes_state_*.py` files: 51.
- Of those 51, the dependency closure finds:
  - 33 seed-coupled modules with a direct import of `agent`, `gateway`, `tools`, `hermes_cli`,
    or the root `hermes_state` facade;
  - 18 modules that depend on a seed-coupled module;
  - 0 movable today.
- Root `hermes_constants.py`, `hermes_logging.py`, `hermes_time.py`, the two scratch modules,
  and `utils.py` all have back-edges except `hermes_yaml.py` and
  `hermes_constants_scratch_stuck.py`.

The guardrails are live in `scripts/code_health`:

- `LAYER_VIOLATION` enforces the package dependency table.
- `IMPORT_CYCLE` freezes existing package cycles and blocks new ones.
- `LATE_IMPORT` blocks new function-level cross-package imports.
- `ROOT_MODULE` blocks new top-level Python files.
- `MOVED_MODULES` gives a move credit while the old path is still in a base revision.
- `ROOT_PACKAGE` lets root compatibility shims remain importable during the migration.

Current deliberate waivers, all visible in `python3 scripts/check --only health` output:

- `hermes_config/defaults.py`: `FILE_LINES` for the moved pure data table.
- `hermes_platform/fs.py`: one `LATE_IMPORT` because `hermes_constants` imports `fs` lazily too.
- `hermes_store/user_copy.py`: one `LATE_IMPORT` for `profile_cli_selector`.

## Target end state

### `hermes_store`

| Subpackage | Responsibility |
|---|---|
| `hermes_store/api.py` | Public protocols, types, and the compatibility facade the root `hermes_state.py` delegates to. |
| `hermes_store/schema/` | Schema creation, migrations, database files, WAL, holders, registry. |
| `hermes_store/common/` | Pure epoch, SQL, title, and identity helpers. No agent or gateway imports. |
| `hermes_store/sessions/` | Sessions, messages, titles, timeline, identity, usage, detached results, API content. |
| `hermes_store/mutations/` | Session mutations, branches, resets, retirements, transcript updates. |
| `hermes_store/compression/` | Compression, rewind, prune/rewrite, worker compression. |
| `hermes_store/search/` | FTS and session search. |
| `hermes_store/runtime/` | Runtime workers, worker context and lifecycle, read pool, lock owners. |
| `hermes_store/repair/` | Repair, reconcile, coverage, profile repair, maintenance, portability, lineage migrations. |
| `hermes_store/media/` | Media references and spillover storage. |
| `hermes_store/adapters/` | Surface-specific state helpers that do not belong in the core: Telegram topics, terminal state, todo persistence, gateway process probes. |

The root `hermes_state.py` remains only as a compatibility facade. No `hermes_state_*` sibling
files remain at the root.

### `hermes_platform`

| Module | Responsibility |
|---|---|
| `constants.py` | Home paths, profile names, root resolution, display paths, secure directory policy. |
| `logging.py` | Handlers, rotation, queue plumbing, log routing. Redaction arrives through a protocol. |
| `time.py` | Pure clock, timezone conversion, and formatting. Timezone source arrives through a protocol. |
| `scratch.py` | Scratch retention and reaping. Liveness arrives through callbacks. |
| `startup_watchdog.py` | Pre-loop liveness, progress leases, and exit forensics. Lifecycle and home callbacks arrive through protocols. |
| `yaml.py` | The YAML 1.1 policy loader. |
| `utils.py` | Generic filesystem and truthiness helpers. No config or agent imports. |
| `fs.py` | Directory ACL and secure filesystem helpers. Already moved. |

### `hermes_config`

| Module | Responsibility |
|---|---|
| `paths.py` | Config paths, env paths, profile selectors, and path helpers shared with the store. |
| `time.py` | Config-backed timezone resolution, when it cannot stay in `hermes_platform/time.py`. |

Root after the split: `setup.py`, the three compatibility shims `hermes_constants.py`,
`hermes_state.py`, and `utils.py`, plus `hermes_bootstrap.py`. The bootstrap stays at the root
because it runs before import-path hardening, resolves the repository root from its own
`__file__`, and is the interrupted-update recovery entry point. It is not a shim.

## Dependency rules

- `hermes_platform` imports only `hermes_types`. During the migration it may import the root
  shims; remove that allowance in Phase 8. The startup watchdog's fire-time home resolver is
  one of those temporary imports; Phase 8 injects it from the arm sites.
- `hermes_store` imports `hermes_types`, `hermes_config`, and `hermes_platform`, plus its own
  subpackages. It must not import `agent`, `gateway`, `tools`, `cron`, `tui_gateway`,
  `hermes_cli`, or `plugins`.
- Surface packages call into the store. The store never calls a surface.
- Domain concerns enter the store through small protocols in `hermes_store/api.py`:
  session activity, compression markers, transcript repair, media admission, process identity,
  gateway status, and lifecycle hooks.
- State modules must not import the root `hermes_state` facade. Shared types go to
  `hermes_store/api.py`; the facade only re-exports.
- Every phase ends with `python3 scripts/check` and targeted tests. Do not start the next phase
  with a red check.
- Do not add root modules. Do not weaken `PACKAGE_LAYERS` to make a move pass. Add a protocol or
  split the module instead.

## Phase 0: Baseline

0a. Confirm `git status` is clean and `git log --oneline -1` records the starting commit.
0b. Run `python3 scripts/check --only ruff,health` and record the allowed findings.
0c. Run the inventory in Appendix A. Do not edit this plan with the result.

Exit criteria:

- The baseline is known.
- The full check is green.

## Phase 1: Break the facade cycle

The root `hermes_state.py` facade is imported by state siblings. That is a cycle and it keeps
the facade load-bearing.

1a. Inventory every state-module import of the facade:
   `rg -n 'from hermes_state import|import hermes_state\\b' hermes_state_*.py`.
1b. Move the shared types and protocols those imports need into `hermes_store/api.py`.
   Prefer `TYPE_CHECKING` imports for annotations and explicit protocols for callbacks.
1c. Replace each state-module facade import with `hermes_store.api` or an injected argument.
1d. Make the root `hermes_state.py` a thin re-export of `hermes_store.api`.
1e. Run the state tests and the code-health check.

Exit criteria:

- No `hermes_state_*` module imports `hermes_state`.
- `hermes_state.py` contains no SQL and no state-machine logic.
- State tests pass.

## Phase 2: Split `hermes_state_common`

`hermes_state_common` is the central hub. Its back-edges are:

- `agent.context_compressor`
- `agent.skill_commands`
- `hermes_cli.config`
- `hermes_cli.lifecycle`
- `hermes_cli.timefmt`

2a. Move epoch coercion and time formatting to `hermes_store/common/time.py`. Replace the
   `hermes_cli.timefmt` imports.
2b. Move SQL helpers, placeholders, title sources, and file identity to `hermes_store/common/`.
2c. Move skill-invocation formatting to `hermes_store/common/skills.py`. If the behavior needs
   agent data, take it as arguments instead of importing `agent`.
2d. Move compression marker constants to `hermes_store/common/compression.py` or
   `hermes_store/types.py`. Inject the compressor behavior.
2e. Move lifecycle hook invocation behind a `LifecycleHooks` protocol in
   `hermes_store/api.py`; implement it in `hermes_cli` or `agent`.
2f. Keep `hermes_state_common` only as a re-export shim, then delete it.

Exit criteria:

- No import of `agent` or `hermes_cli` from the common cluster.
- `hermes_state_common` is gone.
- State tests pass.

## Phase 3: Sessions and messages

Cluster: `sessions`, `messages`, `identity`, `titles`, `timeline`, `api_content`,
`detached_results`, `sessions_model_config`, `usage`, `telegram`.

Back-edges:

- `messages` imports `agent.agent_runtime_helpers`, `agent.context_compressor`,
  `agent.memory_context`, `agent.message_metadata`, `agent.message_sanitization`,
  `agent.transcript_repair`, `hermes_cli.timefmt`, and the facade.
- `sessions` imports `agent.session_activity` and the facade.
- `identity`, `titles`, `timeline`, and `detached_results` import message and compression
  helpers from `agent`.
- `telegram` depends on the common hub.

3a. Move message metadata, sanitization, and memory-context helpers into
   `hermes_store/sessions/messages.py` or `hermes_types/messages.py`. Keep pure shape logic in
   the lower layer.
3b. Replace compression markers and activity reads with the protocols from Phase 1.
3c. Move title and timeline projections into `hermes_store/sessions/` and keep display-only
   formatting in the surfaces.
3d. Move Telegram topic state to `hermes_store/adapters/telegram.py`; it must not import
   `gateway`.
3e. Move `sessions_model_config` and `usage` once their dependencies are in `hermes_store`.

Exit criteria:

- No `agent` or `gateway` imports in the cluster.
- The root facade still exposes the public session API.
- Session, message, and Telegram tests pass.

## Phase 4: Mutations

Cluster: `mutations`, `mutation_binding`, `mutation_branch`, `mutation_chat_pick`,
`mutation_compress`, `mutation_guards`, `mutation_prepared`, `mutation_reset`,
`mutation_retirement`, `mutation_transcript`.

Back-edges:

- `gateway.session`, `gateway.config`, `gateway.session_lifecycle`, `gateway.session_identity`
- `agent.context_compressor`
- The facade.

4a. Define a `MutationHooks` protocol in `hermes_store/api.py` for session identity, config
   snapshot, lifecycle events, and branch selection.
4b. Implement the protocol in `gateway` and pass it to the store.
4c. Move the pure mutation state machines into `hermes_store/mutations/`.
4d. Keep transcript-specific repairs in `hermes_store/sessions/` and call them from the
   mutation layer.

Exit criteria:

- No `gateway` or `agent` imports in the mutation cluster.
- Mutation tests pass.
- The root facade exposes the same mutation methods.

## Phase 5: Compression, search, repair, runtime, media, domain adapters

This phase is one cluster per commit, in this order:

5a. Compression: `compression`, `rewind`, `prune_rewrite`, `worker_compression`.
   Inject the compressor, compaction display, and conversation archive. Move pure rewind and
   retention logic to `hermes_store/compression/`.
5b. Search: `search`, `fts`. Move the pure index and query builders to `hermes_store/search/`.
   Skill context becomes an argument.
5c. Repair: `repair`, `reconcile`, `coverage`, `profile_repair`, `maintenance`, `portability`,
   `local_lineage`, `local_migration`. Inject gateway status, ownership, and SQLite safe-read
   probes. Move pure recovery and migration logic to `hermes_store/repair/`.
5d. Runtime: `runtime`, `runtime_workers`, `worker_context`, `worker_lifecycle`, `readpool`,
   `lockowners`. Inject process identity and session activity. Move pure runtime bookkeeping to
   `hermes_store/runtime/`.
5e. Media: `media`. Inject gateway media admission and tool spillover storage. Move reference
   bookkeeping to `hermes_store/media/`.
5f. Domain adapters: `terminal`, `todo`, `gateway`. Move terminal state and todo persistence to
   `hermes_store/adapters/`, or to the owning surface if the state is not session-shaped. The
   gateway process probe must not stay in the store.

Exit criteria for each commit:

- The cluster has no imports of `agent`, `gateway`, `tools`, or `hermes_cli`.
- The cluster's tests pass.
- `python3 scripts/check --only health` is green.

## Phase 6: Move the remaining state modules

6a. Create the `hermes_store` subpackages from the target table.
6b. Move the now-uncoupled modules with plain filesystem moves and import rewrites.
6c. Add `MOVED_MODULES` entries for each moved module so late imports keep their credit.
6d. Update the root `hermes_state.py` facade to re-export `hermes_store/api.py`.
6e. Delete the root `hermes_state_*` files. Keep only `hermes_state.py`.
6f. Shrink the `ROOT_MODULE` allowlist. Update `MOVED_MODULES` only when a base revision no
   longer needs an entry.

Exit criteria:

- `ls hermes_state_*.py` shows only `hermes_state.py`.
- The facade is under 300 lines.
- The state tests and the full code-health check pass.

## Phase 7: Cross-cutting utilities

Do these after the state split. The state modules import `hermes_constants` and `utils`; moving
the utilities first would force a second import rewrite.

7a. `hermes_yaml` is a clean leaf. Move it to `hermes_platform/yaml.py` first. Keep a root
   alias shim only if the updater surface requires it (it does not today).
7b. `utils` has back-edges:
   - `utils.py:200` imports `agent.retry_utils`.
   - `utils.py:485` and `:555` import `hermes_cli.config`.
   Move the retry helper to `hermes_platform/retry.py` or `hermes_types`, move the config read
   helper to `hermes_config`, then move `utils` to `hermes_platform/utils.py` with a root alias
   shim.
7c. `hermes_constants` has back-edges:
   - `hermes_cli._subprocess_compat` at line 529.
   - `pm` at lines 587 and 612.
   - `pm.environments` at lines 1364, 1416, and 1431.
   - `hermes_constants_scratch` at line 1004.
   Split the path, home, profile, root, and secure-directory helpers into
   `hermes_platform/constants.py`. Move install detection and PM environment lookups to `pm` or
   `hermes_cli` adapters and pass the results in. The scratch import becomes
   `hermes_platform.scratch` after 7f. Keep the root `hermes_constants.py` alias shim.
7d. `hermes_logging` has back-edges:
   - `agent.redact` at lines 175, 390, and 434.
   - `hermes_cli.config` at line 472.
   - `hermes_cli.config_effective` at line 1030.
   Move handlers, rotation, and queue plumbing to `hermes_platform/logging.py`. Define a
   `Redactor` protocol and inject the agent implementation, or move redaction to
   `hermes_platform/redact.py` if it has no agent dependencies. Pass config snapshots in
   instead of reading config.
7e. `hermes_time` has back-edges:
   - `agent.secret_scope` at line 71.
   - `hermes_cli.config_effective` at line 94.
   Move the pure clock, timezone conversion, and formatting to `hermes_platform/time.py`.
   Put config-backed timezone resolution in `hermes_config/time.py`, or inject a
   `TimezoneSource`.
7f. Scratch has back-edges:
   - `hermes_cli.process_identity` at line 185.
   - `gateway.status` at line 212.
   Move retention and reaping to `hermes_platform/scratch.py`. Inject `is_live_process` and
   gateway status callbacks. Move the pure `hermes_constants_scratch_stuck` helpers with it.
7g. Delete the root utility implementations and leave the three compatibility shims plus
   `hermes_bootstrap.py`.

Exit criteria:

- `hermes_platform` has no imports of `agent`, `gateway`, `tools`, or `hermes_cli`.
- The utility implementations are out of the root. Only the entry-point modules scheduled for
  Stage 3.5, `setup.py`, the three shims, and `hermes_bootstrap.py` remain.
- The three root shims are aliases, not copies.
- Full `scripts/check` passes.

## Phase 8: Tighten the guardrails

8a. Remove `ROOT_PACKAGE` from the `hermes_platform` and `hermes_store` allowed sets once their
   callers import package paths.
8b. Remove the temporary `# health: allow` waivers. Inject the startup watchdog's home
   resolver from the arm sites so its fire-time root import can go too.
8c. Remove `MOVED_MODULES` entries whose old paths no longer exist in any supported base
   revision.
8d. Update `PACKAGE_LAYERS` to the final table:
   - `hermes_platform` imports `hermes_types`.
   - `hermes_config` imports `hermes_types`, `hermes_platform`.
   - `hermes_store` imports `hermes_types`, `hermes_config`, `hermes_platform`.
   - `hermes_providers` imports `hermes_types`, `hermes_config`, `hermes_platform`.
   - `agent`, `gateway`, `tools`, `cron`, `plugins` import the lower layers they need.
   - Surfaces may import inward.
8e. Set the `ROOT_MODULE` allowlist to `setup.py`, `hermes_constants.py`, `hermes_state.py`,
   `utils.py`, and `hermes_bootstrap.py`.
8f. Update the root `AGENTS.md` routing table and `hermes_platform/AGENTS.md`.

Exit criteria:

- `python3 scripts/check` passes with no migration allowances.
- A synthetic new root module fails `ROOT_MODULE`.
- A synthetic new layer violation fails `LAYER_VIOLATION`.

## Verification

Run these after each phase:

- `python3 scripts/check` for every blocking lint check.
- `python3 scripts/check --only health` for the ratchet output and allowed findings.
- `scripts/run_tests.sh tests/hermes_state/ tests/scripts/test_code_health_imports.py`.
- `scripts/run_tests.sh tests/ci/test_update_ci_routing.py` after moving a module that the update
  transaction imports.
- Import smoke for the moved package:
  `scripts/run-in-hermes-env python3 -c "import hermes_store, hermes_platform.logging"`.

Inspect the graph directly when a move is rejected:

```python
from pathlib import Path
from scripts.code_health import gitio
from scripts.code_health.imports import _graph_paths, build_graph

repo = Path.cwd()
base = gitio.default_base(repo, "HEAD")
paths = _graph_paths(repo, base)
graph = build_graph(paths, gitio.read_files(repo, base, paths))
print(graph.cycle_edges)
print(sorted((ref.source_pkg, ref.target_pkg, ref.target_module) for ref in graph.refs))
```

## Risks and mitigations

- A split changes behavior. Mitigation: one cluster per commit, behavior tests before and after,
  no schema changes in the same commit.
- A protocol becomes a god interface. Mitigation: small per-cluster protocols, implemented by the
  surface that owns the behavior.
- A move reintroduces a cycle. Mitigation: the ratchet blocks it; split further instead of
  weakening `PACKAGE_LAYERS`.
- Test patch seams break. Mitigation: alias moved modules in the old import path only when the
  updater surface requires it; otherwise update the patch target to the new module and keep the
  same module object.
- The facade stays load-bearing. Mitigation: Phase 1 is mandatory before any bulk move.

## Bootstrap for a fresh session

This plan is standalone. It contains the current inventory, the target layout, the back-edge
evidence, the phase order, and the verification commands. A fresh session can start here.

1. Read this file and `docs/plans/PLAN-architecture-reset.md`.
2. Run `git status`, `git log --oneline -10`, and `ls -1 *.py | wc -l`.
3. Run `python3 scripts/check --only ruff,health`.
4. Run the inventory in Appendix A if HEAD is newer than `8b7262cba3`; the file list will tell
   you what already moved.
5. Start at the first phase whose exit criteria are not met. Do not re-derive the architecture
   from the conversation.
6. Commit one phase-sized unit at a time and stop after each commit lands.

Assumptions:

- The repository still uses `scripts/check`, `scripts/run_tests.sh`, and the code-health
  ratchet described in `AGENTS.md`.
- The root compatibility shims remain required by `tests/compat/old_updater_surface.json`.
- The current branch has the commits through `8b7262cba3`. If the branch was rebased, re-run the
  inventory and compare.

## Appendix A: State module inventory at the baseline

### Seed-coupled modules

| Module | Back-edges |
|---|---|
| `hermes_state_common` | `agent.context_compressor`, `agent.skill_commands`, `hermes_cli.config`, `hermes_cli.lifecycle`, `hermes_cli.timefmt` |
| `hermes_state_compression` | `gateway.session_policy`, facade |
| `hermes_state_coverage` | `agent.context_compressor`, `agent.conversation_compression_archive`, `gateway.message_timestamps`, `hermes_cli.timefmt` |
| `hermes_state_dbfile` | `hermes_cli.backup`, `hermes_cli.sqlite_safe_read`, facade |
| `hermes_state_detached_results` | `agent.message_metadata` |
| `hermes_state_gateway` | `hermes_cli.dashboard_procs`, facade |
| `hermes_state_identity` | `agent.message_metadata`, `agent.message_sanitization` |
| `hermes_state_local` | `agent.session_client_env`, `gateway.session_policy` |
| `hermes_state_maintenance` | facade |
| `hermes_state_media` | `gateway.session_ingress_media`, `tools.tool_result_storage` |
| `hermes_state_messages` | `agent.agent_runtime_helpers`, `agent.context_compressor`, `agent.memory_context`, `agent.message_metadata`, `agent.message_sanitization`, `agent.transcript_repair`, `hermes_cli.timefmt`, facade |
| `hermes_state_mutation_binding` | `gateway.session_identity` |
| `hermes_state_mutation_branch` | `gateway.config`, `gateway.session`, `gateway.session_lifecycle` |
| `hermes_state_mutation_reset` | `gateway.session`, `gateway.session_lifecycle` |
| `hermes_state_mutations` | `agent.context_compressor` |
| `hermes_state_portability` | `agent.skill_commands`, `hermes_cli.timefmt` |
| `hermes_state_profile_repair` | `gateway.session` |
| `hermes_state_prune_rewrite` | `agent.context_compressor`, `agent.conversation_compression_archive`, `agent.message_metadata`, `agent.transcript_repair` |
| `hermes_state_readpool` | facade |
| `hermes_state_reconcile` | `gateway.runtime_ownership`, `gateway.status`, `hermes_cli.sqlite_safe_read` |
| `hermes_state_registry` | facade |
| `hermes_state_repair` | `hermes_cli.config`, `hermes_cli.sqlite_safe_read`, facade |
| `hermes_state_rewind` | `agent.context_compressor`, `agent.message_content`, `agent.message_metadata`, `agent.session_persistence` |
| `hermes_state_runtime` | `agent.conversation_compression_archive`, `agent.message_metadata`, `gateway.session_policy`, `hermes_cli.sqlite_safe_read`, facade |
| `hermes_state_search` | `agent.context_compressor`, `agent.skill_commands` |
| `hermes_state_sessions` | `agent.session_activity`, facade |
| `hermes_state_terminal` | `agent.turn_context` |
| `hermes_state_timeline` | `agent.compaction_display`, `agent.context_compressor` |
| `hermes_state_titles` | `agent.message_sanitization`, facade |
| `hermes_state_todo` | `tools.todo_tool` |
| `hermes_state_wal` | `hermes_cli.config`, `hermes_cli.sqlite_runtime` |
| `hermes_state_worker_compression` | `hermes_cli.goals`, `hermes_cli.heartbeat`, `hermes_cli.loops`, facade |
| `hermes_state_worker_lifecycle` | `agent.session_activity` |

### Modules blocked by a coupled dependency

| Module | Blocking dependencies |
|---|---|
| `hermes_state_api_content` | `hermes_state_messages` |
| `hermes_state_fts` | `hermes_state_common` |
| `hermes_state_holders` | `hermes_state_registry` |
| `hermes_state_local_lineage` | `hermes_state_compression`, `hermes_state_local`, `hermes_state_local_migration`, `hermes_state_mutation_guards`, `hermes_state_runtime` |
| `hermes_state_local_migration` | `hermes_state_compression`, `hermes_state_mutation_binding`, `hermes_state_mutation_guards`, `hermes_state_runtime` |
| `hermes_state_lockowners` | `hermes_state_holders` |
| `hermes_state_mutation_chat_pick` | `hermes_state_runtime` |
| `hermes_state_mutation_compress` | `hermes_state_mutation_prepared`, `hermes_state_worker_compression` |
| `hermes_state_mutation_guards` | `hermes_state_common`, `hermes_state_compression`, `hermes_state_local`, `hermes_state_local_lineage`, `hermes_state_mutation_binding`, `hermes_state_runtime`, `hermes_state_sessions` |
| `hermes_state_mutation_prepared` | `hermes_state_local`, `hermes_state_local_lineage`, `hermes_state_mutation_guards`, `hermes_state_runtime` |
| `hermes_state_mutation_retirement` | `hermes_state_local`, `hermes_state_media`, `hermes_state_mutation_guards`, `hermes_state_runtime`, `hermes_state_terminal` |
| `hermes_state_mutation_transcript` | `hermes_state_messages` |
| `hermes_state_runtime_workers` | `hermes_state_compression`, `hermes_state_local`, `hermes_state_local_lineage`, `hermes_state_runtime`, `hermes_state_sessions` |
| `hermes_state_schema` | `hermes_state_common`, `hermes_state_fts`, `hermes_state_holders`, `hermes_state_search`, `hermes_state_titles` |
| `hermes_state_sessions_model_config` | `hermes_state_common`, `hermes_state_sessions` |
| `hermes_state_telegram` | `hermes_state_common` |
| `hermes_state_usage` | `hermes_state_worker_lifecycle` |
| `hermes_state_worker_context` | `hermes_state_runtime` |

### Cross-cutting utility back-edges

| Module | Back-edges |
|---|---|
| `hermes_constants` | `hermes_cli._subprocess_compat` (529), `pm` (587, 612), `pm.environments` (1364, 1416, 1431), `hermes_constants_scratch` (1004) |
| `hermes_logging` | `agent.redact` (175, 390, 434), `hermes_cli.config` (472), `hermes_cli.config_effective` (1030) |
| `hermes_time` | `agent.secret_scope` (71), `hermes_cli.config_effective` (94) |
| `hermes_constants_scratch` | `hermes_cli.process_identity` (185), `gateway.status` (212) |
| `hermes_constants_scratch_stuck` | none |
| `utils` | `agent.retry_utils` (200), `hermes_cli.config` (485, 555) |
| `hermes_yaml` | none |

## Appendix B: Inventory commands

```bash
ls -1 hermes_state_*.py | sort
rg -n 'from hermes_state import|import hermes_state\b' hermes_state_*.py
rg -n '^\s*(from|import) (agent|gateway|tools|hermes_cli|cron|tui_gateway|plugins|pm|providers|acp_adapter)\b' hermes_state_*.py
rg -n '^(from|import) (agent|gateway|tools|hermes_cli|cron|tui_gateway|plugins|pm|providers|acp_adapter)\b' hermes_constants.py hermes_logging.py hermes_time.py hermes_constants_scratch.py hermes_constants_scratch_stuck.py utils.py hermes_yaml.py
```

The dependency closure used to classify the 51 modules is a small AST walk: any import of a
surface package, the facade, or a coupled state module keeps the module at the root until the
dependency is split.

## Appendix C: Definition of done

- No `hermes_state_*` siblings at the root; only `hermes_state.py`.
- `hermes_store` owns the state layer behind `hermes_store/api.py`.
- `hermes_platform` owns the pure constants, logging, time, YAML, filesystem, and scratch core.
- The root has `setup.py` plus three alias shims.
- `PACKAGE_LAYERS` has no `ROOT_PACKAGE` allowance for packages.
- `MOVED_MODULES` has no entries whose old paths are gone from supported bases.
- `ROOT_MODULE` allowlist is four files.
- `python3 scripts/check` is green with no migration waivers.
