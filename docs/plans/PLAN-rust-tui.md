# Rust TUI (Greenfield)

## Intent

Build a new terminal client for Hermes in Rust with ratatui. It is a fourth renderer
alongside Ink, the desktop app, and the dashboard. It consumes the existing Python
gateway over the canonical WebSocket JSON-RPC.

This is a greenfield client, not a port of `ui-tui`. The existing TUI is a reference for
which RPCs exist, not a specification for behavior or layout. The new client chooses a
smaller product surface on purpose.

The project is a personal experiment. It ships no binaries, changes no installers, and
does not replace Ink. It stays small and incremental.

## Why this is viable

The backend already separates rendering from agent behavior. `tui_gateway/AGENTS.md`
states that TypeScript owns the screen while Python owns sessions, tools, model calls,
and slash logic. The desktop app is an independent renderer on the same backend, so a
third client is an intended shape.

The wire is an explicit contract. `tui_gateway/contracts/registry.py` declares every
method, server request, and event, and `scripts/gen_gateway_contracts.py` renders the
OpenRPC artifact at `apps/shared/src/gateway-contract.openrpc.json`. A focused client
needs a narrow subset, not the full 258-method surface.

The only backend-specific coupling is local gateway discovery and ticket minting. A
small CLI seam, `hermes gateway connect-info --json`, keeps that logic in Python and
avoids reimplementing discovery in Rust.

## Non-goals

- No changes to `ui-tui`.
- No feature parity with Ink.
- No engine switch, launcher integration, or config key.
- No packaging, release artifacts, installers, or platform binaries.
- No changes to the agent, gateway, tools, store, or protocol.
- No user JS widgets, i18n, pets, billing, subscription, journey, voice, connectors,
  skills/plugins hubs, subagents, todos, dashboard PTY, sidecar mirror, inline mode,
  native scrollback, or image attachments.
- No visual parity. The layout is new.

## v1 scope

| Area | Included |
|---|---|
| Chat | Session create, resume, and list; streaming assistant text; tool activity; reasoning; queue, steer, and interrupt |
| Composer | Multiline editing, paste, history, slash completion, path completion |
| Prompts | Approval, clarify, sudo, secret |
| Pickers | Session picker, model picker |
| Transcript | Scroll, mouse wheel, markdown, fenced code, diffs |
| Status | Connection state, session title, model, token usage |
| Theme | One dark and one light palette, selected from the terminal background |
| Persistence | Resume recent sessions; no client-side prompt journal |

Deferred until the core is useful: subagents, event replay on reconnect, inline mode,
i18n, skin tokens, text selection, search, voice, images, and every peripheral overlay.

## Architecture

### Workspace

Add a root `Cargo.toml` workspace with one member, `crates/hermes-tui`. Exclude
`apps/bootstrap-installer/src-tauri` so the Tauri installer keeps its own lockfile and
workspace.

Do not split `hermes-rpc` yet. A second crate is justified only when a second consumer
exists. The transport lives in `crates/hermes-tui/src/client` until then.

### Modules

| Module | Responsibility |
|---|---|
| `main` | Argument parsing, terminal setup, runtime, shutdown |
| `protocol` | Hand-written v1 request, event, and server-request types |
| `client` | Gateway discovery, WebSocket channel, heartbeat, reconnect, server requests |
| `app` | Model, actions, reducer, turn state, session state, composer state |
| `view` | Pure ratatui rendering for layout, transcript, composer, prompts, pickers |
| `input` | Key mapping, editor buffer, history, paste |
| `theme` | Dark and light palettes, terminal background detection |

### Dependencies

Pin current stable versions at implementation time and verify `rust-version`.

| Need | Crate |
|---|---|
| TUI | `ratatui`, `crossterm` |
| Async and transport | `tokio`, `tokio-tungstenite`, `rustls` |
| Serialization | `serde`, `serde_json` |
| Unicode | `unicode-width`, `unicode-segmentation` |
| Markdown | `pulldown-cmark` |
| CLI and errors | `clap`, `anyhow`, `thiserror` |
| Logging | `tracing`, `tracing-subscriber` |
| Tests | `insta`, `ratatui::backend::TestBackend`, `tokio-tungstenite` test server |

### State and event loop

Use a single-threaded `tokio` runtime. Select over terminal input, transport messages,
and timers. Keep one `Model` containing connection state, session metadata, transcript,
turn state, composer, prompts, and the active picker.

Use an Elm-style flow: `Action` values from input and transport feed `update()`, and
`view()` renders the whole model. Redraw on input, on turn boundaries, and at a capped
rate while streaming.

### Transport

`hermes gateway connect-info --json` prints a WebSocket URL and subprotocol list. The
Rust client spawns that command, or accepts an explicit `--url`. The ticket travels in
a WebSocket subprotocol, never in the URL and never in logs.

Implement the JSON-RPC channel directly:

- Send `client.capabilities {server_requests: true}` after `gateway.ready`.
- Track request IDs, pending promises, timeouts, and structured errors.
- Send `gateway.ping` on the heartbeat interval and fail the socket after the deadline.
- Reconnect with exponential backoff. On reconnect, re-run `session.resume` and replace
  the transcript from the snapshot, then continue live. Do not implement event replay
  in v1.
- Route server requests to prompt cards. Answer unsupported desktop-only requests with
  `-32601` so the agent fails fast.
- Never log tickets, full URLs with query strings, or prompt contents.

### Protocol subset

About 20 methods:

`client.capabilities`, `runtime.describe`, `session.create`, `session.resume`,
`session.list`, `session.info`, `session.detach`, `prompt.submit`, `prompt.cancel`,
`session.interrupt`, `session.steer`, `config.get`, `session.mutate`, `approval.respond`,
`clarify.respond`, `clarify.lock`, `commands.catalog`, `complete.slash`, `complete.path`,
`slash.exec`, `command.dispatch`.

About 15 events:

`gateway.ready`, `session.info`, `message.start`, `message.delta`, `message.complete`,
`thinking.delta`, `reasoning.delta`, `reasoning.available`, `tool.start`, `tool.progress`,
`tool.complete`, `request.cancel`, `status.update`, `notification.show`, `session.usage`,
`error`.

Four server requests:

`approval`, `clarify`, `sudo`, `secret`.

Hand-write these types. Add a test that parses the OpenRPC artifact and asserts every
method name, event name, server-request name, and field used by the client exists in
the contract. This catches drift without a code generator.

The model picker uses the model projection if the backend serves one. Otherwise it
accepts a typed model name and applies it through `session.mutate`.

### UI

Use the alternate screen only. The dashboard PTY and Termux modes stay on Ink.

Layout, top to bottom:

- Status row: connection state, session title, model, token usage.
- Prompt zone: approval, clarify, sudo, or secret card when one is open.
- Transcript: user rows, assistant rows, collapsed reasoning, tool rows, errors.
- Composer: prompt glyph, multiline buffer, completion menu above it.
- Hint row: queued message count, busy state, key hints.

Rendering behavior:

- Render markdown headings, lists, quotes, tables, fenced code with a small keyword
  highlighter, inline code, emphasis, links, diffs, and basic TeX-to-Unicode.
- Keep the transcript virtualized by measured row height. Do not re-render the whole
  history on each delta.
- Collapse reasoning by default; expand with a key.
- Show tool rows as one line with status, duration, and a preview. Expand on demand.
- Use a single accent color, a muted tone, and semantic ok, warn, and error tones.

Input behavior:

- Enter submits, Shift+Enter inserts a newline.
- Up and Down cycle completions first, then history.
- Left and Right move by character; Ctrl or Alt with arrows moves by word.
- Home and End move to line boundaries.
- Backspace and Delete remove a character; Ctrl+W removes a word; Ctrl+U and Ctrl+K
  remove to line boundaries.
- Ctrl+C clears a draft, interrupts a running turn, or exits when idle.
- Ctrl+D exits only when the composer is empty.
- Bracketed paste inserts text inline.
- Mouse wheel scrolls the transcript.

### Terminal behavior

- Enter raw mode, hide the cursor, and use the alternate screen.
- Restore terminal modes on normal exit, signal, and panic.
- Redraw on resize.
- Detect light or dark from `COLORFGBG` and `HERMES_TUI_LIGHT`, with an explicit
  `--theme` override. Do not query OSC 11 in v1.

## Stages

Each stage is one atomic commit. Each stage leaves the tree buildable and testable.

### Stage 0: Backend seam and protocol skeleton (3-5 days)

- Add `hermes gateway connect-info --json`, reusing the existing discovery, ticket, and
  `gateway_ws_target` logic. It prints `{url, protocols}` and nothing else.
- Add the root Cargo workspace and the `crates/hermes-tui` skeleton.
- Define the v1 protocol types and the OpenRPC cross-check test.
- Add a fake WebSocket gateway harness for tests.

Exit criteria:

- `cargo test` passes.
- The contract cross-check fails when a used method or field is renamed.
- `hermes gateway connect-info --json` returns a URL against a running gateway.

### Stage 1: Transport and session (1 week)

- WebSocket dial, JSON-RPC request and response handling, capabilities, heartbeat,
  timeout and error mapping.
- Session create, resume, list, and detach.
- Event dispatch into a headless model.
- Server-request routing with unsupported methods declined.

Exit criteria:

- A headless command creates a session, submits one prompt, and prints streaming
  assistant text from a real gateway.
- Killing the socket mid-turn reconnects, resumes the session, and restores the settled
  transcript.

### Stage 2: UI shell, transcript, composer (1-2 weeks)

- Alternate-screen setup, cleanup, resize, and the main layout.
- Transcript rendering, markdown, code blocks, and scrolling.
- Composer editing, history, paste, submit, and completion menu.
- Dark and light palettes.

Exit criteria:

- An interactive session can be created, typed into, and resumed.
- Snapshot tests cover empty, streaming, tool, and error states.
- Terminal modes are restored after a simulated panic.

### Stage 3: Turn loop, tools, reasoning (1-2 weeks)

- Streaming deltas and completion transitions.
- Tool start, progress, complete, and reasoning rows.
- Interrupt, queue, and steer.
- Usage, notices, and error rows.

Exit criteria:

- A real tool-using turn renders fully and survives an interrupt.
- Queued prompts send in order after the active turn.

### Stage 4: Prompts, pickers, slash (1 week)

- Approval, clarify, sudo, and secret cards.
- Session picker and model picker.
- Command catalog, slash completion, path completion, local help and quit, and
  fallthrough to `slash.exec` and `command.dispatch`.

Exit criteria:

- An approval survives a disconnect and is answered after reconnect with the backend
  effect verified.
- A skill-backed slash command reaches the gateway and renders its reply.

### Stage 5: Polish and dogfood (1 week)

- Mouse wheel, hyperlinks, scroll bounds, and copy-friendly output.
- Session resume from the picker.
- Startup errors and connection failures rendered as plain text.
- A short runbook for building and running the client.

Exit criteria:

- One week of personal daily use without falling back to Ink for the included scope.
- Known gaps are listed in the runbook.

Total estimate: five to eight weeks for one developer.

## Verification

- `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`.
- OpenRPC cross-check for every protocol name and field the client uses.
- Fake-gateway tests for request flow, event flow, server requests, declines, and
  reconnect.
- `insta` snapshots for transcript, composer, prompts, and pickers at fixed sizes.
- One live smoke test against a real gateway, run manually.
- Manual checklist for the included v1 scope.

No PTY parity suite and no cross-engine comparison. They test the old TUI, not this one.

## Risks

- The text editor is the largest UI risk. Grapheme movement, wrapping, wide characters,
  and paste need dedicated tests.
- Streaming markdown can be slow if the whole transcript re-parses per delta. Cache
  settled blocks and re-render only the tail.
- A reconnect mid-turn can miss deltas. The resume snapshot restores settled content,
  but partial output may be incomplete. Event replay is the later fix.
- Some canonical methods are served by legacy handlers with different shapes. Validate
  each call against a real gateway during Stage 1.
- Ratatui has no flexbox. Layout is manual, so every size class needs snapshot coverage.
- It is easy to drift back into porting Ink features. Treat the v1 scope table as the
  contract for this experiment.

## Change-set discipline

- `connect-info` is its own commit, before the crate.
- Every stage is one atomic commit.
- Do not mix plan edits with code.
- Do not change `ui-tui`, the launcher, or release scripts.
- Keep the protocol subset and the UI scope stable until Stage 5.

## Open decisions

- Whether to add `session.events.since` replay immediately after Stage 1 or defer until
  after dogfood. Recommendation: defer.
- Whether the binary should live at `crates/hermes-tui/target/...` via a workspace or as
  a standalone crate. Recommendation: root workspace with one member.
- Whether inline mode is ever needed for this client. Recommendation: keep it out until
  there is a concrete use.
- Whether to add subagents next or improve transcript rendering first. Recommendation:
  improve rendering and reconnect behavior first.

## References

- `tui_gateway/AGENTS.md` for the three-consumer model and transport contract.
- `tui_gateway/contracts/registry.py` for declared methods, events, and server requests.
- `apps/shared/src/gateway-contract.openrpc.json` for the generated wire artifact.
- `hermes_cli/gateway_client.py` for discovery, ticket, and WebSocket target helpers.
- `ui-tui/scripts/gateway_bootstrap.py` for the existing local bootstrap shape.
- `ui-tui/src/gatewayClient.ts` and `apps/shared/src/json-rpc-channel.ts` for transport
  behavior worth matching where it affects correctness.
