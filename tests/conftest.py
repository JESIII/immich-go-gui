"""Shared pytest fixtures for Immich-Go GUI test suite."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app import ImmichGoGUI


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(scope="session")
def gui(qapp):
    """One shared window for the whole suite.

    Session teardown must not show Save/Discard dialogs: function-scoped
    monkeypatches are already gone when this fixture exits. Use _force_close.
    """
    with patch.object(ImmichGoGUI, "check_binary_version"), patch.object(
        ImmichGoGUI, "load_configuration"
    ), patch.object(ImmichGoGUI, "_probe_keyring", return_value=True), patch(
        "PySide6.QtWidgets.QMessageBox.warning"
    ), patch(
        "PySide6.QtWidgets.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Discard,
    ):
        g = ImmichGoGUI()
        g.binary_path = "./immich-go"
        # Never fire silent connection tests during the suite — they hit the
        # network with a 4s timeout and dominate wall time when Qt processes events.
        if hasattr(g, "_conn_test_debounce"):
            g._conn_test_debounce.stop()
            g._conn_test_debounce.timeout.disconnect()
        g._auto_test_connection = lambda: None
        yield g
        g._force_close = True
        g.close()


@pytest.fixture(autouse=True)
def suppress_qt_dialogs(monkeypatch):
    """Suppress modal QMessageBox dialogs during each test function."""
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", MagicMock())
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.warning", MagicMock())
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", MagicMock())
    # Discard: close-without-save path. Lock-prompt tests that need Yes override this.
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.question",
        MagicMock(return_value=QMessageBox.StandardButton.Discard),
    )


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    from core.profile_manager import clear_profiles_cache

    clear_profiles_cache()
    yield
    clear_profiles_cache()


@pytest.fixture(autouse=True)
def _reset_shared_config(gui):
    cfg = gui.inputs["config"]
    cfg["skip-ssl"].setChecked(False)
    yield
