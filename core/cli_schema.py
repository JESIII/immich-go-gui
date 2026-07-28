"""Stable metadata constants, mappings, and compatibility matrices.

Now delegates to the unified flag registry (core/flag_registry.py).
MUST NOT import PySide6 or Qt.
"""

from .flag_registry import REGISTRY  # re-export FlagDef for compat

TAB_KEYS = REGISTRY.tab_keys
TAB_COMMANDS = REGISTRY.tab_commands
UPLOAD_TABS = REGISTRY.upload_tabs
ARCHIVE_TABS = REGISTRY.archive_tabs
SERVER_REQUIRED_TABS = REGISTRY.server_required_tabs
SERVERLESS_TABS = REGISTRY.serverless_tabs
ENV_KEY_MAP = REGISTRY.env_key_map
TAB_ALLOWED_FLAGS = {k: REGISTRY.allowed_flags(k) for k in REGISTRY.tabs}

# Flags that must always be masked in previews.
SECRET_FLAGS = {
    "--api-key",
    "--from-api-key",
    "--admin-api-key",
    "--from-admin-api-key",
}


def flag_allowed_for_tab(tab_key: str, flag_name: str) -> bool:
    """Checks whether a given flag name (without --) is allowed for a tab."""
    return REGISTRY.flag_allowed(tab_key, flag_name)


def assert_flag_allowed(tab_key: str, flag_name: str) -> None:
    """Raises ValueError if flag_name is not allowed for tab_key."""
    if not flag_allowed_for_tab(tab_key, flag_name):
        raise ValueError(
            f"Flag '--{flag_name.lstrip('-')}' is not allowed for tab '{tab_key}'."
        )


# Future compatibility metadata.
COMPATIBILITY_MATRIX = {
    "0.32.0": {
        "tested": True,
        "notes": (
            "GUI-tested version. Upstream removed the ReplaceAsset API. "
            "The asset.replace API-key permission is no longer required. "
            "No known immich-go CLI flag breakage for this GUI."
        ),
        "renamed_flags": {},
        "removed_flags": [],
    },
}
