"""Unit tests for configuration loading and quarantine behavior."""

from pathlib import Path

from core.config_manager import load_config, get_config_load_warning


def test_corrupt_config_quarantined_and_defaults_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(tmp_path / "config.toml"))
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("not valid {{{{ toml", encoding="utf-8")

    cfg = load_config()
    warning = get_config_load_warning()

    assert cfg.server_url == ""
    assert cfg.theme_mode == "system"
    assert warning is not None
    assert "could not be parsed" in warning.lower()

    corrupt_files = list(tmp_path.glob("config.toml.corrupt-*"))
    assert len(corrupt_files) == 1
    assert not cfg_path.exists()
