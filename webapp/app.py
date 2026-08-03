"""Starlette application: routes, rendering, and orchestration over core/."""

from __future__ import annotations

import asyncio
import json
import secrets
import shlex
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from core import (
    BinaryManager,
    default_config_path,
    get_binary_path,
    get_secret_with_fallback,
    load_binary_metadata,
    load_config,
    save_binary_metadata,
    save_config,
    save_secret_with_fallback,
    save_server_url,
)
from core.advanced_flags import validate_advanced_state
from core.app_update import (
    get_latest_gui_release,
    is_parseable_semver,
    is_update_available,
)
from core.binary_manager import clean_version
from core.cli_contract import check_binary_help, check_fixtures
from core.cli_schema import SERVER_REQUIRED_TABS, SERVERLESS_TABS
from core.command_builder import build_plan_from_state, validate_state
from core.flag_registry import REGISTRY
from core.network import check_preflight_server_connection, test_immich_connection
from core.process_tracker import cleanup_stale_locks, scan_locks
from core.profile_manager import (
    active_profile_name,
    create_profile,
    delete_profile,
    duplicate_profile,
    list_profiles,
    rename_profile,
    set_active_profile_name,
    validate_profile_name,
)
from webapp import auth as authmod
from webapp.auth import (
    AUTH_COOKIE,
    SESSION_COOKIE,
    AuthMiddleware,
    auth_enabled,
    check_login,
    drop_session,
    get_session,
)
from webapp.diagnostics import build_diagnostics_zip, gui_version
from webapp.forms import (
    initial_tab_state,
    option_flags,
    parse_advanced_state,
    parse_tab_state,
    source_flags,
)
from webapp.history import HISTORY
from webapp.presets import presets_for
from webapp.runner import RUNS, RunInProgress

BASE = Path(__file__).resolve().parent.parent
TEMPLATES = Jinja2Templates(directory=str(BASE / "templates"))
BINMGR = BinaryManager()

SECRET_ENV_MARKERS = ("API_KEY", "ADMIN_API_KEY")

# Short labels for horizontal sub-tabs, mirroring the desktop QTabWidget titles.
_SUB_TAB_LABELS: dict[str, str] = {
    "upload-folder": "From Folder",
    "upload-gp": "Google Takeout",
    "upload-icloud": "iCloud",
    "upload-picasa": "Picasa",
    "upload-immich": "From Immich",
    "archive-folder": "From Folder",
    "archive-gp": "Google Takeout",
    "archive-icloud": "iCloud",
    "archive-picasa": "Picasa",
    "archive-immich": "From Immich",
    "stack": "Stack Duplicates",
}


def _keyring_available() -> bool:
    """True if the OS keyring backend is usable (containers usually lack one)."""
    if _keyring_available.cached is not None:
        return _keyring_available.cached
    try:
        import keyring

        keyring.get_password("immich-go-gui-probe", "probe")
        _keyring_available.cached = True
    except Exception:
        _keyring_available.cached = False
    return _keyring_available.cached


_keyring_available.cached: bool | None = None


# ──────────────────────────────────────────────────────────────────────
# Session-scoped working state (mirrors the Qt window's in-memory widgets)
# ──────────────────────────────────────────────────────────────────────
def sess(request: Request) -> dict[str, Any]:
    return get_session(request)


def ensure_loaded(request: Request) -> dict[str, Any]:
    s = sess(request)
    if "config" not in s:
        cfg = load_config()
        if cfg.secrets_provider == "fallback":
            cfg.secrets_provider = "config"
        # A running container usually has no OS keyring; default to the local
        # secrets file (or IMMICH_GO_GUI_* env overrides) so a fresh container
        # works without keyring.
        if cfg.secrets_provider == "keyring" and not _keyring_available():
            cfg.secrets_provider = "config"
        prof = cfg.profile_name
        s["config"] = cfg
        s["secrets"] = {
            "api_key": get_secret_with_fallback(prof, "api_key", cfg.secrets_provider),
            "admin_api_key": get_secret_with_fallback(
                prof, "admin_api_key", cfg.secrets_provider
            ),
        }
        s.setdefault("tab_state", {})
        s.setdefault("adv_state", {})
        s.setdefault("view", ("overview", ""))
        s.setdefault("pending", {})
    return s


def current_config_state(request: Request) -> dict[str, Any]:
    s = ensure_loaded(request)
    cfg = s["config"]
    return {
        "server": cfg.server_url,
        "api_key": s["secrets"].get("api_key", ""),
        "admin_api_key": s["secrets"].get("admin_api_key", ""),
        "skip-ssl": cfg.skip_ssl,
        "client_timeout_minutes": cfg.client_timeout_minutes,
    }


# ──────────────────────────────────────────────────────────────────────
# Rendering helpers
# ──────────────────────────────────────────────────────────────────────
def base_ctx(request: Request, **extra: Any) -> dict[str, Any]:
    s = ensure_loaded(request)
    view = s.get("view", ("overview", ""))
    active_section = ""
    if view[0] == "tab" and view[1] in REGISTRY.tabs:
        active_section = REGISTRY.tabs[view[1]].section
    ctx = {
        "request": request,
        "version": gui_version(),
        "profile": active_profile_name(),
        "advanced": bool(s["config"].advanced_mode),
        "theme": request.cookies.get("igg_theme", "dark"),
        "auth_enabled": auth_enabled(),
        "csrf": request.cookies.get(authmod.CSRF_COOKIE, ""),
        "busy": RUNS.is_busy(),
        "view": view,
        "active_section": active_section,
    }
    ctx.update(extra)
    return ctx


def page(request: Request, partial_name: str, **ctx: Any) -> HTMLResponse:
    ctx_dict = base_ctx(request, **ctx)
    inner = TEMPLATES.get_template(partial_name).render(ctx_dict)
    if request.headers.get("HX-Request"):
        crumb = ctx_dict.get("crumb") or "overview"
        adv = ctx_dict.get("advanced")
        state_label = "⚡ Advanced" if adv else "🌱 Simple"
        action_label = "→ Simple" if adv else "→ Advanced"
        oob_crumb = f'<div id="crumb" hx-swap-oob="innerHTML:#crumb">{crumb}</div>'
        oob_mode = (
            f'<button id="mode-toggle-btn" class="btn btn-sm btn-ghost" '
            f'hx-post="/mode/toggle" hx-target="#content" hx-swap-oob="outerHTML:#mode-toggle-btn" '
            f'title="Toggle Advanced Mode">'
            f'<span class="mode-state">{state_label}</span>'
            f'<span class="mode-action">{action_label}</span>'
            f"</button>"
        )
        oob_nav = TEMPLATES.get_template("partials/nav.html").render(ctx_dict, oob=True)
        oob_profile = TEMPLATES.get_template("partials/profile_chip.html").render(
            ctx_dict, oob=True
        )
        return HTMLResponse(
            f"{inner}\n{oob_crumb}\n{oob_mode}\n{oob_nav}\n{oob_profile}"
        )
    full_html = TEMPLATES.get_template("base.html").render(
        ctx_dict,
        content=inner,
        partial=partial_name,
        **{k: v for k, v in ctx.items() if k != "content"},
    )
    return HTMLResponse(full_html)


def partial(request: Request, frag_name: str, **ctx: Any) -> HTMLResponse:
    """Render a fragment partial (e.g. 'panels.html#toast').

    The ``#fragment`` suffix selects which block inside ``partials/panels.html``
    the template emits; it is *not* part of the file path, so we split it off
    before calling get_template and pass the full name back as the ``partial``
    context variable the template conditions compare against.
    """
    template_path, _, fragment = frag_name.partition("#")
    if fragment:
        ctx.setdefault("partial", frag_name)
    return HTMLResponse(
        TEMPLATES.get_template(template_path).render(base_ctx(request, **ctx))
    )


def crumb_for(view: tuple[str, str]) -> str:
    kind, key = view
    if kind == "tab" and key in REGISTRY.tabs:
        return f"{REGISTRY.tabs[key].section} · {' '.join(REGISTRY.tabs[key].command)}"
    if kind == "config":
        return "configuration"
    return "overview"


# ──────────────────────────────────────────────────────────────────────
# Page routes
# ──────────────────────────────────────────────────────────────────────
async def home(request: Request) -> Response:
    s = ensure_loaded(request)
    kind, key = s.get("view", ("overview", ""))
    if kind == "tab" and key in REGISTRY.tabs:
        return await tab_page(request)
    if kind == "config":
        return await config_page(request)
    return await overview_page(request)


async def overview_page(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    s["view"] = ("overview", "")
    groups = {
        "upload": [k for k, t in REGISTRY.tabs.items() if t.section == "upload"],
        "archive": [k for k, t in REGISTRY.tabs.items() if t.section == "archive"],
        "stack": [k for k, t in REGISTRY.tabs.items() if t.section == "stack"],
    }
    recent = [RUNS.runs[r] for r in reversed(RUNS.order) if r in RUNS.runs][:6]
    # Merge persisted history (survives restarts) with in-memory runs so the
    # Rebuild action remains available after the process restarts.
    seen = {r.run_id for r in recent}
    for entry in reversed(HISTORY.entries()):
        if entry.get("run_id") in seen:
            continue
        seen.add(entry["run_id"])
        recent.append(
            SimpleNamespace(
                run_id=entry["run_id"],
                tab_key=entry.get("tab_key", "?"),
                display_cmd=entry.get("display_cmd", ""),
                started_at=entry.get("started_at", ""),
                finished=True,
                exit_code=0,
                dry=bool(entry.get("dry", False)),
                rebuildable=True,
            )
        )
        if len(recent) >= 6:
            break
    return page(
        request,
        "partials/overview.html",
        groups=groups,
        tabs=REGISTRY.tabs,
        commands=REGISTRY.tab_commands,
        serverless=REGISTRY.serverless_tabs,
        recent=recent,
        rebuildable=HISTORY.ids(),
        crumb="overview",
    )


async def tab_page(request: Request, tab_key: str | None = None) -> Response:
    key = tab_key or request.path_params.get("tab", "")
    if key not in REGISTRY.tabs:
        return RedirectResponse("/overview", status_code=303)
    s = ensure_loaded(request)
    s["view"] = ("tab", key)
    s["tab_state"].setdefault(key, initial_tab_state(key))
    tabdef = REGISTRY.tabs[key]
    sibling_keys = [k for k, t in REGISTRY.tabs.items() if t.section == tabdef.section]
    sub_tabs = [{"key": k, "label": _SUB_TAB_LABELS.get(k, k)} for k in sibling_keys]
    return page(
        request,
        "partials/tab_form.html",
        tab=key,
        tabdef=tabdef,
        command=REGISTRY.tab_commands[key],
        src_flags=source_flags(key),
        opt_flags=option_flags(key),
        adv_defs=REGISTRY.advanced_defs(key),
        st=s["tab_state"][key],
        adv=adv_state_for(request, key),
        presets=presets_for(key),
        cfg=current_config_state(request),
        serverless=key in SERVERLESS_TABS,
        sub_tabs=sub_tabs,
        crumb=crumb_for(("tab", key)),
    )


async def section_page(request: Request) -> Response:
    """Render the first (or last-active) tab within a workflow section.

    Mirrors the desktop app's sidebar: clicking "Upload" lands on the upload
    page with horizontal sub-tabs.  If the session already holds a tab in the
    requested section, re-use it so the user returns to where they left off.
    """
    section = request.path_params["section"]
    tabs_in_section = [k for k, t in REGISTRY.tabs.items() if t.section == section]
    if not tabs_in_section:
        return RedirectResponse("/overview", status_code=303)
    s = ensure_loaded(request)
    kind, key = s.get("view", ("overview", ""))
    if kind == "tab" and key in tabs_in_section:
        return await tab_page(request, tab_key=key)
    return await tab_page(request, tab_key=tabs_in_section[0])


def adv_state_for(request: Request, key: str) -> dict[str, Any]:
    s = ensure_loaded(request)
    defs = REGISTRY.advanced_defs(key)
    stored = s["adv_state"].get(key, {})
    return {
        d.key: stored.get(d.key, {"enabled": False, "value": d.default}) for d in defs
    }


async def config_page(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    s["view"] = ("config", "")
    cfg = s["config"]
    from core.config_manager import default_secrets_path

    last_conn = s.get("conn") or {}
    binary = BINMGR.check_binary()
    checklist = {
        "dismissed": bool(s.get("checklist_dismissed")),
        "server": bool(cfg.server_url),
        "api_key": bool(s["secrets"].get("api_key")),
        "conn": bool(last_conn.get("ok")),
        "binary": binary.state == "ok",
        "dry_run": bool(RUNS.order),
    }

    return page(
        request,
        "partials/config.html",
        cfg=cfg,
        secrets=s["secrets"],
        secrets_path=default_secrets_path(),
        keyring_available=_keyring_available(),
        checklist=checklist,
        binary_status=binary,
        binary_path=BINMGR.resolve_binary_path(),
        manual_path=load_binary_metadata().get("manual_path", ""),
        crumb="configuration",
    )


# ──────────────────────────────────────────────────────────────────────
# Config endpoints
# ──────────────────────────────────────────────────────────────────────
async def config_save_server(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    form = dict(await request.form())
    cfg = s["config"]
    prof = cfg.profile_name
    url = str(form.get("server") or "").strip()
    cfg.server_url = url
    save_server_url(url, path=default_config_path(prof), profile_name=prof)
    res = save_secret_with_fallback(
        prof, "api_key", str(form.get("api_key") or "").strip(), cfg.secrets_provider
    )
    s["secrets"]["api_key"] = str(form.get("api_key") or "").strip()
    note = res.message or "Server connection saved."
    return partial(request, "partials/panels.html#toast", toast=note, tone="ok")


async def config_save_app(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    form = dict(await request.form())
    cfg = s["config"]
    cfg.skip_ssl = form.get("skip_ssl") == "on"
    try:
        cfg.client_timeout_minutes = max(
            5, min(240, int(form.get("client_timeout_minutes") or 60))
        )
    except ValueError:
        pass
    cfg.secrets_provider = str(form.get("secret_provider") or "keyring")
    if cfg.secrets_provider == "fallback":
        cfg.secrets_provider = "config"
    cfg.allow_untested_updates = form.get("allow_untested_updates") == "on"
    cfg.preferred_terminal = str(form.get("preferred_terminal") or "auto")
    cfg.advanced_mode = form.get("advanced_mode") == "on"
    save_config(cfg, profile_name=cfg.profile_name)
    save_secret_with_fallback(
        cfg.profile_name,
        "admin_api_key",
        str(form.get("admin_api_key") or "").strip(),
        cfg.secrets_provider,
    )
    s["secrets"]["admin_api_key"] = str(form.get("admin_api_key") or "").strip()
    return partial(
        request, "partials/panels.html#toast", toast="Configuration saved.", tone="ok"
    )


async def config_test_connection(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    form = dict(await request.form())
    res = test_immich_connection(
        str(form.get("server") or "").strip(),
        str(form.get("api_key") or "").strip(),
        skip_ssl=form.get("skip_ssl") == "on",
    )
    s["conn"] = {
        "ok": bool(res.ok),
        "message": res.message,
        "server_version": getattr(res, "server_version", "") or "",
    }
    return partial(
        request,
        "partials/panels.html#conn_result",
        conn=res,
        toast=res.message,
        tone="ok" if res.ok else "err",
    )


async def test_connection_chip(request: Request) -> Response:
    """Ambient (debounced) connection check returning JSON for the inline chip."""
    s = ensure_loaded(request)
    form = dict(await request.form())
    res = test_immich_connection(
        str(form.get("server") or "").strip(),
        str(form.get("api_key") or "").strip(),
        skip_ssl=form.get("skip_ssl") == "on",
    )
    server_version = getattr(res, "server_version", "") or ""
    s["conn"] = {
        "ok": bool(res.ok),
        "message": res.message,
        "server_version": server_version,
    }
    return Response(
        content=json.dumps(
            {
                "ok": bool(res.ok),
                "message": res.message,
                "server_version": server_version,
            }
        ),
        media_type="application/json",
    )


async def checklist_dismiss(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    s["checklist_dismissed"] = True
    return partial(
        request,
        "partials/panels.html#toast",
        toast="First-run checklist dismissed.",
        tone="ok",
    )


async def mode_toggle(request: Request) -> Response:
    s = ensure_loaded(request)
    cfg = s["config"]
    cfg.advanced_mode = not cfg.advanced_mode
    save_config(cfg, profile_name=cfg.profile_name)
    kind, key = s.get("view", ("overview", ""))
    if kind == "tab" and key in REGISTRY.tabs:
        return await tab_page(request, tab_key=key)
    if kind == "config":
        return await config_page(request)
    return await overview_page(request)


async def theme_set(request: Request) -> Response:
    form = dict(await request.form())
    resp = Response(status_code=204)
    resp.set_cookie(
        "igg_theme",
        str(form.get("theme", "dark")),
        max_age=86400 * 365,
        httponly=False,
        samesite="lax",
    )
    return resp


def _tokenize_plan(plan: Any) -> list[dict]:
    """Map a plan's masked display argv to color-coded {arg, source} tokens."""
    source_map = {
        str(e.get("key", "")): e.get("source", "static") for e in plan.emission_log
    }
    tokens = []
    for arg in plan.display_argv:
        flag = arg.lstrip("-").split("=", 1)[0]
        tokens.append({"arg": arg, "source": source_map.get(flag, "static")})
    return tokens


async def tab_live_preview(request: Request) -> HTMLResponse:
    """Debounced live command ribbon (proposal P1). Builds a plan server-side
    and returns masked argv tokens color-coded by emission source, plus the
    active safety warnings shelf."""
    key = request.path_params["tab"]
    s = ensure_loaded(request)
    if key not in REGISTRY.tabs:
        return Response(status_code=404)
    form = dict(await request.form())
    config_state = current_config_state(request)
    tab_state = parse_tab_state(key, form)
    advanced_state = (
        parse_advanced_state(key, form) if s["config"].advanced_mode else None
    )
    binary_path = get_binary_path(load_binary_metadata()) or "./immich-go"
    plan = build_plan_from_state(
        tab_key=key,
        config_state=config_state,
        tab_state=tab_state,
        binary_path=binary_path,
        dry_run=False,
        advanced_state=advanced_state,
    )
    return partial(
        request,
        "partials/panels.html#live_ribbon",
        tokens=_tokenize_plan(plan),
        warnings=plan.warnings,
    )


# ──────────────────────────────────────────────────────────────────────
# Tab form endpoints: preview → confirm → run
# ──────────────────────────────────────────────────────────────────────
async def tab_preview(request: Request) -> HTMLResponse:
    key = request.path_params["tab"]
    s = ensure_loaded(request)
    form = dict(await request.form())
    dry = form.get("dry") == "1"

    config_state = current_config_state(request)
    tab_state = parse_tab_state(key, form)
    advanced_state = (
        parse_advanced_state(key, form) if s["config"].advanced_mode else None
    )

    s["tab_state"][key] = tab_state
    if advanced_state is not None:
        s["adv_state"][key] = advanced_state

    res = validate_state(key, config_state, tab_state)
    adv_res = validate_advanced_state(key, advanced_state or {})
    res.errors.extend(adv_res.errors)
    res.warnings.extend(adv_res.warnings)

    if res.errors:
        modal = partial(
            request,
            "partials/panels.html#errors",
            tab=key,
            errors=res.errors,
            field_errors=res.field_errors,
            dry=dry,
        )
        # Inline per-field errors: out-of-band swap each field's error span so it
        # renders red text directly under the offending control (in addition to
        # the modal summary). See macros.html render_flag_field.
        oob = "".join(
            f'<span id="field-err-{k}" class="field-error" '
            f'hx-swap-oob="outerHTML:#field-err-{k}">{v}</span>'
            for k, v in res.field_errors.items()
        )
        return HTMLResponse(modal.body.decode("utf-8") + oob)

    binary_path = get_binary_path(load_binary_metadata()) or "./immich-go"
    plan = build_plan_from_state(
        tab_key=key,
        config_state=config_state,
        tab_state=tab_state,
        binary_path=binary_path,
        dry_run=dry,
        advanced_state=advanced_state,
    )
    if plan.errors:
        return partial(
            request,
            "partials/panels.html#errors",
            tab=key,
            errors=plan.errors,
            field_errors={},
            dry=dry,
        )

    preflight = None
    if key in SERVER_REQUIRED_TABS:
        preflight = check_preflight_server_connection(
            key, config_state, tab_state, timeout=3.0
        )
        if not preflight.ok:
            plan.warnings.insert(
                0, f"Server pre-flight check failed: {preflight.message}"
            )

    env_rows = sorted((k, v) for k, v in plan.env.items() if k.startswith("IMMICH_GO_"))
    masked_env = [
        (k, "********" if any(m in k for m in SECRET_ENV_MARKERS) else v)
        for k, v in env_rows
    ]

    nonce = secrets.token_hex(8)
    s["pending"][nonce] = plan
    s["pending"] = dict(list(s["pending"].items())[-5:])

    return partial(
        request,
        "partials/confirm.html",
        plan=plan,
        nonce=nonce,
        dry=dry,
        tab=key,
        cmd_str=" ".join(shlex.quote(p) for p in plan.display_argv),
        env_rows=masked_env,
        preflight=preflight,
        emission_log=plan.emission_log,
    )


async def run_start(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    form = dict(await request.form())
    plan = s["pending"].get(str(form.get("nonce", "")))
    if plan is None:
        return partial(
            request,
            "partials/panels.html#toast",
            toast="Preview expired — preview again.",
            tone="err",
        )

    status = BINMGR.check_binary()
    if status.state == "err":
        return partial(
            request,
            "partials/panels.html#toast",
            toast="immich-go binary missing — download it from Configuration → Binary Management.",
            tone="err",
        )
    try:
        run = RUNS.start(plan, plan.binary_path)
    except RunInProgress as e:
        return partial(request, "partials/panels.html#toast", toast=str(e), tone="err")
    HISTORY.record(
        run_id=run.run_id,
        tab_key=run.tab_key,
        dry=run.dry_run,
        warnings=len(plan.warnings),
        display_cmd=run.display_cmd,
        raw_state=s["tab_state"].get(run.tab_key, {}),
    )
    s["view"] = ("run", run.run_id)
    return page(
        request, "partials/run_panel.html", run=run, crumb=f"run · {run.tab_key}"
    )


async def run_rebuild(request: Request) -> Response:
    """Rehydrate a previous run's (non-secret) form state into the session."""
    s = ensure_loaded(request)
    entry = HISTORY.get(request.path_params["rid"])
    if not entry:
        return partial(
            request,
            "partials/panels.html#toast",
            toast="No saved state for that run.",
            tone="err",
        )
    tab = entry.get("tab_key", "")
    if tab not in REGISTRY.tabs:
        return partial(
            request,
            "partials/panels.html#toast",
            toast="That workflow no longer exists.",
            tone="err",
        )
    current = s["tab_state"].get(tab, {})
    # Secret fields (e.g. source API keys) were stripped when stored, so they
    # stay blank for re-entry while everything else is restored.
    s["tab_state"][tab] = {**current, **entry.get("tab_state", {})}
    s["view"] = ("tab", tab)
    return HTMLResponse("", status_code=204, headers={"HX-Redirect": f"/tab/{tab}"})


async def run_panel_page(request: Request) -> Response:
    rid = request.path_params["rid"]
    run = RUNS.runs.get(rid)
    if not run:
        return RedirectResponse("/", status_code=303)
    return page(
        request, "partials/run_panel.html", run=run, crumb=f"run · {run.tab_key}"
    )


async def run_stream(request: Request) -> Response:
    run = RUNS.runs.get(request.path_params["rid"])
    if not run:
        return Response(status_code=404)

    async def gen():
        cursor = 0
        yield "retry: 1500\n\n"
        while True:
            new, cursor = run.snapshot(cursor)
            for kind, text in new:
                payload = json.dumps({"k": kind, "h": text})
                yield f"event: line\ndata: {payload}\n\n"
            if run.finished and cursor >= run.total:
                chip = (
                    '<span class="chip ok">exit 0</span>'
                    if run.exit_code == 0
                    else f'<span class="chip err">exit {run.exit_code}</span>'
                )
                yield f"event: done\ndata: {json.dumps({'chip': chip})}\n\n"
                break
            if await request.is_disconnected():
                break
            await asyncio.sleep(0.25)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def run_stop(request: Request) -> HTMLResponse:
    run = RUNS.stop(request.path_params["rid"])
    tone = "ok" if run and not run.finished else "warn"
    return partial(
        request, "partials/panels.html#toast", toast="Stop signal sent.", tone=tone
    )


async def run_state_reset(request: Request) -> HTMLResponse:
    n = RUNS.reset_all()
    return partial(
        request,
        "partials/panels.html#toast",
        toast=f"Run state reset ({n} locks cleared).",
        tone="ok",
    )


async def advanced_reset(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    s["adv_state"] = {}
    return partial(
        request,
        "partials/panels.html#toast",
        toast="Advanced flags reset to defaults.",
        tone="ok",
    )


# ──────────────────────────────────────────────────────────────────────
# Status / binary / updates / diagnostics
# ──────────────────────────────────────────────────────────────────────
async def status_partial(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    st = BINMGR.check_binary()
    cfg_state = current_config_state(request)
    if cfg_state["server"] and cfg_state["api_key"]:
        srv = ("ok", "Server: Configured")
    else:
        srv = ("err", "Server: Not Set")
    conn = s.get("conn")
    active = RUNS.active()
    locks = scan_locks()
    return partial(
        request,
        "partials/status.html",
        binary=st,
        srv=srv,
        conn=conn,
        active=active,
        locked=bool(locks) or RUNS.is_busy(),
    )


DL_STATE: dict[str, Any] = {
    "active": False,
    "pct": 0,
    "done": False,
    "ok": False,
    "msg": "",
    "version": "",
    "cancel": False,
}


async def binary_check_updates(request: Request) -> HTMLResponse:
    s = ensure_loaded(request)
    current = BINMGR.check_binary().version_text
    latest = BINMGR.get_latest_version()
    decision = None
    if latest and clean_version(current) != clean_version(latest):
        notes = BINMGR.get_release_notes(latest)
        decision = BINMGR.evaluate_update(
            current,
            latest,
            allow_untested=s["config"].allow_untested_updates,
            release_notes=notes,
        )
    return partial(
        request,
        "partials/panels.html#binary_update",
        latest=latest,
        current=current,
        decision=decision,
        allow_untested=s["config"].allow_untested_updates,
    )


async def config_reload(request: Request) -> HTMLResponse:
    """Reload config + secrets from disk into the session (File -> Load Config)."""
    s = ensure_loaded(request)
    for k in ("config", "secrets", "conn"):
        s.pop(k, None)
    ensure_loaded(request)
    return partial(
        request,
        "partials/panels.html#toast",
        toast="Configuration reloaded from disk.",
        tone="ok",
    )


async def config_download(request: Request) -> Response:
    """Download a redacted representation of the active configuration."""
    cfg = load_config()
    redacted = {
        k: (
            "***redacted***"
            if any(s in k for s in ("key", "secret", "token", "password"))
            else v
        )
        for k, v in cfg.__dict__.items()
    }
    text = "\n".join(f"{k} = {v!r}" for k, v in sorted(redacted.items()))
    return Response(
        content=text,
        media_type="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="immich-go-gui-config.txt"'
        },
    )


async def logs_tail(request: Request) -> Response:
    """Return the last N lines of the app log file."""
    from core.config_manager import default_config_dir

    log_file = default_config_dir() / "logs" / "immich-go-gui.log"
    if not log_file.exists():
        return Response(content="(no log file yet)", media_type="text/plain")
    try:
        tail = "".join(
            log_file.read_text(encoding="utf-8", errors="replace").splitlines(
                keepends=True
            )[-100:]
        )
    except OSError:
        tail = "(log file unreadable)"
    return Response(content=tail, media_type="text/plain")


async def about_partial(request: Request) -> HTMLResponse:
    from core.binary_manager import TESTED_IMMICH_GO_VERSION

    return partial(
        request,
        "partials/panels.html#about",
        about_text=(
            "Immich-Go Web Console is a Docker/HTMX web interface for the "
            "immich-go CLI, providing 1:1 parity with the desktop GUI."
        ),
        cli_target=TESTED_IMMICH_GO_VERSION,
    )


async def binary_download(request: Request) -> HTMLResponse:
    form = dict(await request.form())
    version = str(form.get("version") or "").strip()
    if not version or DL_STATE["active"]:
        return partial(
            request,
            "partials/panels.html#toast",
            toast="Download already in progress or missing version.",
            tone="err",
        )
    DL_STATE.update(
        active=True, pct=0, done=False, ok=False, msg="", version=version, cancel=False
    )

    def work() -> None:
        ok, msg = BINMGR.download_and_install(
            version=version,
            progress_cb=lambda p: DL_STATE.update(pct=p),
            cancel_check=lambda: bool(DL_STATE["cancel"]),
        )
        DL_STATE.update(active=False, done=True, ok=ok, msg=msg)

    threading.Thread(target=work, daemon=True).start()
    return partial(request, "partials/panels.html#dl_live", version=version)


async def binary_download_events(request: Request) -> StreamingResponse:
    async def gen():
        yield "retry: 1500\n\n"
        while True:
            yield f"event: progress\ndata: {json.dumps({'pct': DL_STATE['pct']})}\n\n"
            if DL_STATE["done"]:
                tone = "ok" if DL_STATE["ok"] else "err"
                yield f"event: done\ndata: {json.dumps({'msg': DL_STATE['msg'], 'tone': tone})}\n\n"
                break
            if await request.is_disconnected():
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


async def binary_download_cancel(request: Request) -> HTMLResponse:
    DL_STATE["cancel"] = True
    return partial(
        request, "partials/panels.html#toast", toast="Cancelling download…", tone="warn"
    )


async def binary_manual_path(request: Request) -> HTMLResponse:
    form = dict(await request.form())
    meta = load_binary_metadata()
    meta["manual_path"] = str(form.get("manual_path") or "").strip()
    save_binary_metadata(meta)
    return partial(
        request,
        "partials/panels.html#toast",
        toast="Manual binary path updated.",
        tone="ok",
    )


async def app_update_check(request: Request) -> HTMLResponse:
    installed = gui_version()
    rel = get_latest_gui_release()
    toast_url = None
    if rel is None:
        msg, tone = "Could not reach GitHub to check for updates.", "err"
    elif not is_parseable_semver(installed):
        msg, tone = f"Development build - latest release is v{rel.version}.", "warn"
        toast_url = rel.html_url
    elif is_update_available(installed, rel.version):
        msg, tone = f"Update available: v{rel.version} (you run {installed}).", "warn"
        toast_url = rel.html_url
    else:
        msg, tone = f"Up to date (v{installed}).", "ok"
    return partial(
        request,
        "partials/panels.html#toast",
        toast=msg,
        tone=tone,
        toast_url=toast_url,
    )


async def compat_partial(request: Request) -> HTMLResponse:
    from core.binary_manager import TESTED_IMMICH_GO_VERSION

    report = check_fixtures(TESTED_IMMICH_GO_VERSION)
    live = None
    bp = BINMGR.resolve_binary_path()
    if bp and Path(bp).exists():
        live = check_binary_help(Path(bp), TESTED_IMMICH_GO_VERSION)

    rows: dict[str, dict] = {}
    for tab_key in REGISTRY.tabs:
        # Merge the fixture-derived report with the live binary help scan (if any),
        # mirroring the desktop show_cli_compatibility_dialog behavior.
        missing = set(report.missing_flags_by_tab.get(tab_key, set()))
        unknown = set(report.unknown_flags_by_tab.get(tab_key, set()))
        if live is not None:
            missing |= set(live.missing_flags_by_tab.get(tab_key, set()))
            unknown |= set(live.unknown_flags_by_tab.get(tab_key, set()))
        rows[tab_key] = {
            "ok": not missing,
            "missing_flags": sorted(missing),
            "unknown_flags": sorted(unknown),
        }
    return partial(
        request,
        "partials/panels.html#compat",
        report=rows,
        tested=TESTED_IMMICH_GO_VERSION,
    )


async def diagnostics_zip(request: Request) -> Response:
    data = build_diagnostics_zip()
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="immich-go-diagnostics-{gui_version()}.zip"'
        },
    )


# ──────────────────────────────────────────────────────────────────────
# Profiles
# ──────────────────────────────────────────────────────────────────────
async def profiles_partial(request: Request) -> HTMLResponse:
    return partial(
        request,
        "partials/profiles.html",
        profiles=list_profiles(),
        active=active_profile_name(),
    )


async def profile_switch(request: Request) -> Response:
    s = ensure_loaded(request)
    form = dict(await request.form())
    name = str(form.get("name") or "").strip()
    action = form.get("action", "switch")
    dirty = form.get("dirty") == "1"

    if dirty and action == "switch":
        return partial(request, "partials/panels.html#profile_prompt", name=name)
    if action == "save":
        cfg = s["config"]
        save_config(cfg, profile_name=cfg.profile_name)
        save_secret_with_fallback(
            cfg.profile_name,
            "api_key",
            s["secrets"].get("api_key", ""),
            cfg.secrets_provider,
        )
        save_secret_with_fallback(
            cfg.profile_name,
            "admin_api_key",
            s["secrets"].get("admin_api_key", ""),
            cfg.secrets_provider,
        )
    set_active_profile_name(name)
    for k in ("config", "secrets", "tab_state", "adv_state", "pending"):
        s.pop(k, None)
    ensure_loaded(request)
    resp = Response(status_code=204)
    resp.headers["HX-Refresh"] = "true"
    return resp


async def profile_create(request: Request) -> HTMLResponse:
    form = dict(await request.form())
    name = str(form.get("name") or "").strip()
    existing = [p.name for p in list_profiles()]
    ok, err = validate_profile_name(name, existing)
    if not ok:
        return partial(
            request,
            "partials/panels.html#toast",
            toast=err or "Invalid profile name.",
            tone="err",
        )
    copy_from = str(form.get("copy_from")) if form.get("copy_from") else None
    create_profile(name, copy_from=copy_from)
    return partial(
        request,
        "partials/panels.html#toast",
        toast=f"Profile '{name}' created.",
        tone="ok",
    )


async def profile_duplicate(request: Request) -> HTMLResponse:
    form = dict(await request.form())
    name = str(form.get("name") or "").strip()
    try:
        duplicate_profile(active_profile_name(), name)
    except ValueError as e:
        return partial(request, "partials/panels.html#toast", toast=str(e), tone="err")
    return partial(
        request,
        "partials/panels.html#toast",
        toast=f"Duplicated to '{name}'.",
        tone="ok",
    )


async def profile_rename(request: Request) -> Response:
    form = dict(await request.form())
    try:
        rename_profile(active_profile_name(), str(form.get("name") or "").strip())
    except ValueError as e:
        return partial(request, "partials/panels.html#toast", toast=str(e), tone="err")
    resp = Response(status_code=204)
    resp.headers["HX-Refresh"] = "true"
    return resp


async def profile_delete(request: Request) -> Response:
    try:
        delete_profile(active_profile_name())
    except ValueError as e:
        return partial(request, "partials/panels.html#toast", toast=str(e), tone="err")
    resp = Response(status_code=204)
    resp.headers["HX-Refresh"] = "true"
    return resp


# ──────────────────────────────────────────────────────────────────────
# Auth pages
# ──────────────────────────────────────────────────────────────────────
async def login_page(request: Request) -> HTMLResponse:
    return HTMLResponse(
        TEMPLATES.get_template("login.html").render(
            {
                "request": request,
                "error": False,
                "csrf": request.cookies.get(authmod.CSRF_COOKIE, ""),
            }
        )
    )


async def login_post(request: Request) -> Response:
    form = dict(await request.form())
    if not check_login(str(form.get("user", "")), str(form.get("password", ""))):
        return HTMLResponse(
            TEMPLATES.get_template("login.html").render(
                {
                    "request": request,
                    "error": True,
                    "csrf": request.cookies.get(authmod.CSRF_COOKIE, ""),
                }
            )
        )
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(AUTH_COOKIE, "1", httponly=True, samesite="lax")
    return resp


async def logout(request: Request) -> Response:
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        drop_session(sid)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(AUTH_COOKIE)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


async def healthz(request: Request) -> Response:
    return Response("ok", media_type="text/plain")


# ──────────────────────────────────────────────────────────────────────
# Session cookie issuance + app factory
# ──────────────────────────────────────────────────────────────────────
async def session_cookies_middleware(request: Request, call_next: Any) -> Response:
    resp = await call_next(request)
    sid = getattr(request.state, "new_sid", None)
    if sid and not request.cookies.get(SESSION_COOKIE):
        resp.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="lax")
    if not request.cookies.get(authmod.CSRF_COOKIE):
        resp.set_cookie(
            authmod.CSRF_COOKIE,
            secrets.token_urlsafe(24),
            httponly=False,
            samesite="lax",
        )
    return resp


def create_app() -> Starlette:
    cleanup_stale_locks()

    routes = [
        Route("/", home),
        Route("/overview", overview_page),
        Route("/tab/{tab}", tab_page),
        Route("/section/{section}", section_page),
        Route("/config", config_page),
        Route("/healthz", healthz),
        Route("/login", login_page, methods=["GET"]),
        Route("/login", login_post, methods=["POST"]),
        Route("/logout", logout),
        # tab workflow
        Route("/tabs/{tab}/preview", tab_preview, methods=["POST"]),
        Route("/tabs/{tab}/live-preview", tab_live_preview, methods=["POST"]),
        Route("/runs", run_start, methods=["POST"]),
        Route("/run/{rid}", run_panel_page),
        Route("/runs/{rid}/stream", run_stream),
        Route("/runs/{rid}/stop", run_stop, methods=["POST"]),
        Route("/runs/{rid}/rebuild", run_rebuild, methods=["POST"]),
        Route("/run-state/reset", run_state_reset, methods=["POST"]),
        Route("/advanced/reset", advanced_reset, methods=["POST"]),
        # config
        Route("/config/save-server", config_save_server, methods=["POST"]),
        Route("/config/save", config_save_app, methods=["POST"]),
        Route("/config/test-connection", config_test_connection, methods=["POST"]),
        Route("/config/test-connection-async", test_connection_chip, methods=["POST"]),
        Route("/config/reload", config_reload, methods=["POST"]),
        Route("/config/download", config_download),
        Route("/logs/tail", logs_tail),
        Route("/partial/about", about_partial),
        Route("/checklist/dismiss", checklist_dismiss, methods=["POST"]),
        Route("/mode/toggle", mode_toggle, methods=["POST"]),
        Route("/theme", theme_set, methods=["POST"]),
        # ops
        Route("/partial/status", status_partial),
        Route("/binary/check", binary_check_updates, methods=["POST"]),
        Route("/binary/download", binary_download, methods=["POST"]),
        Route("/binary/download/events", binary_download_events),
        Route("/binary/download/cancel", binary_download_cancel, methods=["POST"]),
        Route("/binary/manual-path", binary_manual_path, methods=["POST"]),
        Route("/app-update/check", app_update_check, methods=["POST"]),
        Route("/partial/compat", compat_partial),
        Route("/diagnostics.zip", diagnostics_zip),
        # profiles
        Route("/partial/profiles", profiles_partial),
        Route("/profiles/switch", profile_switch, methods=["POST"]),
        Route("/profiles/create", profile_create, methods=["POST"]),
        Route("/profiles/duplicate", profile_duplicate, methods=["POST"]),
        Route("/profiles/rename", profile_rename, methods=["POST"]),
        Route("/profiles/delete", profile_delete, methods=["POST"]),
        Mount(
            "/static", app=StaticFiles(directory=str(BASE / "static")), name="static"
        ),
    ]

    app = Starlette(
        debug=False,
        routes=routes,
        middleware=[
            Middleware(AuthMiddleware),
            Middleware(BaseHTTPMiddleware, dispatch=session_cookies_middleware),
        ],
    )
    return app
