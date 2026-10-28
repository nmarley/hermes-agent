# Remove Native Windows Support

## Intent

Delete every line of Windows support from Hermes: the win32 runtime, the native
installer, the Windows desktop packages, the Microsoft Store pipeline, the WSL
host glue, the CI lanes, and the test scaffolding that exists only to exercise
them.

The goal is not a smaller support matrix alone. It is a smaller, more honest
core. Windows branches are load-bearing abstractions: they forced a platform
hook protocol, dual-format path handling, a second PTY implementation, a second
process-kill model, a second file-locking model, and a second package-manager
target set. Removing only the Windows arm would leave one-armed abstractions
behind. This plan removes the arms and then collapses the seams.

This is a design and sequencing document, not a progress tracker. Progress lives
in git history and the working conversation. The plan file changes only when the
plan itself changes.

## Decision

- **Native Windows is removed entirely.** No win32 process, no MSIX, no
  Microsoft Store, no `install.ps1`.
- **WSL2 is not a runtime.** It is a Linux VM running the existing Linux path.
  Hermes has no WSL2 runtime to keep. The WSL-specific code is Windows-host glue
  (drive-letter path translation, WSLg display launch, clipboard bridging) and it
  goes with Windows.
- **WSL2 users are served by the Linux documentation.** One paragraph in the
  Linux install guide is enough. No separate guide, no separate code path.
- **macOS and Linux stay.** Their differences (launchd vs systemd, Keychain vs
  libsecret, APFS vs ext4) remain real and in scope.
- **The platform seam is collapsed, not merely emptied.** A win32 branch deleted
  from a shared function is step one; deleting the function's Windows-shaped
  parameter and the test that exists only for it is step two. Both are in scope.

## Why

Windows is currently Tier 1 in `website/docs/getting-started/platform-support.md`.
That tier is backed by real infrastructure, not a compatibility shim:

- 10 Windows-named production Python modules, 6,107 lines.
- 7,353 production PowerShell lines, 10,724 including tests.
- 4,222 production TypeScript/JavaScript lines for Windows, MSIX, and WSL host
  glue, plus 5,098 test lines.
- 125 Windows-named test files, 22,977 lines.
- 476 `platforms(...)` markers across 155 test files.
- 246 `windows-footgun: ok` suppressions.
- 508 production files containing Windows-specific branches, about 1,826
  branch lines.
- 34 `win32` dependency markers in `pyproject.toml`.
- 9 package-manager targets, 2 of them Windows.
- 5 dedicated Windows CI workflows, plus Windows matrices inside
  `tests-os.yml`, `stable-release.yml`, and `desktop-bundled-release.yml`.
- Two release lanes (`windows`, `windows-store`), plus `windows-live`,
  `transitions-win32`, and `windows-packaged`.
- 54 plugin-catalog entries that advertise Windows.

The area is also hot, not dormant: 4,405 commits mention Windows, 2,038 touch
Windows-named files, and the last 12 months added 64,221 lines and deleted
26,644 lines in those files. This is not stale code that can be left to rot. It
is active surface that will keep demanding review, CI time, release engineering,
and test maintenance until it is deleted.

## Baseline at plan creation

- Repository head: `2e1868b574` (`Point dashboard display font vars at theme sans`).
- Total tracked lines: 364,892.
- Windows-named production Python: 10 files, 6,107 lines, including the
  970-line `scripts/check-windows-footguns.py`.
- Production PowerShell: 7,353 lines across installers, update scripts, and
  build scripts.
- Windows, MSIX, and WSL TypeScript/JavaScript: 4,222 production lines and
  5,098 test lines.
- Windows test files: 125 files, 22,977 lines, plus the two Windows-only test
  directories `tests/e2e/core/windows` (1,174 lines) and
  `tests/e2e/core/windows_update` (4,154 lines).
- Shared production files with Windows branches: 508 files, about 1,826 lines.
- Dependency markers: 34 `win32` markers in `pyproject.toml`, including
  `pywin32`, `pywinpty`, four `winrt-*` packages, `concurrent-log-handler`, a
  `tzdata` marker, and a `ruamel.yaml.clib` marker.

The exact counts will move. The baseline exists to size the work and to measure
the reduction at the end, not to gate stages on line counts.

## Goal

1. A core that runs on macOS and Linux only, with one explicit refusal at boot
   for every other host.
2. A platform layer that no longer models Windows: no `windows` parameters, no
   `_IS_WINDOWS` branches, no Windows target set, no PATHEXT or drive-letter
   handling.
3. One install and update story for each supported platform, with no PowerShell
   in the core tree.
4. Desktop builds for macOS and Linux only, with no MSIX, Store, signing, or
   Windows updater code.
5. CI that exercises exactly the supported platforms and no others.
6. A test suite that proves behavior contracts on macOS and Linux, with no
   Windows-only skips, fakes, or marked lanes.
7. A measurable reduction: roughly 20,000 lines of Windows-specific production
   and test code removed, before counting the shared-branch collapse.

## Non-goals

- No rewrite of the Linux or macOS paths beyond what the Windows removal
  exposes.
- No change to the prompt-caching invariant, message-flow invariants, profile
  isolation, or the narrow-waist tool policy.
- No new platform abstraction to replace the Windows one. The replacement is
  fewer abstractions, not a generalized one.
- No support for Cygwin, MSYS2, or Git Bash as a host. Git Bash is only a tool
  users may run inside the Linux shell; it is not a Hermes host.
- No new Linux or macOS features. This plan removes and simplifies.
- No change to Docker, Nix, or Termux support.
- No deletion of user data or migration of existing Windows installs. The final
  Windows release is the migration path.

## Principles

- One-way door, cut deliberately. Ship a final Windows release and pin its tag
  before the first deletion lands.
- Delete first, collapse second. Deletion exposes the real shape; collapse is a
  design change and needs its own review.
- Keep the tree green on macOS and Linux after every stage.
- No compatibility shims for removed platforms. No `if sys.platform == "win32"`
  that returns a helpful error deep in a helper. One refusal, at the entry point.
- Prefer deleting a parameter to defaulting it. `venv_bin_dir(windows=False)` is
  not an improvement over the Windows branch.
- Tests follow behavior. A test that exists only because Windows exists is
  deleted with the behavior, not rewritten to assert the absence.
- Data cleanup is part of the work. Platform lists in plugin metadata, catalogs,
  and translations are code-adjacent and must be swept in the same series.

## Target state

Supported hosts:

- macOS on arm64, Tier 1.
- Linux on x86_64 and aarch64, glibc, Tier 1.
- Docker containers, Tier 1.
- WSL2 documented as a Linux VM, no special code.
- Nix and Termux unchanged.

Removed hosts:

- Native Windows, including Windows 10, Windows 11, x64 and arm64.
- Microsoft Store and MSIX distribution.
- Windows-hosted WSLg desktop launch.

Package-manager targets after removal:

- `linux-x64`, `linux-arm64`, `linux-x64-musl`, `linux-arm64-musl`,
  `linux-arm64-bionic`, `darwin-x64`, `darwin-arm64`.
- 7 targets instead of 9.

Desktop builds after removal:

- macOS arm64.
- Linux (local and bundle checks; release publication stays as it is today).

The only allowed win32 reference in the core is the boot refusal. It lives in
`hermes_bootstrap.py` and in the standalone `pm` bootstrap path, prints a clear
message pointing at the final Windows release, and exits non-zero.

## Stages

### Stage 1: Freeze and gate

Cut the final Windows release while the lanes still exist. Pin the tag and keep
the artifacts. Then close the door.

- 1a: Cut a stable release that includes the Windows desktop MSIX (x64, arm64,
  universal bundle) and the Microsoft Store bundle. Tag it as the final Windows
  release. Keep the release artifacts and the branch that produced them.
- 1b: Add the host refusal. It must run before imports that assume a POSIX host:
  in `hermes_bootstrap.py`, in `hermes_cli/main.py` before dispatch, and in the
  standalone `pm` entry point. The message names the final Windows release and
  the Linux install path. A test passes `"win32"` as data to the refusal helper,
  so it runs on macOS and Linux without faking the host.
- 1c: Turn off Windows CI and release jobs in the same commit series, because
  the refusal makes them fail by design:
  - remove the Windows matrices from `.github/workflows/tests-os.yml`;
  - remove the Windows jobs and lane inputs from
    `.github/workflows/stable-release.yml`,
    `.github/workflows/desktop-bundled-release.yml`, and
    `.github/workflows/desktop-bundle-smoke.yml`;
  - remove Windows steps from `.github/workflows/ci.yaml` and
    `.github/workflows/tests.yml`;
  - delete the five dedicated workflows and the Windows build-deps action;
  - remove `scripts/check-windows-footguns.py` from `scripts/check`, since it
    will immediately fail on the first deletion.
- 1d: Add a temporary CI guard that fails if a new Windows-named module or a new
  `win32` dependency marker appears. This guard is deleted in Stage 9 when the
  final grep gate replaces it.

Exit gate: the final Windows release is published and tagged; no CI job runs on
Windows; macOS and Linux suites are green; the refusal test passes.

### Stage 2: Documentation and support policy

Make the written contract match the decision before the code does.

- 2a: Move Windows out of Tier 1 in
  `website/docs/getting-started/platform-support.md`. State the final release
  and the Linux VM path. Remove Windows from the installation matrix.
- 2b: Delete `website/docs/user-guide/windows-native.md` and its
  `website/i18n/zh-Hans` copy. Delete
  `website/docs/user-guide/windows-wsl-quickstart.md` and its translation.
  Replace both with one short paragraph in
  `website/docs/getting-started/installation.md` that says any Linux host or VM
  works, WSL2 included, using the Linux one-liner.
- 2c: Sweep install and product docs: `index.mdx`, `quickstart.md`,
  `updating.md`, `faq.md`, `user-guide/desktop.md`, `user-guide/docker.md`,
  `reference/package-management.md`, `developer-guide/stable-releases.md`,
  `developer-guide/shared-bundle-builds.md`,
  `developer-guide/plugins/application-declarations.md`, and
  `developer-guide/contributing.md`.
- 2d: Remove Windows guidance from `CONTRIBUTING.md` and
  `CONTRIBUTING.es.md`, including the 150-line Windows footgun section, the
  `platforms("windows")` examples, the PowerShell instructions, and the
  `install.ps1` tree entry.
- 2e: Update `README.md` and the three translated READMEs. Remove the native
  Windows one-liner, the `%LOCALAPPDATA%` paths, the Defender guidance, the
  `uv.exe` note, and the "native Windows is fully supported" statement.
- 2f: Remove Windows references from `AGENTS.md`, area `AGENTS.md` files, the
  `hermes-agent` skill references, and
  `skills/autonomous-ai-agents/hermes-agent/references/windows-quirks.md`.
- 2g: Sweep `locales/` for install and platform strings that advertise Windows.

Exit gate: the docs site builds; no supported install path advertises native
Windows; the only Windows mention is the final-release note.

### Stage 3: Runtime core removal

Delete the Windows implementations before touching the seams that used them.

- 3a: Delete `hermes_cli/gateway_windows.py` (1,891 lines),
  `hermes_cli/gateway_windows_legacy.py`, and
  `gateway/runtime_bootstrap_windows.py` (538). Remove the named-pipe transport
  from `gateway/control_socket.py`, the Scheduled Task path from
  `hermes_cli/gateway.py`, and the Windows service manager branches.
- 3b: Delete `hermes_cli/win_pty_bridge.py` and the `pywinpty` path from
  `hermes_cli/pty_bridge.py`, `hermes_cli/web_server_pty.py`, and the TUI
  terminal startup. Keep `ptyprocess` only.
- 3c: Delete `hermes_cli/update_cmd_windows.py` (1,692 lines),
  `hermes_cli/windows_store_update.py`,
  `hermes_cli/windows_appinstaller_update.py`, and
  `hermes_cli/update_windows_acl.py`. Collapse the Windows arms in
  `hermes_cli/update_cmd.py`, `update_lock.py`, `update_custody.py`,
  `update_abort_recovery.py`, `update_restart_recovery.py`, and
  `_early_recovery.py`.
- 3d: Delete `hermes_cli/windows_ssh_runtime.py` (484 lines). Keep the macOS
  and Linux SSH runtimes. Remove the Windows SSH binary discovery from
  `apps/desktop/electron/ssh-binary.ts` in Stage 7.
- 3e: Remove the process model: taskkill and start-time identity in
  `gateway/status.py`, `tools/process_registry.py`,
  `tools/environments/fd_wait.py`, and `hermes_cli/process_identity.py`; the
  `CREATE_NO_WINDOW` flags and `.cmd` shim handling in
  `hermes_cli/_subprocess_compat.py`; the detached `pythonw.exe` path in
  `cron/scheduler.py` and `cron/scheduler_script.py`; the job-object teardown in
  `hermes_cli/gateway_windows.py`.
- 3f: Remove the filesystem model: ACLs in `hermes_platform/fs.py` and
  `hermes_cli/uninstall.py`, junctions in `pm/filesystem.py`, long-path
  conversion in `scripts/install.ps1` callers and `pm/filesystem.py`, drive
  roots and UNC handling in `hermes_platform/constants.py`, and the WSL path
  translators `windows_path_to_wsl` and `wsl_unc_path_to_posix`.
- 3g: Remove the console model: the UTF-8 bootstrap and VT enablement in
  `hermes_bootstrap.py`, the `platform._syscmd_ver` patch, and the Windows
  encoding fallbacks in `hermes_platform/logging.py`.
- 3h: Remove the Windows capture and permission backends from
  `tools/computer_use/`, including `cua_backend_capture.py` branches, the
  Windows permission checks, and the `get-windows` native dependency.
- 3i: Remove Windows LSP resolution: `.cmd` and `.exe` probing, the PowerShell
  language server, and the Windows binary resolution tests.
- 3j: Remove Windows branches from the TUI and gateway transports:
  `ui-tui/src/lib/clipboard.ts`, `terminalSetup.ts`, `editor.ts`,
  `openExternalUrl.ts`, and `tui_gateway/transport.py`.

Exit gate: no core module imports a Windows-named module; `rg` finds no
`pywin32`, `pywinpty`, `winrt`, `msvcrt`, `winreg`, `icacls`, `taskkill`, or
`pythonw` outside the boot refusal; macOS and Linux suites are green.

### Stage 4: Platform seam collapse

This is the elegance pass. Every abstraction that existed only because Windows
existed is collapsed to its POSIX form.

- 4a: Collapse `hermes_platform/hooks.py`. Remove `windows_hide_flags` and the
  `windows` parameters on `venv_bin_dir` and `venv_python`. Keep the hook
  provider only if it is still needed to break the `hermes_platform` to
  `hermes_state` import cycle; otherwise remove the indirection entirely.
- 4b: Collapse `hermes_platform/constants.py`. Remove the 20-plus `win32`
  branches, PATHEXT lookup, `.exe` probing, `%VAR%` expansion differences, and
  the two WSL translators. Keep one `darwin` plus `linux` decision where the
  behavior genuinely differs.
- 4c: Collapse `hermes_platform/host/facts.py`. Remove `winreg`, WOW64
  detection, `windows_native_arch`, and the Windows CPU and GPU probes. Keep
  sysctl, procfs, sysfs, and IOKit.
- 4d: Collapse `hermes_platform/resolver/`. Remove `%VAR%` expansion, uninstall
  registry lookups, `pe_resource` version reads, and the Windows app
  definitions. Keep plist and desktop-file resolution.
- 4e: Collapse `tools/environments/local.py`. Remove MSYS path conversion, Git
  Bash discovery, `hermes.exe` shim handling, and the Windows shell selection.
  The result is one POSIX shell model. Keep the environment scrubber and the
  UTF-8 defaults only where they still protect Linux or macOS.
- 4f: Collapse the locking and logging models in `hermes_platform/logging.py`,
  `hermes_store/locks.py`, `hermes_store/lockguard.py`, and
  `hermes_cli/update_lock.py`. Replace `concurrent-log-handler` with the POSIX
  path and remove the Windows lock-timeout retry.
- 4g: Collapse the build target model in `scripts/build/inputs.py`,
  `scripts/build/launchers.py`, `scripts/build/agent.py`, and
  `scripts/build/mint_launchers.py`. Delete `mint_launchers.py` if it exists
  only to mint `.exe` wrappers.
- 4h: Collapse the test platform gate in `tests/_fixtures/platform_gating.py`,
  `scripts/ci/list_os_marked_tests.py`, and
  `scripts/ci/check_os_marker_fakes.py`. Keep `macos`, `linux`, and `posix`;
  remove `windows`.

Exit gate: `rg` finds no `_IS_WINDOWS`, no `windows_hide_flags`, no
`windows=` parameter, and no `platform.system() == "Windows"` outside the boot
refusal. The platform layer reads as a two-platform layer, not a
three-platform layer with one arm deleted.

### Stage 5: Package manager and dependency graph

Remove the Windows target set and let the lockfiles regenerate.

- 5a: Remove `win32-x64` and `win32-arm64` from `pm/store.py`
  (`ALL_TARGETS`, `current_target`, architecture detection), `pm/packages.py`
  (`_RUST_TRIPLE`, `_NODE_PLAT`, per-package release tables),
  `pm/registry.py`, `pm/extras.py`, `pm/install.py`, `pm/environment.py`,
  `pm/environments.py`, `pm/index_config.py`, `pm/native_build.py`,
  `pm/security_packages.py`, `pm/shell.py`, `pm/update.py`, and
  `pm/user_facing.py`.
- 5b: Remove the Windows store root, junction handling, long-path shim, and
  zip-symlink handling from `pm/filesystem.py` and `pm/store.py`.
- 5c: Remove the Windows-only package legs: VC runtime, Windows node sidecar,
  Windows ripgrep runtime, and the Windows ABI checks.
- 5d: Remove `pywin32`, `pywinpty`, `winrt-windows-applicationmodel`,
  `winrt-windows-foundation`, `winrt-windows-foundation-collections`,
  `winrt-windows-services-store`, `concurrent-log-handler`, the `tzdata`
  win32 marker, and the `ruamel.yaml.clib` win32 marker from
  `pyproject.toml`. Remove `uvloop`'s Windows exclusion if it simplifies to a
  plain POSIX marker.
- 5e: Regenerate `pm/lock.json` with `hermes pm lock` and `uv.lock` with the
  project's lock command. Commit both in the same atomic unit as the
  declarations they describe.
- 5f: Sweep `scripts/bundles/native.py`,
  `scripts/bundles/desktop_toolchain.py`, `scripts/bundles/payload.py`,
  `scripts/bundles/release_artifacts.py`, and `scripts/gen-bootstrap-pins.py`
  for Windows target handling.

Exit gate: `pm lock` is clean; a fresh macOS install and a fresh Linux install
both succeed; the lockfiles contain no win32 target.

### Stage 6: Installers and update machinery

Remove the native install and update story, not just its entry point.

- 6a: Delete `scripts/install.ps1` (1,672 lines), `setup-hermes.ps1`,
  `activate.ps1`, `scripts/build-bundle.ps1`,
  `scripts/windows-build-deps.ps1`, `scripts/build/windows-deps.ps1`,
  `scripts/windows_e2e_harness.ps1`, and `scripts/desktop-update.ps1`.
- 6b: Delete the Windows desktop update job:
  `scripts/desktop-update/windows.ps1` (1,820 lines), `marker.ps1`,
  `marker-claim.ps1`, `update-job.ps1`, `runtime.ps1`,
  `scripts/update-test/hermes-update-rehearsal.ps1`,
  `scripts/update-test/smoke-test.ps1`, and the PowerShell tests under
  `scripts/tests/`.
- 6c: Remove the Windows update handoff from `hermes_cli/update_handoff.py`,
  `update_completion.py`, `update_inventory.py`, `update_abort_recovery.py`,
  `relaunch.py`, and `_install_repair.py`. Keep the macOS and Linux handoff.
- 6d: Remove the Windows launcher self-heal and `.cmd` trampolines from
  `hermes_cli/main.py`, `hermes_cli/_launchers.py`, `_install_repair.py`, and
  `hermes_bootstrap.py`. Keep one launcher model per supported host.
- 6e: Remove the Windows uninstall registry handling from
  `hermes_cli/uninstall.py` and `hermes_cli/gui_uninstall.py`. Keep the macOS
  and Linux uninstall paths.
- 6f: Sweep optional-skill install scripts and platform lists for Windows
  (for example `optional-skills/software-development/ast-grep/install.ps1`).
  Optional skills are data, but they advertise a platform that no longer exists.

Exit gate: the core tree contains no `.ps1` file; the install and update e2e
lanes pass on macOS and Linux; no doc points at `install.ps1`.

### Stage 7: Desktop application and packaging

Remove Windows from the Electron app, the MSIX pipeline, and the bootstrap
installer.

- 7a: Delete the Windows Electron modules:
  `windows-remote-lifecycle.ts` (853 lines), `windows-sandbox-fallback.ts`
  (429), `windows-stack-cookie-fallback.ts` (322), `session-windows.ts` (218),
  `windows-hermes-path.ts` (183), `windows-user-env.ts` (99),
  `windows-child-options.ts` (61), `windows-msys-bash-env.ts` (20), and
  `get-windows.d.ts`.
- 7b: Delete the WSL host glue: `wsl-path-bridge.ts` (227),
  `wslg-launch.ts` (81), `wslg-launch-process.ts` (53),
  `wsl-clipboard-image.ts` (93), `wsl-clipboard-script.ts` (14), and
  `src/app/shell/wslg-window-controls.tsx` (81).
- 7c: Delete `src/store/windows.ts` (292) and remove the Windows branches from
  `src/lib/platform.ts`, `src/store/updates.ts`, the translucency code, the
  window-state code, the zoom code, the external-terminal code, and the
  uninstall section.
- 7d: Delete the MSIX and Store pipeline: `scripts/msix-shared.mjs`,
  `scripts/stage-msixbundle.mjs`, `scripts/bundle-store-msixbundle.mjs`,
  `apps/desktop/scripts/sign-msix.mjs`,
  `apps/desktop/scripts/gen-msix-manifest.mjs`,
  `apps/desktop/scripts/windows-bundle-tools.mjs`,
  `apps/desktop/scripts/prepare-packaging-tools.mjs`,
  `apps/desktop/assets/msix-manifest.xml`, and the Windows signing resources.
- 7e: Remove the Windows targets and scripts from
  `apps/desktop/package.json` (`dist:win`, `dist:win:msix`,
  `test:desktop:msix`, `get-windows`), the electron-builder configuration, and
  `apps/desktop/scripts/after-pack.mjs`, `after-extract.mjs`, and
  `stage-native-deps.mjs`.
- 7f: Remove the Windows updater host and relaunch waiter:
  `apps/desktop/electron/updater/channel-windows-host.ts`,
  the Windows branches in `relaunch-waiter.ts`, `updater-process.ts`,
  `app-updater.ts`, `update-marker.ts`, and `updater/marker-helper.ts`.
- 7g: Remove the Windows stages from the Tauri bootstrap installer:
  `apps/bootstrap-installer/src-tauri/src/powershell.rs` (842 lines),
  the Windows manifest, the Windows marker code, and the Windows bootstrap
  branches.
- 7h: Remove Windows and WSL claims from `apps/desktop/BUILDING.md`,
  `apps/desktop/AGENTS.md`, `apps/desktop/src/AGENTS.md`, and the desktop
  user-guide page.

Exit gate: the desktop builds for macOS; the Linux build scripts still run
locally; no MSIX or Windows updater code remains; no `get-windows` dependency.

### Stage 8: Tests and catalogs

Delete the test scaffolding that exists only for Windows, then clean the data
that points at it.

- 8a: Delete the Windows test directories
  `tests/e2e/core/windows` and `tests/e2e/core/windows_update`.
- 8b: Delete the 125 Windows-named test files, including the native support,
  subprocess flags, gateway, PTY, update lock, ACL, MSIX, long-path, taskkill,
  and PowerShell tests. Do not rewrite them to assert that Windows is gone.
- 8c: Remove `windows` from `tests/_fixtures/platform_gating.py`,
  `tests/conftest.py`, `tests/test_os_marker_gating.py`,
  `tests/test_platforms_marker.py`, and every `@pytest.mark.platforms(...)`
  spec. Keep `macos`, `linux`, and `posix`.
- 8d: Remove the 68 Windows skip conditions and the `wine2e` lane and its 20
  markers.
- 8e: Remove the Windows target from `scripts/run_tests_parallel.py`,
  `scripts/ci/setup_toolchain.py`, and the CI job matrices.
- 8f: Remove Windows from the 54 plugin-catalog platform lists. Delete the
  plugins that are Windows-only and have no Linux or macOS story:
  `hermes-windows-computer-use.yaml`, `hermes-windows-ops.yaml`,
  `account-switcher.yaml`, and `cdp-manager.yaml` if it is Windows-only.
- 8g: Delete `docker-compose.windows.yml` and any Nix reference to it.
- 8h: Sweep `skills/`, `optional-skills/`, `website/i18n/`, and `locales/` for
  Windows install and platform instructions.

Exit gate: `scripts/run_tests.sh` is green on macOS and Linux; the catalog
validator passes; no test file mentions `windows` except the boot-refusal test.

### Stage 9: Final sweep and lock

Prove the removal and make it hard to reintroduce.

- 9a: Add the permanent grep gate. It fails on `win32`, `pywin32`, `pywinpty`,
  `winrt`, `msvcrt`, `winreg`, `icacls`, `taskkill`, `PATHEXT`, `CREATE_NO_WINDOW`,
  `install.ps1`, `msix`, and `windows-store` in the core tree, with an explicit
  allowlist for the boot refusal, the final-release note in the docs, and
  unrelated uses of the word "window" (Electron windows, terminal windows).
- 9b: Remove the temporary Stage 1 guard and replace it with the permanent gate.
- 9c: Run `python scripts/check` and both platform test suites.
- 9d: Verify the package manager on a clean Linux container and a clean macOS
  host, including install, update, and uninstall.
- 9e: Record the final inventory in the commit message: files removed, lines
  removed, targets removed, CI jobs removed, and dependency markers removed.
- 9f: Keep the final Windows release tag and artifacts. Do not delete them.

Exit gate: the grep gate passes; `scripts/check` passes; macOS and Linux suites
pass; a fresh install works on both; no supported document advertises Windows.

## Sizing

Rough effort for one senior engineer who knows the repository. The ranges are
for sequencing, not for a deadline.

| Stage | Scope | Effort |
| --- | --- | --- |
| 1 | Freeze, refusal, CI off | 3 to 5 days |
| 2 | Docs and policy | 3 to 5 days |
| 3 | Runtime core deletion | 2 to 3 weeks |
| 4 | Platform seam collapse | 2 to 3 weeks |
| 5 | Package manager and locks | 1 to 1.5 weeks |
| 6 | Installers and update | 1 to 1.5 weeks |
| 7 | Desktop and packaging | 1.5 to 2.5 weeks |
| 8 | Tests and catalogs | 1 to 2 weeks |
| 9 | Final sweep and lock | 3 to 5 days |

Total: 10 to 12 engineer-weeks. Remove-only, without the Stage 4 collapse, is
about 8 weeks. With two engineers the calendar compresses to roughly 5 to 7
weeks, with the shared-file edits and lockfile regeneration serializing review.

## Verification

- The boot refusal is the only win32 check, and it has a unit test that passes
  `"win32"` as data.
- `rg` gate: zero core references to the removed tokens outside the allowlist.
- `python scripts/check` passes.
- `scripts/run_tests.sh` passes on macOS and Linux, including the platform
  marker lanes for `macos` and `linux`.
- A fresh macOS install, a fresh Linux install, and a fresh Linux container
  install each pass install, update, and uninstall.
- `pm lock` produces no diff after regeneration.
- The desktop app builds and launches on macOS; the Linux local build still
  runs.
- The docs site builds with no broken links to the deleted guides.
- The plugin catalog validates with no Windows-only entry.

## Risks and mitigations

- **One-way door for users.** Cut and tag the final Windows release before the
  first deletion. Point every refusal and doc at it. Keep the artifacts.
- **Silent POSIX regressions.** Windows branches sometimes share code with
  Linux (path normalization, encoding, locking). Mitigate with the grep gate,
  the full suites, and a fresh-install e2e after each stage that touches the
  platform layer.
- **Lockfile churn.** Removing markers can reshuffle `uv.lock` and
  `pm/lock.json` more than expected. Regenerate once per stage, never by hand,
  and review the diff for unrelated upgrades.
- **Dead imports after CI removal.** Removing the Windows lane means a stray
  `import win32api` no longer fails CI. The Stage 1 guard covers the gap until
  the Stage 9 gate.
- **Third-party packages still pull Windows deps.** Transitive Windows wheels
  may remain in the lock. Remove direct markers first; do not chase transitive
  wheels that are inert on macOS and Linux.
- **Data left behind.** Plugin catalogs, skills, locales, and optional-skill
  scripts advertise Windows. Sweep them in Stage 8, not "later".
- **Accidental scope creep into a rewrite.** The collapse is limited to
  removing Windows-shaped abstractions. Do not redesign the macOS or Linux
  paths in the same series.

## Rollback

The work lands as a series of atomic commits, one per stage unit, in the order
above. Rolling back means reverting the series in reverse order. The final
Windows release tag and its artifacts are the user-facing fallback. Do not
force-push, rewrite history, or amend landed commits.

## What this buys

- About 6,100 lines of Windows production Python, 7,400 lines of production
  PowerShell, and 4,200 lines of Windows TypeScript deleted outright.
- About 23,000 lines of Windows-only tests deleted.
- 2 package-manager targets, 5 CI workflows, 2 release lanes, and 34 dependency
  markers removed.
- A platform layer with two hosts instead of three, and one shell model, one
  PTY model, one process-kill model, one lock model, and one install model.
- The remaining macOS and Linux differences become the only platform
  complexity in the core, which is the point.
