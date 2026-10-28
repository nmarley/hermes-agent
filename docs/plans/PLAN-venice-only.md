# Venice-Only Inference Provider

## Goal

Make Venice AI the only built-in inference provider in Hermes. Keep custom and local
OpenAI-compatible endpoints as an escape hatch. Keep MoA, model fallback, multi-key rotation,
and every non-inference capability provider (TTS, STT, image, video, web search, browser,
memory). Remove every named vendor integration, its auth flow, catalog data, picker surface,
tests, and docs.

This is a hard fork. Upstream merge compatibility is not a goal.

## Decisions

- Scope is inference providers only. Capability-provider registries stay untouched.
- Keep `custom` and `lmstudio` profiles, plus local aliases such as Ollama, vLLM, and llama.cpp.
- Custom and local endpoints use the OpenAI chat-completions wire only. The Anthropic
  Messages, Codex Responses, and Bedrock Converse transports are removed.
- Keep MoA, fallback, and the credential pool, restricted to Venice and custom/local routes.
- Add Venice account billing to `/usage` using the Venice billing API.
- Remove non-Venice OAuth, device-code, external-process, AWS SDK, Entra, Vertex, and Copilot
  auth, plus the Nous portal, free tier, credits, keepalive, and vendor account-usage fetchers.
- Keep Venice-related marketplace entries (`web-venice`, `gondola-provider`, `quotum`).
  Remove the other model-category plugin-catalog entries.
- Old configs that name a removed provider fail with a clear migration message instead of
  silently switching models or cost.

## Venice Facts

- Base URL: `https://api.venice.ai/api/v1`
- Credentials: `VENICE_API_KEY`, optional `VENICE_BASE_URL`
- Auth type: API key only. No OAuth, no external process, no cloud SDK.
- `GET /models` is public and returns 142 text models with context length, max output,
  USD pricing, cache pricing, tool calling, vision, structured output, reasoning support,
  reasoning-effort options, and model traits.
- Chat is OpenAI-compatible: streaming, tool calling, parallel calls, structured output,
  vision, audio/video input on capable models, and `reasoning_effort`.
- Prompt caching is automatic. Do not send `prompt_cache_key`.
- Billing endpoints exist under `/billing/balance`, `/billing/usage-history`, and
  `/billing/usage-analytics`. They are beta, so billing failures must fail open.
- The live catalog is the primary metadata source. models.dev remains a fallback for custom
  routes.

## Venice Model Defaults

Use live catalog traits where possible, with these modern explicit defaults.

| Purpose | Model ID |
| --- | --- |
| Default agent model | `deepseek-v4-1-flash-1017` |
| Flagship reasoning/coding | `z-ai-glm-5-3` |
| Cheap auxiliary, vision, and high-throughput | `z-ai-glm-5-3-flash` |
| Catalog code trait | `deepseek-v4-pro-0813` |
| Catalog reasoning trait | `kimi-k3` |
| Catalog vision trait | `qwen-3-8-27b` |
| Uncensored text | `abliteration-abliterated-model-large-v2` |
| Uncensored multimodal | `abliteration-abliterated-model-large-flash` |
| Uncensored DeepSeek | `deepseek-v4-1-flash-1017-uncensored` |

`z-ai-glm-5-3` is the 1M-context GLM 5.3 flagship. `z-ai-glm-5-3-flash` is the cheap
1M-context multimodal variant and is the preferred auxiliary model.

## Target Architecture

- One bundled `venice` model-provider plugin.
- Existing `custom` and `lmstudio` profiles remain.
- The `moa` virtual provider remains, restricted to Venice and custom/local models.
- One Venice row in the provider registry, canonical catalog, overlays, and environment map.
- One Venice transport path: `chat_completions`.
- One account-usage fetcher for Venice billing.
- Provider pickers collapse to Venice, custom, local, and MoA.
- Capability registries and their plugins are unchanged.

## Stages

### Stage 0: Add Venice First-Class

Add Venice without deleting any existing provider. The app must remain fully functional for
all current providers after this stage.

0a. Create `plugins/model-providers/venice/` with a Venice profile:
`name="venice"`, aliases `venice-ai` and `veniceai`, display name `Venice AI`, API-key auth,
base URL `https://api.venice.ai/api/v1`, `VENICE_API_KEY` and `VENICE_BASE_URL`, streaming
enabled, prompt-cache-key disabled, and the model defaults above.

0b. Implement a cached Venice catalog reader that exposes model traits, context, max output,
pricing, tool calling, vision, structured output, and reasoning-effort options. Use it for
`fallback_models`, auxiliary-model resolution, vision defaults, and reasoning capability
reporting.

0c. Add the Venice row to the auth registry, canonical catalog, overlays, aliases, models.dev
mapping, and URL-to-provider map. Let the profile plugin auto-register env metadata where the
existing mechanisms already do so.

0d. Extend the generic `/models` metadata parser for the Venice shape:
`model_spec.maxCompletionTokens`, `model_spec.pricing.input.usd`,
`model_spec.pricing.output.usd`, `model_spec.pricing.cache_input.usd`, and
`model_spec.pricing.cache_write.usd`. Keep the parser generic, not host-specific.

0e. Add a Venice billing fetcher to `agent/account_usage.py` using `/billing/balance` and
`/billing/usage-analytics`. Map it to `AccountUsageSnapshot`. If billing is unavailable,
fall back to token and cost tracking from chat responses.

0f. Add tests for profile registration, registry and catalog rows, env metadata, catalog
parsing, pricing, billing fixtures, and a live Venice chat with streaming, tools, vision,
and `/usage`.

Verification: `hermes model`, `hermes auth add venice`, `hermes doctor`, a tool-using chat,
a vision request, `/model venice:deepseek-v4-1-flash-1017`, and `/usage`.

### Stage 1: Cut Registry and Catalog Data

Delete every bundled model-provider plugin except `venice`, `custom`, and `lmstudio`. This
removes 39 provider directories and their profiles.

Replace the static catalog with Venice, custom, local, and MoA rows. Delete provider groups,
vendor aliases, overlays, curated model lists, silent-default sets, aggregator sets, retired
aliases, model-specific catalogs, and the provider-specific catalog fetchers.

Keep the registry and discovery mechanisms. Keep plugin admission and per-home layers.

Update picker and catalog tests. The app must boot with only the intended provider rows.

Verification: `hermes model` lists Venice, custom, local, and MoA. `/model` resolves Venice
and local routes. No named vendor is registered.

### Stage 2: Remove Auth and Portal Integrations

Delete non-Venice auth modules and their dispatch:
OAuth device and external flows, Codex, Copilot, xAI, MiniMax, Qwen, Z.AI/Kimi, Nous,
OpenRouter key handling, Vertex, Bedrock, Azure, Vercel, plugin OAuth, anon auth, guest
handoff, Nous account, billing, subscription, and keepalive.

Trim `hermes auth`, `hermes setup`, `hermes status`, `hermes doctor`, `hermes login`,
`hermes logout`, `hermes portal`, `codex-runtime`, and gateway provider proxying to Venice
and custom/local. Keep the API-key credential pool and its rotation, cooldown, and manual-key
paths. Remove OAuth seeders, refreshers, and grant persistence.

Verification: `hermes auth add venice`, `hermes auth status venice`, `hermes auth remove
venice`, `hermes setup`, `hermes status`, and `hermes doctor`.

### Stage 3: Prune Runtime and Transports

Move shared helpers out of vendor modules before deleting anything:
- Prompt-cache helpers currently imported by `chat_completions.py` from the Codex transport.
- The message-summary helper currently in the Codex adapter.
- Any generic reasoning or sanitization helper used outside its vendor module.

Delete the Anthropic Messages, Codex Responses, and Bedrock Converse transports and their
adapters, app-server modules, response converters, runtime history seed, service tiers,
compaction paths, and vendor credential resolvers. Keep the chat-completions transport,
normalized response types, router timeout shim, and generic sanitizers.

Collapse API-mode selection to `chat_completions` for Venice and custom/local. Remove vendor
branches from `agent_init`, the turn loop, client lifecycle, auxiliary client, model metadata,
pricing, error classification, reasoning, prompt caching, image routing, and conversation
compaction.

Replace vendor account-usage fetchers with Venice. Delete Nous billing, credits, plan-limit,
rate-guard, subscription, and usage-gauge modules. Keep generic token and cost tracking.

Keep capability-provider code untouched.

Verification: main turn, streaming, tool calls, vision, fallback, MoA, custom endpoint, local
endpoint, `/usage`, and error handling.

### Stage 4: Collapse User Surfaces

CLI: collapse provider setup, model switching, status, doctor, and inventory to Venice,
custom, local, and MoA. Remove vendor setup flows, OAuth account menus, Nous onboarding, and
vendor-specific default models.

TUI and gateway: collapse provider rows and remove OAuth login/status branches. Keep the
model picker, MoA, and fallback selection for Venice and custom/local routes.

Web dashboard: keep API keys, custom endpoints, and local models. Remove the OAuth accounts
catalog, OAuth cards and modal, vendor onboarding, and vendor-specific status cards. One
Venice API-key card remains.

Desktop: keep the API keys, custom endpoints, and local models panes. Remove the accounts tab,
OAuth picker, vendor quick-start rows, Nous billing, and vendor display-name tables. The
Venice key card is the primary onboarding path.

Verification: CLI, TUI, web, desktop, and gateway can configure Venice, custom, and local
providers. MoA and fallback accept Venice and custom/local models.

### Stage 5: Replace Tests

Delete vendor-specific unit, integration, E2E, and fixture suites. Rewrite provider-universe
and parity tests to assert exactly Venice, custom, local, and MoA are registered. Keep generic
picker, registry, discovery, transport, and credential-pool tests.

Add Venice behavior tests for profile registration, auth, catalog parsing, pricing, billing,
chat, streaming, tools, vision, reasoning effort, fallback, MoA, and custom/local routes.
Keep a loopback fake provider for transport tests.

Verification: `scripts/run_tests.sh` passes with no vendor-specific skips.

### Stage 6: Docs and Packaging

Rewrite the provider documentation to Venice plus custom/local. Remove vendor provider guides
and translations, or rewrite them as Venice-specific pages. Update README files, CLI
reference, environment-variable reference, model catalog, fallback, routing, and developer
provider-plugin docs.

Delete non-Venice model-category plugin-catalog entries. Keep `web-venice`,
`gondola-provider`, and `quotum`. Rewrite `scripts/build_model_catalog.py` and regenerate
`website/static/api/model-catalog.json` for Venice.

Remove provider extras and dependencies for Anthropic, Bedrock, Vertex, and Azure Entra.
Keep the OpenAI SDK and generic HTTP dependencies. Run `hermes pm lock` and commit `uv.lock`.

Rewrite or delete the live-provider CI workflow for Venice. Update `.env.example`,
`cli-config.yaml.example`, and any provider parity checks.

Verification: `python scripts/check` and the docs build.

### Stage 7: Migration and Cleanup

Add a config-load migration that rejects removed provider names with a clear instruction to
run `hermes model`. Ignore or remove stale OAuth rows in `auth.json`. Do not silently remap
models or costs.

Delete remaining dead modules, imports, constants, and config keys. Run the full lint,
typecheck, code-health, and test suites. Verify a fresh install and an upgraded config.

Verification: fresh `hermes setup`, upgraded config with an old provider name, full test
suite, and a live Venice smoke test.

## Invariants

- The app remains runnable after every stage.
- Shared helpers move before their modules are deleted.
- No stage mixes code changes with plan or documentation-status edits.
- No vendor name remains in the provider registry, catalog, pickers, or setup flows.
- Capability providers keep working unchanged.
- Venice billing failures fail open and never block chat.

## Risks

- `chat_completions.py` imports Codex prompt-cache helpers on every request. Move them first.
- `_summarize_user_message_for_log` is generic but lives in the Codex adapter.
- Several vendor modules are imported at module scope. Deleting them before updating importers
  breaks startup.
- `hermes_cli/auth.py` and `hermes_cli/models.py` are already over the 2,000-line cap. Put new
  Venice code in the plugin or a new sibling, and shrink these files through deletion.
- Desktop is the largest UI surface.
- Existing `auth.json` rows and configs can name removed providers. Migration must be explicit.
- Keeping custom/local preserves an escape hatch to non-Venice endpoints. That is intentional.
