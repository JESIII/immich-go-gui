# immich-go Compatibility

The GUI is built and tested against specific immich-go versions. Version compatibility is enforced in `core/binary_manager.py` and surfaced in the Config tab.

## Current Version Policy

| Constant | Value |
|----------|-------|
| Recommended version | `0.32.0` |
| Tested versions | `0.32.0` |
| Minimum supported | `0.32.0` |
| Maximum known compatible | `0.32.0` |

## Version Support Classification

| Status | Meaning | GUI behavior |
|--------|---------|--------------|
| **TESTED** | Version in `TESTED_IMMICH_GO_VERSIONS` | No warnings; full support expected |
| **UNTESTED_BUT_MAY_WORK** | Between min and max, not in tested set | Informational warning |
| **UNTESTED_NEW** | Above `MAX_KNOWN_COMPATIBLE` | Warning; may require confirmation |
| **UNSUPPORTED_OLD** | Below `MIN_SUPPORTED` | Blocked or strong warning |
| **UNKNOWN** | Unparseable version string | Warning |

Enable **Allow untested updates** in config to proceed with newer versions after confirmation.

## Version 0.32.0 Notes

From `VERSION_NOTES` and `COMPATIBILITY_MATRIX`:

- GUI-tested version
- Upstream removed the ReplaceAsset API
- The `asset.replace` API-key permission is no longer required
- No known immich-go CLI flag breakage for this GUI

## Binary Management

### Storage

| Path | Purpose |
|------|---------|
| `~/.immich-go-gui/bin/` | Base directory for all installed versions |
| `~/.immich-go-gui/bin/{version}/immich-go` | Versioned binary (`.exe` on Windows) |
| `~/.immich-go-gui/bin/metadata.json` | `selected_version`, per-version records, optional `manual_path` |

Legacy flat installs (`~/.immich-go-gui/bin/immich-go` without a version subdirectory) are still resolved as a fallback.

### Download Process

Triggered from the Config tab (or a pre-run download prompt), not on every launch:

1. GUI queries [GitHub Releases](https://github.com/simulot/immich-go/releases) for the target version
2. Downloads platform-appropriate archive (`.tar.gz` or `.zip`) to a temp file inside `bin/{version}/`
3. Fetches `checksums.txt` from the same release — **install aborts if missing** (fail-closed)
4. Verifies archive SHA256 against the entry for the downloaded archive name
5. Extracts binary to `~/.immich-go-gui/bin/{version}/immich-go`
6. Runs post-extract verification (`immich-go version`) — install aborts if the binary is unusable
7. Updates `metadata.json` and sets `selected_version`

### Version Detection

The GUI runs `immich-go version` and parses output via `parse_version_output()`. Version strings are normalized (leading `v` stripped, build info removed).

## Updating immich-go

From the Config tab:

1. Check current version and support status
2. Click download/update if a newer recommended version is available
3. Review compatibility warnings before proceeding

For manual updates, place the binary in `~/.immich-go-gui/bin/{version}/` and update `metadata.json` (or set `manual_path`).

## CLI Fixture Workflow

When immich-go releases a new version, maintainers should:

1. Download the new binary (or use Config tab download)
2. Run `uv run scripts/capture_cli_help.py`
3. Edit `core/flags.toml` for any flag changes
4. Update version constants in `binary_manager.py` only
5. Run full test suite: `uv run pytest`
6. Update `CHANGELOG.md` and this document

See [Testing](../developer-guide/testing.md) and [Scripts](../developer-guide/scripts.md).

## Breaking Change Detection

`binary_manager.py` scans release notes for breaking change indicators:

- "breaking change", "BREAKING"
- "removed flag", "renamed flag"
- "incompatible", "deprecated"

Release notes matching these patterns trigger stronger update warnings.

## Related

- [Configuration](../user-guide/configuration.md) — Binary management UI
- [Troubleshooting](../user-guide/troubleshooting.md) — Version warning issues
- [immich-go releases](https://github.com/simulot/immich-go/releases)
