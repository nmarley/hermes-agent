"""Core DEFAULT_CONFIG sections: model, agent, tools, display, and platform defaults."""

from hermes_config.defaults_shared import (
    DEFAULT_SANDBOX_IMAGE, DEFAULT_VERCEL_IMAGE, LEGACY_SANDBOX_IMAGE, LEGACY_SANDBOX_IMAGES,
    LEGACY_VERCEL_RUNTIME, _aux,
)

DEFAULT_CONFIG_CORE = {
    "model": "",
    "providers": {},
    "fallback_providers": [],
    # min_switch_reset_seconds: opt-in (0 = off). When a rate-limited primary declares a reset
    # sooner than this many seconds, stay on it (the retry backoff rides out the window) instead
    # of switching the turn to a fallback model.
    "fallback": {"min_switch_reset_seconds": 0},
    "credential_pool_strategies": {},
    "toolsets": ["hermes-cli"],
    # journal_mode: SQLite journal mode for every Hermes DB. "wal" default; use "delete" on
    # weak-fsync/shared filesystems where WAL is not crash-safe (macOS virtiofs, NFS, SMB).
    "database": {
        "journal_mode": "wal",
        # WAL sizing pragmas (ints). None = SQLite defaults (autocheckpoint 1000 pages, no limit).
        "wal_autocheckpoint": None,
        "journal_size_limit": None,
    },
    # Soft fd limit for long-running server processes; clamped to OS hard limit. 0/false/null = off.
    "runtime": {"nofile_soft_limit": 4096},
    # Global active chat session cap across CLI, TUI/dashboard, and messaging. None/0 = unbounded.
    "max_concurrent_sessions": None,
    # Soft LRU cap on in-memory TUI/desktop/dashboard sessions. Above it the gateway evicts the
    # least-recently-active DETACHED sessions (no live client); reopening re-resumes from disk.
    # 0/null disables.
    "max_live_sessions": 16,
    "session": {
        # Per-terminal `hermes -c`: each CLI session writes a breadcrumb under
        # $HERMES_HOME/terminal-sessions/<terminal-id>, so bare -c/--continue resumes THIS
        # terminal's session (tmux/kitty/wezterm pane, tty). false = resume globally most-recent.
        "terminal_continue": True,
    },
    # Where the TUI/desktop gateway stages session file attachments (uploads, pasted
    # text). "hermes-home" (default) keeps <profile home>/attachments — the dir
    # container backends bind-mount, so @file: refs resolve in the sandbox (#76577).
    # "workspace" opts into <session workspace>/.hermes/attachments: staging lands
    # inside the allowed ref root, so the same profile's agent can always read its
    # own attachments back (#110662). Read per profile from that profile's config;
    # a remote (ssh) workspace keeps the profile home dir either way.
    "attachments": {
        "storage": "hermes-home",
    },
    "agent": {
        # Turn cap. null = unlimited (default; caps caused silent mid-task truncation). Positive int
        # caps; "none"/"unlimited"/"inf"/0/-1 also mean unlimited (resolve_turn_limit).
        "max_turns": None,
        # Optional one-time model-visible checkpoint warning before a finite turn cap is exhausted.
        # null = off; set a ratio strictly between 0 and 1 (for example, 0.75).
        "budget_warning_ratio": None,
        # Wall-clock budget (seconds) per run. null = off. When set: one-time wrap-up notice at 80%
        # elapsed; implicit provider stale timeouts capped to remaining budget. CLI equivalent:
        # `hermes chat --run-budget N`.
        "run_budget_seconds": None,
        # Gateway inactivity timeout (seconds). Only fires when the agent is completely idle — not
        # while calling tools or receiving API responses. 0 = unlimited.
        "gateway_timeout": 1800,
        # Max seconds an alias routing key waits for the active turn holding the same session lease;
        # on expiry the message is rejected with a resend notice. Keep short: Telegram dispatches
        # sequentially, so a waiter delays unrelated topics. Non-positive -> 5s.
        "gateway_turn_lease_timeout": 5,
        # Per-session AIAgent cache in the gateway. Each entry keeps a warm prompt prefix AND the
        # full transcript: too small re-pays uncached prompts, too large fills the heap.
        "agent_cache": {
            "max_size": 128,  # LRU entry cap
            "idle_ttl_secs": 3600,  # evict agents idle this long
            # Anonymous-RSS budget (MB) above which LRU transcripts are shed (reloaded from disk
            # next turn). "auto" = derive from cgroup memory limit (or total RAM); number =
            # explicit; 0/off = disable the pass.
            "memory_high_mb": "auto",
            # Max sessions shed per pass (teardown bursts can't stall the gateway) and the number of
            # most-recently-used sessions the pass never touches.
            "max_evictions_per_pass": 16,
            "protect_recent": 8,
        },
        # Force-interrupt budget (seconds) once gateway stop()/drain has begun (SIGTERM, and the
        # final phase of in-band restart). 0 = interrupt immediately. Keep under systemd
        # TimeoutStopSec or risk SIGKILL mid-cleanup; for /restart prefer restart_after_turn_timeout
        # so turns finish BEFORE stop().
        "restart_drain_timeout": 0,
        # Floor under the stop()/drain wait (seconds) for cron jobs and api_server runs. Interrupted
        # chat turns resume on the next message, but an interrupted cron run is recorded as a
        # permanent failure and an interrupted /v1 run fails its waiting caller, so neither may
        # inherit restart_drain_timeout's 0 (#82161, #132989). Clamped to the shutdown-watchdog
        # leash minus teardown headroom (~50s unless TimeoutStopSec is raised). 0 = opt out.
        "cron_drain_timeout": 30,
        # In-band restart (/restart, SIGUSR1): refuse new work, then wait up to this many seconds
        # for in-flight agents/cron/api runs to finish before stop(). 0 = enter stop() at once. 30
        # min is a safety valve for wedged agents, not a target; raise for long unattended turns.
        # Default 30 min is a safety valve for wedged agents, not a target latency — an interactive `hermes
        # gateway restart` must never block for hours on a turn that wedged (#79133).
        "restart_after_turn_timeout": 1800,
        # Max seconds a submitted prompt waits for the deferred agent build (MCP discovery, model
        # metadata, skills scan) before failing visibly. The prompt is delivered as soon as the
        # build completes (progress notice past 30s), so this only fires on a hung build. Raise for
        # many slow/unreachable MCP servers.
        # See #63078.
        "build_wait_timeout": 600,
        # Hermes-level retry attempts for API errors (connection drops, timeouts, 5xx) wrapping the
        # whole call; the OpenAI SDK also retries transient errors (max_retries=2). Set 1 for fast
        # failover to fallback providers; raise to tolerate longer provider hiccups.
        "api_max_retries": 3,
        # Once api_max_retries AND the fallback chain are spent on a transient outage (5xx,
        # overloaded/529, connect/read timeouts) with nothing delivered yet, wait and retry this many
        # more cycles (jittered 15/30/60/60/60s; a provider Retry-After wins up to 120s) with a
        # visible "retrying automatically" countdown instead of ending the turn. Esc/interrupt stops
        # the wait; auth/format/billing/policy errors never enter. 0 disables.
        "auto_recovery_cycles": 5,
        # Seconds the Codex/Responses stream may keep reading after its terminal frame so the relay
        # finalizer can run. Relays that never close the SSE socket after response.completed would
        # otherwise wedge the turn until the idle watchdog discards the already-billed response
        # (#103864). 0 skips the drain. Well-behaved endpoints close immediately and never wait this long.
        "stream_drain_timeout": 2.0,
        # Empty-response retry guard. Empty retries re-send the full input at full price; this stops
        # re-billing deterministic empties (unsignaled refusals, zero output tokens) while failing
        # open on ambiguous evidence (missing usage, any tokens, model/provider change).
        "empty_response_guard": {
            "enabled": True,  # False = legacy fixed 3 retries unconditionally
            # When one empty attempt's estimated input cost >= this USD, the streak's retry budget
            # drops from 3 to 1. Unknown pricing / missing usage leaves it untouched.
            "cost_threshold_usd": 0.25,
        },
        # Fast mode: "" / "normal" (off), "fast" (always), "auto" (first fast_auto_seconds of every
        # turn), "cold" (first turn of a session only).
        "service_tier": "",
        "fast_auto_seconds": 60,
        # Responses API final-answer length (`text.verbosity`): "" = not sent (provider default),
        # or low | medium | high. Responses-family transports only; chat_completions never sends it.
        "text_verbosity": "",
        # System-prompt guidance telling the model to call tools instead of describing actions.
        # "auto" = gpt/codex models; true/false = force for all models; or a list of model-name
        # substrings (e.g. ["gpt", "codex", "gemini", "qwen"]).
        "tool_use_enforcement": "auto",
        # Execution-discipline prompt block (tool persistence, tools for arithmetic/system facts,
        # read-back after external writes, count reconciliation, literal identifiers,
        # verification-gated completion). Chosen once per session by model name (byte-stable).
        # "auto" = gpt/codex/grok/deepseek/kimi/qwen/glm/minimax/mimo/mistral; true/false = force;
        # or a list of model-name substrings.
        "execution_guidance": "auto",
        # When the model narrates an action ("I'll go check the logs...") but emits no tool call,
        # inject a "continue now, execute the tools" nudge and loop (max 2 nudges/turn). Corrective
        # sibling of tool_use_enforcement. "auto" = codex_responses api_mode only; true = all
        # api_modes (fixes Gemini/Claude "stops after stating intent"); false = never; or a list of
        # model-name substrings.
        "intent_ack_continuation": "auto",
        # Anti-stall guards: (1) identical-call loop breaker appends a notice when the same tool is
        # called 3+ times with identical args AND results (never blocks; pollers like `process`
        # exempt); (2) continue-intent extension of empty-response recovery re-prompts once when the
        # model says it will continue but takes no action. False disables both.
        "stall_guards": True,
        # "Finish the job" prompt block for all models: don't stop at a stub, never fabricate output
        # when the real path is blocked. ~80 cached tokens. False disables.
        "task_completion_guidance": True,
        # Prompt block for all models steering independent tool calls (reads, searches, fetches,
        # read-only commands) into one batched turn; the runtime already runs them concurrently. ~70
        # cached tokens. False disables.
        "parallel_tool_call_guidance": True,
        # Toolchain probe: surfaces Python/pip/uv/PEP-668 state in the system prompt only when
        # something non-default is detected (no pip module, pip/python mismatch, PEP 668 without
        # uv); zero tokens when clean. Skipped for docker/modal/ssh backends (own probe).
        "environment_probe": True,
        # Bot Mode teammate-messaging protocol section (silent unless desktop Bot Mode manages it).
        "bot_mode_protocol": True,
        # Embedder-supplied text appended to the system prompt's environment-hints block, so a host
        # wrapping Hermes (sandbox runner, managed platform) can describe proxy/credential/ mount
        # layout without editing SOUL.md. Env HERMES_ENVIRONMENT_HINT overrides it.
        "environment_hint": "",
        # Coding posture: on interactive coding surfaces (CLI, TUI, desktop, ACP) in a code
        # workspace, add a coding brief + live git/workspace snapshot to the system prompt
        # (agent/coding_context.py). "auto" = prompt-only when interactive AND cwd is a code
        # workspace (toolsets untouched, messaging platforms unaffected); "focus" = auto + collapse
        # toolset to the lean coding set (+ enabled MCP servers) + demote non-coding skill
        # categories to names-only (explicit opt-in); "on" = force everywhere; "off" = disable.
        "coding_context": "auto",
        # Standing operator instructions (string or list) appended to the coding brief as an extra
        # stable system block — project-wide workflow rules, e.g. "Don't run tsc/lint until I
        # approve." Cache-safe: takes effect next session.
        "coding_instructions": "",
        # When verify-on-stop finds edits without fresh verification evidence, add guidance for
        # creative UI work (no broad tsc/lint/test before visual approval) and clean-diff
        # expectations. false = keep the evidence nudge terse.
        "verify_guidance": True,
        # Max consecutive `pre_verify` "continue" nudges per turn (hooks can't trap the loop).
        "max_verify_nudges": 3,
        # Verification closure: after code edits in a workspace, refuse a final answer until fresh
        # verification evidence exists or the agent explains why it can't check (bounded loop,
        # passive ledger). False (default) because the nudges proved more noise than signal; true =
        # force on everywhere; "auto" = on for interactive coding surfaces and programmatic callers,
        # off for messaging surfaces. Doc/markdown/skill-only edits never fire.
        "verify_on_stop": False,
        # Inactivity warning (seconds), once per run before gateway_timeout; no interrupt. 0 = off.
        "gateway_timeout_warning": 900,
        # Max seconds any surface (CLI, TUI/Desktop, messaging gateway) blocks an agent awaiting a
        # clarify-tool reply; then it unblocks with "[user did not respond within Xm]". 0 or less =
        # unlimited. Resolved by tools/clarify_gateway.py::resolve_clarify_timeout (a legacy
        # top-level ``clarify.timeout`` still wins when explicitly set).
        # 1h because users step away and a shorter value evicted the entry mid-think so a later
        # button tap hit a dead entry. Tradeoff: a higher value holds the gateway's running-agent
        # guard longer for a genuinely abandoned prompt — lower it to free the guard sooner. See #32762.
        "clarify_timeout": 3600,
        # "Still working" status interval (seconds); 0 = off. Lower = faster feedback, more noise;
        # 180 catches spinning weak-model runs before users /restart.
        "gateway_notify_interval": 180,
        # Session stall watchdog (seconds): RECOVERY notifier for an in-process AIAgent with an
        # adapter-queued follow-up while its activity clock is stale — NOT a general stall detector
        # (ignores startup restore, build sentinels, leases, debounce, other processes; scan cadence
        # per AIAgent). Notify-only: tells the user to try /new. Distinct from gateway_timeout
        # (kills the turn) and gateway_notify_interval. 0 = disable.
        # See #76354.
        "session_stall_timeout": 300,
        # Transcript-sanitiser heal escalation: after this many pre-send heal passes within a
        # 10-minute window, log one ERROR and queue a ONE-TIME out-of-band notice pointing at /debug
        # share or `hermes doctor` (status channel only; prompt cache untouched). 0 = no escalation
        # (per-window WARNINGs still fire).
        # See #96870.
        "sanitizer_heal_escalation_threshold": 3,
        # Seconds of continuous reconnect failure before a platform gets needs_attention flagged in
        # gateway status (`hermes status` / fleet monitoring). Retries never stop — a signal, not a
        # circuit breaker. 0 = disable.
        "reconnect_attention_after": 7200,
        # Freshness window (seconds) for the auto-continue note. After a crash/restart mid-run the
        # next user message gets "[System note: your previous turn was interrupted...]" prepended;
        # only when the last persisted transcript row is younger than this, so stale markers don't
        # revive an unrelated old task. Covers gateway_timeout (1800) plus slack. 0 = always inject.
        "gateway_auto_continue_freshness": 3600,
        # Max seconds the gateway waits for boot auto-resume turns before releasing the
        # startup-restore inbound gate (all inbound is QUEUED while shut, so one long resumed turn
        # would leave every channel unanswered). On timeout the gate opens and the resume keeps
        # running in the background; duplicate-agent protection is unaffected because the resume
        # slot is claimed synchronously first. 0 = wait forever.
        "gateway_startup_restore_drain_timeout": 30,
        # Max seconds the boot turn-machinery warm-up (run_agent import graph, tool schemas +
        # availability probes, context-file tier) may hold the inbound gate shut, so an early
        # message isn't served with a skeleton system prompt. On timeout the gate opens and warm-up
        # finishes in the background. 0 = disable warm-up (lazy init).
        "gateway_startup_warmup_timeout": 20,
        # Stale-stream ceiling (seconds) for local providers (Ollama, oMLX, llama-cpp). Applied when
        # the base stale timeout is at its 180s default and a local endpoint is detected, so a
        # wedged local server eventually trips the detector instead of hanging forever. Env
        # HERMES_LOCAL_STREAM_STALE_TIMEOUT overrides.
        "local_stream_stale_timeout": 900,
        # How user-attached images reach the main model (gateway, TUI, CLI /attach). "auto" = native
        # when the model reports supports_vision=True AND auxiliary.vision.provider is not
        # explicitly set, else text; "native" = always attach (non-vision models error at the
        # provider or get a last-chance text fallback); "text" = always pre-analyze with
        # vision_analyze and prepend the description. vision_analyze stays a tool regardless.
        "image_input_mode": "auto",
        "disabled_toolsets": [],
        # Model name (any reasonable spelling) -> effort level; overrides agent.reasoning_effort
        # when the current model matches. Edit in config.yaml (no CLI support: dots in keys).
        "reasoning_overrides": {},
        # Stored reasoning is replayed to every provider that can read it by default. This flag
        # only adds the must-echo " " pad on reasoning-less tool-call turns, which DeepSeek,
        # Kimi/Moonshot and Xiaomi MiMo require (auto-detected by provider name/host). Set
        # `reasoning_echo: true` on a `model:` or `fallback_providers:` entry for a custom gateway
        # proxying one of them. Strict providers (Mistral, Groq, Cerebras) never get the field.
        "reasoning_echo": False,
        # Turn liveness watchdog: a turn with no observable progress for `timeout_s` seconds is
        # logged, force-interrupted so the UI can retry, and its lease stops renewing so stale-turn
        # cleanup can reclaim the session even if the interrupt can't unwind a wedged frame.
        # timeout_s <= 0 disables; poll_s = sampling interval. Invalid values (NaN, Inf,
        # non-positive poll) warn and fall back to defaults. See agent/turn_liveness.py.
        "turn_liveness": {"timeout_s": 600.0, "poll_s": 15.0},
    },

    "terminal": {
        "backend": "local",
        "modal_mode": "auto",
        # Remote-backend connection-class failures (SSH host unreachable, Docker daemon down):
        # "warn" = structured degraded tool result with reason + retry hint; "fail" = raise error +
        # traceback.
        "degraded_mode": "warn",
        "cwd": ".",  # Use current directory
        # Root for terminal session temp files (background logs/pid/exit files, code-exec
        # sandboxes). Empty = TMPDIR/TMP/TEMP if set, else HERMES_HOME/cache/terminal (auto-pruned
        # after 72h) — NOT tmpfs /tmp, which is RAM-capped and fills under load. Must be an existing
        # absolute POSIX path; user-set paths are never auto-pruned.
        "temp_dir": "",
        # CSS font-family for the desktop app's xterm.js terminal (e.g. "'CaskaydiaCoveNerdFont',
        # monospace"). Empty = built-in default ("'JetBrains Mono', 'Cascadia Code', 'SF Mono',
        # Menlo, Consolas, monospace"). Lets users use a Nerd Font without patching the app.
        "font_family": "",
        "timeout": 180,
        # Seconds between SIGTERM and escalated SIGKILL for host process trees (browser daemons). 0
        # = SIGTERM only.
        "daemon_term_grace_seconds": 2.0,
        # Max seconds a one-shot CLI run (-q/-Q/-z) lingers for tracked notify_on_complete
        # background processes to finish. The dying parent owns their stdout pipes, so exiting
        # immediately kills the delivery (e.g. Bot Mode handoff replies via message_agent /
        # bot_relay). Plain background processes without notify_on_complete are never waited on. 0
        # disables.
        "oneshot_completion_wait_seconds": 600.0,
        "process_wait_auto_notify": True,  # 2 unchanged wait/poll -> notify_on_complete + stop; False = old polling
        # Env vars passed into sandboxed terminal/execute_code (plus skill-declared required_environment_variables).
        "env_passthrough": [],
        "client_env_passthrough": [],  # Extra non-secret toolchain names a CLI/TUI client sends for its tools
        # Remote-backend sync-back refuses to extract a downloaded state archive larger than this
        # (bytes); raise it for a ~/.hermes tree that legitimately exceeds 2 GiB.
        "sync_back_max_bytes": 2 * 1024 * 1024 * 1024,
        # HOME for host tool subprocesses: "auto" = host keeps the real OS-user HOME, containers use
        # HERMES_HOME/home; "real" = force real HOME; "profile" = force HERMES_HOME/home when it
        # exists (strict per-profile isolation).
        "home_mode": "auto",
        # Extra files sourced in the login shell when building the per-session env snapshot — for
        # nvm/pyenv/asdf/PATH entries registered by files a bash login shell skips (~/.bashrc,
        # ~/.zshrc, ~/.zprofile). Supports ~ and ${VAR}; missing files skipped. When empty and the
        # shell is bash, ~/.profile, ~/.bash_profile, ~/.bashrc are auto-sourced in that order (see
        # auto_source_bashrc).
        "shell_init_files": [],
        # Source ~/.profile, ~/.bash_profile, ~/.bashrc in the snapshot login shell to capture PATH
        # additions, functions, and aliases that `bash -l -c` misses (bash skips bashrc when
        # non-interactive; Debian/Ubuntu ~/.bashrc short-circuits). ~/.profile and ~/.bash_profile
        # go first because n/nvm/asdf write PATH exports there without an interactivity guard. Turn
        # off if an rc file misbehaves when sourced non-interactively (exits on TTY check).
        "auto_source_bashrc": True,
        # The default sandbox for every container backend: the nikolaik/python-nodejs base
        # (Python 3.13 / Node 26) plus a display stack, so Bot Screen, computer_use and the
        # bot's browser run INSIDE the sandbox and the pane can watch them (see bot_desktop).
        "docker_image": DEFAULT_SANDBOX_IMAGE,
        "docker_forward_env": [],
        # Exact key-value env pairs set inside Docker containers (unlike docker_forward_env, which
        # reads host values) — useful under systemd without the user's shell env. Example:
        # {"SSH_AUTH_SOCK": "/run/user/1000/ssh-agent.sock"}
        "docker_env": {},
        "modal_image": DEFAULT_SANDBOX_IMAGE,
        "daytona_image": DEFAULT_SANDBOX_IMAGE,
        "vercel_image": DEFAULT_VERCEL_IMAGE,  # vercel_sandbox backend only: a Vercel-managed or VCR image
        "vercel_runtime": "",  # deprecated by Vercel; a legacy runtime pin (node24 | node22 | python3.13) overrides vercel_image
        # Container limits (docker, modal, daytona, vercel_sandbox, container plugin backends; not local/ssh).
        "container_cpu": 1,
        "container_memory": 5120,       # MB (default 5GB)
        "container_disk": 51200,        # MB (default 50GB)
        "container_persistent": True,   # Persist filesystem across sessions
        # Docker volume mounts, "host_path:container_path" (docker -v syntax), e.g.
        # ["/home/user/.hermes/cache/documents:/output"]. For gateway MEDIA delivery, write to
        # /output/... inside Docker and emit the host-visible path in MEDIA:, not the container one.
        "docker_volumes": [],
        "docker_mount_cwd_to_workspace": False,  # mount host cwd at /workspace (weakens isolation)
        "docker_network": True,  # false = --network=none, no network access from commands
        "docker_extra_args": [],        # Extra flags passed verbatim to docker run
        # /dev/shm size for the Docker sandbox. Docker's 64 MB default silently breaks
        # Chromium/Playwright and PyTorch DataLoader workers; tmpfs is lazily allocated so the
        # higher ceiling is free until used. "" or "0" = omit the flag (Docker default).
        "docker_shm_size": "1g",
        # Run the container as the host uid:gid (`--user`) so files written to bind mounts
        # (docker_volumes, persistent workspace, mounted cwd) are owned by you, not root. Off by
        # default for images whose entrypoints must start as root (e.g. the bundled Hermes image,
        # which drops to `hermes` via s6-setuidgid). When on, SETUID/SETGID caps are omitted.
        "docker_run_as_host_user": False,
        # Snap-packaged Docker under AppArmor (Ubuntu cloud images; LP#1908448) refuses to exec
        # anything under `--init` or `--security-opt no-new-privileges` ("operation not
        # permitted"). True drops those two flags; every other hardening stays. See #9730.
        "docker_snap_compat": False,
        # Trusted profiles sharing one Docker container identity; empty = per-profile boundary.
        "docker_shared_container_key": "",
        # SSH: carry exported env vars between commands (cwd always carries). false = every command
        # starts from the login env, profile functions included. Local: TERMINAL_LOCAL_PERSISTENT.
        "persistent_shell": True,
    },

    "web": {
        "backend": "",           # shared fallback — applies to both search and extract
        "search_backend": "",    # per-capability override for web_search (e.g. "searxng")
        "extract_backend": "",   # per-capability override for web_extract (e.g. "native")
        # per-page char budget for web_extract; larger pages truncate, full text kept in cache/web
        "extract_char_limit": 15000,
        # Keyless free-tier ring: with NO web backend configured or keyed, web_search/web_extract
        # rotate round-robin across exa, parallel, firecrawl, keenable public free tiers, failing
        # over on rate limits. Never pre-empts a configured/keyed backend. false = disable.
        "keyless_fallback": True,
        # One-shot rescue: when the chosen/keyed backend fails a call, THAT call retries once on the
        # keyless ring; the next call tries the chosen backend again (no sticky failover). Off when
        # keyless_fallback is false.
        "keyless_rescue": True,
        # Per-vendor tier for vendors with both a keyless free endpoint and a keyed paid path (exa,
        # parallel, firecrawl, keenable; tavily is opt-in keyless via `hermes tools`, not a ring
        # member). Set by the `hermes tools` picker. "free" = always anonymous endpoint even with a
        # key; "paid" = always keyed (missing key = error; vendor excluded from the ring); unset =
        # keyed when the key is present, else the ring.
        "provider_tier": {},
        # TTL caching for web_search + web_extract: repeat searches (same query + provider) within
        # the TTL come from an in-process memo; repeat extracts from the cache/web store. Concurrent
        # identical searches coalesce into one vendor request. Only successes cached.
        "cache_enabled": True,
        "cache_ttl_minutes": 20,
        # Hosts always fetched live, never from the extract cache (staging deploys, tunnel URLs,
        # preview builds). Entries match exactly, as "*.wildcard", or as a domain suffix
        # ("mysite.dev" also covers "preview.mysite.dev"). localhost/private IPs always exempt.
        "cache_exempt_hosts": [],
    },

    "browser": {
        # "" = Browser Use mode when the browser-use CLI (or uvx) is available, else built-in tools
        # (Camofox setups always keep built-in tools: no CDP surface); "browser-use" = force one
        # browser_exec tool driving the Browser Use CLI over any CDP backend (local Chrome, cloud);
        # "off" = force the built-in browser_navigate/browser_click/... tools.
        "backend": "",
        "inactivity_timeout": 120,
        "command_timeout": 30,  # seconds per browser command (screenshot, navigate, etc.)
        "snapshot_threshold": 15000,  # max chars before snapshot truncate-and-store (min 1000)
        "record_sessions": False,  # auto-record browser sessions as WebM videos
        # headed: visible Chromium window (local); skips per-turn cleanup, idle reaper still applies
        "headed": False,
        "allow_private_urls": False,  # allow private/internal IPs (localhost, 192.168.x.x, ...)
        # Local browser engine for both drivers. "auto" = Chrome; "lightpanda" = faster navigation,
        # no screenshots (Browser Use mode spawns `lightpanda serve` per session; built-in tools
        # pass `--engine <value>` to agent-browser with Chrome fallback); "chrome" = explicit.
        # Ignored while a cloud provider, Camofox, cdp_url or use_real_profile is active. Also
        # settable via AGENT_BROWSER_ENGINE.
        "engine": "auto",
        # With a cloud provider, auto-spawn local Chromium for LAN/localhost URLs instead
        "auto_local_for_private_urls": True,
        "cdp_url": "",  # persistent CDP endpoint for attaching to an existing Chromium/Chrome
        # Consent to browse with the user's REAL logins locally: runs on a Hermes-managed SNAPSHOT
        # of the ACTIVE default-Chromium profile (Local State -> profile.last_used; cookies, logins,
        # prefs copied and re-synced per fresh session) driven by Hermes' packaged Chromium. The
        # snapshot dir sidesteps Chrome 136+'s default-profile debugging block and never contends
        # with the running browser. Turning off deletes ~/.hermes/browser-profile/ so credentials
        # don't outlive consent. Chromium-family only; a profile that can't be copied (Firefox default,
        # Windows browser holding its cookies) gives a fresh, signed-out browser plus a note saying why.
        # Also gates the browser_exec `local` arg (real-profile session under a cloud backend). Desktop Settings -> Browser.
        "use_real_profile": False,
        # Windows only: a running Chrome/Edge/Brave locks its cookie DB (the last snapshot is reused;
        # with none yet, a fresh browser runs). When on, the agent ASKS first; on approval it runs
        # `hermes browser close-profile` (kills that profile's browser tree, unsaved tabs lost) so a
        # new session can copy it; no auto-kill. No effect on macOS/Linux, where a running
        # browser only locks the password/autofill DBs, which are skipped (cookies still copy).
        "real_profile_autoclose": False,
        # Pin WHICH source profile directory is snapshotted for real-profile browsing (e.g. "Profile
        # 2"). Empty = browser's last-used profile, which on multi-profile machines can hand the
        # agent the wrong identity. A pin naming a missing directory never falls back to another
        # profile: the session gets a fresh browser without the user's logins.
        "real_profile_pin": "",
        # restrict_evaluate: opt-in denylist blocking sensitive JS primitives (cookies/storage/
        # clipboard/network/form values) in browser_console(expression=...); allow_unsafe_evaluate
        # is the legacy override that bypasses that denylist entirely.
        "allow_unsafe_evaluate": False,
        "restrict_evaluate": False,
        # CDP supervisor: dialog + frame detection over a persistent WebSocket; active only with a
        # CDP-capable backend (Browserbase, or local Chrome via /browser connect). See
        # website/docs/developer-guide/browser-supervisor.md.
        "dialog_policy": "must_respond",  # must_respond | auto_dismiss | auto_accept
        "dialog_timeout_s": 300,  # safety auto-dismiss after N seconds under must_respond
        "camofox": {
            # true = send a stable profile-scoped userId so Camofox maps it to a persistent Firefox
            # profile; false = random ephemeral userId per session.
            "managed_persistence": False,
            # Externally managed Camofox identity, for when another app owns the visible browser.
            "user_id": "",
            "session_key": "",
            "adopt_existing_tab": False,  # rehydrate tab_id from Camofox before creating a tab
            # Docker Camofox opens page URLs from inside the container: rewrite loopback page URLs
            # (localhost/127.0.0.1/::1) to the host alias; CAMOFOX_URL itself is unchanged.
            "rewrite_loopback_urls": False,
            "loopback_host_alias": "host.docker.internal",
        },
        # Authenticated browser-extension controller lane: a registered extension can become the
        # exact controller for a session's browser_* tools (fail-closed once bound). Local API
        # registration also requires the API server bearer key. developer_mode gates the privileged
        # browser_cdp / browser_evaluate capabilities.
        "extension_control": {"enabled": False, "developer_mode": False},
    },
    # Stale git worktree lifecycle (`hermes -w`, `/worktree new`, subagent isolation, Desktop). The
    # sweep runs at `hermes -w` startup and every 6h from the cron ticker over every repo Hermes made
    # a worktree in. Trees idle past their tier (hermes-*/subagent-* 24h, named 72h) that are clean
    # and merged are removed; dirty or unpushed ones are archived to refs/hermes/archive/<tree>
    # first (`hermes worktree restore <name>`). Live trees and Kanban t_<hex> trees are never touched.
    "worktrees": {
        # false = never remove a dirty/unpushed tree (the pre-archive behaviour, exactly).
        "archive_dirty": True,
        # Untracked files larger than this (MB) are not archived, so a tree holding one is kept.
        "archive_max_file_mb": 50,
        # The sweep deletes archive refs older than this many days. 0 keeps them forever.
        "archive_retention_days": 30,
        # Optional size budget (GB) for idle trees: past it the oldest idle trees are archived and
        # removed first. Live, young and Kanban trees are never counted or touched. 0 = off.
        "max_total_gb": 0,
    },
    # Filesystem checkpoints: snapshot the working directory once per turn (on the first
    # write_file/patch call); restore with /rollback. Opt-in via `hermes chat --checkpoints` or
    # enabled=True (most users never use /rollback). Single shared shadow store with real pruning.
    "checkpoints": {
        "enabled": False,
        # Max checkpoints per working directory; enforced by ref rewrite + GC of older commits.
        "max_snapshots": 20,
        # Hard ceiling on total ~/.hermes/checkpoints/ size (MB); the oldest checkpoint per project
        # is dropped round-robin until under the cap. 0 disables.
        "max_total_size_mb": 500,
        # Skip files larger than this (MB) when staging (datasets, model weights). 0 = no filter.
        "max_file_size_mb": 10,
        # Background sweep (CLI helper thread / gateway housekeeping tick, at most once per
        # min_interval_hours; never on the startup path — its git gc can block for tens of seconds):
        # deletes projects whose last_touch is older than retention_days, GCs the shared store when
        # refs moved, enforces max_total_size_mb, deletes legacy-* archives older than retention_days.
        # It NEVER deletes orphans (workdir missing on
        # disk) — a missing workdir may just be an unmounted volume/VPN, and an unattended sweep
        # must not guess. Orphans: `hermes checkpoints prune` (`--keep-orphans` to skip).
        "auto_prune": True,
        "retention_days": 7,
        "min_interval_hours": 24,
    },
    # Hard cap (chars) for one auto-loaded context file (SOUL.md, AGENTS.md, CLAUDE.md, .hermes.md,
    # .cursorrules) before head/tail truncation. null = scale with the model's context window (floor
    # 20K, ceiling 500K); a positive int pins a fixed cap. Separate from read_file limits.
    "context_file_max_chars": None,
    # Seconds to wait for a single context file read before skipping it with a warning. Guards startup
    # against network-backed filesystems (iCloud Drive, OneDrive, NFS) that can block a cold read.
    "context_file_read_timeout": 5.0,
    # Max chars per read_file call; larger reads are rejected with offset+limit guidance. 100K chars
    # ≈ 25–35K tokens.
    "file_read_max_chars": 100_000,
    # Seconds the first agent build waits for background MCP discovery before snapshotting its tool
    # list. Returns the instant discovery completes (no MCP servers → ~0s); the bound only bites
    # when a server is still connecting. Turn-1 latency knob only: a server that misses it is picked
    # up by the between-turns refresh (agent/turn_context.py), so keep it small — a dead server adds
    # this much to first-response latency.
    "mcp_discovery_timeout": 1.5,
    # Same bound for single-query mode (``hermes -q/-z``). With only ONE turn there is no
    # between-turns refresh, so a server that misses the window is invisible for the whole session;
    # the larger bound lets slow cold-start servers (npx, uvx, remote HTTP) land. Reachable servers
    # still only wait their real handshake time.
    "mcp_single_query_discovery_timeout": 15.0,
    "mcp": {  # MCP runtime behavior (distinct from mcp_servers: definitions and auxiliary.mcp).
        # Auto-reload MCP connections when config.yaml's mcp_servers changes (CLI watcher). Every
        # reload rebuilds the tool surface and INVALIDATES the provider prompt cache (next message
        # re-sends the full prefix) — costly on long-context models. When false the watcher still
        # detects the change and prints /reload-mcp guidance.
        "auto_reload_on_config_change": True,
        # Max MCP servers connected (and their stdio child trees spawned) at once per discovery
        # pass — at boot, on /reload-mcp and on the config watcher's reconcile. Unbounded, a config
        # with N servers spawns N process trees in the same instant (RAM/CPU spike, 429 fan-out on
        # multi-profile fleets). 0 = unlimited.
        "discovery_concurrency": 4,
    },
    # Tool-output truncation. max_bytes: terminal_tool output cap in chars (head+tail kept; 50_000 ≈
    # 12-15K tokens). max_lines: max `limit` one read_file call may request before clamping.
    # max_line_length: per-line cap in read_file's line-numbered view (chars).
    "tool_output": {"max_bytes": 50000, "max_lines": 2000, "max_line_length": 2000},
    # Tool loop guardrails nudge models that repeat failed/non-progressing tool calls. Soft warnings
    # are always on; hard stops are opt-in so interactive sessions keep flowing.
    "tool_loop_guardrails": {
        "warnings_enabled": True,
        "hard_stop_enabled": False,
        # Unattended gateway/cron platforms hard-stop by default (nobody can /stop a model that
        # ignores warnings); interactive cli/tui/desktop/acp stay warning-only.
        "non_interactive_hard_stop_enabled": True,
        "warn_after": {"exact_failure": 2, "same_tool_failure": 3, "idempotent_no_progress": 2},
        "hard_stop_after": {
            "exact_failure": 5, "same_tool_failure": 8, "idempotent_no_progress": 5
        },
        # Per-turn hard ceilings for runaway-prone tools; counters reset every turn, always on
        # regardless of the thresholds above. Dozens of searches/subagents in ONE turn is already
        # pathological, hence low defaults. 0 = unlimited.
        "loop_caps": {
            "max_web_searches": 50,   # web_search calls per turn
            "max_subagents": 50,      # subagents spawned per turn
        },
    },

    "compression": {
        "enabled": True,
        # checkpoint_required: fail closed before lossy compaction unless an active memory provider
        # confirms checkpoint API compatibility and completes the checkpoint.
        "checkpoint_required": False,
        # progress_notices: when True, routine compression progress statuses (compacting/
        # preflight/pre-API/idle/retry) reach chat gateways instead of being filtered as noise.
        # Failure notices and manual /compress feedback are always visible.
        "progress_notices": False,
        # threshold: compress when context usage exceeds this ratio. Models with windows below 512K
        # are floored at 0.75 (raise-only) so compaction doesn't fire with half the window free; set
        # above 0.75 to override the floor.
        "threshold": 0.50,
        # threshold_tokens: optional absolute token cap — when set, compression triggers at the
        # lower of the ratio threshold and this count. Clamped to the model's context length.
        # Off by default: no single count suits windows from 64K to 1M+, so the ratio decides.
        "threshold_tokens": None,
        # "progress_notices": False,    # opt-in (#52995): when True, routine compression
        "target_ratio": 0.20,         # fraction of threshold to preserve as recent tail
        # tail_mode: "lean" = clamped 2.5%-of-window tail (10K floor / 25K cap) plus chunked
        # digests, anchor index, verbatim user messages and session_search pointers in the summary
        # (~3x fewer retained tokens; a few extra summarizer calls at the boundary). "legacy" =
        # 0.20×threshold verbatim tail (100-240K tokens on big windows).
        "tail_mode": "lean",
        # protect_last_n: minimum recent messages kept uncompressed, honoured up to a small count
        # floor; the verbatim tail is otherwise token-bounded and never above 20% of the window.
        "protect_last_n": 20,
        # min_tail_user_messages: REAL (actionable) user messages guaranteed to survive in the tail.
        # 1 = single last-user anchor; raise (e.g. 3) when bulky tool outputs fill the tail budget.
        "min_tail_user_messages": 1,
        # max_attempts: retry rounds before a turn gives up with "max compression attempts reached".
        # Raise (e.g. 6) for tool-schema-heavy sessions. Validated >= 1, cap 10.
        "max_attempts": 3,
        # proactive_prune_tokens: opt-in trigger (tokens) for the deterministic no-LLM tool-result
        # prune, independent of `threshold` (which rarely fires on large windows, so old tool output
        # is re-sent every turn); e.g. 48000 reclaims early. 0 = off. Tail protected by
        # `protect_last_n`. Built-in compressor only. Each committed prune rewrites sent history and
        # breaks the prompt-cache prefix — the min_reclaim gate below keeps those breaks episodic.
        "proactive_prune_tokens": 0,
        # Prune's summarize pass only touches tool results larger than this (chars); clamped >= 200
        # so a generated summary can't be re-summarized.
        "proactive_prune_min_result_chars": 8000,
        # A prune only commits when it reclaims at least this many tokens, then waits for a
        # trigger-sized runway to regrow before rearming. 0 = no minimum-savings gate.
        "proactive_prune_min_reclaim_tokens": 4096,
        # micro_compact: opt-in — after each turn fold the oldest un-absorbed exchange into a
        # rolling summary, amortizing compression cost. Off by default because every pass rewrites
        # sent history and breaks the prompt-cache prefix EVERY turn; enable only if the amortized
        # stall beats the cached-prefix discount. See website/docs/developer-guide/micro-compaction.md.
        "micro_compact": False,
        # Cadence: run a pass every Nth completed turn (1 = one cache break per turn, 5 = a fifth of
        # the breaks). Clamped >= 1; ignored unless micro_compact is true.
        "micro_compact_every_n_turns": 1,
        # Once the rolling summary exceeds this many tokens, the next pass re-summarizes it.
        "micro_compact_defrag_threshold_tokens": 2000,
        # Gateway session-hygiene force-compress threshold, by message count.
        "hygiene_hard_message_limit": 5000,
        # Max seconds the gateway waits for pre-agent hygiene compression WITHOUT forward progress.
        # Inactivity budget: a slow model still streaming tokens extends the wait.
        "hygiene_timeout_seconds": 30,
        # Absolute cap on the hygiene wait even while tokens are moving (bounds a trickle stream).
        # Clamped >= hygiene_timeout_seconds.
        "hygiene_total_ceiling_seconds": 600,
        "hygiene_failure_cooldown_seconds": 300,  # skip repeated failed hygiene attempts
        # Max seconds an ARRIVING user turn is held while a streaming hygiene summary finishes;
        # bounds user-visible latency (keep under chat idle timeouts, Telegram ~30s). On expiry the
        # turn proceeds uncompressed; the detached worker keeps its watermark-fenced commit, so the
        # summary is adopted at the next safe boundary.
        "hygiene_max_turn_hold_seconds": 10,
        # Inactivity budget for in-agent compress_context (loop, /compress, preflight); same
        # progress-aware semantics as hygiene_timeout_seconds. 0 = disable the owned wrapper
        # (callers passing commit_fence, e.g. gateway hygiene, never use it). Floored at the auxiliary
        # compression request timeout (auxiliary.compression.timeout, min 300s): the host never judges
        # silence before the summary request itself would time out.
        "context_timeout_seconds": 120,
        # Absolute cap on the *pre-commit* compress_context wait (summary/stream phase) even while
        # tokens move. Clamped >= context_timeout_seconds when that is > 0. A started SessionDB
        # commit is never abandoned: past the ceiling it is logged (WARNING, then ERROR) and
        # surfaced on the warning channel while the host keeps waiting.
        "context_total_ceiling_seconds": 600,
        # Non-system head messages always kept verbatim, in ADDITION to the (always protected)
        # system prompt. 0 = pin nothing but system prompt + summary + tail.
        "protect_first_n": 3,
        # When True, auto-compression whose summary fails (aux error / non-JSON / timeout) aborts
        # instead of dropping the middle with a "summary unavailable" placeholder; the session
        # freezes at its size until /compress (bypasses the cooldown) or /new.
        "abort_on_summary_failure": False,
        # (Historical key name.) When True, gpt-5.4/5.5/5.6 and gpt-6 Astra (any slug containing
        # "astra" without "900k") on the ChatGPT Codex OAuth route raise their compaction trigger to
        # 85%: Codex hard-caps them at a 272K window, so the global 50% would compact at ~136K. False = global `threshold`. Only that route; the same models via
        # OpenAI direct, OpenRouter or Copilot keep the global value.
        "codex_gpt55_autoraise": True,
        # Show the one-time autoraise banner; False keeps the autoraise, hides the notice.
        "codex_gpt55_autoraise_notice": True,
        # Codex app-server thread compaction mode. The codex agent owns the thread context, so
        # Hermes' summarizer cannot shrink it. native = codex decides; hermes = Hermes' threshold
        # triggers thread/compact/start; off = never auto-trigger.
        "codex_app_server_auto": "native",
        # Opt in to OpenAI server-side compaction on the Responses API. Only gpt-5.6-family on
        # api.openai.com or the Codex backend; local compression stays as fallback.
        "codex_responses_native": False,
        # Absolute server compaction trigger (input tokens). None follows the local trigger with a
        # safety margin; explicit values only clamp downward so the server goes first.
        "codex_responses_compact_threshold": None,
        # in_place: compaction rewrites the message list and system prompt WITHOUT rotating the
        # session id (no parent_session_id chain, no `name #N` renumbering), avoiding the
        # session-rotation bug cluster. Pre-compaction turns are soft-archived under the same id
        # (active=0, compacted=1) — still session_search-able. False = legacy rotating-compaction
        # path.
        "in_place": True,
        # Per-model threshold overrides: keys substring-match the model name (longest wins), values
        # replace the global `threshold`, e.g. {"glm-5.2": 0.40}. Prefix a key with "<provider>:" to
        # scope it to one route ({"openai-codex:astra": 0.85} leaves Astra on OpenRouter/Nous at the
        # global value). The <512K floor (0.75) still applies raise-only on top.
        "model_thresholds": {},
        # Opt-in idle compaction (0 = off): a session resuming after this many idle seconds compacts
        # up front, before the first reply. Time-based complement to `threshold`; skipped when
        # already at/below threshold × target_ratio; honors the same cooldown/ anti-thrash/lock
        # guards. Example: 1800 = 30 min.
        "idle_compact_after_seconds": 0,
    },
    # Anthropic prompt caching (Claude via OpenRouter or native API). cache_ttl: "5m" | "1h" | "auto"
    # (auto = 1h for human-paced sessions — cli/tui/desktop/messaging — and 5m for subagent, cron,
    # oneshot, webhook, kanban, api, tool, batch); other non-falsy values are ignored; falsy (false, null, "off",
    # "disabled", "no", "none") disables caching.
    "prompt_caching": {"cache_ttl": "5m"},
    # OpenRouter settings. response_cache: X-OpenRouter-Cache header — identical requests return
    # cached responses at zero billing; independent of Anthropic prompt caching. response_cache_ttl:
    # seconds (1-86400), only used when response_cache is on. min_coding_score (0.0-1.0):
    # pareto-code router knob, applied only when model.model is "openrouter/pareto-code"; higher =
    # stronger/pricier coders, 0.65 = mid-tier, "" = let OpenRouter pick the strongest. Docs:
    # openrouter.ai/docs/guides/routing/routers/pareto-router
    "openrouter": {"response_cache": True, "response_cache_ttl": 300, "min_coding_score": 0.65},
    "bedrock": {  # AWS Bedrock; only used when model.provider is "bedrock".
        "region": "",  # empty = AWS_REGION env var → us-east-1
        "discovery": {
            "enabled": True,           # auto-discover models via ListFoundationModels
            "provider_filter": [],     # restrict to these providers, e.g. ["anthropic", "amazon"]
            "refresh_interval": 3600,  # cache discovery results (seconds)
        },
        # Bedrock Guardrails: create one in the console, then set ID and version.
        # https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html
        "guardrail": {
            "guardrail_identifier": "",  # e.g. "abc123def456"
            "guardrail_version": "",     # e.g. "1" or "DRAFT"
            "stream_processing_mode": "async",  # "sync" | "async"
            "trace": "disabled",         # "enabled" | "disabled" | "enabled_full"
        },
    },
    # Auxiliary model config — provider/model per side task. provider "auto" = auto-detect;
    # empty model = provider's default aux model; all tasks fall back to
    # openrouter:google/gemini-3-flash-preview when the configured provider is unavailable.
    # extra_body is forwarded verbatim as request body fields for that task, e.g. OpenRouter
    # routing prefs / Pareto Code floor:
    #   auxiliary:
    #     compression:
    #       extra_body:
    #         provider: {order: [anthropic, google], sort: throughput}  # or price | latency
    #         plugins: [{id: pareto-router, min_coding_score: 0.5}]
    # Each task is independent — main-agent provider_routing and openrouter.min_coding_score
    # do NOT propagate to aux calls by design.
    "auxiliary": {
        # Same-provider retries for a transient blip (reset/timeout/5xx/408) on ANY aux call before
        # falling back; clamped [0,6]. Matters for pinned calls (MoA advisors) where provider
        # fallback is not meaningful recovery.
        "transient_retries": 2,
        # When true, the auto-chain's OpenRouter step is skipped unless the fallback model ends in
        # ":free" — a PAID lane is never used for background aux traffic even with
        # OPENROUTER_API_KEY set.
        "free_only": False,
        # Override the auto-chain's OpenRouter fallback model (default google/gemini-3.6-flash,
        # PAID). Pair e.g. "nvidia/nemotron-3-ultra-550b-a55b:free" with free_only: true. A one-time
        # WARNING is logged whenever a non-":free" model is engaged.
        "openrouter_model": "",
        # Endpoints that reject NON-streaming chat (HTTP 400): aux calls are sent with stream=True
        # and aggregated. Case-insensitive URL substrings; copilot.tencent.com is always
        # stream-only.
        "stream_only_base_urls": [],
        # Per-task blocks share one shape (_aux): provider "auto" = inherit the main model; base_url
        # overrides provider; api_key falls back to OPENAI_API_KEY; reasoning_effort:
        # none|minimal|low|medium|high|xhigh|max|ultra ("" = provider default); extra_body =
        # OpenAI-compatible request fields. Vision: download_timeout = image HTTP download (s).
        "vision": _aux(120, download_timeout=30),
        # web_extract and session_search no longer use an aux LLM; leftover blocks in user config
        # are ignored. Compression: raise timeout for local models. no_progress_timeout:
        # seconds a streamed call goes without a substantive chunk before it fails fast into
        # retry/fallback; None = built-in 60s default. Independent of "timeout" (the overall request
        # budget) — raising "timeout" alone does not widen this window. See #108104.
        "compression": _aux(120, no_progress_timeout=None),
        "skills_hub": _aux(30),
        "approval": _aux(30),   # classifier — a fast/cheap model is recommended
        # /review reviewer: a full subagent on the async delegation rail, credentials resolved like
        # delegation.provider pins. "auto" + "" = main agent's model. api_mode forces transport:
        # chat_completions | anthropic_messages | codex_responses.
        "review": {"provider": "auto", "model": "", "base_url": "", "api_key": "", "api_mode": ""},
        "mcp": _aux(30),
        # prefer_fast_model opts in to the provider fast tier; auto otherwise = main model.
        "title_generation": {
            "enabled": True,
            "model_upgrade_enabled": True,  # False = keep the instant derived title, never call a model
            # session_search no longer uses an aux LLM (#27590); leftover auxiliary.session_search is ignored.
            "provider": "auto",
            "model": "",
            "prefer_fast_model": False,
            "base_url": "",
            "api_key": "",
            "timeout": 30,
            "extra_body": {},
            "reasoning_effort": "",
            "language": "",
        },
        "memory_query_rewrite": _aux(8, reasoning_effort=False),
        "tts_audio_tags": _aux(30),
        "voice_chat": {**_aux(120), "reasoning_effort": "none"},  # agent/voice_turn_route.py; off = lowest valid
        # Kanban: triage_specifier expands a Triage one-liner into a spec (cheap model OK);
        # kanban_decomposer emits a JSON graph of child tasks (more tokens).
        "triage_specifier": _aux(120),
        "kanban_decomposer": _aux(180),
        "profile_describer": _aux(60),   # 1-2 sentence profile blurb; short, cheap
        "goal_judge": _aux(60),          # /goal satisfaction + contract drafting; JSON calls
        # Curator skill-usage review can take minutes on reasoning models (umbrellas over hundreds
        # of skills); route cheaper via `hermes model` → auxiliary → Curator.
        "curator": _aux(600),
        "monitor": _aux(60),   # important-mail 0-10 scorer; high-volume, small model fine
        # Post-turn self-improvement fork (save memory / patch skill). "auto" = main model replaying
        # the full conversation (warm cache); other models replay a compact digest (~3-5x cheaper).
        # enabled=false skips auto spawns (/refine still works). An explicit max_input_tokens caps
        # the SUM of replayed input tokens over the review loop (iterations capped at 16); the loop
        # stops before crossing it. When unset, the runtime derives a budget from the active model
        # context window. <= 0 = unlimited.
        # reasoning_effort is IGNORED while the review stays on the main model: the fork inherits the
        # conversation's reasoning config verbatim so its request bytes keep the parent's warm
        # prompt-cache prefix (#30532). Set provider/model below to route the review to another model
        # if you want a different effort level; a one-time warning says so when the key is set.
        "background_review": {"enabled": True, **_aux(120)},
        # No reasoning_effort on MoA blocks by design — configured PER SLOT in the preset
        # (moa.presets.<name>.reference_models[].reasoning_effort / aggregator.reasoning_effort).
        "moa_reference": _aux(900, reasoning_effort=False),
        "moa_aggregator": _aux(900, reasoning_effort=False),
    },

    "display": {
        "compact": False,
        "personality": "",
        "resume_display": "full",
        # Recap tuning for /resume and startup resume.
        "resume_exchanges": 10,            # max user+assistant pairs to show
        "resume_max_user_chars": 300,      # truncate user message text
        "resume_max_assistant_chars": 200, # truncate non-last assistant text
        "resume_max_assistant_lines": 3,   # truncate non-last assistant lines
        # Skip tool-call-only assistant entries in the recap so it isn't dominated by `[2 tool
        # calls: ...]` lines; False shows them inline.
        "resume_skip_tool_only": True,
        "busy_input_mode": "interrupt",  # interrupt | queue | steer
        # steer mode: false hides only the "Steered into current run" bubble; steering itself still
        # happens.
        "busy_steer_ack_enabled": True,
        # Classic CLI multiline beyond Alt+Enter: Ctrl+J newline, trailing backslash+Enter
        # continues, Shift+Enter reported distinctly. False restores the c-j submit fallback for
        # POSIX PTYs whose plain Enter arrives as LF.
        "cli_multiline_shortcuts": True,
        # `hermes`/`hermes chat` launches "cli" (prompt_toolkit REPL) | "tui" (Ink); --cli, --tui, HERMES_TUI=1 win.
        # cli_layout = the REPL's look: "modern" (glyph rows, status under the composer) | "classic" (boxed panels).
        "interface": "cli", "cli_layout": "modern",
        # Native TUI uses the terminal's primary buffer and scrollback instead of the custom
        # alternate-screen viewport. Flags win: `--native` / `--tui-native` and `--cli`.
        "tui_native": False,
        # `hermes --tui` auto-resumes the most recent human-facing session (like `hermes -c`).
        # HERMES_TUI_RESUME=<id> always wins.
        "tui_auto_resume_recent": False,
        # Desktop reopens the last chat/page on cold start (also in Settings → Appearance).
        "resume_last_session": True,
        # One-time TUI hint ("subagents working · /agents to watch live") on first delegation.
        "tui_agents_nudge": True,
        "bell_on_complete": False,
        "bell_on_prompt": False,   # bell when a blocking prompt opens (clarify/approval/sudo)
        # Stream reasoning live before the response; otherwise thinking models show only a spinner
        # for tens of seconds.
        "show_reasoning": True,
        # Post-response "Reasoning" recap collapses to 10 lines; true prints it all (live streaming
        # is always full).
        "reasoning_full": False,
        # Background self-improvement notices in chat: "off" (review still runs) | "on" (generic "💾
        # Memory updated") | "verbose" (content preview). Per-platform via
        # display.platforms.<platform>.memory_notifications.
        "memory_notifications": "on",
        # Gateway notices when a terminal(background=true) process finishes: "concise" (one line;
        # failures append an output tail) | "all" (running updates + final raw output) | "result"
        # (final raw only) | "error" (raw only on non-zero exit) | "off".
        "background_process_notifications": "concise",
        "streaming": False,
        "timestamps": False,      # message timestamps (CLI labels, TUI rows, desktop transcript)
        "timestamp_format": "%H:%M",  # strftime format, e.g. "%b-%d %H:%M"
        "final_response_markdown": "strip",  # render | strip | raw
        # Preserve recent classic-CLI output across Ctrl+L, /redraw and resize clears; disable if an
        # emulator misbehaves with replayed scrollback.
        "persistent_output": True,
        "persistent_output_max_lines": 200,
        # Also clear terminal scrollback on classic-CLI full redraw/resize recovery; enable when a
        # terminal/tmux stack stamps stale prompt chrome into scrollback.
        "cli_rebuild_scrollback_on_redraw": False,
        # Print a one-line summary of resolved modal prompts (approval/clarify) to scrollback.
        "persist_prompts": True,
        "inline_diffs": True,     # inline diff previews for write_file/patch/skill_manage
        # Append a one-line advisory to the final response when a write_file/patch failed this turn
        # and was never superseded by a successful write to the same path (catches "half the
        # parallel patches failed, model claims success").
        "file_mutation_verifier": True,
        # Nous credits status-bar notices (usage bands, grant-spent, depleted/restored). False mutes
        # them; balance data and /usage keep working.
        "credits_notices": True,
        # Append a one-line explanation when a turn ends with no usable reply (empty after retries,
        # truncated stream, pending tool result, iteration/budget limit) instead of the bare
        # "(empty)" sentinel.
        "turn_completion_explainer": True,
        "show_cost": False,       # $ cost in the status bar
        "battery": False,         # battery read-out first in status bar; no-op w/o battery
        # Focus view (/focus): display-only. Pins tool_progress to "off", reports per-turn
        # hidden-line count, pins a "focus" status segment. focus_saved_tool_progress holds the mode
        # /focus off restores. Never affects what the model sees (focus_view.py).
        "focus_view": False,
        "focus_saved_tool_progress": "all",
        "skin": "default",
        # UI language for static messages (approval prompts, some gateway slash replies); not agent
        # responses/logs/tool outputs. en, zh, ja, de, es, fr, tr, uk; unknown → en.
        "language": "en",
        # TUI busy indicator: kaomoji | emoji | unicode (braille) | ascii. `/indicator <style>`.
        "tui_status_indicator": "kaomoji",
        # Seconds between idle prompt_toolkit redraws in the classic CLI; keeps wall-clock
        # status-bar read-outs ticking and the bottom chrome from going stale. 0 disables it if it
        # fights terminal auto-scroll in non-fullscreen mode.
        # See #45592.
        "cli_refresh_interval": 1.0,
        # Vi/vim keybindings in the CLI input composer (config-only, no slash command).
        # Off by default, preserving prompt_toolkit's standard emacs bindings.
        "vim_mode": False,
        "user_message_preview": {  # CLI: submitted user-message lines echoed to scrollback
            "first_lines": 2,
            "last_lines": 2,
        },
        # Gateway: natural mid-turn assistant status messages. Desktop: keep mid-turn narration
        # between tool calls instead of collapsing to the final message.
        "interim_assistant_messages": True,
        # Engine warning/failure notifications stay visible unless an operator opts in.
        # Does not suppress task results, manual commands, or existing logs.
        "suppress_warning_notifications": False,
        # Codex Responses commentary channel: true delivers completed commentary as mid-turn interim
        # updates; false routes it to reasoning (visible only with show_reasoning).
        "show_commentary": True,
        "tool_progress_command": False,  # enable /verbose command in messaging gateway
        # display.tool_progress_overrides is deprecated (use display.platforms); a user-set value is
        # still honored at runtime and folded into platforms by migration.
        "tool_preview_length": 0,  # max chars for tool call previews (0 = no limit)
        # Human-phrased status labels for built-in tools ("Reading <file>") in CLI spinner and
        # gateway/desktop tool-progress; custom/plugin/MCP tools use the raw preview.
        "friendly_tool_labels": True,
        # CLI-only post-turn line: "⋯ 12.4s · edited 2 files +18 -3 · read 4 files · ran 3
        # commands". Never in quiet/non-interactive or gateway surfaces (own footer).
        "turn_summary": True,
        # CLI-only: cumulative turn output tokens on the live spinner ("· ↓ 1.2k tok").
        "spinner_token_flow": True,
        # Gateway tool-progress grouping where edits are supported: "accumulate" edits one bubble |
        # "separate" one message per tool (noisier). Needs tool_progress enabled. Per-platform:
        # display.platforms.<platform>.tool_progress_grouping.
        "tool_progress_grouping": "accumulate",
        # Custom long-running status phrases. Defaults: gateway/assets/status_phrases.yaml.
        # `path`/`paths` = HERMES_HOME-relative YAML files/dirs (or conventional status_phrases.yaml
        # / status_phrases/*.yaml). Keys: status, generic. mode: "append" (default) | "replace".
        # Per-platform: display.platforms.<platform>.status_phrases.
        "status_phrases": {},
        # Reasoning summary rendering: "code" (💭 fenced block) | "blockquote" ("> ") | "subtext"
        # ("-# " Discord small grey text; Discord's default). Per-platform via
        # display.platforms.<platform>.reasoning_style.
        "reasoning_style": "code",
        # Auto-delete EphemeralReply system notices ("✨ New session started!", …) after N seconds
        # where deletion is supported (Telegram; others ignore). Agent responses are never touched.
        # 0 = disabled.
        "ephemeral_system_ttl": 0,
        # Per-platform display/streaming overrides; unset keys fall through to the global. Telegram
        # has smooth native draft streaming (on); Discord/Slack only edit-based streaming, which
        # flickers (off). Gap-fillers only: explicit user values win, and the global
        # streaming.enabled master switch still gates everything.
        "platforms": {
            "telegram": {"streaming": True},
            "discord": {"streaming": False},
            "slack": {"streaming": False},
            # WeCom native streaming (msgtype "stream" via aibot_respond_msg).
            "wecom": {"streaming": True},
        },
        # Gateway runtime footer on the FINAL message, e.g. `model · 68% · ~/projects/hermes`.
        # Per-platform: display.platforms.<platform>.runtime_footer.
        "runtime_footer": {
            "enabled": False,
            # order shown; drop any to hide. Opt-in extras: latency, served_model (alias → the
            # deployment a routing proxy reported / Hermes' fallback route).
            "fields": ["model", "context_pct", "cwd"],
        },
        # CLI/TUI status bar fields. Non-empty = only listed fields show (built-in order kept,
        # config controls visibility not ordering); empty = default set. Available: model,
        # context_detail, context_pct, cache_hit, latency, tps, compressions, bg_tasks,
        # bg_processes, bg_subagents, goal, git_branch (⎇ current branch, opt-in only), duration,
        # prompt_elapsed, idle_since, focus, yolo,
        # stash, battery, title, total_tokens (session Σ, opt-in only). Narrow terminals still drop
        # context_detail/prompt_elapsed/idle_since.
        "status_bar": {
            "fields": [],
        },
        "copy_shortcut": "auto",  # "auto" (platform default) | ctrl_c | ctrl_shift_c | disabled
        # Petdex animated mascot (github.com/crafter-station/petdex): cosmetic sprite across
        # CLI/TUI/desktop, managed with `hermes pets`. No effect on prompt caching.
        "pet": {
            "enabled": False,
            "slug": "",   # active pet slug in get_hermes_home()/pets/; empty → first installed
            # auto (detect kitty/iTerm2/sixel, else unicode half-blocks) | kitty | iterm | sixel |
            # unicode | off
            "render_mode": "auto",
            # Size scalar relative to native 192×208 frames, shared by desktop canvas and CLI/TUI
            # column width. Half-block fallback clamps to a legibility floor.
            "scale": 0.33,
            "unicode_cols": 0,  # Hard override for terminal column width; 0 = derive from scale.
        },
    },

    "dashboard": {
        # Visual theme: "default" | "midnight" | "ember" | "mono" | "cyberpunk" | "rose"
        "theme": "default",
        # Process-isolation rollout controls. Read via the raw config loader, so tui_gateway.server
        # also owns explicit defaults.
        "turn_isolation": False,
        "compute_host_heartbeat_secs": 15,
        "compute_host_respawn_max": 3,
        # Token/cost analytics surfaces are hidden by default: the numbers are a local LOWER-BOUND
        # estimate, not billing — only successful main-agent responses with a response.usage count;
        # auxiliary calls, retries, fallbacks and cache writes are missed, so the total can be
        # 10x-100x under the provider bill.
        "show_token_analytics": False,
        # IPs / bounded CIDRs of reverse proxies trusted to supply X-Forwarded-Proto/-For. Loopback
        # always trusted; wildcards and /0 rejected (spoofing guard).
        "trusted_proxies": [],
        # WebSocket keepalive (seconds), NON-loopback binds only: loopback always disables the
        # protocol ping so an event-loop stall never kills a healthy local connection.
        "ws_ping_interval": 20.0,
        "ws_ping_timeout": 20.0,
        # Grace (seconds) before a WS-orphaned gateway session is interrupted/reaped after its
        # client disconnects. 0 = park forever. Env: HERMES_TUI_WS_ORPHAN_REAP_GRACE_S.
        "ws_orphan_reap_grace_s": 20.0,
        # A detached RUNNING turn is only interrupted once its activity clock (API waits, stream
        # tokens, tool heartbeats) has been idle this many seconds; an active turn runs to
        # completion. Default = agent.turn_liveness.timeout_s. 0 = interrupt at grace.
        # See #100325, #98028.
        "ws_orphan_activity_stale_s": 600.0,
        # On gateway boot, close tui/desktop/subagent rows orphaned by a dead gateway (start AND
        # newest message older than HERMES_TUI_SESSION_TTL_S, default 6h) with
        # end_reason='startup_orphan_reap'; otherwise they stay phantom "active" forever.
        # Messaging-gateway and live sessions are never touched; swept rows stay resumable.
        # The ws-orphan grace timer above is in-process, so a gateway restart (update, crash, systemd)
        # leaves disconnected sessions ``ended_at IS NULL`` forever — phantom "active" rows in /resume and
        # dashboards. See #65194.
        "startup_orphan_sweep": True,
        # OAuth gate (engaged when --host is set and --insecure is not), read by the Nous Portal
        # plugin. Env HERMES_DASHBOARD_OAUTH_CLIENT_ID / HERMES_DASHBOARD_PORTAL_URL win when
        # non-empty. Empty client_id = no provider; empty portal_url = production.
        "oauth": {
            "client_id": "",  # agent:{instance_id} — Portal provisions this
            "portal_url": "",
        },
        # Username/password gate (dashboard_auth/basic plugin, no OAuth IDP). Active when username
        # plus password_hash (preferred) or password (hashed in-memory) are set; empty username =
        # no-op. Env HERMES_DASHBOARD_BASIC_AUTH_USERNAME / _PASSWORD_HASH / _PASSWORD / _SECRET /
        # _TTL_SECONDS win when non-empty. secret signs session tokens; empty = random per-process
        # key (sessions die on restart, no multi-worker) — set 32+ random bytes. Hash:
        # plugins.dashboard_auth.basic.hash_password('PW').
        "basic_auth": {
            "username": "",
            "password_hash": "",  # scrypt$...
            "password": "",
            "secret": "",
            "session_ttl_seconds": 0,  # 0 → plugin default (12h)
        },
        # Drain-control token auth (dashboard_auth/drain plugin). The secret is NOT here: env
        # HERMES_DASHBOARD_DRAIN_SECRET; no-op unless >=256-bit, weak secrets rejected
        # (fail-closed). scope = capability label; min_secret_chars in url-safe-b64 chars.
        "drain_auth": {"scope": "drain", "min_secret_chars": 43},
        # Public URL (env HERMES_DASHBOARD_PUBLIC_URL): full authority (scheme + host + optional
        # prefix, e.g. https://example.com/hermes) for the OAuth redirect_uri; its hostname is
        # trusted by Host/Origin guards and engages the auth gate when non-loopback. For proxies
        # that don't forward X-Forwarded-Host/-Proto/-Prefix; X-Forwarded-Prefix is then IGNORED on
        # the OAuth path. Empty or malformed (no http(s):// + host, or quote/angle/whitespace chars)
        # = reconstruct from headers.
        "public_url": "",
    },

    "privacy": {
        "redact_pii": False,  # hash user IDs and strip phone numbers from LLM context
    },
    # Text-to-speech. Each provider accepts an optional `max_text_length:` override for the
    # per-request input-character cap; omit to use the provider's documented limit (OpenAI 4096, xAI
    # 15000, MiniMax 10000, ElevenLabs 5k-40k model-aware, Gemini 32000, Edge 5000, Mistral 4000,
    # NeuTTS/KittenTTS 2000).
    "tts": {
        # "edge" (free) | "elevenlabs" (premium) | "openai" | "xai" | "minimax" | "mistral" |
        # "gemini" | "deepinfra" | "neutts" (local) | "kittentts" (local) | "piper" (local)
        "provider": "edge",
        # Seconds a local engine (Piper, KittenTTS) stays loaded after the last speech toggle
        # turns off, so a quick re-activation (wake word, voice-chat restart) skips the reload.
        # 0 unloads immediately.
        "keep_warm_seconds": 60,
        "streaming": {
            # Shortest first sentence (chars) spoken on its own by streaming TTS; shorter openers
            # ride with the next sentence. 20 suits English; CJK voice setups use ~6.
            "min_len": 20,
        },
        "edge": {
            # Popular: AriaNeural, JennyNeural, AndrewNeural, BrianNeural, SoniaNeural
            "voice": "en-US-AriaNeural",
        },
        "elevenlabs": {
            "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam
            "model_id": "eleven_multilingual_v2",
        },
        "openai": {
            "model": "gpt-4o-mini-tts",
            # gpt-4o-mini-tts voices: alloy, ash, ballad, cedar, coral, echo, fable, marin, nova,
            # onyx, sage, shimmer, verse
            "voice": "alloy",
            # Forwarded verbatim in the request body for OpenAI-compatible servers whose cloned
            # voices demand it (400 consent_required otherwise); "" sends nothing.
            "consent_attestation": "",
            # Raw PCM rate for streaming playback. OpenAI emits 24 kHz; a compatible endpoint that
            # reports its rate (X-Audio-Sample-Rate header) overrides this automatically.
            "pcm_sample_rate": 24000,
        },
        "gemini": {
            "model": "gemini-2.5-flash-preview-tts",
            "voice": "Kore",
            # Gemini 3.1: aux-model rewrite inserts [audio tags] into the TTS script only.
            "audio_tags": False,
            # Optional local text file with performance direction; may include a `{transcript}`
            # placeholder, else the live transcript is appended.
            "persona_prompt_file": "",
        },
        "xai": {
            "voice_id": "eve",  # or a custom voice ID (docs.x.ai custom voices)
            "language": "en",  # BCP-47 code ("en", "pt-BR") or "auto"
            "speed": 1.0,  # 0.7–1.5
            "auto_speech_tags": False,  # insert expressive audio tags via LLM rewrite
            "optimize_streaming_latency": 0,  # 0–2, trades quality for lower latency
            "sample_rate": 24000,  # 22050 / 24000 / 44100 / 48000
            "bit_rate": 128000,  # MP3 bitrate; only applies when codec=mp3
        },
        "mistral": {
            "model": "voxtral-mini-tts-2603",
            "voice_id": "c69964a6-ab8b-4f8a-9465-ec0925096ec8",  # Paul - Neutral
        },
        "minimax": {"model": "speech-02-hd", "voice_id": "English_expressive_narrator"},
        "kittentts": {
            "model": "KittenML/kitten-tts-nano-0.8-int8",  # nano 25MB; micro 41MB; mini 80MB
            "voice": "Jasper",
        },
        "neutts": {
            "ref_audio": "",  # path to reference voice audio (empty = bundled default)
            "ref_text": "",   # path to reference voice transcript (empty = bundled default)
            "model": "neuphonic/neutts-air-q4-gguf",  # HuggingFace model repo
            "device": "cpu",  # cpu, cuda, or mps
        },
        "piper": {
            # Voice name (downloaded on first use) or absolute path to a .onnx file; list:
            # github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md. Optional keys: voices_dir
            # (~/.hermes/cache/piper-voices/), use_cuda, length_scale (2.0 = twice as slow),
            # noise_scale, noise_w_scale, volume, normalize_audio.
            "voice": "en_US-lessac-medium",
        },
        "deepinfra": {
            "model": "",  # empty = first tts-tagged model from the live catalog
            "voice": "default",
            # optional "base_url" key overrides DEEPINFRA_BASE_URL for TTS only
        },
    },

    "stt": {
        "enabled": True,
        # Echo the raw transcript of gateway voice messages back as a 🎙️ message.
        "echo_transcripts": True,
        # No seeded "provider" (a stored value is an explicit pick; unset = autodetect): local | groq |
        # openai | mistral | elevenlabs | deepinfra | xai. Global language hint unless a per-provider one
        # overrides it; "en" because Whisper auto-detect misreads short clips; "" = auto; "es", ...
        "language": "en",
        "streaming": False,  # live partial text while speaking (openai/xai/elevenlabs); failure = file path
        # Pre-upload ffmpeg silence trim (local whisper uses VAD); failure = raw upload.
        "cloud_trim_silence": True,
        "cloud_trim_threshold_db": -40,  # quieter than this counts as silence
        "cloud_trim_keep_ms": 300,  # how much of each pause survives (natural pacing)
        "local": {
            "model": "base",  # tiny, base, small, medium, large-v3, turbo
            "language": "",  # auto-detect; set "en", "es", ... to force
            "initial_prompt": "",
            # Anti-hallucination (faster-whisper decodes junk from silence). vad: Silero filter
            # (false = raw audio, for music/ambient). A segment is dropped only if no_speech_prob
            # ABOVE no_speech_prob_threshold AND avg_logprob BELOW logprob_threshold.
            "vad": True,
            "vad_min_silence_ms": 500,  # min silence (ms) that splits speech chunks
            "no_speech_prob_threshold": 0.6,
            "logprob_threshold": -1.0,
            "unload_after_idle_seconds": 0,  # 0 = never; e.g. 300 frees the model after 5min
        },
        "groq": {
            "model": "whisper-large-v3-turbo",  # whisper-large-v3-turbo, whisper-large-v3
            "language": "",  # auto-detect; set "en", "es", ... to force
        },
        "openai": {
            # whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe, gpt-transcribe
            "model": "whisper-1",
            "streaming_model": "gpt-live-transcribe",  # stt.streaming; the one model with mid-utterance deltas
            "language": "",  # auto-detect; set "en", "es", ... to force
            "timeout": 60,  # seconds; allow self-hosted backends time to cold-start
            "max_retries": 1,  # OpenAI SDK transport retries
        },
        "mistral": {
            "model": "voxtral-mini-latest",  # voxtral-mini-latest, voxtral-mini-2602
            "language": "",  # auto-detect; set "en", "es", ... to force
        },
        "xai": {
            "model": "",  # "" = STT_XAI_MODEL or grok-voice-transcribe-2.0; or grok-voice-transcribe-1.0
            "language": "",  # auto-detect; set "en", "es", ... to force
        },
        "elevenlabs": {
            "model_id": "scribe_v2",  # scribe_v2, scribe_v1
            "language_code": "",  # auto-detect; set "eng", "spa", ... to force
            "tag_audio_events": False,
            "diarize": False,
        },
        "deepinfra": {
            "model": "",  # empty = first stt-tagged model from the live catalog
            # optional "base_url" key overrides DEEPINFRA_BASE_URL for STT only
        },
    },

    "voice": {
        # How the Desktop voice conversation is wired:
        #   chained  — STT → Hermes turn → TTS (the stt.* / tts.* providers below)
        #   gpt-live — one full-duplex voice model (OpenAI GPT-Live) owns the mic and speaker and
        #              DELEGATES every real request to Hermes (any model / provider you have
        #              selected); needs an OpenAI API key. $0.05/min voice layer billing.
        "voice_chat_mode": "chained",
        "gpt_live": {
            "model": "gpt-live-1",
            "voice": "marin",  # marin | quartz | ripple | vesper | willow | stone | gleam | meridian | ...
            # Extra sentences appended to the live model's conversation persona (tone, pacing, language).
            "instructions": "",
            # optional "api_key" / "base_url" keys override the OpenAI audio credentials for this mode only
        },
        "record_key": "ctrl+b",
        "submit_mode": "direct",  # TUI: direct submits immediately; draft = editable transcript
        "max_recording_seconds": 120,
        "auto_tts": False,
        # Desktop remote clients call STT/TTS providers DIRECTLY (config + key fetched over
        # authenticated REST at session start) instead of relaying via the gateway.
        "client_direct": True,
        "beep_enabled": True,  # record start/stop beeps in CLI voice mode
        "beep_volume": 0.3,  # beep amplitude multiplier, 0.0-1.0
        "thinking_sound": True,  # ambient bubble sound while the agent works (volume = beep_volume)
        "silence_threshold": 200,  # RMS below this = silence (0-32767)
        "silence_duration": 3.0,  # seconds of silence before auto-stop
        "barge_in": True,  # interrupt the agent / stop TTS when the user starts talking
        # Trip suppression after TTS onset (mic stays live the whole turn).
        "barge_in_grace_seconds": 0.5,
        # Speech trigger = quiet-room floor x this (floor calibrated BEFORE playback).
        "barge_in_threshold_multiplier": 3.0,
        # Saying EXACTLY one of these (case-insensitive, punctuation ignored) ends the voice chat
        # instead of going to the agent. [] disables.
        "stop_phrases": ["stop"],
    },
    # Native images (vision_analyze, browser screenshots, replayed user images) are re-sent on every later call.
    "vision": {
        # Byte budget for one embedded image (clamped 64 KiB..4 MiB). Raise it for dense phone
        # screenshots of tables the model calls "unreadable" at 256 KB.
        "embed_target_bytes": 256 * 1024,
        # How often vision_analyze may embed the SAME image (region crops included) per session.
        # null = 3 inside delegated subagents (they run unattended), unlimited for the main agent;
        # an explicit number applies everywhere; 0 = unlimited.
        "max_calls_per_image": None,
        "replay_recent_images": 3,  # newest user images re-sent on turns rebuilt from state.db; 0 = off
    },
    # "Hey Hermes" hands-free wake word: always-on, on-device hotword detection that starts a fresh
    # voice session. Off by default; toggle with /wake.
    "wake_word": {
        "enabled": False,
        "surface": "auto",  # eligible surface: "auto" (first claimant) | "cli" | "tui" | "gui"
        "input_device": None,  # PortAudio input device index/name; null = process default
        "capture": "auto",  # auto | local | client (desktop streams mic via wake.feed)
        # auto: first platform-supported engine (openwakeword, sherpa, porcupine).
        # Explicit choices stay pinned. Porcupine needs PORCUPINE_ACCESS_KEY.
        "provider": "auto",
        # sherpa: this IS the detected phrase; other engines: cosmetic label (detection is keyed by
        # the model/keyword below)
        "phrase": "hey hermes",
        "sensitivity": 0.6,  # 0.0-1.0 threshold, consistent across engines (higher = stricter)
        # openWakeWord/pyopen-wakeword only: consecutive over-threshold frames to fire (higher = fewer
        # false triggers, more latency; 1 = single-frame)
        "confirmation_frames": 3,
        "start_new_session": True,  # fresh session on wake vs. continue the current one
        # sherpa only: listen for every wake-enabled profile's phrase and route to it
        "profile_routing": True,
        "openwakeword": {
            # "hey_hermes" | built-in openWakeWord name ("hey_jarvis", "alexa", ...) | path to a
            # custom .tflite model
            "model": "hey_hermes",
        },
        "sherpa": {
            # sherpa-onnx KWS model dir; empty = auto-download the small English zipformer
            "model_dir": "",
        },
        "porcupine": {
            # built-in keyword ("jarvis", "computer", ...) or path to a custom .ppn
            "keyword": "jarvis",
        },
    },

    "human_delay": {"mode": "off", "min_ms": 800, "max_ms": 2500},

    # Context engine — how the context window is managed near the token limit. "compressor" =
    # built-in lossy summarization; or a plugin name (e.g. "lcm") installed in
    # plugins/context_engine/<name>/ or ~/.hermes/plugins/.
    "context": {
        "engine": "compressor",
        # Return freed glibc pages at agent/TUI cleanup boundaries (no-op elsewhere).
        "memory_trim": {
            "enabled": True,
            "cooldown_seconds": 60.0,
            "log_every_n": 1,  # INFO-log every Nth periodic trim; force paths always log.
            # Suppress INFO logs when the readable RSS delta is smaller; 0 = log all.
            "info_log_min_delta_mb": 0.0,
        },
    },
    "memory": {  # Persistent memory — bounded curated memory injected into the system prompt
        "memory_enabled": True,
        "user_profile_enabled": True,
        "prefetch_spill_enabled": False,  # External recall opt-in to hooks.output_spill.
        # Approval gate for memory writes on BOTH foreground turns and the background review fork.
        # true = foreground writes prompt inline; background writes are staged (/memory
        # pending|approve <id>|reject <id>). To disable memory: memory_enabled.
        "write_approval": False,
        "memory_char_limit": 2200,   # ~800 tokens at 2.75 chars/token
        "user_char_limit": 1375,     # ~500 tokens at 2.75 chars/token
        # Periodic built-in memory review; 0 when an external provider auto-extracts.
        "nudge_interval": 10,
        # One external provider: bundled (retaindb, byterover) or catalog-installed (honcho,
        # hindsight, supermemory, mem0, openviking, holographic). Empty = built-in only.
        "provider": "",
    },
    # Subagent delegation: `backend` = task-routing strategy ("default": keys below), `backends.<name>` = its settings.
    "delegation": {
        "backend": "default",
        "backends": {},
        "model": "",  # e.g. "google/gemini-3-flash-preview" (empty = inherit parent)
        "provider": "",  # e.g. "openrouter" (empty = inherit parent provider + credentials)
        # Fallback chain for delegated children (same entry format as the top-level list).
        # For an unpinned child, null = inherit the parent chain; [] = disable fallback.
        # A child pinned by provider, endpoint, or model gets no fallback unless this
        # setting declares one explicitly.
        "fallback_providers": None,
        "base_url": "",  # direct OpenAI-compatible endpoint for subagents
        "api_key": "",  # key for delegation.base_url (falls back to OPENAI_API_KEY)
        # Wire protocol for delegation.base_url: "chat_completions" | "codex_responses" |
        # "anthropic_messages". Empty = auto-detect from URL (e.g. /anthropic suffix); set
        # explicitly for non-standard endpoints.
        "api_mode": "",
        # Per-child request settings on every delegation call (all resolution branches). Top-level
        # keys = API kwargs (e.g. service_tier); "extra_body" sub-dict merges into extra_body, e.g.
        # {"extra_body": {"provider": {"sort": "throughput"}}}. Explicit values win OVER
        # runtime/parent overrides (extra_body deep-merged 1 level).
        "request_overrides": {},
        # compression_threshold_tokens: optional absolute cap on a subagent's compaction TRIGGER
        # (not the request payload), applied as the lower of this and the child's ratio threshold.
        # 0 (default) = no subagent-specific cap; children compact where the parent does — the lower
        # of 0.50 x window and the global compression.threshold_tokens cap. A replay of a 1,393-agent
        # run showed 200K-400K caps within 5% of each other in cost once cache prefixes are intact,
        # and every compaction is a chance to lose detail, so the default stays off. A token count >= 16000 enables it;
        # other values (true, "200k") are config errors: warned and ignored.
        "compression_threshold_tokens": 0,
        # When delegate_task narrows child toolsets, keep the parent's enabled MCP toolsets (so
        # toolsets=["web"] doesn't strip MCP). false = strict intersection.
        "inherit_mcp_toolsets": True,
        # Per-subagent iteration cap (own budget, independent of the parent's).
        "max_iterations": 250,
        # Hard per-summary char ceiling on subagent results, layered on the dynamic budget (each
        # summary is sized to the parent's remaining context headroom; trimmed text spills to
        # ~/.hermes/cache/delegation/ with a head+tail window + read_file offset footer, nothing
        # lost). 0 disables the ceiling; the dynamic budget still applies.
        "max_summary_chars": 24000,
        # Inactivity cap per child (seconds, floor 30) — time with NO progress, not total runtime. 0 = no cap:
        # children fail only from real errors (API, tools, iteration budget). A progressing child (including one
        # waiting on a multi-minute completion) restarts the window; a frozen one is caught.
        "child_timeout_seconds": 0,
        # Subagent effort: "ultra" | "max" | "xhigh" | "high" | "medium" | "low" | "minimal" |
        # "none" (empty = inherit)
        "reasoning_effort": "",
        # Max parallel children per batch AND max concurrent background delegation units; async
        # dispatches beyond it run synchronously. Floor 1, no ceiling.
        "max_concurrent_children": 10,
        # Background fan-outs return as ONE message when the whole call finishes. true = each task
        # (or `group`) returns on its own as it finishes — more new turns for the orchestrator.
        "independent_completions": False,
        # Orchestrator role controls. Depth floored at 1, no ceiling; each level multiplies cost.
        "max_spawn_depth": 1,  # 1 = flat, 2 = orchestrator→leaf, 3+ = deeper
        "orchestrator_enabled": True,  # kill switch for role="orchestrator"
        # Total subagents a finite one-shot run (hermes chat -q / --oneshot) may spawn; 0 = unlimited.
        # Each child re-pays a cold system prompt and re-explores the repo, and one-shot spawns are mostly
        # "review my own work" rather than parallel work (agent/oneshot_footprint.py).
        "oneshot_max_children": 2,
        # Subagent threads ALWAYS resolve approvals non-interactively (the parent TUI owns stdin;
        # input() from a worker would deadlock). false = auto-deny, true = auto-approve "once"; both
        # log a warning audit line. true only for trusted batch work.
        "subagent_auto_approve": False,
        # Subagent background processes (task_id "sa-...") route notify_on_complete / watch_pattern
        # notifications to the PARENT; false suppresses them (the child's result is the
        # deliverable). Async-delegation results are NEVER suppressed.
        "surface_child_process_notifications": False,
    },
    # Ephemeral prefill messages file — JSON list of {role, content} dicts injected at the start of
    # every API call for few-shot priming. Never saved to sessions/logs/trajectories.
    "prefill_messages_file": "",
    # Goals — persistent cross-turn /goal loop: after each turn an aux-model judge checks if the
    # goal is satisfied, else a continuation prompt re-enters the session until done, budget
    # exhausted, or paused. Judge failures fail OPEN; the budget is the backstop.
    "goals": {
        # Max continuation turns before auto-pause (/goal resume) — guards against judge false
        # negatives and unbounded spend.
        "max_turns": 20,
    },
    # Loops — /loop re-runs a prompt or slash command on a cadence in-session. Fixed interval fires
    # on the user's clock; self-paced (no interval) starts at the floor and backs off exponentially
    # while replies stop changing.
    "loops": {
        "min_interval_seconds": 30,  # smallest fixed interval; tighter cadences raised to it
        "max_ticks": 100,  # auto-pause after this many wakeups unless --times set; 0 = unlimited
        "self_paced_floor_seconds": 60,  # Self-paced cadence bounds (seconds).
        "self_paced_ceiling_seconds": 900,
    },
    # Mixture of Agents — named presets used by /moa. A preset is an execution mode around the main
    # model, not a model itself: references + aggregator synthesize private guidance before each
    # main-model iteration.
    "moa": {
        "default_preset": "default",
        "active_preset": "",
        # Write each MoA turn (reference + aggregator exact input/output/usage) as JSONL to
        # <hermes_home>/moa-traces/<session_id>.jsonl (or trace_dir) for auditing.
        "save_traces": False,
        "trace_dir": "",
        # PII/credential redaction of advisor outputs: "" off | "display" (UI reference blocks +
        # traces only; aggregator sees raw) | "full" (also the aggregator prompt).
        # Advisors can echo PII from the conversation (emails, formatted phone numbers) and credential
        # shapes into reference blocks, traces, and the aggregator prompt. Modes ('' = off, the default):
        # "display" — redact user-visible surfaces only (reference blocks shown in the UI + saved MoA trace
        # records); the aggregator still sees raw advisor text. "full"    — additionally redact the advisor
        # text injected into the aggregator prompt (issue #59959).
        "privacy_filter": "",
        "presets": {
            "default": {
                "reference_models": [
                    {"provider": "openai-codex", "model": "gpt-5.5"},
                    {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
                ],
                "aggregator": {"provider": "openrouter", "model": "anthropic/claude-opus-4.8"},

                "enabled": True,
            }
        },
    },
    # Skills — external skill directories shared across tools/agents. Paths are expanded (~, ${VAR})
    # and resolved; read-only — creation goes to ~/.hermes/skills/ unless create_dir redirects it.
    "skills": {
        "external_dirs": [],   # e.g. ["~/.agents/skills", "/shared/team-skills"]
        # Where skill_manage-created skills go (empty = profile-local dir). When set, new skills
        # land here AND agent-facing instructions name this path; expanded (~, ${VAR}), relative to
        # HERMES_HOME, scanned alongside the local dir.
        "create_dir": "",
        # In a git checkout, <root>/.hermes/skills/ and <root>/.agents/skills/ load as the
        # highest-precedence tier — ONLY if the root is in trusted_project_dirs. false = no scan, no
        # untrusted-skills notice.
        "project_discovery": True,
        # Trusted project roots; managed by `hermes skills trust` / `untrust`.
        "trusted_project_dirs": [],
        # Skill names pinned as fully loaded in every new session (CLI, TUI, gateway, cron, API).
        # Resolved once when the agent's prompt is first built; missing/disabled names warn and
        # skip; HERMES_IGNORE_RULES suppresses the list like the other auto-injected context.
        "auto_load": [],
        # Substitute ${HERMES_SKILL_DIR} / ${HERMES_SESSION_ID} in SKILL.md content.
        "template_vars": True,
        # Pre-execute !`cmd` snippets in SKILL.md, inlining stdout (dates, git state...). Off:
        # host-unapproved skill-author code; community hub installs never auto-execute (#63307).
        "inline_shell": False,
        "inline_shell_timeout": 10,  # seconds per !`cmd` snippet
        # Security-scan skills the agent writes via skill_manage. Off: the agent can run the same
        # code via terminal() ungated, so it mostly blocks prose with risky keywords. On: a
        # dangerous verdict is a tool error the agent can retry. Hub installs are always scanned.
        "guard_agent_created": False,
        # Advisory NVIDIA SkillEvaluator Tier 1 scan on `hermes skills install` (alongside the
        # enforcing built-in guard), only if `skillevaluator` is on PATH (uv tool install
        # "skillevaluator @ git+https://github.com/NVIDIA/SkillEvaluator.git"). Informational, never
        # blocking; secrets-class findings shown red. No-op without it.
        "tier1_advisory": True,
        # Approval gate for skill_manage mutations on BOTH foreground turns and the background
        # review fork. true = ALWAYS stage (SKILL.md too large for an inline prompt): /skills
        # pending, /skills diff <id>, /skills approve|reject <id>.
        "write_approval": False,
        # Audit ledger: every skill mutation appends to ~/.hermes/skills/.curator_ledger.jsonl with
        # before/after hashes (blobs under ~/.hermes/.curator_backups/blobs/); powers `hermes
        # curator ledger` / `rollback <entry-id>`. Never a gate — failures can't block.
        # See #79686.
        "ledger": True,
        # Size cap for that ledger: once the file grows past this, the next append rewrites it
        # through the unchanged-file dedup and, if still over, drops the oldest entries (0 = keep
        # the ledger append-only forever, the previous behaviour).
        "ledger_max_bytes": 5 * 1024 * 1024,
    },

    # Curator — background maintenance of AGENT-CREATED skills (never hub-installed): marks
    # long-unused skills stale, archives (never deletes) obsolete ones, optionally consolidates
    # overlaps via a forked aux-model agent. Inactivity-triggered from session start, no cron
    # daemon. `hermes curator status` shows the last run.
    "curator": {
        "enabled": True,
        "interval_hours": 24 * 7,  # hours between runs
        "min_idle_hours": 2,  # only run after the agent has been idle this long
        "stale_after_days": 14,  # mark "stale" after this many unused days
        "archive_after_days": 30,  # move to skills/.archive/ (recoverable) after this many
        # LLM consolidation (umbrella-building) pass. OFF = deterministic inactivity prune only, no
        # aux-model cost. `hermes curator run --consolidate` overrides once.
        "consolidate": False,
        # Also prune bundled built-ins (a suppression list stops `hermes update` restoring them);
        # hub-installed skills are NEVER pruned. OFF by default: shipped skills vanishing from
        # `skills_list` because nobody loaded them for 30 days surprised people (57 gone in one
        # startup tick). true = built-ins age out like agent-created skills.
        "prune_builtins": False,
        # TTL purge of skills/.archive/: 0 = never; > 0 lets the explicit `hermes curator purge`
        # delete older archived skills (never automatic; logged in the ledger).
        "archive_ttl_days": 0,
        # Before a consolidation pass (the only one that rewrites skill content in place), snapshot
        # ~/.hermes/skills/ to ~/.hermes/skills/.curator_backups/<utc-iso>/skills.tar.gz (`hermes curator
        # rollback`). The prune-only pass just moves directories into .archive/ and takes none.
        "backup": {
            "enabled": True,
            "keep": 2,  # retain last N regular snapshots
        },
    },
    # Honcho memory plugin (plugin catalog) — ~/.honcho/config.json is the source of truth (apiKey,
    # workspace, peerName, sessions, enabled); the plugin reads hermes-specific overrides from here.
    "honcho": {},
    # IANA timezone (e.g. "Asia/Kolkata", "America/New_York"). Empty = server-local time.
    "timezone": "",

    "slack": {
        "require_mention": True,  # require @mention to respond in channels
        "free_response_channels": "",  # comma-separated channel IDs answered without mention
        "allowed_channels": "",  # if set, ONLY respond in these channel IDs (whitelist)
        "require_mention_channels": "",  # channel IDs where @mention is ALWAYS required
        # Ignore messages whose first token @mentions another user unless the bot is also mentioned.
        # Env: SLACK_IGNORE_OTHER_USER_MENTIONS.
        "ignore_other_user_mentions": False,
        "thread_require_mention": False,  # require @mention in thread replies too
        "channel_prompts": {},  # per-channel ephemeral system prompts
    },

    "discord": {
        "require_mention": True,  # require @mention to respond in server channels
        "free_response_channels": "",  # comma-separated channel IDs answered without mention
        "allowed_channels": "",  # if set, ONLY respond in these channel IDs (whitelist)
        "auto_thread": True,  # auto-create threads on @mention in channels (like Slack)
        # Free-response channels reply inline by default; true also gives each top-level
        # message in them its own thread (still mention-free). Env: DISCORD_FREE_RESPONSE_AUTO_THREAD.
        "free_response_auto_thread": False,
        "thread_require_mention": False,  # require @mention in threads too (multi-bot threads)
        # Bot authors must type @thisbot to trigger a reply; Discord reply pings alone do not count.
        # Set False only for trusted legacy relays. Humans are unaffected.
        "bots_require_inline_mention": True,
        # Prepend recent channel scrollback when triggered (recovers messages gated out by
        # require_mention); limit = max messages scanned.
        "history_backfill": True,
        "history_backfill_limit": 50,
        # Replay messages missed while offline, after reconnect/startup.
        "missed_message_backfill": {
            "enabled": False,
            "channels": "",  # comma-separated channel IDs; empty uses free_response_channels
            "window_seconds": 21600,  # only inspect messages from the last 6 hours
            "limit": 100,  # global cap on messages scanned per reconnect
            "max_dispatches": 10,  # cap on recovered messages dispatched per reconnect
            "max_attempts": 3,  # lifetime re-dispatch cap for one message, whatever its outcome
        },
        "reactions": True,  # add 👀/✅/❌ reactions to messages during processing
        # Gateway transport health probe: inspects the WebSocket's ready/open/heartbeat state (never
        # REST) as proof events still arrive. Any value 0 disables it.
        "websocket_liveness_interval_seconds": 15,
        "websocket_liveness_failure_threshold": 2,
        "websocket_heartbeat_ack_max_age_seconds": 60,
        "websocket_max_latency_seconds": 30,
        # Dispatch-side dimension: a socket that ACKs heartbeats but delivers no events for this
        # long is treated as deaf. 4 h absorbs a quiet server overnight; 0 disables it.
        "websocket_event_max_silence_seconds": 14400,
        # per-channel ephemeral system prompts (forum parents apply to child threads)
        "channel_prompts": {},
        # Opt-in DM role auth: DISCORD_ALLOWED_ROLES normally authorizes guild messages only (DMs
        # need DISCORD_ALLOWED_USERS). A guild ID here also authorizes DMs from that guild's members
        # holding the allowed role. Unset / "" / 0 = off.
        # See #12136.
        "dm_role_auth_guild": "",
        # discord / discord_admin tools: allowed actions (comma string or YAML list; empty = all,
        # subject to bot intents; unknown names dropped with a warning): list_guilds, server_info,
        # list_channels, channel_info, list_roles, member_info, search_members, fetch_messages,
        # list_pins, pin_message, unpin_message, create_thread, add_role, remove_role.
        "server_actions": "",
        # DEPRECATED no-op (uploads are always cached; messaging auth is the gate). Kept so existing
        # configs don't error. Env: DISCORD_ALLOW_ANY_ATTACHMENT.
        "allow_any_attachment": False,
        # Max bytes per cached attachment (held in memory while written); 0 = no cap. Env:
        # DISCORD_MAX_ATTACHMENT_BYTES.
        "max_attachment_bytes": 33554432,
        # Mention allowed users on approval prompts so owners notice them in shared channels. Env:
        # DISCORD_APPROVAL_MENTIONS.
        "approval_mentions": False,
        # Voice-channel inactivity timeout (seconds); 0 = stay until `/voice leave`.
        "voice_channel_inactivity_timeout_seconds": 300,
        # Minimum seconds before force-stopping a VC playback; the adapter probes clip duration and
        # extends this floor so long TTS isn't cut off.
        "voice_playback_timeout_seconds": 120,
        # Voice-channel software mixer (plugins/platforms/discord/voice_mixer.py): ambient
        # "thinking" bed, verbal acks and TTS OVERLAP (ambient ducked) vs stop-and-swap.
        "voice_fx": {
            "enabled": False,  # master switch for the mixer subsystem
            "ambient_enabled": True,  # play the idle "thinking" bed while tools run
            "ambient_path": "",  # custom loop audio file; "" = synthesised pad
            "ambient_gain": 0.18,  # idle bed loudness, 0.0–1.0
            "duck_gain": 0.06,  # ambient loudness while speech plays
            "speech_gain": 1.0,  # TTS / ack loudness, 0.0–1.0
            "ack_enabled": True,  # speak a short phrase before the first tool call
            "ack_phrases": [  # picked at random; [] disables phrases
                "Let me look into that.",
                "One moment.",
                "Checking on that now.",
                "Give me a sec.",
                "On it.",
            ],
        },
    },

    "whatsapp": {
        # reply_prefix: None = built-in "☤ *Hermes Agent*" header; "" disables; \n allowed.
    },

    "telegram": {
        "reactions": False,  # add 👀/✅/❌ reactions to messages during processing
        # per-chat/topic ephemeral system prompts (topics inherit from parent group)
        "channel_prompts": {},
        "allowed_chats": "",  # if set, ONLY respond in these group/supergroup chat IDs
        "extra": {
            # Bot API 10.1 native rich messages (tables/task lists/math). Off = legacy MarkdownV2,
            # since rich messages are hard to copy as plain text.
            "rich_messages": False,
            # Experimental rich DM stream previews; off: Telegram Desktop/macOS overlays draft frames.
            "rich_drafts": False,
            # CJK stays on legacy MarkdownV2 (Telegram Desktop/macOS garbles rich CJK, #47653);
            # set True on an unaffected client to get native rich tables for CJK.
            "allow_cjk_rich_messages": False,
            "dm_topic_auto_transfer": False,  # /topic mode: root-DM message opens a fresh topic
        },
    },

    "mattermost": {
        "require_mention": True,  # require @mention to respond in channels
        "free_response_channels": "",  # comma-separated channel IDs answered without mention
        "allowed_channels": "",  # if set, ONLY respond in these channel IDs (whitelist)
        "channel_prompts": {},  # per-channel ephemeral system prompts
    },

    "matrix": {
        "require_mention": True,  # require @mention to respond in rooms
        "free_response_rooms": "",  # comma-separated room IDs answered without mention
        "allowed_rooms": "",  # if set, ONLY respond in these room IDs (whitelist)
    },
}
