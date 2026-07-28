from unittest.mock import MagicMock, patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from core.command_builder import validate_state_light
from theme import apply_application_theme, clear_icon_cache
def test_running_process_boolean_state(gui):
    from PySide6.QtWidgets import QMessageBox

    gui.active_lock_path = None
    gui.running_process = False
    gui.update_status()
    assert gui.lbl_running_warning.isHidden() is True

    gui.running_process = True
    gui.update_status()
    assert gui.lbl_running_warning.isHidden() is False

    with patch(
        "PySide6.QtWidgets.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        gui.on_reset_run_state_clicked()
        assert gui.running_process is False
        assert gui.active_lock_path is None
        assert gui.lbl_running_warning.isHidden() is True

def test_close_event_save_prompt(gui, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    calls = {"save": 0}

    def fake_question(*args, **kwargs):
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.question", fake_question)
    monkeypatch.setattr(
        gui,
        "save_configuration",
        lambda show_popup=True: calls.__setitem__("save", calls["save"] + 1),
    )
    monkeypatch.setattr("gui.main_window.scan_locks", list)
    event = QCloseEvent()
    gui.closeEvent(event)
    assert calls["save"] == 1
    assert event.isAccepted()

def test_close_event_cancel_ignores(gui, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Cancel,
    )
    monkeypatch.setattr(
        gui,
        "save_configuration",
        lambda show_popup=True: (_ for _ in ()).throw(AssertionError("save")),
    )
    monkeypatch.setattr("gui.main_window.scan_locks", list)
    event = QCloseEvent()
    gui.closeEvent(event)
    assert not event.isAccepted()

def test_close_event_discard_no_save(gui, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    calls = {"save": 0}

    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Discard,
    )
    monkeypatch.setattr(
        gui,
        "save_configuration",
        lambda show_popup=True: calls.__setitem__("save", calls["save"] + 1),
    )
    monkeypatch.setattr("gui.main_window.scan_locks", list)
    event = QCloseEvent()
    gui.closeEvent(event)
    assert calls["save"] == 0
    assert event.isAccepted()

def test_icon_cache_cleared_on_theme_switch(gui, monkeypatch):
    cleared = {"n": 0}

    def fake_clear():
        cleared["n"] += 1

    monkeypatch.setattr("gui.mixins.theme_mixin.clear_icon_cache", fake_clear)
    monkeypatch.setattr(
        "gui.mixins.theme_mixin.apply_application_theme", lambda mode: "dark"
    )
    monkeypatch.setattr(gui, "findChildren", lambda *a, **k: [])
    monkeypatch.setattr(gui, "refresh_sidebar_icons", lambda *_: None)
    gui.apply_theme("Dark")
    assert cleared["n"] == 1

def test_theme_switch_light_dark_system(gui, monkeypatch):
    # Avoid full QSS re-apply / widget walk — this test only checks mode state.
    monkeypatch.setattr(
        "gui.mixins.theme_mixin.apply_application_theme", lambda mode: "dark"
    )
    monkeypatch.setattr(gui, "findChildren", lambda *a, **k: [])
    monkeypatch.setattr(gui, "refresh_sidebar_icons", lambda *_: None)
    gui.apply_theme("Light")
    assert gui.theme_mode == "Light"
    gui.apply_theme("Dark")
    assert gui.theme_mode == "Dark"
    gui.apply_theme("System")
    assert gui.theme_mode == "System"

def test_validate_state_light_does_not_call_glob(monkeypatch):
    from core.command_builder import validate_state_light

    called = {"n": 0}

    def fake_glob(*_args, **_kwargs):
        called["n"] += 1
        return []

    monkeypatch.setattr("core.command_builder.glob.glob", fake_glob)
    res = validate_state_light(
        "upload-folder",
        {"server": "http://localhost:2283", "api_key": "key"},
        {"path": "/tmp/*.jpg"},
    )
    assert res.is_valid
    assert called["n"] == 0

def test_binary_debounce_and_ban_file_lines_repeat(gui):
    gui.toggle_advanced(True)
    gui.stacked_widget.setCurrentIndex(1)
    gui.upload_tabs.setCurrentIndex(0)
    gui.inputs["config"]["server"].setText("http://localhost:2283")
    gui.inputs["config"]["api_key"].setText("key")
    gui.inputs["upload-folder"]["path"].setText("/photos")

    fired = {"n": 0}
    original = gui._on_manual_binary_changed

    def counting_handler():
        fired["n"] += 1
        original()

    gui._on_manual_binary_changed = counting_handler
    gui.binary_debounce.timeout.emit()

    ban_row = gui.adv_rows["upload-folder"]["ban-file"]
    ban_row.enable.setChecked(True)
    ban_row.value_widget.setPlainText("*.tmp\n*.bak")
    gui._do_update_status()

def test_inline_field_errors_shown_on_validation(gui):
    gui.stacked_widget.setCurrentIndex(1)
    gui.upload_tabs.setCurrentIndex(0)
    gui.inputs["config"]["server"].setText("http://localhost:2283")
    gui.inputs["config"]["api_key"].setText("key")
    gui.inputs["upload-folder"]["path"].clear()
    gui.update_status()
    lbl = gui._field_error_labels[("upload-folder", "path")]
    assert lbl.text()
    assert "required" in lbl.text().lower()

