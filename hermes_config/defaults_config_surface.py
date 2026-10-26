"""Surface DEFAULT_CONFIG sections: approvals, security, cron, gateway, and runtime."""

DEFAULT_CONFIG_SURFACE = {
    # Approvals for dangerous commands.
    # mode: manual (always prompt) | smart (aux LLM auto-approves low-risk) | off (= --yolo)
    # cron_mode / single_query_mode / unattended_mode: deny | approve — what to do when a
    #   cron job, a -q session (HERMES_INTERACTIVE=1 but nobody to answer), or an unattended
    #   platform (webhook, msgraph_webhook, api_server; no /approve channel) hits one.
    #   deny blocks instantly so the agent finds another way instead of waiting out the
    #   timeout and failing closed.
    # timeout: seconds before an unanswered prompt fails closed (CLI and gateway). 60s
    #   proved too tight for Telegram/Discord push notifications, hence 300.
    "approvals": {
        # single_query_mode — what to do when a single-query (-q) session hits a dangerous command. -q runs
        # export HERMES_INTERACTIVE=1 (for interactive sudo prompts) but have NO user waiting to answer
        # approval prompts — an unanswered prompt just waits the full timeout then fails closed, so the
        # agent is forced to work around the block (often via execute_code). This setting makes that intent
        # explicit: deny    — block the command and let the agent find another way (default, safe; mirrors
        # cron_mode deny) approve — auto-approve all dangerous commands in single-query mode These surfaces
        # bind a session platform like chat gateways do, but have no send_exec_approval and no /approve
        # channel — a pending approval there just blocks for the full timeout with nobody to answer (#37284,
        # #87509): deny    — block the command instantly and let the agent find another way (default, safe;
        # mirrors cron_mode deny) approve — auto-approve all dangerous commands on unattended platforms
        # Shared by the CLI prompt and gateway/messaging waits. Messaging approvals arrive as a push
        # notification the user may not see immediately — 60s proved too tight on Telegram/Discord (the
        # prompt expired before the user reached their phone), so the default is 300.
        "mode": "smart",
        "timeout": 300,
        "cron_mode": "deny",
        "single_query_mode": "deny",
        "unattended_mode": "deny",
        # Extra rules appended to the smart-approval guardian's SYSTEM prompt, e.g. "Always ESCALATE
        # commands touching /etc".
        "smart_policy": "",
        # After this many consecutive guardian DENYs in a session, the deny message escalates to a
        # hard-stop (report to user / ask for /approve). Approval resets; 0 off.
        "denial_breaker_threshold": 3,
        # Case-insensitive fnmatch globs against terminal commands; a match blocks even under --yolo
        # / mode=off. Quote in YAML when starting with * or containing {}/!/: e.g. "git push
        # --force*".
        "deny": [],
        # /reload-mcp confirms before rebuilding the MCP tool set (it invalidates the prompt cache,
        # so the next message re-sends full input). "Always Approve" → false.
        "mcp_reload_confirm": True,
        # /clear, /new, /reset, /undo confirm before discarding state (Approve Once / Always Approve
        # / Cancel via tools.slash_confirm; native buttons on Telegram/ Discord/Slack). "Always
        # Approve" → false. HERMES_TUI_NO_CONFIRM=1 skips the TUI modal.
        "destructive_slash_confirm": True,
    },
    # Permanently allowed dangerous command patterns (added via "always" approval).
    "command_allowlist": [],
    # User-defined quick commands that bypass the agent loop (type: exec only).
    "quick_commands": {},
    # Per-platform system-prompt hint overrides, keyed by platform name (whatsapp, slack, telegram,
    # ...). Value: {"append": text} keeps the built-in hint and appends; {"replace": text}
    # substitutes it; a bare string is shorthand for append. `replace` wins over `append` if both
    # are given.
    "platform_hints": {},
    # Plugin system. `enabled`/`disabled` lists are written by `hermes plugins enable|disable` and
    # deliberately omitted here so an empty default never clobbers a user allow-list.
    "plugins": {
        # Deadline (seconds) for one plugin Git clone, fetch or checkout. Slow repositories may
        # need more time; each network operation is capped at one hour.
        "clone_timeout_seconds": 300,
        # Wall-clock cap (seconds) for one in-process Python plugin hook callback; shell hooks keep
        # their own per-entry `timeout`. 0 = no cap (sync call on agent thread). Max 600.
        "hook_callback_timeout": 30,
        # Deadline (seconds) for one plugin's import + register() at load. A plugin that overruns it is
        # skipped with the reason "load timed out" and the rest keep loading; the stuck worker thread is
        # abandoned. 0 = no deadline (load inline). Max 600.
        "load_timeout_seconds": 10,
        # Read-only plugin update-check cadence, hours (gateway tick; 0 disables). Applying stays
        # explicit: `hermes plugins update <name>`, or auto_apply below (git-class plugins only,
        # scan-gated by that same pipeline).
        "auto_update_check_hours": 24,
        # Opt-in unattended apply for the cadence check. Git-row plugins ONLY; every apply runs the
        # same security scan / consent pipeline as the manual update command.
        "auto_apply": False,
        # Where third-party Python plugins run. in_process: imported into Hermes (default).
        # host: one plugin-host process per profile runs them and they reach Hermes only through
        # ctx (a crashing or hanging plugin takes down its host, which restarts; Hermes keeps
        # running). Bundled plugins stay in-process; `hermes plugins validate` says whether a
        # plugin can run in the host.
        "isolation": "in_process",
        "host": {
            # argv prefix the plugin host runs under, e.g. a sandbox runner. [] = plain subprocess.
            "launcher": [],
        },
    },
    # Shell-script hooks: event name (pre_tool_call, post_tool_call, pre_llm_call, subagent_stop,
    # ...) -> list of {matcher, command, timeout}. First run of a new command prompts for consent;
    # approvals persist in ~/.hermes/shell-hooks-allowlist.json. Schema + examples:
    # website/docs/user-guide/features/hooks.md.
    "hooks": {},
    # Auto-accept shell-hook registrations without a TTY prompt (also --accept-hooks or
    # HERMES_ACCEPT_HOOKS=1). Gateway/cron/non-interactive runs need one of these to pick up
    # newly-added hooks.
    "hooks_auto_accept": False,
    # Custom personalities: {"name": "system prompt"} or {"name": {"description", "system_prompt",
    # "tone", "style"}}.
    "personalities": {},
    "auth": {  # Login policy (credentials themselves live in auth.json / .env).
        # Borrow and refresh the Codex CLI (~/.codex/auth.json) and Claude Code (~/.claude/.credentials.json)
        # logins automatically when Hermes has no usable login of its own. Their refresh tokens are single-use
        # and rotate, so two programs on one login can log each other out; set false to make Hermes use only
        # its own logins (`hermes auth add <provider>`). `hermes auth add openai-codex` still offers the import
        # interactively.
        "adopt_external_logins": True,
        # How `hermes auth add openai-codex` / `hermes model` sign in to OpenAI Codex.
        # "device_code" (default): open a URL, enter a code. "browser": authorization-code + PKCE on
        # the loopback listener http://localhost:1455/auth/callback (the redirect OpenAI registered
        # for the Codex client) — for organizations that disable the device-code grant. Falls back
        # to device code when that port is busy. `hermes auth add openai-codex --browser` opts in
        # for one login without changing this key.
        "codex_login_flow": "device_code",
    },
    "security": {  # Security: URL/private-network guards, redaction and approval presentation.
        "allow_private_urls": False,  # allow requests to private/internal IPs (OpenWrt, VPNs)
        # CIDR blocks a local TUN proxy answers DNS with (Mihomo/Clash fake-ip, Surge enhanced).
        # Answers inside these blocks are the proxy's sentinels, not internal hosts, so the guard
        # dials them instead of rejecting them as private. Empty = normal private-address verdict.
        "fake_ip_ranges": [],
        "redact_secrets": True,
        # Persisted acknowledgement for unattended model overrides whose tier lets the vendor train
        # on prompts. The startup guard still warns every run; cost guards are unaffected.
        "allow_data_training_tiers_noninteractive": False,
        # Human-approval presentation transport. "builtin" = CLI/TUI/gateway/ACP surfaces; a plugin
        # transport is used only when named explicitly. Transport timeout/error/invalid response
        # DENIES unless transport_fallback is "builtin". Presentation only: plugins cannot detect,
        # suppress, or auto-approve commands outside a correlated human response.
        "approval": {"transport": "builtin", "transport_fallback": "deny"},
        # Writes to agent-instruction files (AGENTS.md/CLAUDE.md/SOUL.md/.cursorrules, project-local
        # .hermes config) always need human approval, even under yolo. Extra patterns are fnmatch
        # globs on the basename (e.g. "*.mdc").
        "protected_instruction_files": True,
        "protected_instruction_extra_patterns": [],
        "website_blocklist": {"enabled": False, "domains": [], "shared_files": []},
        # IDs of supply-chain advisories the user has read and acted on; acked ones stop the startup
        # banner. Add via `hermes doctor --ack <id>`; remove by editing the list. Catalog:
        # hermes_cli/security_advisories.py.
        "acked_advisories": [],
        # Lazy-install opt-in backend packages from PyPI when a backend that needs them is first
        # enabled (e.g. `elevenlabs`). False = require explicit pip install for everything beyond
        # the base set (restricted/audited/air-gapped environments).
        "allow_lazy_installs": True,
    },

    "cron": {
        "catch_up_missed": True,  # False skips recurring misses beyond the local grace window.
        # Let cron-spawned agents use the cronjob toolset (the "cron-librarian" pattern). Off by
        # default: policy-denied in cron context to prevent unattended scheduling loops. Jobs
        # created this way are user-owned in the same flat jobs table. Interactive toolsets
        # (messaging/clarify) stay denied in cron regardless.
        "allow_agent_scheduling": False,
        # Pre-dispatch validation: before building any agent machinery, verify the provider API key
        # resolves (unless a fallback chain exists), attached skills are ready, and delivery
        # platforms are configured. Failure -> last_status=blocked_config, ONE alert, no LLM call.
        # False = fail during the run instead.
        "preflight": True,
        # Default model for cron jobs (WHAT model runs). Fire-time resolution: per-job pin >
        # cron.model > model.default (the main agent model). An unpinned job follows the main
        # model on every run; cron.model decouples the whole fleet from chat. "" = fall through.
        "model": "",
        # Inference provider paired with cron.model (NOT the scheduler provider below). "" = resolve
        # from global config.
        "model_provider": "",
        # Cron SCHEDULER provider (WHEN a due job fires). "" = built-in in-process 60s ticker. Name
        # an installed provider (plugins/cron_providers/<name>/ or $HERMES_HOME/plugins/ <name>/),
        # e.g. "chronos" (NAS-mediated managed cron for scale-to-zero). An unknown or unavailable
        # provider falls back to the built-in so cron never loses its trigger.
        "provider": "",
        # Chronos settings; consulted only when provider == "chronos". All non-secret — the agent
        # holds NO scheduler credentials (provision reuses the Nous Portal token).
        "chronos": {
            # NAS/portal base URL that arms/cancels one-shots and mints the inbound fire JWT (used
            # as the expected issuer).
            "portal_url": "https://portal.nousresearch.com",
            # This agent's publicly reachable base URL; NAS POSTs {callback_url}/api/cron/fire. ""
            # -> Chronos unavailable, resolver falls back to the built-in ticker.
            "callback_url": "",
            "expected_audience": "",  # Expected JWT audience (e.g. "agent:{instance_id}").
            # NAS JWKS URL for verifying the fire JWT signature. "" -> the fire endpoint refuses all
            # tokens (never an unsigned decode).
            "nas_jwks_url": "",
        },
        # Wrap delivered cron responses with a task-name header and "The agent cannot see this
        # message" footer. False = clean output.
        "wrap_response": True,
        "delivery": {  # Delivery behaviour for cron output sent through a live gateway adapter.
            # Mark cron deliveries FINAL so the platform pushes them (Telegram's "important" mode
            # otherwise sends with disable_notification=True and briefs look undelivered). False =
            # silent, no-push deliveries.
            "notify": True,
        },
        # Make cron deliveries CONTINUABLE (user can reply to a brief with it in context). False
        # keeps deliveries isolated to the job's session; per-job `attach_to_session` overrides.
        # Thread-capable platforms (Telegram topics, Discord/Slack threads) get a seeded thread per
        # job via create_handoff_thread; DM-only platforms mirror the brief into the target DM
        # session. Appended at a turn boundary via mirror_to_session, cached system prompt
        # untouched. User-written bare platforms address home conversations, unlike `all`
        # broadcast expansions, which do not gain mirror eligibility.
        "mirror_delivery": False,
        # Max due jobs run in parallel per tick. None/0 = unbounded (thread count only); 1 = serial.
        # Env override: HERMES_CRON_MAX_PARALLEL.
        "max_parallel_jobs": None,
        # save_job_output keeps the N most recent .md files per job; 0 or negative disables pruning
        # (for externally managed cleanup).
        "output_retention": 50,
        # Timeout (seconds) for a no-agent cron script. Env: HERMES_CRON_SCRIPT_TIMEOUT. Keep in
        # sync with cron.scheduler._DEFAULT_SCRIPT_TIMEOUT.
        "script_timeout_seconds": 3600,
        # Timeout (seconds) for SessionDB() init inside cron jobs: state.db open/migrate has no
        # timeout of its own against a wedged sqlite3.connect, and an unbounded hang wedges the
        # job's dispatch guard forever. Env: HERMES_CRON_SESSION_DB_TIMEOUT. 0 = unlimited.
        "session_db_timeout_seconds": 10,
        # Timeout (seconds) per media attachment send during gateway delivery; large attachments
        # (long TTS audio, big exports) need more than 30s. Env: HERMES_CRON_MEDIA_SEND_TIMEOUT.
        # Keep in sync with cron.scheduler._DEFAULT_MEDIA_SEND_TIMEOUT.
        "media_send_timeout_seconds": 300,
        # Managed systemd gateway with no user session (containers, no linger): false runs
        # cron jobs as a direct external subprocess (warns once; no cgroup isolation), true
        # fails closed with the enable-linger remedy. Kanban always requires a scope.
        "require_restart_safe_scope": False,
        # A job failing with the SAME error alerts once, then stays silent for this many hours
        # before one reminder ping (the run is still recorded; `hermes cron incidents` shows it).
        # A green run or a different error alerts again immediately; `hermes cron incidents ack`
        # silences a signature for good. 0 = re-alert on every failing run. Keep in sync with
        # cron.scheduler.DEFAULT_FAILURE_REPEAT_ALERT_HOURS.
        "failure_repeat_alert_hours": 6,
    },
    # Kanban multi-agent coordination. The dispatcher ticks every N seconds, reclaims stale claims,
    # promotes dependency-satisfied todos to ready, and fires `hermes -p <assignee> chat -q ...` per
    # claimable task. Run ONE dispatcher per profile; two on the same kanban.db race for claims.
    "kanban": {
        # Auto-subscribe the originating gateway/TUI session to completion + block events when
        # kanban_create is called from a session with a persistent delivery channel. Disable for
        # profiles that prefer explicit kanban_notify-subscribe calls per task.
        "auto_subscribe_on_create": True,
        # Poll and deliver Kanban subscriptions from this gateway. Disable on profiles that do
        # not own notification subscriptions to avoid an idle five-second board probe.
        "notify_in_gateway": True,
        # Run the dispatcher inside the gateway process (~300µs per idle tick). False only if you
        # run it as a separate unit or don't want the gateway spawning workers.
        "dispatch_in_gateway": True,
        # Auto-claim tasks in the review column and spawn the assigned profile with the bundled
        # sdlc-review skill. Disable where every review is done manually from the dashboard.
        "review_dispatch": True,
        # Seconds between dispatcher ticks. Lower = snappier pickup; higher = less SQL pressure.
        "dispatch_interval_seconds": 60,
        # Auto-block after this many consecutive non-success attempts (spawn_failed, timed_out,
        # crashed) for the same task/profile. Reassignment resets the streak.
        "failure_limit": 2,
        # Worker stdout/stderr log rotation at spawn time (2 MiB + one backup). Raise to keep more
        # early failure evidence from long-running workers.
        "worker_log_rotate_bytes": 2 * 1024 * 1024,
        "worker_log_backup_count": 1,
        # Profile for the root/orchestration task after Triage decomposition; "" = default profile.
        # Does not control the decomposer LLM path (see auxiliary.kanban_decomposer).
        "orchestrator_profile": "",
        # Assignee when the orchestrator can't match one to an installed profile; "" = default
        # profile. A task never ends up with assignee=None.
        "default_assignee": "",
        # Global cap: positive int = the HOST never has more than N tasks 'running' across all
        # boards and both dispatch lanes. None = ~MemTotal / 512 MiB clamped to [2, 8]; where
        # MemTotal is unreadable (macOS/Windows) None means no cap.
        # Global concurrency cap (#33488): when set to a positive int, the HOST never has more than N tasks
        # in 'running' at once — counted across every active board and across both the ready and review
        # dispatch lanes (workers are OS processes sharing one machine's memory, so the cap bounds the
        # machine, not each board; OOF-30). Unset (None) means "derive from system memory" (OOF-30/OOF-77):
        # the dispatcher caps concurrency at roughly MemTotal / 512 MiB, clamped to [2, 8] — e.g. 2 workers
        # on a 1 GiB VM. On hosts where total memory can't be read (macOS/Windows), unset falls back to no
        # cap. Set an explicit value to override the derived default in either direction.
        "max_in_progress": None,
        # Per-profile cap: positive int = no single profile runs more than N workers even if the
        # global caps allow; blocked tasks defer to the next tick. None = no per-profile cap. Useful
        # when fan-out would saturate one profile's model/API quota/browser pool.
        # Unset (None) means "no per-profile cap" — backward-compatible with existing installs. Useful for
        # fan-out workflows that would otherwise saturate one profile's local model / API quota / browser
        # pool while leaving other profiles idle. See #21582.
        "max_in_progress_per_profile": None,
        # Per-home claim allowlist for boards shared across Hermes homes (#110995): profile names
        # this home's dispatcher may claim (list or comma-separated string). None = any existing
        # profile is claimable. Set = fail-closed (an empty list claims nothing). Every home has a
        # root profile named "default", so on a shared kanban.db every home can otherwise claim
        # default-assigned cards.
        "dispatch_profiles": None,
        # Auto-run the decomposer on Triage tasks every tick. False = manual via `hermes kanban
        # decompose <id>` or the dashboard's Decompose button.
        "auto_decompose": True,
        # Max triage tasks decomposed per tick, bounding the aux-LLM burst from a bulk load. Excess
        # defers to the next tick.
        "auto_decompose_per_tick": 3,
        # Running tasks with no heartbeat (last_heartbeat_at) for this many seconds are reclaimed to
        # ready on the next tick; a still-running local worker is terminated first. 0 = off.
        "dispatch_stale_timeout_seconds": 14400,
        # Each tick, requeue 'running' cards with broken claim bookkeeping (claim_lock or
        # claim_expires NULL with a dead worker) that TTL/crash/stale recovery can't see. False
        # keeps orphans frozen for manual forensics.
        "reconcile_orphans": True,
        # Notify subscriptions survive `done` (completion is reversible) and are removed on archive.
        # On boards that never archive, the notifier GC purges subscriptions for tasks done with no
        # activity for this many days so stale rows aren't scanned forever. 0 = off.
        "done_sub_retention_days": 30,
    },
    # Bot Mode cross-connection relay (tools/bot_relay.py): envelopes queued by message_agent for
    # agents on other connections wait in an on-disk outbox until the Desktop drains them.
    "bot_mode": {
        # Drain-time TTL (seconds): older envelopes are NOT delivered on drain; the sender gets an
        # error reply (reason 'queued_expired') so a DM can't land hours late as a zombie. 0 = no
        # drain-time expiry (the 6h stale-artifact sweep still applies).
        "envelope_ttl_seconds": 900,
        # How long a second delivery into a busy target profile queues behind the current turn
        # before failing with a structured 'target_busy' error. Deliveries are serialized per
        # profile with a cross-process file lock.
        "turn_wait_seconds": 120,
    },
    "code_execution": {  # execute_code settings (programmatic tool calls).
        # project = run in the session cwd with the active venv/conda python so project deps and
        # relative paths resolve. strict = isolated temp dir with hermes-agent's own python
        # (sys.executable): max isolation, project deps/relative paths won't work. Env scrubbing
        # (*_API_KEY, *_TOKEN, *_SECRET, ...) and the tool whitelist apply in both modes.
        "mode": "project",
        # Session kernels are always on locally (`kernel_mode` is ignored) and remotely
        # (tools/code_kernel_remote.py; a backend that cannot spawn a kernel fails open to
        # per-call). One kernel per (session owner, mode, interpreter, cwd, tool-set) keeps state
        # across calls and turns; subagents get their own. Kernels die with the session, after
        # kernel_idle_timeout idle seconds, or by LRU eviction past max_session_kernels. A
        # timed-out/interrupted cell kills the kernel; env is frozen at spawn (reset=true after
        # changing passthrough). Tool RPC authority (approval, session, allow-list, call budget) is
        # rebound per cell — that runtime boundary is the cross-cell enforcement.
        "kernel_idle_timeout": 1800,
        "max_session_kernels": 4,
    },
    # Tool Search replaces deferred tools in the model-facing array with the
    # tool_search / tool_describe / tool_call bridges and surfaces them on demand.
    # Working-set core tools stay eager, while the explicit ``defer`` list below
    # may include cold, event-triggered built-ins as well as plugin/MCP tools.
    "tools": {
        "tool_search": {
            # Tiered: tier 0 (no deferred tools) = everything eager; tier 1 = bridge + a
            # name+description manifest when it fits the budget (degrades to names-only); tier 2
            # (over budget even names-only, e.g. ~3,300-tool APIs) = bare bridge + a
            # one-line-per-server summary (name + tool count). "auto"|"on" = activate when at least
            # one deferred tool exists ("auto" is an alias of "on" today, reserved for a future
            # budget-gated mode; keep it the default so explicit "on"/"off" pins are unaffected).
            # "off" = pass-through, no bridge.
            "enabled": "auto",
            # Listing budget as % of the model's context length; effective budget = min(this % of
            # context, listing_max_tokens). Range 0..100.
            "threshold_pct": 5,
            # Hits per query when the model omits `limit`. Range 1..max_search_limit.
            "search_default_limit": 5,
            # Hard upper bound the model may request via `limit` (per query). Range 1..50.
            "max_search_limit": 25,
            # Catalog listing embedded in the bridge description (name + first sentence ≤60 chars,
            # grouped by server/toolset). "auto" = include when it fits (falls back to names-only,
            # then bare tier-2 bridge); "on" = same rendering, explicit intent; "off" = always the
            # bare bridge.
            "listing": "auto",
            # Absolute cap on the embedded listing in tokens (chars/4), regardless of context size.
            # Range 200..60000.
            "listing_max_tokens": 4000,
            # Tools replaced by the bridge by default. This list intentionally includes cold,
            # event-triggered built-ins; an explicit list replaces it wholesale and [] keeps every
            # tool eager. The runtime fallback in tools/tool_search.py derives from this value.
            "defer": [
                "computer_use", "session_search", "image_generate",
                "todo_list", "process_manage", "cronjob_manage", "browser_vault",
                # Desktop GUI surface (desktop_ui, project and catalog toolsets)
                "drive_preview", "gui_tour", "desktop_preview", "annotate_preview", "manage_catalog",
                "show_tip", "desktop_project", "close_terminal",
                "set_theme", "read_terminal", "read_window_below", "focus_pane",
            ],
        },
        # Remote connector discovery/lifecycle through the Nous tool gateway.
        # The flag is the user's off switch; availability additionally requires
        # the portal sign-in every managed tool gates on.
        "connectors": {"enabled": True},
    },
    "logging": {  # File logging to ~/.hermes/logs/: agent.log captures INFO+, errors.log WARNING+.
        "level": "INFO",       # minimum level for agent.log: DEBUG, INFO, WARNING
        "max_size_mb": 5,      # max size per log file before rotation
        "backup_count": 3,     # rotated backups to keep
    },
    # Remote model-catalog manifest: curated OpenRouter / Nous Portal model lists fetched from this
    # URL (falls back to the in-repo snapshot on network failure), so picker lists update without a
    # release. Default URL is served by the docs-site GitHub Pages deploy.
    "model_catalog": {
        "enabled": True,
        "url": "https://hermes-agent.nousresearch.com/docs/api/model-catalog.json",
        # Disk cache TTL in minutes. The gateway refreshes in the background on this cadence; the
        # CLI refetches on the next /model or `hermes model` once the cache is older. Network
        # failures silently use the stale cache. Legacy `ttl_hours` is honoured if set.
        "ttl_minutes": 20,
        # Per-provider override URLs for self-hosted curation lists using the same schema, e.g.
        # providers: {openrouter: {url: https://example.com/my-curation.json}}.
        "providers": {},
    },
    # Per-model metadata overrides. Fields: context_window, supports_tools,
    # supports_vision, supports_reasoning, model_family. <provider>.<model_id> wins over
    # models.dev/OpenRouter/hardcoded defaults for the fields it sets (chain order in
    # agent/model_metadata.py). <provider>._default and top-level _default fill gaps ONLY for models
    # the catalog does not know, so they never clamp known models. Unknown ids start from safe
    # defaults (200K context, tools on) and get patched; supports_vision / supports_reasoning stay
    # UNKNOWN (fail-open) unless the override sets them — a context_window-only entry must not turn
    # into "text-only" and hide vision_analyze / reasoning controls (#112649). Provider keys: Hermes
    # or models.dev id; model ids match case-insensitively. Example: {"custom:my-local-vllm":
    # {"my-llava-model": {"context_window": 8192}}}
    # Semantics: 1. NOTE: an explicit model.context_length (global) and a custom_providers per-model
    # context_length are user settings at other layers and are consulted in the resolution chain order
    # documented in agent/model_metadata.py. 2. See #84482, #8731.
    "model_overrides": {},
    # models.dev registry (context windows, capabilities, pricing, modalities): fetched on startup,
    # served from cache, refreshed by a background daemon with ETag conditional GET. Override `url`
    # to point at a mirror (e.g. behind a corporate proxy).
    "models_dev": {
        "url": "",  # empty = default https://models.dev/api.json
    },

    "network": {
        # Force IPv4. With broken/unreachable IPv6, Python tries AAAA first and hangs for the full
        # TCP timeout before falling back. True skips IPv6 entirely.
        "force_ipv4": False,
    },
    # Gateway monitoring: service health + redacted operational diagnostics exported over OTLP to an
    # operator endpoint (OTEL Collector, DataDog, ...). Content-free by construction: no prompts,
    # messages, tool args/results, session history, usage analytics, audit logs, or trajectories.
    # Nothing is collected or sent until enabled with an endpoint.
    "monitoring": {
        # Stable install identifier on exported signals so operators can tell instances apart. "" =
        # mint a fresh UUID on first use; clear it to rotate. Carries no account identity.
        "install_id": "",
        "gateway_health_export": {  # Gateway health & diagnostics export.
            "enabled": False,
            "metrics_enabled": True,
            "diagnostic_events_enabled": True,
            "warning_error_events_enabled": True,
            "export_interval_seconds": 60,
            "logs_export_interval_seconds": 5,
            "resource_attributes": {
                "service.name": "hermes-gateway", "deployment.environment.name": "production"
            },
        },
        # OTLP destination. headers_env maps header names to ENVIRONMENT VARIABLE NAMES (never
        # secret values); values are read from the environment at export time.
        "export": {"otlp": {"enabled": False, "endpoint": "", "headers_env": {}}},
    },
    "gateway": {  # Gateway settings (messaging platforms: Telegram, Discord, Slack, ...).
        "unmanaged_idle_exit_seconds": 600,  # client-auto-started gateway only; 0 disables
        # Seconds a SIGTERM-interrupted agent unwinds before teardown (short: service stop budgets).
        "signal_interrupt_grace_timeout": 1,
        "service_install_choice": None,  # null | install | decline; never authorizes ordinary launch installation.
        # Durable delivery-obligation ledger: final responses are recorded in state.db around the
        # platform send; a gateway that died between finalize and platform ACK redelivers on next
        # boot (ambiguous cases carry a "recovered reply — may be a duplicate" marker;
        # at-least-once). Disable to lose in-flight final responses on crash/restart.
        "delivery_ledger": True,
        # Seconds to wait for one platform to connect at startup/reconnect; raise on "discord
        # connect timed out" loops (many slash commands to sync). 0/negative = wait forever. Bridged
        # to HERMES_GATEWAY_PLATFORM_CONNECT_TIMEOUT, which wins if set explicitly.
        # Seconds the gateway waits for a single messaging platform to finish connecting during startup (and
        # on reconnect). Discord in particular can blow past the old fixed 30s when an account has many
        # slash commands to sync (#19776: 90-173 skills → ~28-31s sync). Raise this if your gateway hits
        # "discord connect timed out" / "Timeout waiting for connection to Discord" restart loops. ``0`` or
        # negative disables the timeout entirely (wait indefinitely).
        "platform_connect_timeout": 30,
        # Event-loop liveness watchdog: a daemon thread probes the asyncio loop; after consecutive
        # missed probes it dumps all-thread stacks and hard-exits with the service-restart code so
        # systemd/launchd revives the process instead of leaving a wedged-but-alive zombie.
        # Set to false to disable. See #69089.
        "loop_watchdog": True,
        # Watchdog tuning (defaults mirror gateway/shutdown_watchdog.py): probe_interval = seconds
        # between probes; probe_timeout = seconds before an unprocessed probe counts as a miss;
        # max_strikes = consecutive misses before hard-exit 75 (~90-120s of sustained loop block at
        # the defaults).
        "loop_watchdog_probe_interval_s": 30.0,
        "loop_watchdog_probe_timeout_s": 10.0,
        "loop_watchdog_max_strikes": 3,
        # Allow all users without allowlists (security opt-in).
        "allow_all_users": False,
        # Bot-to-bot loop guard: admitted bot messages per conversation before a cooldown.
        "bot_loop_guard": {"enabled": True, "max_events": 20, "window_seconds": 300, "cooldown_seconds": 600},
        # Startup-liveness watchdog: stdlib-only daemon thread armed at process entry that
        # hard-exits 75 if the loop isn't live within the deadline. Armed before config loads, so
        # run_gateway() bridges these to HERMES_STARTUP_WATCHDOG / HERMES_STARTUP_WATCHDOG_TIMEOUT_S
        # and re-arms the live handle; explicit env wins.
        "startup_watchdog": True,
        "startup_watchdog_timeout_seconds": 300,
        # Keep writing the legacy ~/.hermes/sessions/sessions.json mirror of the routing index
        # (primary copy: state.db gateway_routing table). True for external tooling and downgrade
        # safety; False stops producing the file.
        "write_sessions_json": True,
        # One gateway for every profile on this host: the DEFAULT profile's gateway also connects
        # each named profile's bots (their own .env / config.yaml, per-profile secret scope) and
        # stamps the profile into session keys. This is the ONLY supported topology — there is no
        # `false` opt-out any more: an explicit `false` still parses (it is the runtime mode flag
        # every scoped code path reads) but is warned about and IGNORED for process topology, and
        # `hermes gateway migrate --multiplex` folds any per-profile fleet that is left.
        # An UNSET key is a request, not a verdict: at boot the gateway runs the migration
        # preflight and stays standalone (logging why) while a secondary still runs its own
        # gateway or a blocker exists, then converges once that is resolved.
        # TWO things DO change on a host that had pinned `false`, and neither is a process:
        #   • INGRESS — `/p/<profile>/` on the default listener goes 404 -> served
        #     (gateway/api_server.py::_resolve_request_profile, gateway/webhook.py). A host that
        #     opted out GAINS that HTTP surface; it is authenticated exactly like the default
        #     profile's, but it is new reachable surface, so audit any reverse proxy that assumed
        #     /p/ was dead.
        #   • SECRET SCOPE — eager multi-profile activation no longer consults the flag
        #     (tui_gateway/launch_profile_policy.py), so a host with a leftover servable profile
        #     dir flips eager=false/reads-open -> eager=true/fail-closed: an UNSCOPED `get_secret`
        #     now raises UnscopedSecretError, and a key that lives ONLY in the unit's
        #     `Environment=` (no .env) disappears from file-built scopes. A genuinely
        #     single-profile host never activates and is byte-identical.
        # Two profiles configuring the same bot token cannot be served together — the duplicate
        # adapter is parked; `hermes profile create --clone` therefore leaves messaging channels
        # behind unless --clone-channels is passed.
        "multiplex_profiles": True,
        # May `hermes update` fold this install onto a multiplexed default gateway by itself?
        # True (the default) keeps today's behaviour: a multi-profile install whose secondaries run
        # their own gateways is migrated automatically after an update when nothing blocks it.
        # Set to False to choose WHEN you converge, not whether: the fold is left to you to run by
        # hand (it is not an opt-out from the one-gateway-per-host model, which has none). Only the
        # AUTOMATIC path reads this: `hermes gateway migrate --multiplex` is explicit and proceeds.
        "auto_multiplex_migration": True,
        # Route inbound chats of the default profile's bots to another profile
        # (gateway/profile_routing.py): [{profile, platform, chat_id|user_id|guild_id|...}].
        # Most-specific match wins; only read by the multiplexing default gateway.
        "profile_routes": [],
        # Scale-to-zero idle TIMEOUT only. When an instance is opted in via the NAS "Labs" toggle
        # (HERMES_SCALE_TO_ZERO env stamp) AND messaging is relay-only/absent AND a wakeUrl is
        # registered, the relay transport goes dormant so the platform (e.g. Fly autostop) can
        # suspend the machine; it wakes on the wakeUrl poke. Enablement is the Labs toggle, never a
        # config key. 0/negative = default.
        "scale_to_zero": {"idle_timeout_minutes": 2},
        # Auto-resume restart-loop breaker. A supervisor-revived gateway auto-resumes the
        # SIGTERM-interrupted session; if that turn keeps triggering the kill, boots no more than
        # `max_gap_seconds` apart (floored by `window_seconds`) chain, and after `max_restarts`
        # auto-resume is SKIPPED for that boot (inbound messages still served). Gap-based chaining
        # also catches SLOW ~150s crash cycles. max_restarts=0 disables.
        "restart_loop_guard": {"max_restarts": 3, "window_seconds": 60, "max_gap_seconds": 300},
        # Respawn-storm circuit breaker (complements restart_loop_guard): counts (re)starts in a
        # sliding window and sleeps an exponential backoff before booting so a crash-looping
        # supervisor can't hammer the process. max_starts <= 0 disables. Env escape hatches:
        # HERMES_GATEWAY_MAX_STARTS / HERMES_GATEWAY_START_WINDOW_S.
        "respawn_storm": {"max_starts": 5, "window_seconds": 120},
        # Prefix user messages IN THE MODEL'S CONTEXT with a timestamp (e.g. "[Tue 2026-04-28
        # 13:40:53 CEST]") for temporal awareness. Persisted transcripts stay clean (timestamp is
        # message metadata regardless), so enabling later surfaces past send-times too.
        "message_timestamps": {"enabled": False},
        # Max bytes of inbound image/audio/video the gateway buffers into RAM and caches to disk.
        # Media is read fully into memory first, so unbounded uploads (Discord Nitro: 500 MB) or
        # huge remote URLs can OOM-kill constrained deployments. Enforced in
        # gateway/platforms/base.py for every adapter. 0 = no cap. Default 128 MiB.
        "max_inbound_media_bytes": 134217728,
        # Let adapters read HTTP_PROXY/HTTPS_PROXY/NO_PROXY/SSL_CERT_FILE from the environment and
        # auto-detect generic/macOS system proxies. False when the gateway inherits a proxy it must
        # not use (e.g. a scheduled task picking up a Clash/V2Ray HTTP_PROXY -> "Cannot connect to
        # host 127.0.0.1:7890"). Per-platform vars (DISCORD_PROXY, TELEGRAM_PROXY, ...) are still
        # honored.
        "trust_env": True,
        # Media delivery. False: any emitted file path is delivered natively unless under the
        # credential/system denylist (/etc, /proc, ~/.ssh, ~/.aws, ~/.hermes/.env, auth.json). True:
        # files must be under the Hermes cache, media_delivery_allow_dirs, or fresher than
        # trust_recent_files_seconds — recommended for public-facing gateways so prompt injection
        # can't exfiltrate host secrets. Bridged to HERMES_MEDIA_DELIVERY_STRICT.
        "strict": False,
        # Extra roots (project/scratch dirs, mounted shares) from which bare file paths may be
        # uploaded; the Hermes cache is always trusted. List of absolute paths or one
        # os.pathsep-separated string; tildes expanded. Bridged to HERMES_MEDIA_ALLOW_DIRS. Honored
        # in both modes.
        "media_delivery_allow_dirs": [],
        # Trust files whose mtime is within trust_recent_files_seconds even outside the cache/
        # allowlist (e.g. `pandoc -o /tmp/report.pdf`); system paths stay blocked. False =
        # pure-allowlist mode. Bridged to HERMES_MEDIA_TRUST_RECENT_FILES. Only consulted when
        # strict is true.
        "trust_recent_files": True,
        # Recency window in seconds; 600 covers a multi-tool turn. Bridged to
        # HERMES_MEDIA_TRUST_RECENT_SECONDS. Only consulted when strict is true.
        "trust_recent_files_seconds": 600,
        "api_server": {  # OpenAI-compatible API server platform (gateway/platforms/api_server.py).
            # Max concurrent agent runs. Requests to /v1/chat/completions, /v1/responses, and
            # /v1/runs beyond this get HTTP 429 + Retry-After, bounding CPU/memory/LLM-quota
            # exhaustion from a request flood. 0 = no cap.
            "max_concurrent_runs": 10,
            # Cap (chars) on each tool output and tool-call argument string in the stored
            # /v1/responses conversation history used for previous_response_id chaining. The
            # stored history is cumulative, so a few large tool outputs can make one
            # response_store.db write several hundred KB. 0 = store tool outputs verbatim
            # (default: the capped text is what the model is replayed on the next turn).
            "history_tool_output_max_chars": 0,
        },
    },
    # Real-time token streaming to messaging platforms (gateway; restart after enabling). Off by
    # default: costs extra edit/draft API calls per response.
    "streaming": {
        "enabled": False,  # When false, each response is delivered as one final message.
        # auto = native drafts where supported (Telegram DMs, Bot API 9.5+), edits elsewhere
        # (Discord, Slack, Matrix, Telegram groups); draft = drafts with edit fallback; edit =
        # progressive editMessageText only; off = disabled.
        "transport": "auto",
        # Minimum seconds between progressive edits (Telegram's ~1 edit/s flood envelope).
        "edit_interval": 0.8,
        # Flush the buffer once this many chars accumulate, so short replies feel instant.
        "buffer_threshold": 24,
        "cursor": " \u2589",  # Cursor glyph appended to the in-progress message.
        # Telegram only: when >0, if the preview was visible at least this many seconds the final
        # edit is sent as a fresh message so the timestamp reflects completion.
        "fresh_final_after_seconds": 0.0,
    },
    # Automatic cleanup of ~/.hermes/state.db, which otherwise grows without bound and slows FTS5
    # inserts, /resume listing, and insights queries.
    "sessions": {
        # Prune ENDED sessions inactive for retention_days (activity = freshest of live activity /
        # latest message / creation) about once per min_interval_hours at CLI/gateway/cron startup.
        # Open, pinned, or mid-turn sessions are never deleted; stale automation sessions whose
        # process died are *closed*, then get a full retention window before removal.
        # Off by default (deleting history is opt-in). While the user's config.yaml has no
        # auto_prune key, every surface asks once the disk holding state.db runs low
        # (hermes_cli/prune_advisor.py); either answer writes the key and ends the question.
        "auto_prune": False,
        # Inactive days of ended-session history to keep (= `hermes sessions prune`).
        "retention_days": 90,
        # Auto-archive (soft-hide, never delete) sessions with no activity for auto_archive_days,
        # once per min_interval_hours. Pinned sessions are exempt.
        "auto_archive": False,
        # Idle days before auto-archive hides a session (only when auto_archive is true).
        "auto_archive_days": 3,
        # List delegate_task subagent runs in session lists (desktop sidebar, dashboard, session.list),
        # nested under their parent. Off by default: they are machinery, not conversations.
        "show_subagents": False,
        # VACUUM after a prune that deleted rows (SQLite never reclaims disk on DELETE). VACUUM
        # blocks writes (~seconds per 100MB), so it runs only at startup, only when ≥1 session was
        # deleted AND freelist/page_count > 25%.
        # SQLite does not reclaim disk space on DELETE — freed pages are just reused on subsequent INSERTs —
        # so without VACUUM the file stays bloated even after pruning. See #54189.
        "vacuum_after_prune": True,
        # Minimum days between VACUUM rewrites; pruning keeps its normal cadence.
        "min_vacuum_interval_days": 30,
        # Minimum hours between auto-maintenance runs (tracked in state.db state_meta, shared across
        # processes).
        "min_interval_hours": 24,

        # Notice about the compact FTS layout (reclaims ~60%+ of state.db). OPT-IN: legacy indexes
        # stay until `hermes sessions optimize-storage` runs, since the rebuild is disk-heavy on
        # large DBs. advise = `hermes update` prints a one-line notice with reclaimable size when a
        # legacy index is detected (a later layout change gets a rebuild notice without a size estimate);
        # require = the same notices worded as REQUIRED (tooling may gate on it); off = none.
        "fts_optimize_notice": "advise",
        # CJK-bigram search index (messages_fts_cjk). When the extension is built
        # (native/fts5_cjk/build.sh → ~/.hermes/lib/libfts5_cjk.so), 1-2 char CJK terms get exact
        # index matches instead of LIKE scans. True = use when present (inert otherwise); False =
        # never load/serve it. Bridged to HERMES_CJK_FTS.
        "cjk_fts": True,
        # Slow session-search threshold (ms): searches at/above it log one INFO line with the
        # routing path (fts_cjk / fts5 / trigram / like_scan). 0 logs every search. Bridged to
        # HERMES_SEARCH_SLOW_MS.
        "search_slow_ms": 1000,
        # Transcript guards (a runaway 100k+ row session can exhaust memory when materialized at
        # once; 0 disables). Max active messages (across the compression lineage) for interactive
        # resume.
        "max_resume_messages": 20000,
        # Max active messages per session for in-memory export (`hermes sessions export`); checked
        # per session, so full-DB backups of small sessions work.
        "max_export_messages": 20000,
    },
    # First-touch onboarding hints (agent/onboarding.py), each latched under `seen` once shown.
    "onboarding": {
        "seen": {},
        "profile_build": "ask",  # first-ever message: ask = offer; off = plain intro only
        # Desktop first run, root profile only (onboarding_run.py): None = fresh install; true = next launch; false = done
        "run": None,
    },
    # Privacy-safe aggregate metrics in this profile's local telemetry dir. Collection (`enabled`)
    # and upload to Nous (`send`) are separate keys that every consent surface sets together; see
    # website/docs/developer-guide/relay-shared-metrics.md Appendix A for consent/retention.
    "telemetry": {
        "shared_metrics": {
            "enabled": False,
            # Requires `enabled` (`send` alone logs an error). A package is sent only if its whole
            # period is inside a recorded consent window.
            "send": False,
            # Ingest endpoint (override for staging/local). Deliberately NOT env- overridable.
            # Non-HTTPS refused unless the host is localhost.
            "endpoint": "https://telemetry.nousresearch.com/v1/telemetry",
        },
    },

    "doctor": {
        # Per-probe timeout (seconds) for `hermes doctor --live` real-call probes.
        "live_probe_timeout": 10,
    },

    "updates": {
        # Passive version/banner checks only; explicit `hermes update --check` remains enabled.
        "check": True,
        # Pre-update backup. quick = snapshot small critical state (pairing JSONs, cron jobs,
        # config.yaml, .env, auth.json, profile DBs) into <HERMES_HOME>/state-snapshots/, skipping
        # files >1 GiB; restore via ``/snapshot``. full = quick PLUS a ``hermes backup`` zip in
        # <HERMES_HOME>/backups/ (``hermes import`` restores; slow on large homes; ``--backup``
        # forces once). off = none (``--no-backup`` forces once). Legacy booleans: true -> full,
        # false -> off.
        # Pre-update safety backup — ONE consolidated mechanism, three modes: Files over 1 GiB (e.g. a
        # bloated state.db) are skipped with a warning so the snapshot stays fast. This is the #48200
        # (wrong-path wipe) safety net.
        "pre_update_backup": "quick",
        # Full backup zips to retain (older pruned after each success; floored to 1 so the newest is
        # always kept). The quick snapshot always keeps exactly 1.
        "backup_keep": 5,
        # Uncommitted source-tree changes during NON-interactive updates (desktop, gateway — no TTY;
        # interactive updates always stash and ask). stash = stash, pull, restore on top (conflicts
        # stay in a git stash). discard = stash and drop after the pull (stash-and-drop, not reset
        # --hard + clean -fd, so ignored paths like node_modules/venv are never touched).
        "non_interactive_local_changes": "stash",
        # If the checkout is parked on a feature branch and the tree is clean, switch to the update
        # target (commits stay on the branch; a loud notice names it) so non-interactive updates
        # keep working. A DIRTY tree blocks the switch and the code update is SKIPPED with a loud
        # warning. False = never auto-switch.
        "auto_switch_parked_branch": True,
        # Clean parked branch with unmerged commits: switch = move to the update target, commits
        # stay on the branch (never conflicts). update_in_place = for a maintained custom branch:
        # merge origin/<target> INTO it after leaving a pre-update-<stamp> tag; a conflict stops the
        # update cleanly. `hermes update --switch-branch` overrides to switch for one run.
        "parked_branch_strategy": "switch",
        # Refresh an installed cua-driver during `hermes update` (best-effort, macOS only). Turn off
        # e.g. on non-admin accounts where /Applications isn't writable.
        "refresh_cua_driver": True,
    },
    # LSP diagnostics (pyright, gopls, rust-analyzer...) in the post-write lint check of
    # write_file/patch. Runs only when the cwd or edited file is inside a git worktree; otherwise
    # dormant and the in-process syntax check is the only tier.
    "lsp": {
        "enabled": True,  # False disables the whole subsystem: no servers, no event loop, no cost.
        # document = wait up to wait_timeout seconds for the current file's diagnostics; full = also
        # request workspace-wide diagnostics (slower).
        "wait_mode": "document",
        "wait_timeout": 5.0,
        # Budget for the FIRST request against a workspace whose server is not running yet (spawn +
        # initialize + the server's initial program build; tsserver on a large project can need a
        # minute). Once the client is up, wait_timeout applies again. 0 = same as wait_timeout.
        "warmup_timeout": 0.0,
        # After a server fails (spawn error or outer timeout) its (server, workspace root) pair is
        # skipped. 0 = for the process lifetime (until `hermes lsp restart`); N = retried after N
        # seconds, so one transient stall does not silence a workspace forever.
        "broken_retry_seconds": 0.0,
        # Workspace roots (glob patterns, ~ expanded; a bare path also matches everything under
        # it) where no language server runs at all, e.g. one huge monorepo whose server cannot
        # finish in budget, while every other workspace keeps its diagnostics. Must be a list —
        # any other shape logs a warning and skips LSP for every workspace until fixed.
        "exclude_roots": [],
        # Directories (~ expanded; everything under an entry counts) whose projects a language
        # server may load code from: the project's own .venv/venv interpreter, node_modules
        # TypeScript SDK, svelte.config.js, build files (cargo, Gradle, mix, ...). The worktree of
        # the launch dir or the session's workspace (hermes -w, a Desktop project, terminal.cwd) is
        # always trusted; in any other checkout (a clone the agent made) only servers that run no
        # project code start, pinned to Hermes-side tools, and the npx tsc / rustfmt lint fallbacks
        # are skipped.
        "trusted_workspaces": [],
        # Missing server binaries: auto = install via npm/go/pip into <HERMES_HOME>/lsp/bin/ on
        # first use; manual = only binaries on PATH; off = alias for manual.
        "install_strategy": "auto",
        # Node package manager for the npm-recipe servers: npm | pnpm | yarn. Installs still land in
        # <HERMES_HOME>/lsp/node_modules; a configured manager that is not installed, or an unknown
        # value, skips the install (no silent fallback to npm) so a pnpm/yarn supply-chain policy is
        # never bypassed.
        "package_manager": "npm",
        # Idle seconds before a server is shut down (respawned on demand), so long- running
        # processes don't accumulate stale children (hundreds of MB + pipe FDs each) across
        # worktrees. 0 = keep servers for process lifetime.
        "idle_timeout": 600.0,
        # Per-server overrides keyed by registry server_id (pyright, gopls...): disabled: true;
        # command: ["path/to/server", "--stdio"] (bypasses auto- install); env: {...};
        # initialization_options: {...} (merged into LSP initializationOptions).
        # A key that is NOT a built-in id declares a custom server (matched before the built-ins):
        # command: ["my-ls", "--stdio"]; extensions: [".ext"]; optional root_markers: [...],
        # language_id: "..." (didOpen languageId), description: "...". Manual install only.
        "servers": {},
    },
    # X (Twitter) Search via xAI's x_search Responses tool. Registers when xAI creds exist
    # (SuperGrok OAuth or XAI_API_KEY) AND the toolset is enabled in `hermes tools`.
    "x_search": {
        # xAI model for the Responses call; any Grok model with x_search access works.
        "model": "grok-4.5",
        # Reasoning effort for models that support it; null keeps the model default.
        "reasoning_effort": None,
        # Request timeout in seconds (minimum 30); complex queries can take 60-120s.
        "timeout_seconds": 180,
        # Retries on 5xx / ReadTimeout / ConnectionError (backoff 1.5x attempt s, cap 5s).
        "retries": 2,
    },
    # External secret sources — pull credentials from secret managers at startup instead of storing
    # them in ~/.hermes/.env.
    # Browser credential vault: which login sources browser_vault may draw from. The local
    # encrypted vault (`hermes vault add`, Desktop → Settings → Credential Vault) is always on.
    # External password managers are unlocked per session with a masked master-password prompt;
    # headless sessions (cron, webhook, API) never prompt and see them as locked.
    "vault": {
        "onepassword": {
            # Detected managers are login sources unless the user opts out (vault.<name>.enabled: false).
            "enabled": True,        # `op` CLI: Login items with a website URL become fillable handles.
            "account": "",          # account shorthand for `op --account`; empty = default account.
            "binary_path": "",      # absolute path to op; empty = PATH.
            # Env var holding a service-account token (headless auth, no unlock prompt). Unset = prompt.
            "service_account_token_env": "OP_SERVICE_ACCOUNT_TOKEN",
        },
        "bitwarden": {
            "enabled": True,        # `bw` CLI (Password Manager, not Secrets Manager); run `bw login` once first.
            "binary_path": "",      # absolute path to bw; empty = PATH.
        },
    },
    "secrets": {
        # Optional ordering of enabled sources (e.g. [onepassword, bitwarden]); default registration
        # order. Mapped sources (explicit VAR→ref) always beat bulk sources (BSM project dumps);
        # first claim on a var wins, later ones warn. "sources": [],
        "bitwarden": {
            "enabled": False,  # When false, BSM is never contacted and bws is never auto-installed.
            # Env var holding the machine-account token — the one bootstrap secret; lives in
            # ~/.hermes/.env (or the shell), never in config.yaml.
            "access_token_env": "BWS_ACCESS_TOKEN",
            "project_id": "",  # UUID of the BSM project to sync from.
            # Seconds to reuse a fresh disk/memory cache entry before contacting Bitwarden again. 0
            # disables fresh-cache reuse.
            "cache_ttl_seconds": 300,
            # Last-good fallback for NETWORK/TIMEOUT outages: AES-GCM cache under ~/.hermes/cache/,
            # reused up to max_stale_seconds. Auth failures never fall back.
            "encrypted_cache": {"enabled": False, "max_stale_seconds": 0},
            # BSM values overwrite existing env vars, so rotating in Bitwarden takes effect without
            # clearing the matching .env line.
            "override_existing": True,
            # Auto-download bws into ~/.hermes/bin/ on first use; False = bws must be on PATH.
            "auto_install": True,
            # Passed to bws as BWS_SERVER_URL. Empty = US Cloud (bws default);
            # https://vault.bitwarden.eu for EU; your own URL for self-hosted.
            "server_url": "",
        },
        "onepassword": {
            "enabled": False,  # When false, the op CLI is never invoked.
            "env": {},  # env-var name → op://vault/item/field; each resolved with one `op read`.
            # Account shorthand / sign-in address for `op read --account`; empty = default.
            "account": "",
            # Env var holding a service-account token for headless auth (exported to op as
            # OP_SERVICE_ACCOUNT_TOKEN). Unset = interactive/desktop op session.
            "service_account_token_env": "OP_SERVICE_ACCOUNT_TOKEN",
            # Absolute path to op, used verbatim (avoids trusting PATH). Empty = PATH.
            "binary_path": "",
            # Seconds to cache values in-process and on disk; 0 disables BOTH layers.
            "cache_ttl_seconds": 300,
            # Overwrite existing env vars so rotation takes effect; False lets .env win.
            "override_existing": True,
        },
    },
    # Paste collapse thresholds (TUI + CLI); 0 disables each. threshold: bracketed pastes with this
    # many newlines collapse to a file reference. fallback: same test for terminals without
    # bracketed paste, gated by chars/newlines-added heuristics. char_threshold: single-line pastes
    # this long collapse too.
    "paste_collapse_threshold": 5,
    "paste_collapse_threshold_fallback": 5,
    "paste_collapse_char_threshold": 2000,

    # Bot Desktop: a headless Xfce screen per profile on the gateway host (Linux), streamed to Hermes
    # Desktop where a human can watch, take over (logins, 2FA, CAPTCHAs) and hand back. `hermes computer-use screen`.
    "bot_desktop": {
        "geometry": "1440x900",
        # Opt-in: start the screen automatically the first time computer_use needs a display on a headless
        # host. Off by default so installing TigerVNC for other reasons never yields a screen nobody asked
        # for; Hermes Desktop's Screen pane offers Start and this toggle.
        "auto_start": False,
        # Refuse to start below this much free memory (MB), measured on the host or its container cgroup,
        # whichever is tighter. Xvnc + Xfce idle at ~220 MB and a takeover's browser adds 0.5-1 GB, so a
        # screen with one page runs past 1 GB; the kernel OOM killer picks its victim by score, so on a
        # small instance the loser is the dashboard or the gateway rather than the desktop. 0 disables the
        # check.
        "min_free_memory_mb": 1536,
        # Stop a screen nobody has used (no computer_use action, browser spawn, viewer or takeover) for this
        # long; it restarts on the next use. Idle Xvnc + Xfce hold ~220 MB, an abandoned browser far more.
        # 0 keeps screens up until stopped.
        "idle_stop_minutes": 30,
        # Where the screen (and with it computer_use and the bot's browser) runs.
        #   auto      follow the terminal backend: inside the docker / ssh / streaming plugin sandbox when one is
        #             configured, on the gateway host when terminal.backend is local. A sandbox backend that
        #             cannot host a screen (modal, daytona, vercel) REFUSES rather than quietly running the
        #             desktop on the host beside the sandbox you chose for the agent.
        #   terminal  always inside the terminal backend (error when it cannot host one).
        #   gateway   always on the gateway host, even with a sandbox terminal: the agent's screen, browser
        #             and computer_use then act OUTSIDE the terminal sandbox. Explicit opt-in.
        # The sandbox image needs the desktop stack: nousresearch/hermes-sandbox:desktop.
        "placement": "auto",
    },
    "computer_use": {
        # cua-driver's upstream PostHog telemetry defaults ON; Hermes sets
        # CUA_DRIVER_RS_TELEMETRY_ENABLED=0 in every child env unless this is true.
        "cua_telemetry": False,
        # Windows only: opt IN to the per-boot cua-driver-serve logon task. False (default)
        # keeps the driver on-demand — Computer Use starts it per session, exactly as on
        # macOS/Linux, and install/enable flows register no scheduled task (#97389). True
        # registers (or repairs) the task at install time — needed to drive Windows over SSH,
        # where Session 0 has no interactive desktop (see the computer-use guide).
        "autostart": False,
        "native_wayland": False,
        # Cap driver screenshot longest edge (pixels) via set_config at session start; shrinks SOM
        # multimodal payloads. 0 disables.
        "max_image_dimension": 1456,
        # capture_after mode: som = screenshot + overlays; ax = elements only, no PNG (faster);
        # vision = pixels only.
        "capture_after_mode": "som",
        # Bound cua-driver's accessibility-tree WALK on every capture (get_window_state max_elements).
        # _DEFAULT_MAX_ELEMENTS in tools/computer_use/tool.py caps the SURFACED element list at 100 and
        # spills the rest to a cache file, so an unbounded walk pays for nodes the model never sees:
        # measured on macOS (cua-driver 0.28.2, M-series) a 1,444-node Chrome window went 540 ms -> 83 ms
        # and a 456-node Finder window 6.9 s -> 0.6 s at 200, with the returned elements a prefix of the
        # unbounded walk. 0 = driver default (2,000 elements / depth 25) — the pre-fix behaviour.
        # ~400 keeps the full first 100 visible elements on a pathological tree, at ~1.4 s on Finder;
        # the walk's cost grows with the bound, so keep it in the low hundreds. This caps the nodes
        # COLLECTED, not the walk's wall clock: a target whose AX surface exceeds the driver's own 20 s
        # walk timeout still fails at every bound (measured; a depth bound does not help there either).
        "ax_max_elements": 200,
        # Disable cua-driver's cursor overlay, which can peg a core when idle (macOS redraw loop;
        # Linux/WSL2 idle spin). None = auto (off on macOS + headless/ WSL2 Linux, on elsewhere);
        # True = always disable; False = always enable.
        # The overlay shows where agent actions land but can peg a core when idle (macOS vImage redraw loop
        # #47032; Linux/WSL2 idle spin #28152). cua-driver ≥ 0.6.x supports --no-overlay; Hermes also calls
        # set_agent_cursor_enabled(false) after start_session when this is on.
        "no_overlay": None,
        # standard = cua-driver's own approval boundary; bounded = no runtime prompts, anything
        # outside capability_manifest fails closed. `unrestricted` is NOT accepted here: it stays on
        # the per-session YOLO toggle so config can't bypass approvals.
        "permission_mode": "standard",
        # Path (~ ok) to the reviewed manifest for permission_mode bounded; passed as
        # --capability-manifest. See cua.ai/docs/reference/cua-driver/permission-modes
        "capability_manifest": "",
        # macOS only: allow an UNSIGNED CuaDriver.app for the private-session daemon. False fails
        # closed unless signed with the official com.trycua.driver identity. Only for local driver
        # development from source.
        "allow_unsigned_driver": False,
    },
    # Egress credential-injection proxy (iron-proxy) for remote terminal sandboxes (Docker today):
    # the sandbox sees opaque tokens and iron-proxy swaps in real credentials at egress, so a
    # compromised sandbox leaks only tokens that work behind the trusted proxy. Configure with
    # `hermes egress setup`.
    "proxy": {
        "enabled": False,  # When false, nothing starts, no docker mounts, no binary installs.
        # Tunnel listener port; sandboxes get HTTPS_PROXY=http://<host>:<port>.
        "tunnel_port": 9090,
        # Auto-download the pinned binary into ~/.hermes/bin/; False = iron-proxy on PATH.
        "auto_install": True,
        # Upstream secret source: env = process env; bitwarden = refetch via `bws secret list` on
        # each proxy restart (requires secrets.bitwarden.enabled).
        "credential_source": "env",
        # True: the Docker backend refuses to start a sandbox if the proxy is enabled but not
        # running. False: fall back to direct outbound with real credentials.
        "enforce_on_docker": True,
        # With credential_source bitwarden, a missing BWS token/project_id or an empty fetch makes
        # the daemon raise. True silently falls back to host env (useful mid-migration). A leftover
        # fail_on_uncovered_providers key is ignored.
        "allow_env_fallback": False,
        # SSRF deny list. None/empty = loopback, link-local (incl. 169.254.169.254 metadata),
        # RFC1918. Explicit [] opts out (only for hermetic loopback tests).
        "upstream_deny_cidrs": None,
        # Extra allowed upstream hosts beyond the bundled major-provider defaults; wildcards
        # (`*.foo.com`) supported.
        "extra_allowed_hosts": [],
    },
    "desktop": {  # Hermes Desktop (Electron) launch options; only affect `hermes desktop`.
        # CSS font-family for the app's chat and UI text (e.g. "OpenDyslexic"). Layered in front
        # of the active theme's own sans stack so missing glyphs still fall through. Empty = the
        # theme's face. The terminal pane is terminal.font_family.
        "font_family": "",
        # Git repo discovery for the Projects sidebar. Empty roots are a safe
        # no-op; users must explicitly configure roots for filesystem scanning.
        # Session-derived projects remain available.
        "repo_scan_enabled": True,
        "repo_scan_roots": [],
        "repo_scan_exclude_paths": [],
        # Extra Electron flags per launch, e.g. ["--ozone-platform=x11"] or GPU workarounds. List of
        # strings; a single string is shell-split.
        "electron_flags": [],
        # V8 old-space ceiling (MB) for the renderer, applied as --js-flags=--max-old-space-size=N by
        # the app itself (also for Start-menu / .desktop launches). 0 = Chromium's default limit.
        # A ceiling turns a machine-wide freeze into a bounded renderer reload (#77311).
        "renderer_max_old_space_mb": 0,
        # Linux Ozone backend, bridged to ELECTRON_OZONE_PLATFORM_HINT (explicit env wins). auto =
        # Chromium default; x11 = XWayland, for compositors that ignore always-on-top for Wayland
        # clients (e.g. COSMIC) — also puts the HUD on the solid-window input path; wayland = force
        # a native Wayland surface.
        # See #84011.
        "ozone_platform_hint": "auto",
        # Bridged to HERMES_DESKTOP_DISABLE_GPU: auto = disable GPU only on remote displays
        # (SSH/VNC/RDP); true = always software rendering (no-GPU VMs where the GPU path hangs);
        # false = always keep GPU on.
        "disable_gpu": "auto",
        # Linux keychain for token storage (Chromium --password-store). auto = detect KWallet (KDE
        # env) or any org.freedesktop.secrets provider via D-Bus;
        # gnome-libsecret|kwallet|kwallet5|kwallet6|basic force one (basic = unencrypted). Bridged
        # to HERMES_DESKTOP_PASSWORD_STORE; ignored off-Linux.
        "password_store": "auto",
        # Expose the renderer's accessibility tree to the OS (macOS/Windows) so dictation/IME tools
        # that insert text via the accessibility APIs can reach the composer (#118271, #92607).
        # False bridges to HERMES_DESKTOP_RENDERER_ACCESSIBILITY=0 and skips the tree (perf opt-out).
        "renderer_accessibility": True,
        # Linux: False preserves an existing custom XDG launcher entry; missing entries
        # are still created. True keeps the generated entry current on each launch.
        "manage_launcher_entry": True,
        # macOS only: code-signing identity (login-keychain cert; self-signed works) to re-sign
        # locally rebuilt apps so the Designated Requirement — and thus TCC grants — survives
        # updates. Empty = default ad-hoc identifier-pinned signing.
        "macos_signing_identity": "",
        # Windows only: explicit ssh client for SSH connections, the -G config probe and SSH
        # terminals, e.g. "C:\\Program Files\\Git\\usr\\bin\\ssh.exe" when the in-box OpenSSH is
        # missing or broken. Empty = System32 OpenSSH, then Git for Windows' ssh.exe, then PATH.
        # Read by the app before its first window; restart to apply. Ignored off-Windows.
        "ssh_path": "",
        # Auto-continue a turn killed by a crash: resuming re-submits the interrupted prompt if
        # fresh; a stale one just shows the recovered partial transcript.
        "auto_continue": {
            "enabled": True,
            # How recent the interruption must be to auto-continue (minutes).
            "freshness_minutes": 15,
            "max_attempts": 2,  # Crash-loop breaker: max automatic re-runs of one interrupted turn.
        },
    },

    "nous": {
        # Upper bound (seconds) on the Nous auth keepalive tick, which derives from the
        # server-issued credential lifetime (raising above it has no effect). 0 disables the
        # keepalive thread.
        "keepalive_interval_seconds": 900,
        # anthropic_wire: which Portal route carries anthropic/* models. "chat" =
        # /v1/chat/completions (default for now); "native" = /v1/messages, the Anthropic
        # Messages wire (signed thinking passthrough, native cache_control scopes); "auto" =
        # start on chat and, per session, switch to native from the first response when the
        # Portal upstream serving the model is one where native is known clean. Native is the
        # better wire but on the OpenRouter-served path it re-writes the previous turn's cache on
        # 14-20% of consecutive calls in concurrent tool loops (measured 2026-09-06;
        # NousResearch/api#227), so chat is the default until that is fixed.
        "anthropic_wire": "chat",
        # Nous free tier: with no other provider configured, Hermes sets up a free Nous identity on
        # first use (inference on nous/welcome + connectors) and offers `/login` (terminal:
        # `hermes auth upgrade`) to sign in. false turns the free tier off entirely: nothing is set
        # up and nothing is used.
        "guest": True,
    },
    # Google Vertex AI (Gemini). Auth is OAuth2 from a service-account JSON or ADC, NOT an API key;
    # the credential path lives in .env (VERTEX_CREDENTIALS_PATH / GOOGLE_APPLICATION_CREDENTIALS).
    # Bridged to VERTEX_PROJECT_ID / VERTEX_REGION.
    "vertex": {
        # GCP project ID. Empty → project_id from the service-account JSON (or ADC).
        "project_id": "",
        # "global" is required for Gemini 3.x preview models (regional endpoints silently 404); use
        # e.g. "us-central1" only if your models are region-pinned.
        "region": "global",
    },
    # Managed llama.cpp runtime (docs: user-guide/local-models): official binaries, one supervised
    # llama-server in router mode. No context/VRAM knobs by design.
    "local_runtime": {
        # Off = detection-only (Hermes still finds an external llama-server you run).
        "enabled": False,
        # Engine versions and every dependent library are pinned by pm/lock.json.
        # auto = CUDA on NVIDIA, Metal on macOS, Vulkan on other GPUs, else CPU. Explicit:
        # cuda|metal|vulkan|hip|cpu.
        "backend": "auto",
        "models_max": 4,  # Router process: how many models may be resident at once.
        "port": 0,  # Port for the managed server. 0 = pick a free port at spawn.
        # Extra ports detection probes for an external llama-server (besides 8080).
        "detect_ports": [],
    },
    "_config_version": 51,  # Config schema version - bump this when adding new required fields
}
