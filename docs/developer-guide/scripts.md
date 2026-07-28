# Scripts

Maintenance scripts in `scripts/` are Qt-free Python utilities. Run them with `uv`:

```bash
uv run scripts/<script>.py
```

## capture_cli_help.py

Captures immich-go `--help` output into versioned test fixtures.

**Purpose:** Keep `TAB_ALLOWED_FLAGS` and CLI contract tests aligned with the installed immich-go binary.

**Usage:**

```bash
uv run scripts/capture_cli_help.py
```

**What it does:**

1. Locates the immich-go binary via `core/binary_manager.get_binary_path()`
2. Runs `--help` for each target subcommand (upload, archive, stack variants)
3. Writes text files to `core/fixtures/cli_help/{version}/`
4. Generates a manifest JSON with capture metadata

**Target commands** include root, all upload/archive subcommands, and stack — matching the 11 GUI tabs.

**When to run:** After upgrading immich-go or when adding a new tab/subcommand.

## bundle_codebase.py

Bundles project source, configuration, `gui/`, `core/`, scripts, and test files into a single text file for LLM code review.

**Usage:**

```bash
uv run scripts/bundle_codebase.py [output_path]         # Lean codebase profile (default)
uv run scripts/bundle_codebase.py --full [output_path]   # Full profile (includes docs/, icons)
```

Default output: `immichgo_modules_bundle.txt`

**Bundled in Lean profile (default):**

- Root entrypoints & configs: `app.py`, `theme.py`, `pyproject.toml`, `README.md`, `.gitignore`, `.pre-commit-config.yaml`
- `core/` — all modules **including** `flags.toml`
- `gui/` — all modules (`widgets/`, `tabs/`, `mixins/`, `main_window.py`, `browse_dialogs.py`)
- `assets/` — `theme.qss`
- `tests/` — suite, `conftest.py`, fixtures (`cli_help`, `command_states`)
- `scripts/` — maintenance utilities
- `packaging/`, `.github/` workflows

**Excluded in Lean profile:** `.venv`, build/site caches, binary assets (`.png`/`.ico`), generated `*_bundle.txt` files, `docs/`, `.vscode/`, `assets/icons/*.svg`. Use `--full` to include docs and icons, or use `bundle_website_docs.py` for documentation review.

## bundle_website_docs.py

Bundles documentation and website files (`docs/`, `mkdocs.yml`, `overrides/`, root docs) into `immichgo_website_bundle.txt` for documentation review.

**Usage:**

```bash
uv run scripts/bundle_website_docs.py [output_path]
```

## generate_diff_bundle.py

Generates a git diff bundle for code review.

**Usage:**

```bash
uv run scripts/generate_diff_bundle.py
```

Useful for sharing changes with reviewers or AI assistants without exposing the full repository.

## Related Documentation

- [Testing](testing.md) — Fixture regeneration workflow
- [Adding Tabs and Flags](adding-tabs-and-flags.md) — When to capture new CLI help
