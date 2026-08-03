"""Diagnostics zip export (ported from gui/mixins/diagnostics.py, Qt-free)."""

from __future__ import annotations

import io
import tomllib
import zipfile
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from core import (
    METADATA_PATH,
    TESTED_IMMICH_GO_VERSION,
    default_config_dir,
    default_config_path,
    get_config_load_warning,
)
from core.profile_manager import global_profiles_path


def gui_version() -> str:
    try:
        return _pkg_version("immich-go-gui")
    except PackageNotFoundError:
        return "dev"


def _redact(text: str) -> str:
    try:
        data = tomllib.loads(text)
    except Exception:
        return "# [unparseable config omitted]\n"

    def _scrub(m: dict[str, Any]) -> None:
        for k, v in list(m.items()):
            kl = str(k).lower()
            if any(s in kl for s in ("api", "secret", "password", "token")):
                m[k] = "***REDACTED***"
            elif isinstance(v, dict):
                _scrub(v)

    fs = data.get("form_state")
    if isinstance(fs, dict):
        _scrub(fs)
    try:
        import tomli_w

        return tomli_w.dumps(data)
    except Exception:
        return "# [redaction failed]\n"


def build_diagnostics_zip() -> bytes:
    buf = io.BytesIO()
    cfg_dir = default_config_dir()
    log_dir = cfg_dir / "logs"
    meta = Path(METADATA_PATH)
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        summary = [
            f"gui_version={gui_version()}",
            "surface=web-console",
            f"cli_target_version={TESTED_IMMICH_GO_VERSION}",
        ]
        w = get_config_load_warning()
        if w:
            summary.append(f"config_load_warning={w}")
        zf.writestr("summary.txt", "\n".join(summary) + "\n")
        cfg = default_config_path()
        if cfg.is_file():
            zf.writestr("config.toml", _redact(cfg.read_text(encoding="utf-8")))
        pidx = global_profiles_path()
        if pidx.is_file():
            zf.write(pidx, arcname="profiles.toml")
        if meta.is_file():
            zf.write(meta, arcname="binary_metadata.json")
        if log_dir.is_dir():
            logs = sorted(
                log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if logs:
                tail = logs[0].read_text(encoding="utf-8", errors="replace")[-200_000:]
                zf.writestr("log_tail.txt", tail)
    return buf.getvalue()
