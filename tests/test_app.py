"""Entry-point tests for app.py."""

import app as app_module


def test_exception_hook_installed(monkeypatch):
    logged = []

    class FakeLogger:
        def critical(self, msg, exc_info=None):
            logged.append((msg, exc_info))

    monkeypatch.setattr(app_module.QTimer, "singleShot", lambda *_a, **_k: None)
    monkeypatch.setattr(app_module.sys, "excepthook", lambda *a, **k: None)
    app_module._install_exception_hook(FakeLogger())
    app_module.sys.excepthook(ValueError, ValueError("boom"), None)
    assert logged
    assert logged[0][0] == "Unhandled exception"
