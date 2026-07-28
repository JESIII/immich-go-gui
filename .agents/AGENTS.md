# Immich-Go GUI Project Knowledge & Design Guidelines

## 1. Work Workflow & Execution Philosophy
- **Step-by-Step Slow Approach**: Take a careful, deliberate, step-by-step approach. Always plan, document, and inspect authoritative source files before writing or modifying code. Never guess code logic or file structures.
- **Frequent Commits**: Keep committing progress in logical, well-demarcated chunks as work progresses so changes are easily tracked and reversible.
- **Reference Project Documentation**: When documentation files or specs are referenced or provided by the user, read and strictly adhere to their guidelines and constraints without deviation.

## 2. Environment & Tooling Rules
- **Python Package Manager (`uv`)**: Always use `uv` for running Python scripts and tests (e.g. `uv run pytest`, `uv run python app.py`, `uv sync --dev`). Never use system `pip` or raw `python`.
- **GitHub CLI (`gh`)**: Always use standard user authentication for local `gh` commands (e.g. `gh pr list`, `gh run view`, `gh workflow run`). Do NOT pass `env -u GITHUB_TOKEN` or `GH_TOKEN` environment variables when running commands locally.
- **Git Branching Policy**:
  - `master`: Production branch (only updated via GitHub Release / PR merges).
  - `staging`: Active development and integration branch.
  - Pull Requests must target `master` from `staging`.
  - **Squash Merges Required for Release Please**: Merges from `staging` into `master` MUST use squash merging (`gh pr merge --squash` or repository squash settings). Non-squash merges pull all historical staging commits into `master`, breaking Release Please commit scanning and pulling old/unreleased history into release PRs.

## 3. Architecture & CLI Parity (11/11 Sub-commands)
- **11 GUI Sub-Tabs**:
  - **Upload**: `upload-folder`, `upload-gp`, `upload-icloud`, `upload-picasa`, `upload-immich`
  - **Archive**: `archive-folder`, `archive-gp`, `archive-icloud`, `archive-picasa`, `archive-immich`
  - **Stack**: `stack`
- **Serverless Tab Rule**: `archive-folder`, `archive-gp`, `archive-icloud`, and `archive-picasa` are strictly classified as `SERVERLESS_TABS`. They must NEVER emit `--server`, `--api-key`, or `--client-timeout` flags.
- **Simple vs. Advanced Control Policy**: Simple mode shows high-frequency inputs only. Advanced mode dynamically generates flag rows from `core/flags.toml` via `core/flag_registry.py` (`mode = "simple"` or `mode = "advanced"`).

## 4. Security & Secret Isolation
- **In-Memory Secret Delivery**: Sensitive API keys (`IMMICH_GO_UPLOAD_API_KEY`, `IMMICH_GO_UPLOAD_FROM_IMMICH_FROM_API_KEY`, etc.) are passed strictly through process memory environment dictionaries (`posix_env` / `win_env`) in `subprocess.Popen`. NEVER write secret environment variables or credentials to disk shell scripts (such as `env.sh`).
- **OS Keychain Integration**: Secret API keys are stored via `keyring` (macOS Keychain, Windows Credential Manager, Linux Secret Service) and omitted from plain TOML or form state persistence.
- **Redaction**: Previews and log outputs must sanitize all API key strings.
- **SSL Bypass Warning Banners**: Display explicit inline warnings when `--skip-verify-ssl` is checked.

## 5. Terminal Launcher & Process Lock Lifecycle
- **POSIX Safe CWD**: POSIX launchers execute inside temporary run directories with a safe `$HOME` fallback directory change to prevent current-working-directory deletion errors.
- **Windows Heartbeat Loop**: Windows `.bat` launchers run a background heartbeat process (`.heartbeat`) to ensure process lock files (`.lock`) are reliably cleaned up even if the command prompt window is killed abruptly.

## 6. Testing & Cross-Platform Assertions
- **Windows Path Normalization**: All test cases in `tests/test_app.py` comparing CLI `argv` vectors MUST pass through `_norm_argv(...)` to strip Windows drive letters (`C:`, `D:`) and normalize backslashes (`\`) to forward slashes (`/`).
- **Headless Terminal Mocks**: Launcher unit tests must mock `sys.platform` and `shutil.which` (`patch("shutil.which", return_value="/usr/bin/gnome-terminal")`) so headless CI environments don't fail.
- **Headless Qt Execution**: Headless Linux test runs require `QT_QPA_PLATFORM=offscreen` and `xvfb-run`.

## 7. CI/CD & Build Packaging Rules
- **App Icon Resource**: `immich-go-gui.ico` is committed in the root workspace directory. Do NOT add build-time `PIL` image conversion scripts.
- **Inno Setup Output Relocation**: `packaging/windows/installer.iss` uses `OutputDir=..\..\`. Windows build steps in `.github/workflows/release.yml` must move compiled `.exe` files from parent directories back into the root workspace folder before `upload-artifact`.
- **AppImageTool**: Linux AppImage packaging uses the `continuous` release of `appimagetool` (`https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage`) with `--appimage-extract-and-run`.
- **Artifact Naming Convention**: All output packages MUST include both Version and Architecture: `Immich-Go-GUI-${VERSION}-${OS}-${ARCH}.${ext}` (e.g. `Immich-Go-GUI-1.1.0-Windows-x86_64-Setup.exe`).
- **Release Please Config Location**: Configuration files belong in `.github/release-please-config.json` and `.github/.release-please-manifest.json`.
- **Release Please Manifest Sync**: `.github/.release-please-manifest.json` must be explicitly updated whenever performing manual version bumps or hotfix releases so Release Please tracks the correct baseline version.



# Immich-Go GUI — Project Context Brief

## What It Is

A **PySide6 desktop GUI** wrapping the [immich-go](https://github.com/simulot/immich-go) CLI (v0.32.0). Users configure upload/archive/stack jobs via forms, preview the exact CLI command, and launch it in an external terminal. **11 workflow tabs** cover every immich-go subcommand.

## Architecture (Non-Negotiable Rules)

- **`core/` is Qt-free.** All business logic, testable headlessly.
- **Secrets never go in argv.** API keys travel via environment variables (`IMMICH_GO_*`), stored in OS keyring.
- **Serverless archive tabs** (`archive-folder`, `archive-gp`, `archive-icloud`, `archive-picasa`) must **never** emit `--server`, `--api-key`, or `--client-timeout`.
- **`core/flags.toml`** is the single source of truth for all flag definitions, loaded by `core/flag_registry.py`. `cli_schema.py` and `advanced_flags.py` are thin delegation shims.

## Key Files

| File | Role |
|---|---|
| `app.py` (~3575 lines) | Qt UI: tabs, widgets, events, run/save/load |
| `theme.py` | Theming, palettes, SVG icons |
| `core/flags.toml` (~2809 lines) | **Single source of truth** for all tabs + flags |
| `core/flag_registry.py` | Loads flags.toml → `REGISTRY` singleton |
| `core/command_builder.py` | `build_plan_from_state()` → `CommandPlan` (argv + env) |
| `core/advanced_flags.py` | `advanced_flag_args()`, `apply_advanced_flags_to_plan()` |
| `core/cli_schema.py` | Re-exports from registry (TAB_COMMANDS, TAB_ALLOWED_FLAGS, etc.) |
| `core/config_manager.py` | TOML config + keyring secrets |
| `core/binary_manager.py` | immich-go download/verify/version |
| `core/terminal_launcher.py` | Cross-platform external terminal launch |
| `core/process_tracker.py` | Run lock files |
| `tests/test_app.py` (~3151 lines) | Main test suite |
| `tests/test_flag_registry.py` | Registry validation tests |
| `tests/test_emission_model.py` | Emission model tests |

## Current Flag Model (1.4.0 emission model)

Implemented in 1.4.0. The `emission` field was removed from `flags.toml`.

### The One Rule
> **A flag reaches the CLI if and only if the user explicitly asked for it.** immich-go applies its own defaults for anything not passed.

### Model
- **`mode` is the only behavioral field:** `simple` | `advanced`
- **Simple mode:** Only `mode=simple` widgets visible. Emit if value ≠ TOML/CLI default.
- **Advanced mode:** Advanced rows shown, **all disabled by default**. Emit **only** if user checks the enable box. Row value pre-populated from saved config (takes precedence) or CLI default.
- **Config tab:** server URL, API key, admin key, skip-SSL, secret provider, theme, binary mgmt, allow-untested, preferred-terminal. No per-flag widgets for `client-timeout`, `concurrent-tasks`, `device-uuid`, `on-errors`, or `pause-immich-jobs` — those are per-tab advanced rows.
- **pause-jobs safety:** Post-check after all flags emitted — if upload/stack tab + no admin key + no explicit pause flag in argv → emit `--pause-immich-jobs=false` + warning (`source="safety"` in emission log).

### Config Persistence for Advanced Rows
- **Values persist** in `form_state.advanced.{tab}.{key}.value`
- **Enabled state persists** in `form_state.advanced.{tab}.{key}.enabled`
- On fresh install / "Reset Advanced Flags": all disabled, values = CLI defaults
- Saved config value takes precedence over flags.toml default for **display only**. Emission still requires the checkbox.

### Emission Logic
1. Structural flags (server, skip-ssl, dry-run) — always when applicable
2. Simple widgets — emit if value ≠ default
3. Advanced rows — emit ONLY if enabled
4. Positional args (paths)
5. Safety post-check (pause-jobs)

## Tech Stack

- Python 3.13 (`>=3.13.0, <3.14`), PySide6, `uv` package manager
- TOML config (`tomllib`/`tomli` + `tomli_w`), `keyring`, `requests`, `packaging`
- pytest + pytest-qt, Nuitka for release builds
- MkDocs Material for docs site

## Branching & Releases

- PRs target **`staging`**, never `master` directly.
- Release Please with Conventional Commits.
- Multi-platform builds: Windows (exe/zip), macOS (dmg), Linux (AppImage/deb/rpm/tar).

## Testing Conventions

- `_norm_argv()` for all path comparisons in argv assertions.
- Golden JSON fixtures in `tests/fixtures/command_states/`.
- CLI help fixtures in `tests/fixtures/cli_help/0.32.0/`.
- Run: `uv run pytest` (Linux headless: `QT_QPA_PLATFORM=offscreen xvfb-run uv run pytest`).