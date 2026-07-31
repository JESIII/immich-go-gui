"""CLI compatibility contract guardrails.

Ensures the GUI flag allowlists (derived from flags.toml) stay in sync with
the captured immich-go ``--help`` fixtures, and that the ignored-upstream-flag
set is well-formed. These catch CLI parity drift when flags.toml or the CLI
fixtures change.
"""

from pathlib import Path

import pytest

from core import cli_help
from core.binary_manager import TESTED_IMMICH_GO_VERSION
from core.cli_contract import IGNORED_UPSTREAM_FLAGS, check_fixtures
from core.cli_help import help_name_for_tab, load_help_fixture
from core.flag_registry import REGISTRY


def test_ignored_upstream_flags_is_frozenset():
    assert isinstance(IGNORED_UPSTREAM_FLAGS, frozenset)


def test_ignored_upstream_flags_contains_secret_flags():
    """Secret flags that immich-go accepts but the GUI routes via env."""
    for f in ("api-key", "admin-api-key", "from-api-key", "from-admin-api-key"):
        assert f in IGNORED_UPSTREAM_FLAGS, (
            f"{f!r} should be ignored as an upstream flag"
        )


def test_check_fixtures_fully_compatible():
    """GUI allowlists must not reference flags absent from CLI fixtures."""
    report = check_fixtures()
    assert report.supported, (
        f"CLI fixtures report unsupported for {report.version}: {report.notes}"
    )
    missing = {
        tab: flags for tab, flags in report.missing_flags_by_tab.items() if flags
    }
    assert not missing, f"GUI references flags missing from CLI fixtures: {missing}"


@pytest.mark.parametrize("tab_key", sorted(REGISTRY.tabs))
def test_help_fixture_exists_for_every_tab(tab_key):
    """A captured --help fixture must exist for each tab's subcommand."""
    name = help_name_for_tab(tab_key)
    flags = load_help_fixture(TESTED_IMMICH_GO_VERSION, name)
    assert flags, (
        f"No help fixture for {tab_key} ({name}.txt) at "
        f"version {TESTED_IMMICH_GO_VERSION}"
    )


def test_cli_help_manifest_exists():
    """The fixture manifest must be present for the tested version."""
    manifest = (
        Path(cli_help.__file__).resolve().parent
        / "fixtures"
        / "cli_help"
        / TESTED_IMMICH_GO_VERSION
        / "manifest.json"
    )
    assert manifest.exists(), (
        f"manifest.json missing for version {TESTED_IMMICH_GO_VERSION}"
    )


def test_every_gui_allowed_flag_is_in_registry():
    """TAB_ALLOWED_FLAGS must be derived from the registry (SSOT)."""
    from core.cli_schema import TAB_ALLOWED_FLAGS

    for tab_key, allowed in TAB_ALLOWED_FLAGS.items():
        registry_allowed = REGISTRY.allowed_flags(tab_key)
        assert allowed == registry_allowed, (
            f"{tab_key}: TAB_ALLOWED_FLAGS drifted from REGISTRY"
        )
