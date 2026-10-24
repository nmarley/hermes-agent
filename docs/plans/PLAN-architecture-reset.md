# Architecture Reset and Rust Beachhead

## Intent

Make Hermes maintainable by enforcing boundaries first, then adopt Rust only where it buys
operational properties that matter, without breaking the plugin ecosystem or user-visible
behavior.

This is a design and sequencing document, not a progress tracker. It defines the target
architecture, the order of work, and the gates that must pass before each irreversible step.
Progress lives in git history and the working conversation, never in this file.

## Why now

Hermes works, but the codebase has outgrown its organization. The symptoms are structural,
not cosmetic:

- ~956k lines of production Python in 2,648 files, plus ~1.5M lines of tests in 7,081 files.
- 26 messaging platforms, 42 model providers, four frontends, 210 skills.
- `gateway/` contains 326 Python files: 120 `session_*` and 45 `run_*`.
- `hermes_state` is a facade over roughly 10 mixins and 59 siblings.
- `hermes_cli` is 295k lines, larger than `agent`, `tools`, or `gateway`.
- 5,479 cross-package imports sit inside functions, versus 822 at module top level. That is
  the cycle-dodge.
- Cycles: `agent <-> hermes_cli` (524/684), `gateway <-> hermes_cli` (546/359),
  `agent <-> tools` (194/351), `gateway <-> tools` (272/123).
- No `mypy`, `pyright`, or `py.typed`; 10,936 lines mention `Any`.
- Four rendering surfaces and two theme systems. The theme list is manually mirrored between
  Python and TS.
- The code-health ratchet caps file size and suggests moving code to a "topical sibling."
  The sibling explosion is the incentive working as designed.
- Tests are exempt from the ratchet. One test file is 22,391 lines.

The problem is not that the team cannot engineer. The guardrails are real. The problem is
that engineering effort went into local correctness and guardrails, not into dependency
direction and domain boundaries. The same accretion pattern appears in code, tests, themes,
and docs, which is why the plan treats them as one system.

## Goal

1. A codebase with an enforced dependency DAG and explicit public APIs.
2. A product with one design-token source and consistent surfaces.
3. A test suite that proves behavior contracts without mirroring implementation.
4. A Rust beachhead for the operational wins that matter: single binary, startup, memory,
   concurrency, cancellation, and crash isolation.
5. A decision gate before any full-core rewrite.

## Non-goals

- No big-bang rewrite. No full Rust core in this plan's committed scope.
- No user-facing behavior changes, feature work, or visual redesign.
- No plugin API break without a compatibility bridge and deprecation window.
- No new core tools or platform adapters.
- No database schema rewrite. Migrations only.
- No change to the prompt-caching invariant, message-flow invariants, or profile isolation.

## Principles

- Boundaries before language.
- Protocol first, then implementation.
- Strangler fig, not big bang.
- Parity before deletion.
- One source of truth per concept.
- No ambient state. Pass profile and config explicitly.
- Ratchet the graph, not just file size.
- The lowest rung that solves the problem wins.
- Every stage leaves the tree green and committable.

## Target architecture

Python packages use underscores. Rust crates use hyphens.

### Python interim DAG

New packages:

- `hermes_types`: ids, message model, errors, protocols. No internal imports.
- `hermes_config`: config load and merge, profiles, secret references.
- `hermes_providers`: model catalog, auth, provider profiles, wire adapters.
- `hermes_store`: SQLite repositories, migrations, FTS, leases.
- `hermes_plugins`: plugin manifest, discovery, public plugin API.

Existing packages keep their names initially:

- `agent`: turn loop, context, compression, memory, delegation.
- `tools`: tool registry and built-ins.
- `gateway`: session service, platform supervisor, adapters.
- `cron`: scheduler.
- `hermes_cli`, `tui_gateway`: surfaces.
- `pm`: environment and dependency manager.
- `hermes_platform`: host paths, constants, YAML and file I/O, logging, time, executable lookup.

Root `.py` files are compatibility shims only. The final allowlist is `setup.py`,
`hermes_constants.py`, `hermes_state.py`, and `utils.py`; the last three replace themselves in
`sys.modules` so the old path and the new module are one object.

Allowed edges:

- `hermes_types` -> nothing internal.
- `hermes_platform` -> `hermes_types`.
- `hermes_config` -> `hermes_types`, `hermes_platform`.
- `hermes_providers` -> `hermes_types`, `hermes_config`, `hermes_platform`.
- `hermes_store` -> `hermes_types`, `hermes_config`.
- `hermes_plugins` -> `hermes_types`, `hermes_config`, `hermes_providers`.
- `agent` -> `hermes_types`, `hermes_config`, `hermes_providers`, `hermes_store`,
  `hermes_plugins`, `tools`.
- `tools` -> `hermes_types`, `hermes_config`, `hermes_store`.
- `gateway` -> `hermes_types`, `hermes_config`, `hermes_providers`, `hermes_store`,
  `hermes_plugins`, `agent`, `tools`.
- `cron` -> `hermes_types`, `hermes_config`, `hermes_store`, `agent`, `gateway`.
- `hermes_cli`, `tui_gateway` -> any package. Surfaces depend inward.
- No package imports `hermes_cli` or `tui_gateway` except another surface.

This table is the contract. The code-health checker enforces it.

Tool handlers receive a `ToolContext` protocol defined in `hermes_types`. They do not import
`agent`. Provider adapters receive request and stream protocols from `hermes_types`. They do
not import `agent` or `gateway`.

### Rust end state

Crates:

- `hermes-types`
- `hermes-config`
- `hermes-store`
- `hermes-provider`
- `hermes-agent`
- `hermes-tools`
- `hermes-gateway`
- `hermes-rpc`
- `hermes-plugins`
- `hermes-cron`
- `hermes-cli`, `hermes-tui`, `hermesd`

Only the beachhead crates are in the committed scope: `hermes-rpc`, `hermesd`, `hermes-tui`,
`hermes-store`. The rest are exercised after the decision gate.

## Work plan

### Stage 1: Freeze the seams and add graph guardrails

1a. Add an evidence snapshot to this document's appendix. Do not add a live dashboard.
1b. Extend `scripts/code_health` with three rules:
   - `LAYER_VIOLATION`: forbidden package edges from the table above.
   - `IMPORT_CYCLE`: no new cycles between top-level packages. Existing cycles get a frozen
     count that can only go down.
   - `LATE_IMPORT`: count function-level cross-package imports. Ratchet down.
1c. Update `METRIC_FIX` so the remedy for a large file is "extract a domain subpackage or a
   public API," not "move it to a sibling."
1d. Add `docs/plans/` to the docs layout and link this plan from the root `AGENTS.md` routing
   table.
1e. Run `python scripts/check` and record the baseline in the appendix.

Exit criteria:

- The checker fails on a synthetic forbidden edge and a synthetic cycle.
- The baseline is committed.
- No production code changes.

### Stage 2: Extract config, auth, and model resolution

2a. Create `hermes_config` from `hermes_cli/config.py`, `config_defaults.py`, path helpers,
   profile loading, and YAML merge.
2b. Create `hermes_providers` from `hermes_cli/auth.py`, `providers.py`, `models.py`,
   `models_pricing.py`, `model_normalize.py`, `route_identity.py`, `runtime_provider.py`, and
   `anon_auth.py`.
2c. Keep `hermes_cli.config` and friends as compatibility shims that re-export the new
   modules. No caller changes in this stage.
2d. Move `hermes_cli.sqlite_util` to `hermes_store.sqlite`.
2e. Move `hermes_cli.process_identity` to `hermes_platform.process`.
2f. Update `agent`, `gateway`, `tools`, `cron`, and `tui_gateway` to import the new packages
   directly.
2g. Delete the shims only after the import graph is clean.

Exit criteria:

- `agent`, `gateway`, `tools`, `cron`, and `tui_gateway` import zero `hermes_cli` modules.
- The `agent <-> hermes_cli` and `gateway <-> hermes_cli` cycles are gone.
- All tests pass with no behavior changes.

### Stage 2.5: Package the leaf root modules

The repository root holds 80 Python files, and most of them are not entry points. This stage
moves the low-level utilities every package imports. It comes before the state move so the
state modules re-point their imports once.

2.5a. Create `hermes_platform` modules for host paths and low-level I/O: `constants` from
   `hermes_constants.py`, `utils` from `utils.py`, `yaml` from `hermes_yaml.py`, `fs` from
   `hermes_dir_acl.py`, `logging` from `hermes_logging.py`, and `time` from `hermes_time.py`.
2.5b. Move the scratch-cache helpers in `hermes_constants_scratch*.py` into
   `hermes_platform/scratch.py`.
2.5c. Keep root alias shims for the old-updater surface: `hermes_constants.py` and `utils.py`
   replace themselves in `sys.modules`, so the old path and the new path are one module object.
2.5d. Update production imports with a codemod. Update `PACKAGE_LAYERS` so `hermes_platform`
   imports only `hermes_types`, and `hermes_config` may import `hermes_platform`.
2.5e. Add a `ROOT_MODULE` code-health rule with a frozen allowlist of the remaining root
   Python files. A new root `.py` file fails. Each later stage removes the files it moves.
2.5f. Run `python scripts/check` and the config, tools, and state tests.

Exit criteria:

- The leaf utilities live in `hermes_platform`; the root shims are aliases, not copies.
- `ROOT_MODULE` fails on a synthetic new root module.
- No behavior changes.

### Stage 3: Split the state layer into repositories

3a. Create `hermes_store` with submodules: `schema`, `migrations`, `sessions`, `messages`,
   `usage`, `leases`, `search`, `compression`, `maintenance`, `errors`.
3b. Replace the mixin assembly in `hermes_state.py` with composition. `hermes_state.py`
   remains a thin compatibility facade.
3c. Move inline schema creation to versioned SQL migrations. Keep the existing schema version
   and migration semantics.
3d. Introduce typed row models at the repository boundary. No raw dicts across the boundary.
3e. Keep the existing WAL, read-pool, lock-guard, and recovery behavior. This stage is a move,
   not a redesign.
3f. Add repository tests for transactions, leases, FTS, and recovery.
3g. Add `LATE_IMPORT` exemptions only for the compatibility facade, with a removal target.

Exit criteria:

- No new code imports `hermes_state_*` siblings.
- `hermes_state.py` is under 300 lines and contains no SQL.
- Schema changes are migration files, not code paths.
- The state tests pass unchanged.

### Stage 3.5: Package the entry points and facades

3.5a. Move `run_agent.py` into `agent/` after Stage 2 has removed its `hermes_cli` imports. Keep
   a root alias shim for one release, then delete it.
3.5b. Move `cli.py` into `hermes_cli/`. The `hermes` console entry point stays on
   `hermes_cli.main:main`.
3.5c. Move `model_tools.py`, `toolsets.py`, and `toolset_distributions.py` into `tools/` once
   the graph allows their imports there.
3.5d. Move `hermes_bootstrap.py`, `hermes_startup_watchdog.py`, and
   `registration_lifecycle.py` into `hermes_cli/`.
3.5e. Move `batch_runner.py`, `mini_swe_runner.py`, and `trajectory_compressor.py` into
   `hermes_cli/runners/`.
3.5f. Shrink the `ROOT_MODULE` allowlist after each move. The final allowlist is `setup.py`
   plus the three compatibility shims.
3.5g. Update `pyproject.toml`, `setup.py`, the updater compatibility surface, and docs paths in
   the same change as each move.

Exit criteria:

- `ls *.py` at the root shows only `setup.py` and the three alias shims.
- `ROOT_MODULE` passes.
- Console entry points and updater compatibility still work.

### Stage 4: Reorganize the gateway by domain

4a. Create subpackages: `gateway/session/`, `gateway/run/`, `gateway/runtime/`,
   `gateway/platforms/`.
4b. Move `session_*` modules into `gateway/session/` by subdomain: lifecycle, admission,
   routing, persistence, controls, hosted.
4c. Move `run_*` modules into `gateway/run/` by phase: bootstrap, inbound, turn, delivery,
   shutdown.
4d. Move runtime and status modules into `gateway/runtime/`.
4e. Give each subpackage an `__init__.py` with a small public API. Internal modules are
   private by convention and by the checker.
4f. Keep `gateway/run.py` as the composition root and public entry point.
4g. Ban new flat `gateway/*_*.py` siblings. New behavior goes into a domain subpackage.

Exit criteria:

- `gateway/` has no more than 20 flat Python modules.
- Each subpackage has a documented public API.
- The gateway tests pass with import rewrites only.

### Stage 5: Consolidate platform adapters

5a. Define `PlatformAdapter` in `gateway/platforms/base.py` with explicit methods: `start`,
   `stop`, `send`, `receive`, `resolve_target`, `health`, `capabilities`.
5b. Move shared behavior into the base: reconnect and backoff, rate limits, dedup, token
   locks, chunking, media transfer, webhook verification, profile scope, metrics.
5c. Group adapters by transport: webhook, long-poll, socket, email, SMS.
5d. Build a shared conformance suite with a fake platform server. Every adapter must pass:
   auth failure, reconnect, inbound text, inbound media, send text, send media, edit, delete,
   reactions, threads, rate limit, shutdown, profile isolation.
5e. Port the highest-traffic adapters first: Telegram, Discord, Slack, Teams, WhatsApp.
5f. Delete duplicated code only after the conformance suite is green.
5g. Do not add new platforms during this stage.

Exit criteria:

- Every ported adapter passes the same conformance suite.
- Shared base coverage is measured and increasing.
- No adapter imports `hermes_cli` or `agent` internals.

### Stage 6: Reset the test strategy

6a. Classify tests: unit, contract, integration, e2e, replay. Add markers and a default fast
   lane.
6b. Replace mock-heavy adapter tests with the conformance suite and fake servers.
6c. Replace change-detector tests with behavior contracts at public APIs.
6d. Split test files over 2,000 lines by behavior, not by line count.
6e. Add golden fixtures for provider streams and turn events. Scrub secrets.
6f. Add a flaky-test quarantine and a runtime budget for the default lane.
6g. Add a coverage floor for the new packages, not the whole tree.

Exit criteria:

- No test file over 2,000 lines.
- The default lane runs within its budget.
- The fake-server harness is the standard for adapters.
- New packages have contract tests.

### Stage 7: Unify design tokens

7a. Create one token source: palette, typography, spacing, radius, motion. Use `apps/shared`
   as the source of truth.
7b. Generate CSS variables, TS types, Python theme maps, and Rust constants from the source.
7c. Remove the manually mirrored theme list in `hermes_cli/web_server.py` and
   `web/src/themes/presets.ts`.
7d. Make desktop and web share components where the interaction model matches. Keep
   terminal-specific rendering in the TUI.
7e. Add visual regression tests for web and desktop. Add TUI snapshot tests for semantic
   colors.
7f. Audit hardcoded colors outside the token source.

Exit criteria:

- One token source. No handwritten theme list in Python.
- No hardcoded hex outside the token source and tests.
- Theme parity tests cover web, desktop, TUI, and CLI skins.

### Stage 8: Freeze the protocol and build fixtures

8a. Define `hermes-rpc` as JSON-RPC 2.0. Methods: session, turn, tool, config, plugin, and
   gateway status. Events: turn delta, tool call, turn done, session updated, gateway status.
8b. Make Rust types the source. Generate JSON Schema with `schemars`, TS with `ts-rs`, and
   Python models with `datamodel-code-generator`.
8c. Record golden fixtures: provider SSE streams, tool outputs, turn event sequences,
   cancellation, errors.
8d. Version the protocol. Add a compatibility test between the Python server and the
   generated clients.
8e. Add a protocol conformance test to CI.

Exit criteria:

- One schema generates all clients.
- The Python server passes the protocol conformance test.
- Golden fixtures cover success, tool call, cancellation, provider error, and compression.

### Stage 9: Build the Rust daemon

9a. Create `hermesd` with `tokio`: config loading, profile context, process supervision,
   health and metrics, HTTP and WebSocket server.
9b. Implement the session registry and lease manager in Rust over the existing SQLite
   database. Read-only first.
9c. Implement cron scheduling in Rust. Fire turns through RPC.
9d. Proxy turn execution to the Python agent over the protocol. Do not reimplement the loop.
9e. Add a config switch: `daemon.engine: python | rust`. Default remains Python.
9f. Add crash recovery, graceful shutdown, and cancellation tests.
9g. Ship behind the switch on one platform and one profile.

Exit criteria:

- The Rust daemon serves sessions, cron, and health with the Python agent behind it.
- No message loss on crash or restart.
- Startup and idle memory are measured against the Python gateway.
- The Python path remains the default.

### Stage 10: Build the Rust TUI

10a. Implement the TUI in `ratatui` against `hermes-rpc`.
10b. Match the existing keybindings, slash palette, streaming, tool timeline, and approval
   flows.
10c. Add a parity checklist and side-by-side screenshots for the main states.
10d. Ship behind `tui.engine: ink | rust`. Keep Ink until parity.
10e. Delete Ink only after the parity checklist and user acceptance.

Exit criteria:

- Feature parity for the main interactive flows.
- TUI startup and memory are measured.
- The Ink path remains available until the deletion commit.

### Stage 11: Move the store to Rust

11a. Implement `hermes-store` in Rust with `sqlx`, SQLite WAL, FTS5, and checked-in
   migrations.
11b. Open the existing database read-only. Serve session and message reads. Compare results
   with Python.
11c. Make Rust the only writer for new sessions. Python writes through RPC.
11d. Migrate old sessions with no schema change. Keep a rollback path.
11e. Add corruption, lock, and recovery tests that mirror the Python behavior.

Exit criteria:

- Shadow reads match on a representative sample.
- Dual-write windows have no divergence.
- Rollback is tested.
- The Python store is removed only after the parity gate.

### Stage 12: Parity gate

12a. Replay all golden fixtures against the Rust path.
12b. Run e2e for every supported platform, profile, and cancellation path.
12c. Run adapter conformance and store recovery tests.
12d. Measure startup, idle memory, turn overhead, and crash recovery.
12e. Verify plugin compatibility through the Python bridge.
12f. Record the go or no-go decision in the working conversation and the commit message. Do
   not mutate this plan to track it.

Exit criteria:

- All parity tests pass.
- No user-facing regression.
- The decision is recorded before any full-core work starts.

### Stage 13 and beyond: Optional full-core continuation

Only after a go decision:

- Port providers and the agent loop. Use the append-only transcript and differential replay.
- Port tools. Keep Python tools behind the plugin RPC.
- Port adapters one at a time behind conformance tests.
- Move desktop to Tauri or keep Electron after a visual-consistency review.
- Remove the Python core. Keep the Python plugin sidecar and `pm`.

## Risks and mitigations

- Boundary refactor stalls on cycles. Mitigation: extract leaves first, keep compatibility
  shims, ratchet the graph down, and allow no new cycles.
- Mechanical moves create huge diffs. Mitigation: one package per stage, import rewrites only,
  no behavior changes, and green tests after each move.
- Plugin compatibility breaks. Mitigation: versioned plugin API, out-of-process Python bridge,
  and a deprecation window.
- Rust scope creeps. Mitigation: beachhead only, decision gate, and no full core before
  parity.
- Behavior drift. Mitigation: golden fixtures, differential replay, e2e, and adapter
  conformance.
- Performance regressions. Mitigation: benchmarks for startup, turn latency, gateway
  throughput, and memory.
- Design drift returns. Mitigation: generated tokens, visual regression, and no handwritten
  theme lists.
- Contributor confusion. Mitigation: update `AGENTS.md`, docs, and codemods in the same stage.

## Metrics

Graph:

- Zero new cycles between top-level packages.
- `agent`, `gateway`, `tools`, and `cron` import zero `hermes_cli` modules.
- Function-level cross-package imports reduced by at least half.
- Existing cycles have a frozen count that only decreases.

Structure:

- `hermes_cli` under 100k lines.
- Root `.py` files: 80 at baseline, 4 at the end (`setup.py` plus three compatibility shims).
- No new root modules outside the `ROOT_MODULE` allowlist.
- Zero `hermes_state_*` siblings in new code.
- Fewer than 20 flat modules in `gateway/`.
- Every adapter passes the conformance suite.
- One design-token source, no handwritten theme list in Python.

Tests:

- No test file over 2,000 lines.
- Default lane within its runtime budget.
- Mock-heavy test files reduced by at least half.
- New packages have contract tests.

Rust:

- Daemon startup, idle RSS, binary size, and turn proxy overhead are benchmarked.
- Zero message loss on crash and restart.
- Parity gate passes before deletion.

## Open decisions

- Package naming: new top-level packages (`hermes_config`, `hermes_providers`, `hermes_store`)
  versus a single `hermes_core/` namespace. Recommendation: new top-level packages first.
  Root file placement is committed in Stages 2.5 and 3.5; a `src/hermes/` layout remains a
  separate plan.
- Whether `hermes_cli` remains a surface package or is renamed to `hermes_surfaces/cli`.
- Plugin RPC scope: tools and hooks first, memory and model providers next.
- Desktop: Tauri for footprint versus Electron for Chromium consistency. Recommendation:
  decide after the Rust TUI and daemon prove the protocol.
- `pm`: keep it in Python. It manages Python environments and has no reason to move.
- Whether the Rust daemon ever runs the agent in-process or always delegates to a sidecar.
  Recommendation: keep the sidecar boundary until the full-core gate.

## Appendix: baseline evidence

Package graph values are produced by `scripts/code_health/imports.py` on the baseline tree.

| Metric | Baseline |
|---|---|
| Tracked files | 20,799 |
| Production Python | ~956k lines, 2,648 files |
| Test Python | ~1.5M lines, 7,081 files |
| TS/TSX | ~1.07M lines |
| Messaging platforms | 26 |
| Model providers | 42 |
| Registered tools | ~55 |
| Toolset entries | 109 |
| Skills | 210 |
| `gateway/` Python files | 326 |
| `session_*` and `run_*` in `gateway/` | 120 and 45 |
| Root Python files | 80 |
| Root state files | 60 (`hermes_state.py` plus 59 siblings) |
| Other root Python files | 20 |
| `hermes_state` siblings | 59 |
| `hermes_cli` lines | 295k |
| Cross-package imports, function-level and top-level | 5,479 and 822 |
| Package graph files | 2,393 |
| Package graph refs | 6,889 |
| Package graph edges | 9 |
| Package graph cycles | 1 SCC, 9 packages, 59 internal edges |
| `agent <-> hermes_cli` | 524 / 684 |
| `gateway <-> hermes_cli` | 546 / 359 |
| `agent <-> tools` | 194 / 351 |
| `gateway <-> tools` | 272 / 123 |
| Type checker | none |
| Lines mentioning `Any` | 10,936 |
| Test files using mocks | 2,176 |
| Largest test file | 22,391 lines |
| Web unique hex colors | ~71 |
| TUI unique hex colors | ~165 |
