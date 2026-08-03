"""Translate HTML forms ⇄ core state dicts, driven entirely by core.flag_registry.

Because every widget is generated from the same flags.toml definitions the Qt
app uses, adding a flag upstream automatically appears here with correct kind,
default, and emission semantics.
"""

from __future__ import annotations

from typing import Any

from core.flag_registry import REGISTRY, FlagDef

# Keys owned by the Configuration page (never rendered on workflow tabs).
STRUCTURAL_KEYS = {"server", "skip-ssl", "dry-run"}
# Keys rendered in the "Source Configuration" card; the rest go to "Options".
SOURCE_KEYS = {"from-server", "from-api-key", "from-date-range", "from-albums"}


def renderable_simple_flags(tab_key: str) -> tuple[FlagDef, ...]:
    return tuple(
        f
        for f in REGISTRY.flags.get(tab_key, ())
        if f.mode == "simple" and not f.hidden and f.key not in STRUCTURAL_KEYS
    )


def source_flags(tab_key: str) -> tuple[FlagDef, ...]:
    return tuple(
        f
        for f in renderable_simple_flags(tab_key)
        if (f.kind in ("path", "paths") and f.key != "write-to") or f.key in SOURCE_KEYS
    )


def option_flags(tab_key: str) -> tuple[FlagDef, ...]:
    src = {f.key for f in source_flags(tab_key)}
    return tuple(f for f in renderable_simple_flags(tab_key) if f.key not in src)


def coerce(def_: FlagDef, raw: str) -> Any:
    raw = (raw or "").strip()
    if def_.kind == "bool":
        return raw in ("on", "true", "1", "yes")
    if def_.kind in ("int", "duration_minutes"):
        try:
            v = int(raw)
        except ValueError:
            return def_.default
        if def_.min_val is not None:
            v = max(def_.min_val, v)
        if def_.max_val is not None:
            v = min(def_.max_val, v)
        return v
    return raw


def parse_tab_state(tab_key: str, form: dict[str, Any]) -> dict[str, Any]:
    """HTML form → tab_state dict matching Qt's _collect_tab_state contract."""
    state: dict[str, Any] = {}
    for f in REGISTRY.flags.get(tab_key, ()):
        if f.mode != "simple" or f.hidden or f.key in STRUCTURAL_KEYS:
            continue
        state[f.key] = coerce(f, str(form.get(f"fld_{f.key}", "")))
    return state


def parse_advanced_state(
    tab_key: str, form: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """HTML form → advanced_state dict ({key: {enabled, value}})."""
    st: dict[str, dict[str, Any]] = {}
    for d in REGISTRY.advanced_defs(tab_key):
        enabled = form.get(f"adv_{d.key}_en") == "1"
        st[d.key] = {
            "enabled": enabled,
            "value": coerce(d, str(form.get(f"adv_{d.key}_val", ""))),
        }
    return st


def parse_config_state(form: dict[str, Any]) -> dict[str, Any]:
    """Hidden config block on every tab form → config_state for the builder."""
    try:
        timeout = int(form.get("client_timeout_minutes") or 60)
    except ValueError:
        timeout = 60
    return {
        "server": str(form.get("server") or "").strip(),
        "api_key": str(form.get("api_key") or "").strip(),
        "admin_api_key": str(form.get("admin_api_key") or "").strip(),
        "skip-ssl": form.get("skip_ssl") == "on",
        "client_timeout_minutes": timeout,
    }


def initial_tab_state(tab_key: str) -> dict[str, Any]:
    """Defaults for a fresh form (mirrors Qt widget construction)."""
    state: dict[str, Any] = {}
    for f in renderable_simple_flags(tab_key):
        if f.kind == "bool":
            state[f.key] = bool(f.default)
        elif f.kind in ("int", "duration_minutes"):
            state[f.key] = f.default if isinstance(f.default, int) else 0
        elif f.kind == "enum":
            state[f.key] = f.default if f.default is not None else ""
        else:
            state[f.key] = ""
    return state
