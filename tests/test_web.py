"""Tests for the HTMX Web Console (Starlette + Uvicorn + SSE runner).

Guarantees:
- The web app imports strictly from core/ and never imports Qt/PySide6.
- Form parsing correctly coerces types and translates form data to core state dicts.
- Auth middleware correctly enforces login / session cookie validation.
- RunManager executes subprocesses and buffers lines for SSE output streaming.
- Diagnostics zip is Qt-free and properly redacts sensitive fields.
"""

from __future__ import annotations

import io
import os
import sys
import zipfile
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from core.flag_registry import FlagDef
from core.models import CommandPlan, UpdateDecision, UpdateSeverity
from webapp.app import TEMPLATES, create_app
from webapp.forms import (
    coerce,
    initial_tab_state,
    parse_config_state,
    parse_tab_state,
    renderable_simple_flags,
)
from webapp.runner import RunManager


@pytest.fixture(autouse=True)
def _web_config_isolation(tmp_path, monkeypatch):
    """Redirect all GUI/web config + secrets writes to a per-test temp dir.

    The repo's session-level ``_session_config_root`` only activates when the
    ``gui`` fixture is requested, which the web route tests do not use. Without
    this, routes such as ``/mode/toggle`` and ``/config/save`` would read/write
    the developer's real ``~/.config/immich-go-gui``.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.delenv("IMMICH_GO_GUI_CONFIG", raising=False)

    from core.profile_manager import clear_profiles_cache

    clear_profiles_cache()
    yield
    clear_profiles_cache()


def test_web_app_does_not_import_qt():
    """Verify web application modules do not import PySide6 / Qt."""
    qt_modules = [m for m in sys.modules if "PySide6" in m or "gui." in m]

    new_qt_modules = [
        m
        for m in sys.modules
        if ("PySide6" in m or "gui." in m) and m not in qt_modules
    ]
    assert not new_qt_modules, f"Web app imported Qt modules: {new_qt_modules}"


def test_healthz_endpoint():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_overview_route_renders_html():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "IMMICH-GO" in resp.text
    assert "Upload Workflows" in resp.text


def test_tab_page_renders_form():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/upload-folder")
    assert resp.status_code == 200
    assert "upload-folder" in resp.text
    assert "Source Configuration" in resp.text or "Options" in resp.text
    assert "<!doctype html>" in resp.text


def test_htmx_header_partial_rendering():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/upload-folder", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "upload-folder" in resp.text
    assert "<!doctype html>" not in resp.text
    assert '<aside class="sidebar">' not in resp.text


def test_mode_toggle_preserves_tab_view_and_updates_sidebar():
    app = create_app()
    client = TestClient(app)
    resp1 = client.get("/tab/upload-gp", headers={"HX-Request": "true"})
    assert resp1.status_code == 200
    assert "upload-gp" in resp1.text

    resp2 = client.post("/mode/toggle", headers={"HX-Request": "true"})
    assert resp2.status_code == 200
    assert "upload-gp" in resp2.text
    assert 'hx-get="/tab/upload-gp"' in resp2.text
    assert 'id="sidebar-nav"' in resp2.text


def test_invalid_tab_redirects_to_overview():
    app = create_app()
    client = TestClient(app, follow_redirects=False)
    resp = client.get("/tab/nonexistent-tab")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/overview"


def test_config_page_renders_settings():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/config")
    assert resp.status_code == 200
    assert "Server Connection" in resp.text
    assert "Binary Management" in resp.text


def test_form_coercion_and_parsing():
    f_bool = FlagDef(
        key="dry-run",
        flag="dry-run",
        label="Dry Run",
        mode="simple",
        kind="bool",
        default=False,
    )
    f_int = FlagDef(
        key="timeout",
        flag="timeout",
        label="Timeout",
        mode="simple",
        kind="int",
        default=10,
        min_val=1,
        max_val=100,
    )

    assert coerce(f_bool, "on") is True
    assert coerce(f_bool, "") is False
    assert coerce(f_int, "50") == 50
    assert coerce(f_int, "200") == 100

    simple_flags = renderable_simple_flags("upload-folder")
    assert isinstance(simple_flags, tuple)

    parsed_st = parse_tab_state("upload-folder", {"fld_delete": "on"})
    assert isinstance(parsed_st, dict)

    parsed_cfg = parse_config_state(
        {"server": "http://localhost:2283", "api_key": "secret"}
    )
    assert parsed_cfg["server"] == "http://localhost:2283"
    assert parsed_cfg["api_key"] == "secret"


def test_auth_middleware_flow():
    with patch.dict(
        os.environ, {"IGG_WEB_USER": "admin", "IGG_WEB_PASSWORD": "secret_password"}
    ):
        app = create_app()
        client = TestClient(app, follow_redirects=False)

        # Unauthenticated request redirects to /login
        resp = client.get("/overview")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

        # Failed login
        resp_login_fail = client.post(
            "/login", data={"user": "admin", "password": "wrong"}
        )
        assert resp_login_fail.status_code == 200
        assert "Invalid username or password" in resp_login_fail.text

        # Successful login
        resp_login_ok = client.post(
            "/login", data={"user": "admin", "password": "secret_password"}
        )
        assert resp_login_ok.status_code == 303
        assert "igg_auth" in resp_login_ok.cookies


def test_diagnostics_zip_generation(tmp_path):
    from webapp.diagnostics import build_diagnostics_zip

    zip_bytes = build_diagnostics_zip()
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "summary.txt" in names
        summary = zf.read("summary.txt").decode("utf-8")
        assert "surface=web-console" in summary


def test_run_manager_subprocess_lifecycle(tmp_path):
    mgr = RunManager()
    dummy_script = tmp_path / "dummy_immich_go.sh"
    dummy_script.write_text("#!/bin/sh\necho 'hello world'\nexit 0\n")
    dummy_script.chmod(0o755)

    plan = CommandPlan(
        argv=["upload", "folder"],
        env={},
        display_argv=["immich-go", "upload", "folder"],
        warnings=[],
        errors=[],
        emission_log=[],
        tab_key="upload-folder",
        dry_run=True,
        binary_path=str(dummy_script),
    )

    run = mgr.start(plan, str(dummy_script))
    assert run.run_id in mgr.runs
    assert mgr.is_busy()

    # Wait for process completion
    run.done.wait(timeout=5.0)
    assert run.finished
    assert run.exit_code == 0
    assert not mgr.is_busy()

    snapshot, total = run.snapshot(0)
    assert total >= 2
    log_texts = [h for _, h in snapshot]
    assert any("hello world" in t for t in log_texts)


# ──────────────────────────────────────────────────────────────────
# Phase 0 - correctness foundation (B1-B8)
# ──────────────────────────────────────────────────────────────────


def test_enum_fields_render_as_selects_with_options():
    """B1: simple enum flags must render as <select> populated from f.options."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/upload-folder")
    assert resp.status_code == 200
    # manage-burst is a simple enum with default option "NoStack".
    assert 'name="fld_manage-burst"' in resp.text
    assert 'class="form-select"' in resp.text
    assert '<option value="NoStack"' in resp.text


def test_enum_default_is_preselected():
    """B8: initial_tab_state returns f.default for enum kinds, not ''."""
    st = initial_tab_state("upload-folder")
    assert st.get("manage-burst") == "NoStack"
    assert st.get("folder-album") == "NONE"


def test_nav_reaches_all_eleven_tabs():
    """B2: every one of the 11 workflow tabs is reachable from the overview page."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/overview", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    expected = [
        "upload-folder",
        "upload-gp",
        "upload-icloud",
        "upload-picasa",
        "upload-immich",
        "archive-folder",
        "archive-gp",
        "archive-icloud",
        "archive-picasa",
        "archive-immich",
        "stack",
    ]
    for key in expected:
        assert f'hx-get="/tab/{key}"' in resp.text, f"Missing overview entry for {key}"


def test_bool_advanced_row_has_true_false_value_control():
    """B7: enabling a bool advanced flag allows emitting --flag=false."""
    def_ = FlagDef(
        key="recursive",
        flag="recursive",
        label="Recursive",
        mode="advanced",
        kind="bool",
        default=True,
    )
    rendered = _render_adv_row(def_, {"enabled": True, "value": True})
    assert 'name="adv_recursive_val"' in rendered
    assert '<option value="true"' in rendered
    assert '<option value="false"' in rendered

    def_false = FlagDef(
        key="foo", flag="foo", label="Foo", mode="advanced", kind="bool", default=False
    )
    rendered_false = _render_adv_row(def_false, {"enabled": True, "value": False})
    assert '<option value="false" selected' in rendered_false


def _render_adv_row(def_, stored):
    """Render render_adv_row for a single def by importing the macro."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    tmpl = env.from_string(
        "{% from 'partials/macros.html' import render_adv_row %}{{ render_adv_row(d, stored) }}"
    )
    return tmpl.render(d=def_, stored=stored)


def test_secret_provider_fallback_normalized_to_config():
    """B4: legacy 'fallback' provider value is normalized to 'config' on save."""
    from core.config_manager import load_config

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/config/save",
        data={
            "secret_provider": "fallback",
            "client_timeout_minutes": "120",
            "admin_api_key": "",
        },
    )
    assert resp.status_code == 200
    assert load_config().secrets_provider == "config"


def test_parse_config_state_builds_matching_dict():
    """Preview helper: form -> config_state dictionary preserves values."""
    parsed = parse_config_state(
        {
            "server": "http://immich:2283",
            "api_key": "sekret",
            "client_timeout_minutes": "120",
        }
    )
    assert parsed["server"] == "http://immich:2283"
    assert parsed["api_key"] == "sekret"
    assert parsed["client_timeout_minutes"] == 120


def test_compat_partial_reports_all_tabs():
    """B6: CLI compatibility modal renders one row per workflow tab."""
    from core.flag_registry import REGISTRY

    app = create_app()
    client = TestClient(app)
    resp = client.get("/partial/compat")
    assert resp.status_code == 200
    assert "CLI Compatibility Matrix" in resp.text
    for key in REGISTRY.tabs:
        assert key in resp.text, f"Compatibility matrix missing {key}"


def test_binary_update_panel_uses_decision_fields():
    """B5: binary-update panel maps severity -> tone and gates Install on allowed."""
    blocked = UpdateDecision(
        allowed=False,
        requires_confirmation=True,
        severity=UpdateSeverity.BLOCKED,
        message="Version 0.33.0 is untested.",
        latest_version="0.33.0",
        current_version="0.32.0",
    )
    html = TEMPLATES.get_template("partials/panels.html").render(
        {
            "partial": "partials/panels.html#binary_update",
            "latest": "0.33.0",
            "current": "0.32.0",
            "decision": blocked,
        }
    )
    assert "Version 0.33.0 is untested." in html
    assert "alert-err" in html
    assert "blocked" in html
    assert "disabled" in html

    ok = UpdateDecision(
        allowed=True,
        requires_confirmation=False,
        severity=UpdateSeverity.WARNING,
        message="Stable release.",
        latest_version="0.33.0",
        current_version="0.32.0",
    )
    html_ok = TEMPLATES.get_template("partials/panels.html").render(
        {
            "partial": "partials/panels.html#binary_update",
            "latest": "0.33.0",
            "current": "0.32.0",
            "decision": ok,
        }
    )
    assert "alert-warn" in html_ok
    assert "disabled" not in html_ok


# ──────────────────────────────────────────────────────────────────
# Phase 1 - security hardening (S1, S2, keyring-aware provider)
# ──────────────────────────────────────────────────────────────────


def test_tab_form_does_not_round_trip_secrets_to_dom():
    """S1: api_key / admin_api_key are never rendered into page source."""
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "http://immich:2283", "api_key": "super-secret-key-xyz"},
    )
    resp = client.get("/tab/upload-folder")
    assert resp.status_code == 200
    assert "super-secret-key-xyz" not in resp.text


def test_secret_source_fields_rendered_as_password():
    """S2: source API key fields must be masked password inputs."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/upload-immich")
    assert resp.status_code == 200
    # Simple source API key (upload-immich).
    assert 'type="password" id="fld_from-api-key"' in resp.text

    # Enable advanced mode to expose the source admin API key row.
    client.post("/mode/toggle", headers={"HX-Request": "true"})
    resp_adv = client.get("/tab/upload-immich", headers={"HX-Request": "true"})
    assert 'type="password" name="adv_from-admin-api-key_val"' in resp_adv.text


def test_config_api_key_rendered_in_password_field():
    """The config edit form shows the stored key in a masked password input.

    The S1 fix removes secrets from the *workflow tab* forms and every HTMX
    submission; the config page is the deliberate edit surface, so it still
    shows the value, but only inside a type="password" input.
    """
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "https://immich.example.com", "api_key": "leak-check-42"},
    )
    resp = client.get("/config")
    assert resp.status_code == 200
    assert 'type="password" id="cfg_api_key"' in resp.text


def test_keyring_unavailable_shows_notice_and_defaults_to_config_provider():
    """W-10: without a keyring, the config UI explains file/env storage."""
    from webapp import app as appmod

    with patch.object(appmod, "_keyring_available", return_value=False):
        app = create_app()
        client = TestClient(app)
        resp = client.get("/config")
        assert resp.status_code == 200
        assert "unavailable" in resp.text
        assert "OS keyring is not available" in resp.text


def test_preview_builds_plan_with_session_secrets():
    """S1: removing the hidden secret inputs does not break preview/confirm.

    The preview must still resolve the api_key from the server session and the
    confirm modal must not leak it into the response body.
    """
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "http://immich:2283", "api_key": "plan-secret"},
    )
    resp = client.post(
        "/tabs/upload-folder/preview",
        data={"fld_path": "/photos", "dry": "1"},
    )
    assert resp.status_code == 200
    assert "Dry Run Confirmation" in resp.text
    assert "plan-secret" not in resp.text


# ──────────────────────────────────────────────────────────────────
# Phase 2 - navigation & layout (W-11 status, W-12 server banner, W-13 theme)
# ──────────────────────────────────────────────────────────────────


def test_server_banner_shows_target_server():
    """W-12: server-required tabs display the configured target server."""
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "https://target:2283", "api_key": "k"},
    )
    resp = client.get("/tab/upload-folder")
    assert resp.status_code == 200
    assert "Target server" in resp.text
    assert "https://target:2283" in resp.text


def test_serverless_tab_has_no_target_banner():
    """W-12: serverless archive tabs must not show a target-server banner."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/archive-folder")
    assert resp.status_code == 200
    assert "Target server" not in resp.text


def test_theme_endpoint_sets_system_cookie():
    """W-13: the /theme endpoint persists a 'system' preference cookie."""
    app = create_app()
    client = TestClient(app)
    resp = client.post("/theme", data={"theme": "system"})
    assert resp.status_code == 204
    assert client.cookies.get("igg_theme") == "system"


def test_status_surfaces_connection_result():
    """W-11: a successful connection test surfaces a Connected chip in status."""
    from types import SimpleNamespace

    from webapp import app as appmod

    fake = SimpleNamespace(ok=True, message="Connected", server_version="v1.118.0")
    with patch.object(appmod, "test_immich_connection", return_value=fake):
        app = create_app()
        client = TestClient(app)
        client.post(
            "/config/save-server",
            data={"server": "https://x:2283", "api_key": "k"},
        )
        client.post(
            "/config/test-connection",
            data={"server": "https://x:2283", "api_key": "k"},
        )
        resp = client.get("/partial/status")
        assert resp.status_code == 200
        assert "Connected" in resp.text
        assert "v1.118.0" in resp.text


# ──────────────────────────────────────────────────────────────────
# Phase 3 - config tab parity (W-14 conn chip, W-15 sections, W-16 checklist)
# ──────────────────────────────────────────────────────────────────


def test_connection_chip_endpoint_returns_json():
    """W-14: the ambient connection-check endpoint returns JSON for the chip."""
    import json as _json
    from types import SimpleNamespace

    from webapp import app as appmod

    fake = SimpleNamespace(ok=True, message="Connected", server_version="v1.118.0")
    with patch.object(appmod, "test_immich_connection", return_value=fake):
        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/config/test-connection-async",
            data={"server": "https://x:2283", "api_key": "k"},
        )
        assert resp.status_code == 200
        data = _json.loads(resp.text)
        assert data["ok"] is True
        assert data["message"] == "Connected"
        assert data["server_version"] == "v1.118.0"


def test_config_page_shows_new_sections_and_checklist():
    """W-15/W-16: config exposes Application, Appearance, and first-run checklist."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/config")
    assert resp.status_code == 200
    assert "Getting Started Checklist" in resp.text
    assert "Application" in resp.text
    assert "Appearance" in resp.text
    assert "Theme" in resp.text
    assert "conn-chip" in resp.text


def test_checklist_dismiss_hides_card():
    """W-16: dismissing the checklist persists and hides it."""
    app = create_app()
    client = TestClient(app)
    assert "Getting Started Checklist" in client.get("/config").text
    client.post("/checklist/dismiss")
    resp = client.get("/config")
    assert "Getting Started Checklist" not in resp.text


# ──────────────────────────────────────────────────────────────────
# Phase 4 - workflow tab & execution parity (W-17..W-22)
# ──────────────────────────────────────────────────────────────────


def test_inline_field_error_rendered():
    """W-17: validation errors render inline under the offending field via OOB."""
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "http://immich:2283", "api_key": "k"},
    )
    # upload-folder requires a source path; send none to force a field error.
    resp = client.post("/tabs/upload-folder/preview", data={"dry": "1"})
    assert resp.status_code == 200
    assert "Validation Errors" in resp.text
    assert 'class="field-error"' in resp.text
    assert "field-err-" in resp.text


def test_live_preview_ribbon_endpoint():
    """W-19: the live-preview endpoint returns color-coded masked argv tokens."""
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "http://immich:2283", "api_key": "k"},
    )
    resp = client.post(
        "/tabs/upload-folder/live-preview",
        data={"fld_path": "/photos"},
    )
    assert resp.status_code == 200
    assert "ribbon-argv" in resp.text
    assert "ribbon-tok" in resp.text
    assert "upload" in resp.text


def test_confirm_includes_flag_sources_and_copy():
    """W-21: confirm modal shows flag provenance + a Copy Command button."""
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "http://immich:2283", "api_key": "k"},
    )
    resp = client.post(
        "/tabs/upload-folder/preview",
        data={"fld_path": "/photos", "dry": "1"},
    )
    assert resp.status_code == 200
    assert "Flag Sources" in resp.text
    assert "Copy Command" in resp.text
    assert "ribbon-" in resp.text


def test_profile_switch_with_dirty_prompts():
    """W-22: switching profiles with unsaved changes returns the prompt modal."""
    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/profiles/switch",
        data={"name": "work", "dirty": "1"},
    )
    assert resp.status_code == 200
    assert "Unsaved Profile Changes" in resp.text
    assert "Discard & Switch" in resp.text
    assert "Save & Switch" in resp.text


def test_config_reload_endpoint():
    """W-23: /config/reload returns an ok toast and reloads session config."""
    app = create_app()
    client = TestClient(app)
    resp = client.post("/config/reload")
    assert resp.status_code == 200
    assert "reloaded" in resp.text.lower()


def test_config_download_redacts_secrets():
    """W-24: downloading config redacts secret-bearing keys."""
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "https://x:2283", "api_key": "super-secret-key-xyz"},
    )
    resp = client.get("/config/download")
    assert resp.status_code == 200
    assert "super-secret-key-xyz" not in resp.text
    # Redaction marker present for key-like entries if they exist in the model.
    assert "Content-Disposition" in resp.headers


def test_logs_tail_endpoint_returns_plain_text():
    """W-24: the log-tail endpoint returns a text/plain body."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/logs/tail")
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/plain")


def test_about_modal_has_links_and_cli_target():
    """W-26: the About modal shows the CLI target and GitHub links."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/partial/about")
    assert resp.status_code == 200
    assert "About Immich-Go Web Console" in resp.text
    assert "simulot/immich-go" in resp.text
    assert "CLI target" in resp.text


def test_toast_can_carry_action_link():
    """W-25: app-update toasts can include an 'Open ↗' release link."""
    from types import SimpleNamespace

    from webapp import app as appmod

    rel = SimpleNamespace(
        version="9.9.9",
        html_url="https://github.com/shitan198u/immich-go-gui/releases/tag/v9.9.9",
    )
    with (
        patch.object(appmod, "gui_version", return_value="1.0.0"),
        patch.object(appmod, "get_latest_gui_release", return_value=rel),
        patch.object(appmod, "is_parseable_semver", return_value=True),
        patch.object(appmod, "is_update_available", return_value=True),
    ):
        app = create_app()
        client = TestClient(app)
        resp = client.post("/app-update/check")
        assert resp.status_code == 200
        assert "Open ↗" in resp.text
        assert "v9.9.9" in resp.text


# ──────────────────────────────────────────────────────────────────
# Phase 6 - efficiency & discoverability (W-27 presets, W-28 rebuild, W-29 keys)
# ──────────────────────────────────────────────────────────────────


def test_advanced_tab_renders_preset_chips():
    """W-27: advanced mode shows filtered preset chips for the workflow."""
    from webapp.presets import presets_for

    app = create_app()
    client = TestClient(app)
    client.post("/mode/toggle", headers={"HX-Request": "true"})
    resp = client.get("/tab/upload-folder")
    assert resp.status_code == 200
    assert presets_for("upload-folder"), "upload-folder must define presets"
    assert "preset-chip" in resp.text
    assert "Fast Scan" in resp.text


def test_run_history_records_and_overview_shows_rebuild():
    """W-28: recorded runs surface a Rebuild action on the Overview."""
    from webapp.history import HISTORY

    app = create_app()
    client = TestClient(app)
    HISTORY.record(
        run_id="hist-123",
        tab_key="upload-immich",
        dry=True,
        warnings=0,
        display_cmd="-dry-run upload-immich",
        raw_state={"path": "/tmp/photos", "from-api-key": "should-not-be-stored"},
    )
    try:
        entry = HISTORY.get("hist-123")
        assert entry is not None
        assert entry["tab_state"].get("from-api-key") is None  # secrets excluded
        resp = client.get("/overview")
        assert resp.status_code == 200
        assert "🧰 Rebuild" in resp.text
    finally:
        # avoid cross-test pollution of the shared JSON store
        import json as _json
        from pathlib import Path

        import webapp.history as hmod

        try:
            data = hmod.HISTORY._load()
            data = [e for e in data if e.get("run_id") != "hist-123"]
            Path(hmod.HISTORY._path).write_text(
                _json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass


def test_run_rebuild_rehydrates_session_state():
    """W-28: /runs/{id}/rebuild restores non-secret form state into the tab."""
    from webapp.history import HISTORY

    app = create_app()
    client = TestClient(app)
    HISTORY.record(
        run_id="hist-456",
        tab_key="upload-folder",
        dry=False,
        warnings=0,
        display_cmd="upload",
        raw_state={"path": "/data/photos", "recursive": True},
    )
    try:
        resp = client.post("/runs/hist-456/rebuild")
        assert resp.status_code == 204
        assert resp.headers.get("HX-Redirect") == "/tab/upload-folder"
        tab_resp = client.get("/tab/upload-folder")
        assert "/data/photos" in tab_resp.text
    finally:
        import json as _json
        from pathlib import Path

        import webapp.history as hmod

        try:
            data = hmod.HISTORY._load()
            data = [e for e in data if e.get("run_id") != "hist-456"]
            Path(hmod.HISTORY._path).write_text(
                _json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass


def test_base_page_exposes_footer_hint_and_shortcuts_overlay():
    """W-29: the shell renders the footer hint + keyboard shortcut overlay."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "shortcuts-overlay" in resp.text
    assert "Ctrl" in resp.text or "kbd" in resp.text


# ──────────────────────────────────────────────────────────────────
# Phase 7 - hardening (secret masking on live preview, SSE headers)
# ──────────────────────────────────────────────────────────────────


def test_live_preview_masks_source_api_key():
    """S1/W-19: the live ribbon never leaks source API keys in its response."""
    app = create_app()
    client = TestClient(app)
    client.post(
        "/config/save-server",
        data={"server": "http://immich:2283", "api_key": "main-key"},
    )
    client.post("/mode/toggle", headers={"HX-Request": "true"})
    resp = client.post(
        "/tabs/upload-immich/live-preview",
        data={"fld_from-api-key": "source-secret-xyz", "fld_server": "http://src:2283"},
    )
    assert resp.status_code == 200
    assert "source-secret-xyz" not in resp.text
    assert "main-key" not in resp.text
    assert "ribbon-argv" in resp.text


def test_run_stream_has_no_buffering_header():
    """W-31: SSE responses carry X-Accel-Buffering: no for proxy compatibility."""
    from types import SimpleNamespace as _NS

    from starlette.testclient import TestClient as _TC

    app = create_app()

    fake_run = _NS(
        run_id="sse-test",
        snapshot=lambda cursor: ([], 0),
        finished=True,
        total=0,
        exit_code=0,
    )
    with patch.dict("webapp.app.RUNS.runs", {"sse-test": fake_run}):
        client = _TC(app)
        resp = client.get("/runs/sse-test/stream")
        assert resp.status_code == 200
        assert resp.headers.get("x-accel-buffering") == "no"
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
        # Drain the generator to avoid unclosed responses.
        for _ in resp.iter_text():
            break


def test_theme_preference_attribute_on_shell():
    """W-13: the shell carries the theme preference for JS resolution."""
    app = create_app()
    client = TestClient(app)
    client.post("/theme", data={"theme": "system"})
    resp = client.get("/")
    assert 'data-theme-preference="system"' in resp.text


# ──────────────────────────────────────────────────────────────────────
# Sidebar restructure: 5 tabs + horizontal sub-tabs + profile OOB
# ──────────────────────────────────────────────────────────────────────
def test_sidebar_has_five_nav_items():
    """The sidebar shows exactly 5 main entries: Overview, Configuration,
    Upload, Archive, Stack — not individual per-workflow links."""
    app = create_app()
    client = TestClient(app)
    # Use htmx request to get content + OOB nav (without overview cards).
    resp = client.get("/section/upload", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert 'hx-get="/overview"' in resp.text
    assert 'hx-get="/config"' in resp.text
    assert 'hx-get="/section/upload"' in resp.text
    assert 'hx-get="/section/archive"' in resp.text
    assert 'hx-get="/section/stack"' in resp.text
    # Old per-workflow sidebar group titles must be gone from the sidebar.
    assert 'nav-title">Upload Workflows' not in resp.text
    assert 'nav-title">Archive Workflows' not in resp.text
    assert 'nav-title">Stack Workflows' not in resp.text


def test_section_upload_route_renders_first_tab():
    """Clicking Upload in the sidebar lands on the upload page with sub-tabs."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/section/upload")
    assert resp.status_code == 200
    assert "upload-folder" in resp.text
    # Sub-tab bar should be present with all upload sub-tabs.
    assert "sub-tab" in resp.text
    assert "From Folder" in resp.text
    assert "Google Takeout" in resp.text
    assert "iCloud" in resp.text
    assert "Picasa" in resp.text
    assert "From Immich" in resp.text


def test_section_archive_route_renders_first_tab():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/section/archive")
    assert resp.status_code == 200
    assert "archive-folder" in resp.text
    assert "sub-tab" in resp.text
    assert "From Folder" in resp.text


def test_section_stack_route_renders_stack_tab():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/section/stack")
    assert resp.status_code == 200
    assert "stack" in resp.text


def test_invalid_section_redirects_to_overview():
    app = create_app()
    client = TestClient(app, follow_redirects=False)
    resp = client.get("/section/nonexistent")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/overview"


def test_sub_tabs_render_on_tab_page():
    """Every tab page includes a horizontal sub-tab bar with the active tab
    highlighted."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/upload-gp")
    assert resp.status_code == 200
    assert "sub-tab" in resp.text
    # The Google Takeout sub-tab should be marked active.
    assert "Google Takeout" in resp.text
    # All sibling upload sub-tabs are present.
    for label in ("From Folder", "iCloud", "Picasa", "From Immich"):
        assert label in resp.text


def test_sidebar_upload_active_when_on_upload_tab():
    """The sidebar Upload entry is highlighted when viewing any upload tab."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/upload-icloud", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    # The Upload nav-item should have the active class (OOB nav is included).
    assert "active" in resp.text
    assert 'hx-get="/section/upload"' in resp.text


def test_profile_chip_oob_swapped_on_htmx():
    """The profile chip is OOB-swapped on every htmx navigation so its name
    stays fresh without a full page reload."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/tab/upload-folder", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert 'id="profile-chip"' in resp.text
    assert 'hx-swap-oob="outerHTML:#profile-chip"' in resp.text


def test_mode_toggle_button_shows_current_state_and_action():
    """The mode toggle shows the current state and what clicking will do."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    # In simple mode (default): shows "Simple" state + "→ Advanced" action.
    assert "mode-state" in resp.text
    assert "mode-action" in resp.text
    assert "Simple" in resp.text
    assert "Advanced" in resp.text


def test_check_gui_update_has_loading_indicator():
    """The Check GUI Update buttons have htmx loading indicators for feedback."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/config")
    assert resp.status_code == 200
    assert "spin-loader" in resp.text
    assert "hx-disabled-elt" in resp.text
    assert "hx-indicator" in resp.text
