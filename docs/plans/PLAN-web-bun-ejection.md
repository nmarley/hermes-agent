# Eject the Dashboard to a Bun-Managed Root

## Intent

The dashboard (`web/`) becomes a standalone Bun project inside this repository.
Everything else stays in the root npm workspace. Bun owns dependency
installation, package scripts, and the production build. PM provisions Bun so
`hermes update` and source launches keep working.

This is a design and sequencing document, not a progress tracker. Progress
lives in git history and the working conversation, never in this file.

## Why

- Bun is the preferred JavaScript and TypeScript runtime for this project.
- `web/` is the only package that benefits from an independent dependency root.
- Keeping `web/` in this repository preserves `@hermes/shared`, build receipts,
  and one git history.
- The dashboard is a product with its own toolchain. Entangling it with the
  root npm workspace makes every dependency change a monorepo lockfile change.

## Decisions

- In-repo ejection, not a separate repository or submodule.
- Pin Bun `1.4.2` in `web/package.json` and in `pm/lock.json`.
- Keep Vite, Vitest, ESLint, Tailwind, and the React Compiler. Bun is the
  package manager and script runner, not a replacement bundler or test runner.
- One lockfile per manager. `web/bun.lock` is the only lock for web. The root
  `package-lock.json` no longer contains web. No dual lockfiles.
- `@hermes/shared` moves from `file:../apps/shared` to `link:../apps/shared`,
  which Bun installs as a single symlink to live source.
- Bun executes the production build only after install, update, CI, Docker, and
  Nix parity is green.
- PM Bun stays optional. Source checkouts install it on demand; Docker and
  release builds use their own Bun stage or `pkgs.bun`.

## Current coupling

`web/` is not just a workspace member. It is a product input to the Python
build and update paths.

- The root `package.json` lists `web` in `workspaces` and carries
  `install:web`, `audit:web`, and `audit:fix:web`.
- The root `package-lock.json` is the only dependency lock for web.
- `scripts/build/node-deps.mjs` validates selected workspaces against the npm
  lock and runs one `npm ci` union.
- `hermes_cli/source_build.py` passes `web` into that union for launch, update,
  and desktop builds.
- `scripts/bundles/stage.py`, `scripts/bundles/desktop.py`, and
  `scripts/bundles/desktop_prepare.py` do the same for release bundles.
- `Dockerfile` installs web in the `frontend_build` stage with npm.
- `nix/web.nix` builds web with `buildNpmPackage` and `nix/lib.nix` discovers
  workspace members from the root `package.json`.
- `.github/workflows/js-tests.yml` installs with `npm ci`, and
  `.github/scripts/run-workspace-checks.mjs` discovers checks with
  `npm query .workspace`.
- `.github/workflows/osv-scanner.yml`, `scripts/ci/classify_changes.py`,
  `scripts/ci/lockfile_diff.py`, and `scripts/ci/desktop_build_cache.py`
  assume npm lockfiles.
- `hermes_cli/doctor_tools.py` audits web through the npm workspace.
- `.npmrc` release-age policy and root `overrides` apply to web only because
  web is in the root workspace.

## Target state

- `web/` has its own `package.json`, `bunfig.toml`, and `bun.lock`.
- The root npm workspace contains `apps/*`, `ui-tui`, `ui-tui/packages/*`, and
  `tests-js`. It does not contain web.
- `scripts/build/node-deps.mjs` accepts the same workspace union from callers
  and routes `web` to `bun ci`. Python and bundle callers keep their current
  arguments.
- PM can provision Bun for every supported target, including bionic through
  Bun's Android build.
- Source updates, release bundles, CI, Docker, and Nix all install web with Bun.
- Doctor audits web with `bun audit`.
- The dashboard build runs under Bun.
- `scripts/build/freshness.mjs` may stay on Node because it is a read-only
  hasher and needs no web dependencies.

## Non-goals

- No separate repository, submodule, or published package for web.
- No replacement of Vite with `bun build`.
- No replacement of Vitest with `bun test`.
- No change to dashboard behavior, routes, auth, or PTY handling.
- No change to the root npm packages or the TUI toolchain.
- No new dashboard feature work.

## Stage 0: Record the plan

Write this file and commit it alone.

## Stage 1: Pin Bun in PM

### Changes

- Add a `Bun` package class in `pm/packages.py`.
  - Binary name: `bun` on POSIX, `bun.exe` on Windows.
  - Archives come from the `oven-sh/bun` GitHub release for the pinned version.
  - Target mapping:
    - `darwin-arm64` to `bun-darwin-aarch64.zip`
    - `darwin-x64` to `bun-darwin-x64.zip`
    - `linux-x64` to `bun-linux-x64.zip`
    - `linux-arm64` to `bun-linux-aarch64.zip`
    - `linux-x64-musl` to `bun-linux-x64-musl.zip`
    - `linux-arm64-musl` to `bun-linux-aarch64-musl.zip`
    - `win32-x64` to `bun-windows-x64.zip`
    - `win32-arm64` to `bun-windows-aarch64.zip`
    - `linux-arm64-bionic` to `bun-linux-aarch64-android.zip`
  - Verify the binary by probing `bun --version`.
  - Mark the package `optional = True` and not a default, so only source
    builds that need web download it.
- Pin the version with `hermes pm lock --bump bun 1.4.2`.
- Add PM tests for every target URL, the bionic mapping, the probe, and
  `pm.ensure("bun")`.

### Verification

- `hermes pm install bun` on macOS returns a working `bun --version`.
- PM tests for the new package pass.
- No existing package pin changes.

### Rollback

Revert the commit. No caller uses Bun yet.

## Stage 2: Eject web and update every consumer

This is one contract change: web becomes a Bun project. It lands as one commit
because an intermediate state leaves required CI lanes, Docker, and Nix red.

### Packaging

- Remove `web` from the root `workspaces` array.
- Remove `install:web`, `audit:web`, and `audit:fix:web` from the root scripts.
- Add to `web/package.json`:
  - `"packageManager": "bun@1.4.2"`.
  - `"@hermes/shared": "link:../apps/shared"`.
  - The root `overrides` entries that can appear in web's dependency graph.
- Add `web/bunfig.toml`:
  - `[install] minimumReleaseAge = 1209600` for the 14-day policy.
  - `minimumReleaseAgeExcludes` ported from `.npmrc`.
  - `auto = "disable"` so `bun run` never installs on demand.
  - `linker = "hoisted"` to preserve the npm-like layout Vite and TypeScript
    expect.
- Generate and commit `web/bun.lock`.
- Delete the npm-installed `web/node_modules` and regenerate the root
  `package-lock.json` without web.
- Add the `@hermes/shared` alias to `web/vitest.config.ts`, because Vitest does
  not read the Vite alias.

### Install and update seam

- `scripts/build/node-deps.mjs`:
  - Split the selected workspace union into npm workspaces and Bun web.
  - Validate that `web/bun.lock` exists before selecting web.
  - Run `bun ci` in `web/` with a receipt keyed on the lockfile, Bun version,
    platform, and argument set.
  - Keep the CLI and the workspace selection arguments unchanged so
    `hermes_cli/source_build.py`, `hermes_cli/main_desktop.py`, and the bundle
    scripts need no caller changes.
- `hermes_cli/source_build.py`:
  - Ensure Bun when web is selected, including the update and launch paths.
  - Compose Bun into the build environment alongside npm.
  - Respect `HERMES_DISABLE_LAZY_INSTALLS` and the explicit-install policy.
- `hermes_cli/doctor_tools.py`:
  - Replace the web npm audit row with `bun audit`.
  - Update the audit remedy text so it does not recommend npm for web.

### Hints and local tooling

- Update `hermes_cli/main_dashboard.py`, `hermes_cli/subcommands/dashboard.py`,
  and `hermes_cli/web_server_dashboard.py` to say `bun install` and
  `bun run build`.
- Update `justfile` and `lefthook.yml` to run web lint through Bun.

### CI and supply chain

- `.github/workflows/js-tests.yml`:
  - Install the pinned Bun.
  - Cache `web/node_modules` against `web/bun.lock`.
  - Run `bun ci` in `web/`.
- `.github/scripts/run-workspace-checks.mjs`:
  - Add web as an explicit unit that runs `bun run --cwd web check`, because
    `npm query .workspace` no longer sees it.
- `.github/workflows/osv-scanner.yml`: add `--lockfile=web/bun.lock`.
- `scripts/ci/classify_changes.py`: treat `web/bun.lock` as an npm lock change.
- `scripts/ci/lockfile_diff.py`: report `web/bun.lock` in the advisory.
- `scripts/ci/desktop_build_cache.py`: include `web/bun.lock` in the desktop
  build cache inputs.

### Docker

- Add a digest-pinned Bun stage or base image.
- In `frontend_build`, copy `web/package.json`, `web/bun.lock`, and
  `apps/shared`, then run `bun ci` in `web/`.
- Keep the npm union for `ui-tui` only.
- Keep the web build command on Node until Stage 3.
- Update the Dockerfile comments that describe the workspace set.

### Nix

- `nix/lib.nix`: web falls out of workspace discovery automatically. Add a
  Bun build helper for a package with its own lockfile.
- `nix/web.nix`: replace `buildNpmPackage` with a Bun derivation. Use
  `pkgs.bun` from the pinned nixpkgs and a fixed-output dependency
  derivation for `bun ci`.
- `nix/devShell.nix`: install web dependencies with Bun, or document the
  explicit `bun install` step.
- Keep `apps/shared` and the build scripts in web's source set.

### Tests

- Update `tests/hermes_cli/test_source_build.py` for the Bun branch and its
  receipts.
- Update `tests/hermes_cli/test_doctor_workspace_audit.py` and
  `tests/hermes_cli/test_update_finish.py`.
- Update `tests-js/package-json-lazy-deps.test.ts` comments that name the web
  workspace install graph.

### Verification

- `cd web && bun run typecheck && bun run test && bun run lint`.
- `cd web && bun run build` still produces `hermes_cli/web_dist`.
- `node scripts/build/node-deps.mjs --source . --workspace web --reuse`
  installs through Bun and reuses its receipt.
- `node scripts/build/web.mjs --source . --icons . --out <tmp>` still builds
  from a Bun-installed tree.
- Targeted pytest for source build, doctor, update finish, and PM.
- `python scripts/check`.
- `nix build .#web` and a Docker frontend build where the host supports them.
- No `--workspace web` remains in the npm install path.

### Rollback

Revert the commit. The root workspace and `package-lock.json` return; delete
`web/bun.lock`, `web/bunfig.toml`, and the Bun branch in `node-deps.mjs`.

## Stage 3: Run the production web build on Bun

### Changes

- `scripts/build/web.mjs`:
  - Skip the Node heap re-exec when `process.versions.bun` is present.
  - Keep the Rayon thread cap, which the Rolldown native binding still reads.
  - Keep the existing Node path unchanged for Node callers.
- Change the web build script in `web/package.json` to
  `bun ../scripts/build/web.mjs`.
- Switch the build callers to Bun:
  - `hermes_cli/source_build.py::build_source_web`.
  - `scripts/bundles/stage.py`.
  - `scripts/bundles/desktop.py`.
  - `Dockerfile`.
  - `nix/web.nix`.
- Add a `run_source_bun_script` helper or a runtime argument instead of
  changing the shared Node runner used by the TUI.
- Keep `scripts/build/freshness.mjs` on Node. It hashes sources and writes
  receipts; it does not need web's dependency tree.

### Verification

- A fresh `bun run build` produces a working dashboard.
- `hermes dashboard` serves the new build and the PTY still works.
- The build receipt is accepted by `scripts/build/freshness.mjs`.
- The TUI build path still uses Node and is unchanged.
- A release bundle build uses Bun for web and Node for the rest.

### Rollback

Revert the commit. Web remains a Bun package, but the build script returns to
Node. This rollback does not touch the dependency root.

## Stage 4: Documentation and cleanup

### Changes

- Update `web/README.md`, `web/AGENTS.md`, and root `AGENTS.md`.
- Update `scripts/build/README.md` with the Bun install and build commands.
- Update any install or contributing docs that tell users to run
  `npm install --workspace web`.
- Remove stale npm references from hints, comments, and tests.
- Confirm `.gitignore` covers `web/node_modules` and does not ignore
  `web/bun.lock`.

### Verification

- `python scripts/check`.
- The JS suite and the targeted Python tests.
- `git status` is clean after a full build.

## Risks and mitigations

- Lockfile migration: Bun may search upward for the root `package-lock.json`
  when generating `web/bun.lock`. Generate the web lock with no root lock in
  scope, or set `BUN_CONFIG_SKIP_LOAD_LOCKFILE=1` for the first run, then
  verify the resolved versions.
- Lifecycle scripts: Bun blocks dependency lifecycle scripts by default. Add
  `trustedDependencies` only for packages that need them, and prove the build
  works with a clean install.
- Audit output: `bun audit --json` may not match npm's schema. Adapt the
  doctor parser or report a clear failure instead of silently skipping.
- Nix offline builds: use a fixed-output derivation keyed on `web/bun.lock`
  so the flake check does not need network access.
- Docker multi-arch: select the correct Bun archive or image for amd64 and
  arm64, and pin it by digest.
- Termux: bionic maps to Bun's Android build. Verify it runs under Termux. If
  it does not, report a clear unsupported message for the dashboard build
  rather than falling back to npm.
- Vitest under Bun: verify the suite under the Bun script runner. If Vitest
  requires Node, keep the package manager on Bun and run the test binary with
  Node; do not migrate the suite.
- Supply-chain parity: port `.npmrc` release-age excludes and the applicable
  root `overrides` before deleting web from the root lock.

## Effort

- Stage 1: 2 to 4 hours.
- Stage 2: 1 to 1.5 days.
- Stage 3: 2 to 4 hours.
- Stage 4: 1 to 2 hours.
