# Hermes Desktop: Tauri and Rust Rewrite Plan

## Intent

Rewrite the Hermes desktop shell and renderer from first principles on Tauri and Rust.
This is not a line-by-line port of Electron. It is a fresh composition built around one
small, working vertical slice at a time.

The Python agent and the existing gateway protocol stay. This plan replaces the desktop
shell, its renderer, and its distribution machinery. It does not rewrite the agent core,
the gateway, the plugin catalog, or the mobile surfaces.

Related architecture context lives in `docs/plans/PLAN-architecture-reset.md`. That plan
explicitly rejects a big-bang rewrite and places a desktop shell decision after the Rust
daemon, TUI, store, and parity gate. This document is the desktop-specific rewrite plan
that can proceed independently, beside the existing Electron app, without waiting for the
full-core decision.

## Why rewrite

The current desktop is an Electron-shaped product:

- The Electron main process is about 77k non-test lines across 316 non-test files.
  `electron/main.ts` alone is about 18.4k lines.
- It exposes about 205 `ipcMain` channels and about 306 preload bridge keys.
- The renderer is about 428k non-test lines across 3,192 source files.
  About 240 files and 647 call sites use `window.hermesDesktop`.
- The desktop carries 332 Electron unit tests and 58 Playwright end-to-end specs.
- The preview browser depends on Electron's `<webview>` element: partitions, preloads,
  `executeJavaScript`, capture, annotations, popouts, focus, and DOM layout.
- The release pipeline depends on electron-builder, electron-updater, MSIX, App Installer
  feeds, Microsoft Store packaging, Azure signing, and notarization.

A mechanical port would reproduce all of that structure in a different runtime. A rewrite
can remove it and make the shell small enough to reason about.

## Scope

In scope:

- A new Tauri shell that owns windows, webviews, process supervision, native capabilities,
  updates, and packaging.
- A new React renderer built as small vertical slices, reusing design tokens and pure
  primitives where they are genuinely shell-independent.
- A typed bridge between renderer and shell.
- A capability and security model designed before features grow.
- A migration path from the Electron app.
- A test and release strategy that supports every phase.

Out of scope:

- Reimplementing the Python agent, gateway, tools, providers, memory, cron, or plugin core.
- A Rust daemon or Rust agent core. The existing gateway protocol remains the work
  boundary.
- Mobile clients.
- Electron API compatibility. No shim that recreates `window.hermesDesktop`.
- Porting the current 428k-line renderer feature tree wholesale.
- HUD, pet, quick entry, plugins, MSIX, and Store distribution before the core chat
  product is viable.

## Planning assumptions

These assumptions drive the estimates. If one changes, the estimate changes.

- The core team is three people: two Rust or full-stack engineers and one frontend
  engineer, with part-time QA and release engineering.
- macOS is the first target for a usable build. Windows follows. Linux follows after
  Windows. Store and MSIX distribution come after a signed direct-download path works.
- The new renderer is a thin React application, not a reuse of the current feature tree.
  Design tokens, icon assets, and pure presentational primitives may be reused.
- The Python gateway remains the backend. The renderer connects to it over the existing
  WebSocket JSON-RPC protocol, using generated types from the shared gateway contract.
- Eventual full parity is the destination. The first releases intentionally expose fewer
  surfaces.
- Existing Electron users must be able to upgrade in place eventually. The migration
  design is part of the plan, not an afterthought.

## First principles

Start from user jobs, not from Electron's feature list.

1. Talk to Hermes.
2. Work with Hermes on a repository.
3. Inspect or preview web content safely.
4. Stay in flow across the desktop.
5. Stay updated.
6. Extend the product.

Each phase delivers one small, usable slice of one job. No phase is infrastructure-only
for more than two weeks. Every phase ends with an installable build and a named workflow a
human can perform.

## Architecture

### Responsibilities

The shell is a capability broker and process supervisor, not an application server.

- The renderer owns navigation, presentation, and ephemeral interaction state.
- The shell owns the machine: process lifecycle, native windows, filesystem, git, PTY,
  notifications, tray, power, deep links, preview webviews, updates, and packaging.
- The gateway owns sessions, messages, turns, tools, and model calls.
- The renderer talks directly to the gateway over WebSocket. The shell mints tickets,
  opens SSH tunnels, and returns a loopback URL. It does not proxy chat traffic.
- The shell never reimplements agent behavior. The renderer never reaches for Node,
  Electron, or arbitrary Tauri capabilities.

This is the central simplification. Recreating the current 205-channel main process would
defeat the rewrite.

### Rust crates

Use a Cargo workspace. Crates are domain-oriented, and none of the domain crates depend on
Tauri.

- `hermes-domain`: identifiers, errors, capabilities, connection and profile types. Pure
  data and invariants. No I/O, no Tauri.
- `hermes-config`: Hermes home resolution, profile loading, settings, secret references.
- `hermes-gateway`: gateway discovery, health, ticket broker, and the backend supervision
  state machine.
- `hermes-connections`: local, remote, cloud, OAuth, SSH tunnels, and reconnect policy.
- `hermes-native`: filesystem, git, PTY, notifications, tray, power, screen, clipboard,
  and deep links. Traits define the boundary; platform adapters implement them.
- `hermes-preview`: child webview lifecycle, navigation policy, capture, and annotation
  support.
- `hermes-update`: update policy, feed compatibility, and migration.
- `hermes-bridge`: command and event schema, plus generated TypeScript bindings.
- `hermes-shell`: the Tauri application. Thin command handlers, window and webview
  management, capability wiring, and app lifecycle only.

Keep business logic out of `hermes-shell`. A rule of thumb: if a function can be tested
without Tauri, it belongs in a domain crate.

### Renderer

Use React, TypeScript, and Vite. Organize by user-facing feature, not by technical layer.

- Chat and sessions.
- Connections and profiles.
- Composer and attachments.
- Work panes: files, git, terminal.
- Preview browser.
- Settings, themes, and i18n.
- Onboarding and recovery.

Each feature owns its stores and actions. Shared renderer state is limited to what multiple
features genuinely need. Server data is a cache of gateway truth. Presentation state
remains local to the feature that owns it.

The renderer must not grow one global desktop object. Use a typed `DesktopClient` with
namespaced capabilities such as `system`, `window`, `backend`, `connections`, `fs`, `git`,
`pty`, `preview`, and `update`. Each namespace has request and response types generated
from the Rust side.

### Protocol

Two protocols exist, and they stay separate.

- Gateway protocol: the existing WebSocket JSON-RPC used by the agent backend. Reuse the
  shared contract in `apps/shared/src/gateway-contract.openrpc.json`. Generate the
  renderer client types from that source. Do not invent a second agent protocol.
- Desktop bridge protocol: shell commands and events for machine capabilities. Define it
  once in `hermes-bridge`, generate TypeScript with `specta` or `ts-rs`, and add a
  contract test that fails when the generated client is stale.

Every bridge command is namespaced, typed, and capability-scoped. No stringly typed
message bags. No ambient authority.

### Backend supervision

Model the local backend as an explicit state machine:

- `Stopped`
- `Starting`
- `Ready`
- `Degraded`
- `Stopping`
- `Failed`

Transitions are explicit and tested. The shell owns readiness probes, port selection,
environment composition, log capture, crash backoff, and shutdown. No caller may assume
that spawning a process means the backend is usable.

The state machine is pure Rust and independent of Tauri. A fake gateway exercises every
transition in integration tests.

### Windows and auxiliary surfaces

The main window, HUD, pet overlay, quick entry, OAuth windows, browser popouts, and session
windows are separate Tauri windows or child webviews. Each gets its own capability set.
There is no shared global bridge that exposes every capability to every window.

The focused surface owns its keys. A background event never steals focus, navigates, or
opens a window. Auxiliary windows use explicit, narrow commands rather than a general
relay.

### Preview browser

Preview is the highest-risk surface. Treat it as its own subsystem.

- The shell owns child webviews.
- Guest content receives no Tauri IPC, no Node, and no bridge object.
- Navigation is allowlisted by scheme and policy.
- `window.open` and target-blank links are denied by default. A trusted-click bridge may
  forward `http` and `https` to `openExternal`.
- Each webview gets an isolated data directory or data store identifier.
- Capture, annotation, and popouts are explicit commands with a narrow contract.
- Native bounds are synchronized from the renderer's layout through a typed geometry
  command. Handle scrolling, transforms, multi-monitor DPI, and popouts explicitly.

Do not start this subsystem until the one-week spike proves reliable child webview
creation and positioning on macOS and Linux.

### State authority

- Gateway: sessions, transcripts, turns, tools, model state.
- Shell: machine facts, process state, connection reachability, window state, update state.
- Renderer: presentation, navigation, focus, and transient interaction state.

Persisted renderer state declares its scope in its key: connection, profile, stored
session, project, or window. The rewrite must not repeat the current global-key ambiguity.

### Security

- Tauri capabilities per window. Least privilege by default.
- Path scopes for filesystem and git commands. No arbitrary path from the renderer without
  a policy check.
- No shell execution from the renderer. Shell commands are allowlisted, typed, and scoped.
- Secrets live in the OS keyring through the shell. Never send secrets to the renderer.
- Preview guests have no IPC. The trusted-click bridge is the only outbound path.
- CSP is explicit. Remote content never loads in the main webview.
- Capability review is a release gate, not a cleanup task.

### Packaging and updates

- Tauri bundler for DMG, zip, NSIS, MSI, AppImage, deb, and rpm.
- Tauri updater with a dedicated signing key and feed. This cannot reuse the existing
  electron-updater feed.
- MSIX, App Installer, Microsoft Store packaging, and Store identity continuity are custom
  work. Tauri produces EXE and MSI, not MSIX.
- The Electron-to-Tauri migration needs a signed one-time installer or updater path that
  installs the new app and optionally removes the old one.
- The new web origin means localStorage, IndexedDB, and OAuth cookies do not carry over
  automatically. Plan a one-time preferences import and define which credentials must be
  re-established.

## Delivery principles

- Build the new app beside Electron. Electron keeps shipping until parity.
- Every phase ends with an installable build and a named workflow a human can perform.
- Every risky subsystem gets a one-week working spike before production work starts.
- No compatibility shim for `window.hermesDesktop`. That shim would preserve the monolith.
- Reuse design tokens, assets, and pure primitives. Do not reuse feature code that assumes
  Electron.
- No dead buttons. An unfinished surface is absent or feature-flagged, never a placeholder.
- Use separate development profiles. Running Electron and Tauri against the same
  `HERMES_HOME` profile risks state corruption.
- Each phase adds the tests, logs, error states, and documentation needed for that phase.
  Do not defer them to a hardening phase.
- Prefer a working narrow slice over a broad non-working scaffold.

## Phases

Estimates are calendar weeks for the assumed three-person core team. They are ranges, not
commitments. Spikes and QA run in parallel where noted.

### Release 0: Foundations and risk retirement, 4 to 6 weeks

| Phase | Working deliverable | Demo | Exit gate | Estimate |
|---|---|---|---|---|
| 0. Shell skeleton | New app launches, shows shell, app, and backend status, runs a typed `system.health` command, and produces a signed development build | Launch the app and show the health response | CI builds macOS, Windows, and Linux; structured logs; error boundary; capability allowlist | 2 weeks |
| 0.1 Child webview spike | A real child webview that opens a URL, can be positioned, resized, focused, and closed | Open an isolated preview beside the main window, then close it | Reliable on macOS and Linux; no guest IPC; navigation policy enforced | 1 week |
| 0.2 PTY spike | A terminal pane that spawns the user shell, renders output, accepts input, and exits cleanly | Run `pwd`, resize the pane, close it | No orphan process; resize and cleanup tested | 1 week |
| 0.3 Updater spike | Tauri updater checks a local feed, downloads, installs, and relaunches | Upgrade a local build from N-1 to N | Signature verification; rollback path recorded | 1 week |
| 0.4 MSIX spike | Wrap a Tauri EXE in an MSIX package with the intended identity and install it | Install the MSIX and launch the app | Same identity as the intended product; uninstall clean | 1 week |

The spikes are functional demos, not architecture documents. A failed spike changes the
plan before later phases depend on it.

### Release 1: Usable chat client, 10 to 14 weeks

| Phase | Working deliverable | Demo | Exit gate | Estimate |
|---|---|---|---|---|
| 1. Connection doctor | Enter a gateway URL, see health, version, ticket state, and actionable errors | Connect to a running gateway and show its status | Handles unreachable, auth-required, expired, and wrong-version gateways | 2 weeks |
| 2. Chat vertical slice | Sessions list, transcript streaming, send, cancel, markdown and code rendering, reconnect | Hold a real conversation with Hermes | Golden stream fixtures; cancel is prompt; no lost messages on reconnect | 5 weeks |
| 3. Local backend lifecycle | App starts and stops the Python gateway, finds ports, waits for readiness, captures logs, and restarts after a crash | Launch the app and chat with no manual setup | State-machine tests; no orphan processes; degraded state is visible | 4 weeks |
| 4. Profiles and persistence | Switch profiles, restore window and session state, complete onboarding | Restart the app and land exactly where you left off | Profile isolation; no cross-profile reads or writes | 2 weeks |

Release 1 exit: internal users can dogfood it daily with a local gateway. This is the first
real product milestone.

### Release 2: Daily driver, 14 to 18 weeks

| Phase | Working deliverable | Demo | Exit gate | Estimate |
|---|---|---|---|---|
| 5. Connections | Remote URL, OAuth or native login, cloud, SSH tunnel, reconnect | Switch between local and remote gateways | 401 and 403 handling; tunnel recovery; no secret reaches the renderer | 5 weeks |
| 6. Composer parity | Attachments, drag and drop, slash commands, model picker, approvals, clarify, queued prompts | Complete the common chat workflows without Electron | End-to-end coverage for each interaction; keyboard and screen-reader pass | 5 weeks |
| 7. Work panes | Files, git status, diff, stage, commit, PTY terminal, pane layout, keep-alive | Inspect a repository, stage a change, and run a command | Path scoping; PTY cleanup; no orphan processes; pane lifecycle tests | 6 weeks |
| 8. Settings, themes, i18n | Settings, themes, native theme, locales, design tokens | Configure the app and switch themes and languages | No handwritten theme lists; locale completeness; no layout regressions | 2 weeks |

Release 2 exit: alpha for external users. Chat and repository work are usable without
Electron.

### Release 3: Desktop integration, 12 to 16 weeks

| Phase | Working deliverable | Demo | Exit gate | Estimate |
|---|---|---|---|---|
| 9. Preview browser | Child webview panes with navigation policy, capture, annotation, and popouts | Open a local preview, annotate it, and pop it out | No guest IPC; trusted-click only; security review; macOS, Windows, Linux behavior | 6 weeks |
| 10. Desktop behaviors | Tray, notifications, minimize-to-tray, deep links, single instance, global shortcuts, power resume, HUD, pet, quick entry | Use the app from the tray and from a global shortcut | No focus stealing; per-window capability audit; platform matrix | 5 weeks |
| 11. Updates and distribution | Tauri updater, DMG and zip, NSIS, AppImage, deb, rpm, MSIX and App Installer, signing, channels, rollback, Electron migration | Upgrade N-1 to N on each supported OS | Signed artifacts; rollback tested; MSIX installs with the intended identity | 5 weeks |

Release 3 exit: beta release with a signed update path.

### Release 4: Parity and cutover, 12 to 18 weeks

| Phase | Working deliverable | Demo | Exit gate | Estimate |
|---|---|---|---|---|
| 12. Plugins | Plugin discovery, install, enable, disable, runtime loader, permission model | Install and enable a desktop plugin | A plugin cannot escape its capability scope | 4 weeks |
| 13. Remaining user jobs | Cron, webhooks, kanban, bots, capabilities, review, and other surfaces justified by user jobs | Complete the parity checklist for each accepted surface | Each surface has a user job, tests, and an owner; rejected surfaces are documented | 7 weeks |
| 14. Hardening | Performance, memory, startup, accessibility, offline and degraded states, crash recovery, docs | Compare startup, idle memory, and install size with Electron | Budgets met; no regression; recovery paths proven | 5 weeks |
| 15. Cutover | Preferences import, credential re-establishment, uninstall old app, support path, old app retired | An existing Electron user upgrades in place and keeps working | Rollback tested; migration documented; Electron app removed | 2 weeks |

## Estimate summary

Assumes the three-person core team described above.

| Milestone | Calendar | Confidence |
|---|---|---|
| Internal chat MVP | 4 to 5 months | Medium |
| Alpha daily driver | 7 to 10 months | Medium |
| Beta with preview and updates | 10 to 13 months | Low to medium |
| Full parity | 14 to 18 months | Low to medium |

One senior engineer should expect roughly 30 to 40 months. A five-person team does not
halve the schedule; several phases are on the critical path.

The largest estimate variances are:

- Tauri child webview stability and multi-window geometry.
- Windows MSIX, App Installer, Store identity, and the Electron-to-Tauri migration.
- How much of the renderer is rewritten versus reused.
- Linux WebKitGTK rendering and media parity.
- Team familiarity with Rust and Tauri.

## Verification strategy

- Rust unit tests for every domain crate. No Tauri in the test path.
- Integration tests for backend supervision with a fake gateway process.
- Golden fixtures for gateway streaming, cancellation, reconnect, and errors.
- Contract tests that fail when generated TypeScript bindings are stale.
- WebdriverIO Tauri tests for each phase's named workflow. Use the embedded WebDriver
  service where it is the only option, including macOS.
- Browser-mode tests for renderer-only flows where they add speed without losing fidelity.
- Capability tests that attempt forbidden paths, commands, and preview IPC.
- Performance budgets for startup, idle memory, and install size, measured against
  Electron before cutover.

Each phase's definition of done:

- The named workflow works end to end.
- The build installs and launches on the phase's target platforms.
- Errors and degraded states are visible and actionable.
- Logs identify the phase's subsystem without leaking secrets.
- Tests cover the contract and the failure path that would break a user.
- Documentation tells a new contributor how to run and demo the phase.
- The capability surface added by the phase is reviewed and scoped.

## Risk register

| Risk | Impact | Mitigation | Gate |
|---|---|---|---|
| Child webviews are unstable or unpositionable | Preview browser cannot ship | One-week spike before Phase 9; fallback to an external-browser preview or a reduced in-app viewer | Phase 0.1 |
| System webview differences | UI, media, and terminal regressions across platforms | macOS first; per-platform QA; avoid Chromium-only APIs; keep Electron until parity | Every release |
| MSIX and update migration | Existing users cannot upgrade | Prototype MSIX wrapper early; keep Store identity; test in-place upgrade | Phase 0.4 and Phase 11 |
| Two apps share one profile | Data corruption during dogfood | Separate dev profile; single-instance lock; never run both against the same profile | Phase 1 |
| Web origin change loses prefs and cookies | Users lose settings or sessions | Preferences import; explicit credential re-establishment; document the boundary | Phase 11 and Phase 15 |
| Renderer rewrite scope grows into a port | Schedule collapse | New thin renderer; feature modules; no compatibility shim; parity checklist | Every phase |
| Rust or Tauri learning curve | Slower delivery | At least one strong Rust engineer; keep domain crates small; spike risky APIs early | Phase 0 |
| Maintaining two apps | Duplicate work and drift | Timebox Electron to maintenance; dogfood the new app early; cut over at parity | Release 4 |
| Plugin compatibility | Ecosystem break | Keep the Python plugin bridge; design a new desktop capability API with a compatibility plan | Phase 12 |
| Release pipeline complexity | Beta slips | Start signing and packaging in Release 3; do not defer to the end | Phase 11 |

## Open decisions

These decisions change the plan and should be settled before Release 1.

1. Renderer strategy: new thin renderer, recommended, versus reuse of the current UI
   through a compatibility bridge. Reuse saves time but preserves the bridge monolith and
   breaks on `<webview>` surfaces.
2. Platform order: macOS first, recommended, versus all three platforms from day one. All
   three adds three to five months.
3. Parity definition: daily-driver parity versus full surface parity. Full parity includes
   cron, webhooks, kanban, bots, plugins, HUD, pet, quick entry, MSIX, and Store
   distribution.
4. Existing-user migration: in-place upgrade, recommended, versus a one-time reinstall.
   In-place upgrade adds four to six weeks and needs a release-engineering owner.
5. Protocol ownership: keep the existing gateway WebSocket protocol, recommended, versus a
   new desktop-specific protocol. A new protocol adds a second compatibility problem.
6. Backend future: Python gateway now, optional Rust daemon later. Do not couple the
   desktop rewrite to the daemon decision.

## Baseline evidence

Measured on the current tree at planning time. Counts drift.

- Electron non-test source: about 77k lines, 316 files.
- `electron/main.ts`: about 18.4k lines.
- `ipcMain` channels: about 205.
- Preload bridge keys: about 306.
- Renderer non-test source: about 428k lines, 3,192 files.
- Renderer files using `window.hermesDesktop`: about 240.
- Renderer call sites using `window.hermesDesktop`: about 647.
- Electron unit tests: 332.
- Playwright end-to-end specs: 58.
- Preview `<webview>` usage: about 12 files, 46 API calls.
- Tauri 2.12.5 `WebviewBuilder`: behind the `unstable` feature.
- Tauri Windows bundling: EXE and MSI only; MSIX and App Installer are custom work.
