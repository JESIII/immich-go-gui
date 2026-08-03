"""Flag presets for the web console (proposal P4).

Presets are *references* to existing advanced flags only — the actual flag
definitions stay in ``flags.toml`` (SSOT). ``presets_for`` filters each preset
against the current tab's advanced flag definitions so unknown keys are never
rendered or applied.
"""

from __future__ import annotations

from typing import Any

from core.flag_registry import REGISTRY

PRESETS: dict[str, list[dict[str, Any]]] = {
    "upload-folder": [
        {
            "name": "🚀 Fast Scan",
            "desc": "Higher concurrency for large libraries",
            "flags": {"concurrent-tasks": 8},
        },
        {
            "name": "🧩 Metadata First",
            "desc": "Prefer EXIF dates, keep sidecars untouched",
            "flags": {"date-from-name": False, "ignore-sidecar": True},
        },
        {
            "name": "🔒 Conservative",
            "desc": "Explicit dates, no silent ignores",
            "flags": {"date-from-name": True, "ignore-sidecar": False},
        },
    ],
    "upload-immich": [
        {
            "name": "⭐ Favorites Only",
            "desc": "Only favorite, non-archived source assets",
            "flags": {"from-favorite": True, "from-archived": False},
        },
        {
            "name": "👥 Partners Too",
            "desc": "Also pull partner + trashed assets",
            "flags": {"from-partners": True, "from-trash": True},
        },
    ],
    "stack": [
        {
            "name": "🐢 Gentle",
            "desc": "Pause jobs while stacking runs",
            "flags": {"pause-jobs": True},
        },
        {
            "name": "🐛 Debug",
            "desc": "API trace + debug logging",
            "flags": {"api-trace": True, "log-level": "DEBUG"},
        },
    ],
}


def presets_for(tab_key: str) -> list[dict[str, Any]]:
    """Return presets whose flags all exist in the tab's advanced definitions."""
    if tab_key not in REGISTRY.tabs:
        return []
    valid = {d.key for d in REGISTRY.advanced_defs(tab_key)}
    out = []
    for preset in PRESETS.get(tab_key, []):
        flags = {k: v for k, v in preset.get("flags", {}).items() if k in valid}
        if flags:
            out.append({**preset, "flags": flags})
    return out
