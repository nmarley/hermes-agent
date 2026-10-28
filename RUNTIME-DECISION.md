# Runtime Decision: Rust vs Bun/TypeScript

This is a decision memo for a greenfield Hermes architecture. It answers one
question: should the non-web product be written in Rust or Bun/TypeScript?

There is no universal winner. Rust is better at operating-system properties.
Bun/TypeScript is better at product-integration properties. Hermes is mostly
integration work, not systems work, so Bun wins on engineering economics unless
the integration surface is deliberately narrowed.

## Summary

- Rust wins on footprint, startup time, binary size, compile-time correctness,
  concurrency safety, and predictable runtime behavior.
- Bun/TypeScript wins on provider and platform SDK breadth, MCP and plugin
  extensibility, iteration speed, shared types with the web app, and the size of
  the contributor pool.
- The agent loop is dominated by model latency and tool I/O. Rust does not make
  the agent meaningfully faster. Its advantages are operational, not turn
  latency.
- A broad, plugin-heavy agent favors Bun/TypeScript. A narrow, lean,
  systems-quality agent favors Rust.

## Where Rust clearly wins

- **Footprint and startup.** A Rust daemon is typically tens of MB of RAM and
  single-digit milliseconds to start. Bun is tens of MB to low hundreds and tens
  of milliseconds. For a CLI used constantly or a daemon on a 2 vCPU VPS, Rust
  is materially better.
- **Distribution.** Rust produces a small native binary with no runtime. Bun's
  compiled binaries embed the runtime and are much larger. Rust cross-compilation
  is harder, but the output is leaner.
- **Compile-time correctness.** Ownership, `Result`, exhaustive matching, and
  strong types catch classes of bugs that TypeScript cannot.
- **Concurrency and cancellation.** Tokio plus Rust's type system is excellent
  for many concurrent streams, timeouts, and structured shutdown. It is more
  work to write, but it is more robust when done well.
- **TUI.** `ratatui` is excellent. If the terminal experience is a primary
  surface, Rust is a strong fit.
- **Predictable performance.** No garbage collector, no JIT warmup, no runtime
  surprises. Good for a long-lived daemon.
- **Crash isolation.** Rust services are easier to keep small and
  supervision-friendly.

## Where Bun/TypeScript clearly wins

- **Integration breadth.** LLM provider SDKs, MCP, messaging platform SDKs,
  browser automation, document parsing, OAuth flows, and web tooling are
  first-class in TypeScript and often lag or require raw HTTP in Rust. Hermes
  currently spans dozens of providers and platforms. That is the dominant cost.
- **Plugin and hook extensibility.** TypeScript supports dynamic import,
  workers, and in-process plugins cleanly. Rust has no stable ABI. Plugins
  become WASM, subprocesses, or MCP servers. That is fine if MCP is the plugin
  model, but it is a real constraint if rich in-process hooks are required.
- **Iteration speed.** The agent loop, prompts, context shaping, tool schemas,
  and provider quirks change constantly. Rust compile times and type ceremony
  slow that loop. Bun is effectively instant.
- **Shared types and UI.** Web, desktop, TUI, protocol clients, and design
  tokens can share one TypeScript codebase. Rust requires code generation for
  every boundary.
- **Contribution pool.** More people can read and extend TypeScript. That
  matters for plugins, skills, and community adapters.
- **Ecosystem churn.** Provider APIs change weekly. TypeScript SDKs and raw HTTP
  clients are faster to adapt. Rust adapters are more code per change.

## Where it is roughly a wash

- HTTP, SSE, and WebSocket clients.
- SQLite, WAL, and FTS.
- PTY support. Bun now has native PTY, including ConPTY. Rust has
  `portable-pty`.
- Config parsing, YAML/TOML, and JSON Schema.
- Testing frameworks.
- Observability. Both have good tracing and logging.
- Supply-chain risk. Crates and npm both need pinning and auditing.
- Memory safety. Rust prevents memory corruption. TypeScript also avoids manual
  memory management. The risk in TypeScript is type drift, not segfaults.

## Product-specific deciders

1. **Plugin model.** If users write small in-process tools and hooks,
   TypeScript is much better. If plugins are MCP servers or external processes,
   language is neutral.
2. **Provider and platform breadth.** A narrow v1 with three providers and two
   platforms is viable in Rust. Porting every current provider and adapter to
   Rust is a large, slow, low-leverage effort.
3. **TUI importance.** If the TUI is a flagship surface, `ratatui` is a real
   argument for Rust. If the TUI is a client of the same protocol and can stay
   simpler, TypeScript is fine.
4. **Target hardware.** Small VPS or embedded-like constraints favor Rust.
   Desktop and server with adequate RAM make Bun's footprint irrelevant.
5. **Team and timeframe.** A solo or small team gets a working, extensible
   system far faster in Bun. Rust buys operational quality at the cost of
   delivery speed.
6. **Correctness criticality.** The agent loop is orchestration over network
   I/O. Schema validation plus strict TypeScript catches most integration
   errors. Rust's advantage is largest in concurrency-heavy, stateful systems,
   not in JSON mapping.

## What a Rust-everything architecture looks like

It is coherent:

- Crates for types, config, store, providers, tools, agent, gateway, plugins,
  protocol, daemon, CLI, and TUI.
- `axum` plus `tokio-tungstenite` for HTTP and WebSocket.
- `sqlx` or `rusqlite` for SQLite, with checked-in migrations.
- `schemars` for JSON Schema, `ts-rs` for TypeScript types, and a generator for
  other clients.
- `ratatui` for the TUI.
- Tauri for desktop, with the same web UI.
- Plugins as WASM or MCP servers.
- A small TypeScript-only web app.
- Very small Docker images and Nix packages, with no Bun or Python at runtime.

Operationally, that is a better system. Engineering-wise, it is a longer build
with a harder extension story and slower iteration on the most volatile code.

## What a Bun/TypeScript architecture looks like

- One Bun workspace, one lockfile, one runtime.
- Bun for the daemon, CLI, TUI, gateway, providers, tools, store, and plugins.
- Vite for the web renderer.
- Tauri or Electron for desktop, with a Bun sidecar.
- MCP and TypeScript plugins.
- `bun build --compile` for binaries.
- Much faster to a working v1, and much easier for contributors and plugin
  authors.

Operationally, it is heavier than Rust but far leaner than the current Python
plus Node plus npm plus PM stack.

## Recommendation for the current product

Bun/TypeScript is the better engineering tradeoff. The value is in integrations
and extensibility, not raw systems performance. The agent's latency is dominated
by model calls and tool I/O, not by the runtime. Rust would make the daemon
leaner while making the product slower to build and harder to extend.

For a deliberately narrow product, Rust is defensible and possibly better. If v1
is a small core, MCP plugins, three providers, two platforms, a strong TUI, and
footprint and single-binary deployment matter, Rust is a legitimate first
choice. At that point the integration surface is small enough that Rust's costs
are bounded.

The worst outcome is a split core: Rust for some services and TypeScript for
others, without a hard protocol boundary. That gives you two ecosystems and the
complexity of both.

## Deciding question

The deciding question is not "Rust or Bun." It is:

**Do you want a broad, dynamic, plugin-heavy agent, or a narrow, lean,
systems-quality agent?**

The first points to Bun. The second points to Rust.
