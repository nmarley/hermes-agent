# Rust TUI Spike

## Purpose

This plan is a timeboxed, throwaway spike that decides whether the Hermes TUI should be rebuilt
in Rust with `ratatui`. It is the decision instrument for Stage 10 of
`docs/plans/PLAN-architecture-reset.md`, which already names `hermes-tui` in `ratatui` against
`hermes-rpc`, shipped behind `tui.engine: ink | rust`, with Ink kept until parity.

The spike answers four questions:

1. Can Rust speak the existing newline JSON-RPC protocol without changing Python?
2. Can `ratatui` render the current transcript, composer, streaming, tool activity, and
   approval flows without unacceptable UX loss?
3. Are startup, idle memory, and frame time better than Ink, or at least not worse?
4. Is the parity gap understood well enough to estimate a full rewrite?

This is a design and sequencing document. It is not a progress tracker. The go or no-go decision
is recorded in the spike's commit message and pull request, never by editing this file.

Tauri is not in scope. It is a desktop WebView shell, not a terminal renderer, and it cannot
replace the TUI's terminal, SSH, tmux, or Termux surfaces.

## Baseline at plan creation

- Repository head: `14aaa7cbce` (`Remove migration allowances from code health`).
- `ui-tui` application: 53,816 non-test TS/TSX lines in 236 files.
- Custom Ink fork: 27,451 non-test lines in 126 files. Core files include the renderer
  (`ink.tsx`, 2,850 lines), cell rendering (`render-node-to-output.ts`, 1,888 lines), selection
  (1,143 lines), styles (750 lines), the TypeScript Yoga port (2,393 lines), and the terminal
  parser (464 lines).
- Tests: 35,187 lines across 240 files.
- Transport: newline-delimited JSON-RPC over stdio between the TUI and
  `python -m tui_gateway.entry`.
- Contracts: Python models in `tui_gateway/contracts/`, generated TypeScript in
  `apps/shared/src/gateway-contract.generated.ts`, and the checked-in OpenRPC document
  `gateway-contract.openrpc.json`.

The exact lines will move. The baseline exists to size the rewrite, not to gate it on line
counts.

## Goal

Produce one runnable Rust binary that:

- spawns the existing `tui_gateway` process and completes the handshake;
- creates or resumes a session;
- submits a prompt and renders streaming assistant text, tool activity, and one approval;
- interrupts a turn;
- replays a scrubbed recorded session with no model or network;
- reports measured startup, memory, render, and scroll numbers against Ink.

The spike is successful when those flows run and the measurements plus parity checklist are
credible enough to support a go or no-go decision.

## Non-goals

- No production integration, no `tui.engine` switch, and no launcher changes.
- No deletion of Ink or `ui-tui`.
- No daemon, store, agent, provider, or protocol rewrite.
- No Python gateway changes.
- No plugin or public API changes.
- No full keybinding, slash command, overlay, image, IME, or platform parity.
- No packaging, Nix, Docker, Termux, or bundle changes.
- No Tauri.
- No Bun conversion work. That plan is parked while this spike runs.

## Constraints

- The spike crate lives on a draft branch and pull request. It is not merged unless the decision
  is to continue.
- Use the existing gateway protocol. If the spike needs a Python change, that is a finding, not
  a licence to change Python.
- Keep the crate standalone. Do not add a repository-wide Cargo workspace or alter npm, Bun,
  Python, or packaging build graphs.
- Timebox the spike to four weeks. Stop at the gate even if more features are tempting.
- The output is a decision, not a product. Prefer small, boring Rust over a premature framework.

## Deliverables

- A standalone crate at `native/tui-spike`.
- A scrubbed fixture set under `native/tui-spike/fixtures` containing recorded JSON-RPC frames
  and the expected terminal outcomes.
- A replay gateway that emits recorded frames over stdio without a model.
- `insta` snapshot tests for streaming, tool activity, and approval states.
- A measurement note in the pull request with the Ink baseline and spike results on the same
  host, terminal, and fixture.
- A parity checklist that lists covered flows, known gaps, unknowns, and the remaining estimate.
- A recorded go or no-go decision.

## Stages

### Stage 0: Fixtures and baseline

0a. Select one representative session that contains user and assistant text, a tool call, an
approval, an interrupt, and at least 1,000 transcript rows.

0b. Scrub the session: remove credentials, secrets, private paths, hostnames, and user data.
Keep the event ordering and payload shapes intact.

0c. Record raw JSON-RPC frames for `gateway.ready`, `session.info`, `message.delta`,
`message.complete`, `tool.start`, `tool.complete`, an `approval` server request and its response,
and `session.interrupt`.

0d. Build a replay gateway that emits the frames over stdio on a deterministic schedule. The
replay path must need no model, network, or real session database.

0e. Capture the Ink baseline on the same host and terminal:
cold start to first frame, idle RSS, p95 frame time during streaming, p95 frame time during a
1,000-row scroll, and built bundle size.

Exit criteria:

- The fixture replays in the current Ink TUI without a model.
- The same frames are available to a Rust process as newline JSON.
- The baseline numbers and the exact host and terminal are recorded.

### Stage 1: Transport

1a. Create the standalone `native/tui-spike` crate. Pin `ratatui`, `crossterm`, `tokio`,
`serde`, `serde_json`, and `insta`. Add `cargo fmt`, `cargo clippy`, and `cargo test` entry
points for the crate only.

1b. Spawn `python -m tui_gateway.entry` with the same environment contract Ink uses:
`HERMES_PYTHON`, `HERMES_PYTHON_SRC_ROOT`, and `PYTHONPATH`. Capture stderr into a ring buffer
instead of the terminal.

1c. Implement the newline JSON-RPC framing, request IDs, response correlation, event dispatch,
timeouts, and a clean shutdown. The envelope is JSON-RPC 2.0; the transport is one JSON object
per line.

1d. Implement the handshake in order: `gateway.ready`, then
`client.capabilities {server_requests: true}`, then `runtime.describe`, then
`session.create` or `session.resume`.

1e. Implement `prompt.submit` and `session.interrupt`. Render stderr and protocol errors as
activity lines rather than panics.

1f. Decide whether to generate Rust wire types from `gateway-contract.openrpc.json` or
hand-write only the frames used by the spike. Prefer generated types if codegen takes less than
one day; otherwise record the gap in the parity checklist.

Exit criteria:

- The replay gateway drives the handshake and a full turn.
- A live gateway can create or resume a session and receive streaming events.
- No Python changes are required.
- The gateway child exits cleanly on shutdown and on terminal close.

### Stage 2: Terminal shell

2a. Enter raw mode, alternate screen, and mouse capture with `crossterm`. Install a panic hook
and signal handler that restore terminal modes and clear the alternate screen.

2b. Build the shell layout with `ratatui` constraints: status line, transcript viewport,
activity line, and composer. Handle resize without losing transcript position.

2c. Render plain transcript rows with ANSI-aware wrapping and scroll. Append streaming deltas,
follow the tail while the user is at the bottom, and stop following when the user scrolls up.

2d. Implement composer input: insert, delete, newline, submit, and basic history. Show a cursor.
Selection, mouse editing, and IME are not required in the spike.

2e. Coalesce gateway events and cap redraws at 60 Hz. Redraw only when state is dirty.

Exit criteria:

- The recorded transcript scrolls smoothly and follows streaming text.
- The composer accepts and submits text against the replay gateway.
- Resize and quit leave the terminal in a usable state.
- A live streaming turn renders.

### Stage 3: Interaction proof

3a. Render tool activity rows from `tool.start` and `tool.complete`. Use plain text with basic
styles. Full markdown and the streaming markdown parser are out of scope.

3b. Implement one server-to-client `approval` request as a modal with selectable choices and a
response frame. This proves the server-request path, not the full prompt family.

3c. Implement one local slash command and a completion popup against the existing catalog. If
the completion path needs more than a day, stub it and record the gap.

3d. Implement session resume and interrupt against the live gateway. Ensure pending requests are
cancelled and no late event mutates a dead session.

3e. Add `insta` snapshot tests using `ratatui::backend::TestBackend` for streaming text, tool
activity, and approval. Keep snapshot sizes small and semantic.

Exit criteria:

- One end-to-end turn runs against the replay gateway and one against a live gateway when
  available.
- Approval and interrupt both work.
- Snapshot tests pass and cover the three main states.
- Protocol gaps and terminal gaps are written down.

### Stage 4: Measurement and decision

4a. Measure cold start to first frame, idle RSS, p95 frame time during streaming, p95 frame time
during a 1,000-row scroll, binary size, and lines of Rust on the same host and fixture.

4b. Compare the results with Stage 0. Record variance and the exact commands used.

4c. Write the parity checklist: covered flows, missing flows, terminal edge cases, protocol
gaps, test gaps, and an estimate for full parity.

4d. Record the go or no-go decision in the pull request and commit message. Do not edit this
plan to track it.

Exit criteria:

- The measurements are reproducible.
- The parity checklist is complete enough for a maintainer to challenge the estimate.
- The decision is recorded.

## Measurement targets

| Metric | Target |
|---|---|
| Cold start to first frame | No worse than Ink, with a goal of 20 percent faster |
| Idle RSS | No worse than Ink |
| p95 frame time during streaming | 16 ms or less |
| p95 frame time during a 1,000-row scroll | 18 ms or less |
| Approval and interrupt | Both work against a live gateway |
| Python changes | Zero |
| Binary size | Recorded, no fixed gate |
| Full parity estimate | At or below 24 engineer-months with a credible breakdown |

The targets are deliberately small. The spike is proving the shape of the problem, not shipping
a renderer.

## Go criteria

A go decision requires all of the following:

- Every stage exit criterion is met.
- The gateway protocol is sufficient for the main flows without Python changes.
- Transcript, composer, streaming, tool activity, and approval are viable in `ratatui`.
- Startup and idle memory are no worse than Ink, and frame time meets the targets.
- The remaining parity work is understood and estimated at 24 engineer-months or less.
- The team accepts the platform and test cost.

## No-go triggers

A single trigger is enough to stop:

- Essential behavior lives only in the TypeScript app and would need a large reimplementation.
- `ratatui` cannot express an essential layout or interaction without rebuilding a custom
  layout engine.
- Text input, IME, or selection requires a second engine and dominates the remaining work.
- Performance is not better than Ink after accounting for the spike's shortcuts.
- The credible full-parity estimate exceeds 24 engineer-months.
- Cancellation, replay, or server-request behavior is too fragile to make reliable.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The protocol has hidden behavior used only by Ink. | Exercise live create, resume, submit, approval, and interrupt. Treat any Python change as a finding. |
| Server requests and cancellation are harder than they look. | Prove one approval and one interrupt in Stage 3. Do not generalize early. |
| Text input parity is the real project. | Use a small editor crate if it saves time, but timebox selection and IME out of the spike. |
| Streaming markdown and diffing are expensive. | Render plain styled text in the spike and record the gap. |
| Layout parity is poor. | Accept visual differences, list them, and judge whether they are essential. |
| Terminal edge cases consume the schedule. | Test macOS and Linux first. Add Windows and Termux smoke tests only after the core gate. |
| Spike scope creeps into a rewrite. | Keep the crate standalone and stop at the gate. Close the pull request if the answer is no. |

## If the decision is go

Write `docs/plans/PLAN-rust-tui.md` for the full implementation and keep the spike out of
`main` unless it becomes the seed of the production crate. The full plan should cover:

- crate scaffolding and the `tui.engine: ink | rust` switch;
- generated protocol types and conformance tests;
- transcript, virtual history, scroll anchoring, and selection;
- composer, IME, bracketed paste, and clipboard;
- slash commands, completions, pickers, prompts, and overlays;
- subagent roster and detail flows;
- theme tokens, i18n, images, and terminal mode handling;
- platform matrix, snapshot parity, and end-to-end tests;
- packaging, launcher selection, and rollback;
- parity gate, then deletion of Ink.

Ink remains the default until the parity gate passes.

## If the decision is no-go

Close the spike pull request, keep Ink, and resume the Bun conversion plan. Record the blocking
finding in the pull request so the question is not reopened without new evidence.

## Open questions

- Which recorded session best represents real usage without exposing user data?
- Should the spike use generated Rust types from the OpenRPC document or hand-written frames?
  Prefer generated types when codegen fits the timebox.
- Does the first platform target macOS only, or macOS and Linux together? The recommendation is
  both for the core gate, with Windows and Termux after.
- Should the production crate live under `native/` or a future `crates/` directory? The
  spike uses `native/tui-spike` to avoid committing the final layout early.
- Is the 24 engineer-month ceiling still the right gate? Revisit only with evidence from the
  measurement stage.
