# Performance Budgets

## Problem

Hermes works, but it feels heavy, slow, and clunky to use. The repository holds
20,799 tracked files, 2.5M lines of Python (1.0M source, 1.5M tests), 1.07M
lines of TypeScript, and 57,745 commits. Perceived cost is spread across
startup, per-turn work, and TUI rendering, and nothing measures it from the
user's side.

The project already has measurements for outbound telemetry (bucketed and
opt-in) and a TUI frame profiler, but no local baseline, no regression gate,
and no agreed budget. "Feels slow" cannot be falsified, so fixes are guesses.

## Goal

Put five user-visible numbers on the felt cost, freeze them in a checked-in
baseline, and gate regressions in CI. Change no product behavior in this plan.

## Metrics

| Metric | Start | End | Budget |
|---|---|---|---|
| First paint | OS process start | First Ink frame | p95 <= 400ms |
| Cold start to prompt | OS process start | First frame after gateway ready and first session info | p95 <= 1.5s |
| Enter to visible | CR written | First frame that changes the transcript | p95 <= 100ms |
| Keystroke echo | Key written | Cell appears in the VT screen | p95 <= 33ms |
| Idle cost | Animation settle | 60s later | 0 polling frames, CPU < 1% per process |
| Per-turn overhead | CR written | Turn end | submit to wire <= 150ms, wire to first chunk <= 50ms, chunk to paint <= 50ms, all p95 |
| Tool surface | Default core toolset | Serialized schema | Freeze at baseline, ratchet down only |

Notes:

- TUI numbers are end-to-end through a real PTY, not internal counters alone.
- The provider is local and scripted, so per-turn numbers measure Hermes
  overhead, not model or network variance.
- p95 comes from at least 10 runs. Report p50 and max too.

## Existing assets to reuse

- `scripts/profile-tui.py` already launches the built TUI under
  `HERMES_DEV_PERF`, holds keys, and reports frame and React p50/p95/p99 with
  save/compare.
- `ui-tui/src/lib/perfPane.tsx` writes per-frame JSONL when
  `HERMES_DEV_PERF=1`: yoga, renderer, diff, optimize, write, patch counts,
  and backpressure.
- `ui-tui/src/app/startupLatency.ts` already computes process uptime at the
  first `gateway.ready`.
- `hermes_cli/observability/shared_metrics_startup.py` already identifies
  process-start-to-ready points for the CLI, gateway, and serve. Reuse the
  points, not the outbound telemetry.
- `tests/e2e/core/terminal/_pty.py` already drives the real CLI and TUI
  through a PTY with a VT screen and `FakeLLMServer`.
- `tests/fakes/fake_llm_provider.py` already scripts streams with chunk size
  and per-chunk delay.
- `scripts/ci/classify_changes.py` and the existing workflow `detect` job
  provide the change-aware CI pattern.

## Budget policy

- A metric is blocking only once its baseline is stable: at least 10 runs with
  a p95 spread under 10% on a dedicated runner class. Until then it warns.
- Deterministic metrics block from day one: tool count, schema bytes, hot
  import count, and idle polling frames.
- Wall-clock budgets are absolute for local runs and trend-relative for CI.
  CI compares against the 7-day median for the same runner class, not a
  committed wall-clock constant.
- Baselines move down, never up, unless the plan file records the reason in
  the same commit as the baseline change.
- Budget changes are their own commit and never ride with a code change.

## Stages

1. Harness skeleton
   1a. Create `scripts/perf/` with `metrics.py`, `run.py`, `budget.py`, and
   `baseline.json`.
   1b. Move `scripts/profile-tui.py` to `scripts/perf/tui_frames.py` and
   update its docstring. No compatibility wrapper.
   1c. Standardize one report shape: metric, unit, runs, p50, p95, max,
   budget, pass/warn/fail.
   1d. Add `--runs`, `--save`, `--compare`, `--json`, and a `--build` flag
   that rebuilds `ui-tui/dist`.
2. Startup trace
   2a. Add `ui-tui/src/lib/startupTrace.ts`, gated on `HERMES_DEV_PERF=1`,
   with zero cost when unset.
   2b. Emit `{src:'startup', phase, uptimeMs, pid, ts}` for module eval, first
   frame, gateway spawn, gateway ready, and first session info.
   2c. Add `uptimeMs` to the frame rows in `perfPane.tsx`.
   2d. Add `scripts/perf/startup.py`: N cold runs in a temp `HOME` and
   `HERMES_HOME`, reporting first paint, gateway ready, and session ready.
   2e. Record a CLI-only import baseline with
   `python -X importtime -c "import hermes_cli.main"`: self time and the hot
   import count.
3. Input and idle
   3a. Add `scripts/perf/input.py`: PTY single-key latency, repeat-key scroll,
   and first open of the model picker and session picker.
   3b. Detect the echoed cell through the VT screen, not by parsing ANSI
   blindly.
   3c. Add `scripts/perf/idle.py`: 60s with no input after settle; count frames
   and sample CPU for the TUI and backend processes.
   3d. Classify idle frames by trigger (animation, poll, background RPC) so the
   fix list is actionable.
4. Turn overhead
   4a. Add `scripts/perf/turn.py`: `FakeLLMServer` with
   `Text(chunk_chars=8, delay_per_chunk=0)` and a scripted tool call.
   4b. Timestamp the CR, request arrival at the fake provider, first SSE chunk,
   first painted assistant cell, and turn end.
   4c. Record prompt bytes and tool schema bytes for the exact turn.
   4d. Assert the fake provider sees the expected request shape so the
   measurement cannot silently drift.
5. CI and baselines
   5a. `budget.py --check` exits non-zero on a deterministic breach or a
   regression above tolerance, and emits JSON for artifacts.
   5b. Add the deterministic check to PR CI behind the existing change
   classifier: tool surface, import cost, and headless idle-frame check.
   5c. Add a nightly `perf-trend.yml` on macOS: full PTY suite, JSON artifact,
   job summary, and an alarm above 20% versus the 7-day median.
   5d. Keep the nightly non-blocking for two weeks, then promote metrics whose
   variance is under 10%.
   5e. Document the five numbers, the budgets, and `scripts/perf/run.py` in the
   developer guide.
6. Baseline report
   6a. Run 10 iterations per metric on the reference Mac and the CI runner
   class.
   6b. Publish one table: metric, current, budget, gap, top cost source.
   6c. Rank fix candidates by user-visible impact and measured cost. That
   ranking becomes the next plan.

## Budget rationale

- 400ms first paint stays under the roughly one-second instant threshold and
  leaves room for a cold terminal.
- 1.5s cold start p95: the documented prewarm alone is about 1.5s for the
  agent runtime, so this budget forces the UI and backend to separate.
- 100ms Enter to visible: acknowledgment is a UI obligation. The model may be
  slow, but the app must not look dead.
- 33ms echo is two 60fps frames. Anything above reads as lag.
- 50ms chunk to paint is one frame plus the RPC hop.
- Idle: nothing should redraw when nothing changed.
- Tool surface: 51 core tools is the current state, 28 of them browser and
  kanban. This plan freezes the surface. The target cut is a follow-on plan.

## Constraints

- No product behavior changes. The only product-adjacent change is a local
  trace gated on `HERMES_DEV_PERF`.
- No outbound telemetry changes. Shared metrics stay opt-in and untouched.
- No new core CLI command. The harness lives in `scripts/perf/`.
- The harness never writes to `~/.hermes`; it uses a temp `HOME` and
  `HERMES_HOME`.
- No network and no credentials. The fake provider is the only model.
- Windows is out of scope for the PTY suite initially. Deterministic checks
  run everywhere.

## Decision point

After Stage 2, the report answers whether the felt slowness is first paint,
gateway boot, agent build, or the provider. No fixes are proposed before that
table exists.

## Non-goals

- TUI redesign or renderer replacement.
- Tool-surface cuts.
- Startup refactor.
- Test-suite reduction.
- Any rewrite.
