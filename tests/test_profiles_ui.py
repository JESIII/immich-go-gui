from PySide6.QtWidgets import QMessageBox

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


def test_profile_manager_lifecycle(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config_dir"
    monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(cfg_dir / "config.toml"))

    profiles = list_profiles()
    assert len(profiles) >= 1
    assert active_profile_name() == "default"

    # Create new profile
    pinfo = create_profile("work")
    assert pinfo.name == "work"

    all_p = [p.name for p in list_profiles()]
    assert "work" in all_p

    # Set active
    set_active_profile_name("work")
    assert active_profile_name() == "work"

    # Duplicate
    dup = duplicate_profile("work", "work_copy")
    assert dup.name == "work_copy"
    assert "work_copy" in [p.name for p in list_profiles()]

    # Rename
    rename_profile("work_copy", "work_renamed")
    assert "work_renamed" in [p.name for p in list_profiles()]
    assert "work_copy" not in [p.name for p in list_profiles()]

    # Delete
    delete_profile("work_renamed")
    assert "work_renamed" not in [p.name for p in list_profiles()]


def test_profile_name_validation():
    valid, err = validate_profile_name("work_profile-1")
    assert valid is True

    valid, err = validate_profile_name("../bad_path")
    assert valid is False

    valid, err = validate_profile_name("")
    assert valid is False


def test_profile_switch_save_discard_cancel(gui, monkeypatch):
    actions = []

    def fake_question(*args, **kwargs):
        return actions[-1]

    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.question", fake_question)
    monkeypatch.setattr(
        gui, "save_configuration", lambda show_popup=True: actions.append("saved")
    )
    monkeypatch.setattr(
        "gui.mixins.profiles_ui.set_active_profile_name",
        lambda name: actions.append(f"active:{name}"),
    )
    monkeypatch.setattr(gui, "load_configuration", lambda: actions.append("loaded"))
    monkeypatch.setattr(gui, "update_profiles_menu", lambda: None)
    monkeypatch.setattr(gui, "update_window_title", lambda: None)
    monkeypatch.setattr("gui.mixins.profiles_ui.active_profile_name", lambda: "default")

    actions.append(QMessageBox.StandardButton.Cancel)
    gui._mark_configuration_clean()
    gui.inputs["config"]["server"].setText("http://changed:2283")
    gui.switch_profile("work")
    assert "active:work" not in actions

    actions.clear()
    gui._mark_configuration_clean()
    gui.switch_profile("work")
    assert "saved" not in actions
    assert "active:work" in actions
    assert "loaded" in actions

    actions.clear()
    actions.append(QMessageBox.StandardButton.Discard)
    gui._mark_configuration_clean()
    gui.inputs["config"]["server"].setText("http://changed:2283")
    gui.switch_profile("home")
    assert "saved" not in actions
    assert "active:home" in actions
    assert "loaded" in actions

    actions.clear()
    actions.append(QMessageBox.StandardButton.Save)
    gui._mark_configuration_clean()
    gui.inputs["config"]["server"].setText("http://save-me:2283")
    gui.switch_profile("office")
    assert "saved" in actions
    assert "active:office" in actions
