# Branding Carve-Out

## Intent

Hermes should identify itself at the boundaries of the product, not decorate every
functional surface. This plan removes repeated brand marks, wordmarks, taglines,
attributions, and watermarks from the places people actually work: the CLI, the
TUI, the web dashboard, the Desktop app, messaging defaults, installers, and
generated artifacts.

The problem is not that Hermes has a brand. It is repetition. A logo on an About
page is identity. The same glyph on every status line, response label, footer, and
message prefix is clutter. It consumes attention and screen space without carrying
information.

This is a design and sequencing document, not a progress tracker. Progress lives in
git history and the working conversation. The plan file changes only when the plan
itself changes.

## Decision

- Remove the Caduceus glyph (U+2624) from functional chrome. Keep it only in logo
  art and custom skin art.
- Keep one identity anchor per shell or screen.
- Clean only the default Hermes skin. Non-default built-in themes and custom skins
  keep their opt-in symbols and labels.
- Add no new configuration key. Clean is the default. Skins remain the escape hatch
  for users who want brand art or labels.
- Keep legal, provenance, and machine identity.
- Clean messaging defaults while keeping every per-platform prefix configurable.
- Replace the startup ASCII art and taglines with one compact identity line.
- Treat sluggishness as a separate track. Removing banner art may incidentally cut
  some render work, but it is not the performance fix.

This plan supersedes the earlier `display.show_brand_mark` opt-out idea.

## Why

- Repetition costs attention. The brand mark competes with the model name, status,
  and content the user is trying to read.
- The glyph has no functional role. It is decoration repeated as a line prefix.
- Brand strings are copied across Python, TypeScript, shell, locales, and generated
  artifacts. Each copy is maintenance and translation churn.
- Narrow terminals pay for the repetition twice: once in the extra column, once in
  the reduced room for actual status.
- A single anchor preserves orientation without the noise.

## Branding Rule

Keep:

- Window, tab, and OS application titles.
- One visible anchor per shell or screen: sidebar wordmark, About page, installer
  title, setup screen title, startup identity line.
- Package metadata, app IDs, installer names, API titles, MCP and ACP identities,
  and bot display names.
- Legal and provenance text: billing authorization, licenses, official plugin
  authorship, security contacts.
- System prompt identity.
- Custom skin art and labels.

Remove:

- Glyphs and wordmarks repeated in status lines, response labels, footers, headers,
  notices, and buttons.
- Taglines and slogans.
- "Nous Research" attributions appended to model, banner, or summary lines.
- ASCII logos and hero art from default startup.
- Watermarks in generated artifacts.
- Default reply prefixes.
- Secondary wordmarks on screens that already have an identity anchor.

## Surface Decisions

| Surface | Keep | Remove |
|---|---|---|
| CLI | `Hermes vX` startup line, `/version`, one-time setup and installer titles | Caduceus, ASCII logo, `- Nous Research`, glyphs in status, response, billing, notices, and box titles |
| TUI | One `Hermes Agent vX` session-panel line, custom skin art | Hardcoded banner art, caduceus hero, taglines, `· Nous Research`, glyph footer and working state, compact banner |
| Web dashboard | Sidebar wordmark, tab title, favicon, theme names | Sidebar `Nous Research` footer link and its i18n key |
| Desktop | OS app name, window and menu identity, About page, first-run identity | BrandMark on update and install overlays |
| Messaging | Platform bot name and avatar, per-platform prefix configuration | WhatsApp default reply prefix, glyphs in Telegram, Discord, and QQ update prompts |
| Installers and export | One installer title line, `Generated on <date>` | Glyph, "An open source AI agent by Nous Research" tagline, "Built with Hermes Agent" watermark |

Functional copy that mentions Hermes for context stays. Examples: "Hermes stopped
unexpectedly", "Connection to Hermes lost", "Update Hermes". Those sentences name
the system the user is operating. They are not decoration.

## Stages

Each stage is one atomic commit. Stop after each stage unless a full-run instruction
is explicitly given. Re-check `git status` before staging, and stage only the files
for the current stage.

### Stage 0: Plan File

This document is committed alone before Stage 1.

### Stage 1: Default Branding and CLI Transcript

- `hermes_cli/skin_engine.py`: clean only the default Hermes branding. Set
  `response_label` to an empty string, set `goodbye` to `Goodbye!`, and update the
  `get_active_goodbye` fallback. Keep the welcome and help text. Non-default
  built-in skins (Ares, Poseidon, Sisyphus, Charizard) keep their themed symbols
  and labels as opt-in. Custom skins keep their overrides.
- `hermes_cli/cli_modern_layout.py`: when the response label is empty, open the
  answer with the accent rule only. Do not print a brand row.
- `hermes_cli/cli_chat_turn_mixin.py`, `hermes_cli/cli_commands_mixin.py`, and
  `hermes_cli/cli_stream_mixin.py`: treat an empty label as "no title". The classic
  panel falls back to `Assistant`, not a brand label.
- `hermes_cli/cli_status_bar_mixin.py`: show the model name without a glyph or
  brand prefix.
- `hermes_cli/cli_tui_mixin.py`: replace the `☤` working indicator with a neutral
  busy marker.
- `hermes_cli/cli_billing_mixin.py`: remove the glyph from block headers and the
  subscription status line.
- Tests: `tests/hermes_cli/test_cli_modern_layout.py`,
  `tests/hermes_cli/test_cli_status_bar.py`,
  `tests/hermes_cli/test_cli_skin_integration.py`, and
  `tests/hermes_cli/test_skin_engine.py`.

### Stage 2: Startup Banners, CLI and TUI

- `hermes_cli/banner.py`: remove the hardcoded `HERMES_CADUCEUS` hero,
  `HERMES_AGENT_LOGO` wordmark, and the `· Nous Research` model suffix. Keep the
  panel title `Hermes Agent vX` and the functional model, cwd, session, tools, and
  skills information. Keep rendering a custom `banner_logo` or `banner_hero` when
  the active skin supplies one.
- `hermes_cli/cli_render.py`: reduce the compact banner to one identity line. Use
  `Hermes vX` for the default skin and the skin's agent name for a custom skin.
  Remove `☤ NOUS HERMES` and `- Nous Research`.
- `ui-tui/src/components/branding.tsx`: remove the hardcoded logo, caduceus hero,
  taglines, and `· Nous Research` suffix. Render a banner only when the active skin
  supplies `banner_logo` or `banner_hero`; otherwise render no banner.
- `ui-tui/src/components/appLayout.tsx`: drop the default `Banner` call. Keep the
  skin-only banner path and remove the `☤` footer marker.
- `ui-tui/src/components/appChrome.tsx`: remove `☤` from the emoji spinner frames.
- `ui-tui/src/theme.ts`: default the brand icon to empty and the goodbye text to
  `Goodbye!`.
- `ui-tui/src/i18n/en/chatBits.ts` and the 17 `locales/*.tui.yaml` catalogs:
  remove `chatBits.branding.tagFull` and `chatBits.branding.tagMid`. Regenerate
  `locales/_keys.tui.json` with `npm run i18n:keys` in `ui-tui/`.
- Tests: `tests/hermes_cli/test_banner.py`,
  `tests/hermes_cli/test_cli_skin_integration.py`, and the TUI unit and visual
  tests that assert banner content.

### Stage 3: Static Terminal Screens, Installers, Export

- Remove the glyph from `hermes_cli/setup.py`, `hermes_cli/setup_quick.py`,
  `hermes_cli/status.py`, `hermes_cli/config_show.py`,
  `hermes_cli/tools_config.py`, `hermes_cli/uninstall.py`,
  `hermes_cli/update_cmd.py`, `hermes_cli/gateway.py`,
  `hermes_cli/gateway_setup_wizard.py`,
  `hermes_cli/main_platform_setup.py`,
  `plugins/platforms/whatsapp_cloud/setup_wizard.py`,
  `hermes_cli/sandbox_image_switch.py`, `hermes_cli/main_tui_launch.py`, and
  `hermes_cli/prune_advisor.py`.
- Keep each screen's one title as its identity anchor. Do not add the product name
  to body copy that does not need it.
- `hermes_cli/session_export_html.py`: replace `Built with ☤ Hermes Agent` with
  `Generated on <date>` only.
- `setup-hermes.sh`, `scripts/install.sh`, and `scripts/install.ps1`: remove the
  glyph and the "An open source AI agent by Nous Research" tagline. Keep one
  installer title.
- Update stale comments in `hermes_cli/__init__.py` and
  `hermes_config/defaults_config_core.py`.
- Tests: update command, setup, installer, and session-export assertions.

### Stage 4: Web Dashboard and Desktop

- `web/src/components/SidebarFooter.tsx`: remove the `Nous Research` link. Keep the
  version.
- Remove the `footer.org` i18n block from the 17 `web/src/i18n/*.ts` files,
  `web/src/i18n/types.ts`, and any tests that assert it.
- Keep the sidebar wordmark, browser tab title, favicon, theme names, and
  functional copy that names Hermes for context.
- Desktop: remove `BrandMark` from `apps/desktop/src/app/updates-overlay.tsx` and
  `apps/desktop/src/components/desktop-install-overlay.tsx`. Keep it on the About
  page (`apps/desktop/src/components/update-status.tsx`) and first-run
  (`apps/desktop/src/components/remote-setup/first-run.tsx`). `VersionHero` is
  shared by About and the updates overlay, so parameterize it (for example
  `showBrandMark`) rather than removing the mark from About.
- Keep `apps/desktop/package.json`, `product-identity.ts`, app menu, About panel,
  and installer metadata unchanged.
- Tests: web sidebar and footer tests, desktop UI snapshots, and desktop typecheck.

### Stage 5: Messaging Defaults and Glyph Purge

- `gateway/platforms/whatsapp_common.py`: set `DEFAULT_REPLY_PREFIX` to an empty
  string.
- `scripts/whatsapp-bridge/bridge.js`: set `DEFAULT_REPLY_PREFIX` to an empty
  string.
- `hermes_config/defaults_config_core.py`: update the `reply_prefix` comment to
  describe an empty default and the opt-in header.
- `plugins/platforms/telegram/adapter.py`,
  `plugins/platforms/discord/adapter.py`, and
  `plugins/platforms/qqbot/adapter.py`: remove the glyph from update prompts.
- Remove `☤` from the 17 `locales/*.yaml` strings for update prompts, update
  titles, first-run notices, launch notices, and goodbye. Keep the text and the
  product name where it is the one-time identity anchor.
- `hermes_cli/main_platform_setup.py`: update the WhatsApp tip. The default response
  is no longer prefixed, and `reply_prefix` is the opt-in.
- Remove the remaining `☤` from core product strings in the 17
  `web/src/i18n/*.ts` files. Do not edit `share.tweet_text`, which is the
  achievements share text, and do not edit the vendored achievements bundle.
  Coordinate that copy with its upstream plugin.
- Tests: WhatsApp prefix defaults, platform prompt formatting, locale coverage, and
  web i18n key coverage.

### Stage 6: Docs and Regression Guard

- Sync `website/docs/user-guide/cli.md`, `website/docs/user-guide/tui.md`,
  `website/docs/user-guide/features/skins.md`,
  `website/docs/reference/cli-symbols.md`, and
  `website/docs/user-guide/messaging/whatsapp.md`.
- Final glyph sweep: run `rg -n '☤'` from the repo root. Allowed remaining
  locations are README and docs logo art, the vendored achievements bundle,
  `share.tweet_text`, tests that use it as a Unicode sample, and skill docs. Every
  other occurrence is a defect.
- Add behaviour tests that prove the default chrome is clean:
  - Default CLI startup output contains no `☤`, no `Nous Research`, and no tagline.
  - Default TUI banner and session panel contain no `☤`, no `Nous Research`, and no
    tagline, and keep one identity line.
  - Default WhatsApp reply prefix is empty.
  - A custom skin with `response_label` and `banner_logo` still renders them. This
    proves the carve-out did not remove customization.
- Run:
  - `python scripts/check`
  - `scripts/run_tests.sh` on the touched Python tests
  - `bun run check` in `web/`
  - `npm run check` in `ui-tui/`
  - `npm run typecheck` and `npm run test:ui` in `apps/desktop/`
- Manual smoke matrix: `hermes`, `hermes setup`, `hermes status`, the TUI, the web
  dashboard, the Desktop app, and one WhatsApp reply.

## Exclusions

- README, docs logo art, favicon, app icons, package metadata, and installer names.
- Billing, consent, legal, and provenance text.
- MCP, API, ACP, and OAuth client identities.
- `hermes_cli/default_soul.py` and system-prompt identity. Changing those risks
  behavior and prompt caching.
- Theme names such as "Hermes Teal" and "Nous Blue".
- Custom skins. They can still restore art and labels.
- The vendored achievements bundle. Its share text belongs to the upstream plugin.
- Performance work.

## Risks and Mitigations

- **Skins lose default art.** Keep custom `banner_logo` and `banner_hero` rendering.
  Remove only the hardcoded fallback.
- **i18n key drift.** Regenerate `locales/_keys.tui.json`, update `web/src/i18n/types.ts`,
  and run the existing key checks.
- **Tests assert old strings.** Update them to the new behavior contract. Do not add
  source-reading or change-detector tests.
- **Messaging prefix surprise.** Document the empty default and keep the per-platform
  `reply_prefix` configuration.
- **Narrow terminal alignment.** Verify box and status widths after removing leading
  glyphs.

## Performance Note

Sluggishness is a separate plan. The useful next step is measurement: cold start,
TUI ready time, dashboard first paint, and gateway message latency. Branding cleanup
should not be presented as a performance fix even if it removes some render work.

## Success Criteria

- Default functional chrome contains no `☤` glyph.
- Default functional chrome contains no "Nous Research" attribution and no taglines.
- Each shell or screen has at most one identity anchor.
- Custom skins can still render their own art and labels.
- No new configuration key is introduced.
- Lint, typecheck, and the targeted Python, web, TUI, and Desktop tests pass.
