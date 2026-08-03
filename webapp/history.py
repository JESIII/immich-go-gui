"""Persistent (disk) run history for the web console.

Records lightweight, secret-free entries for recently started runs so the
Overview can offer one-click "Rebuild" (rehydrates non-secret form state).
Secrets are never written here: any flag with ``secret_env`` is stripped.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config_manager import default_config_dir
from core.flag_registry import REGISTRY

MAX_RECORDS = 25


def nonsecret_tab_state(tab_key: str, raw_state: dict[str, Any]) -> dict[str, Any]:
    """Return tab form state minus any secret-bearing fields."""
    secret_keys = {
        f.key for f in REGISTRY.flags.get(tab_key, ()) if getattr(f, "secret_env", "")
    }
    return {k: v for k, v in raw_state.items() if k not in secret_keys}


class RunHistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (default_config_dir() / "run_history.json")
        self._lock = threading.Lock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self._path.read_text("utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def record(
        self,
        *,
        run_id: str,
        tab_key: str,
        dry: bool,
        warnings: int,
        display_cmd: str,
        raw_state: dict[str, Any],
    ) -> None:
        entry: dict[str, Any] = {
            "run_id": run_id,
            "tab_key": tab_key,
            "started_at": datetime.now(UTC).isoformat(),
            "dry": bool(dry),
            "warnings": int(warnings),
            "display_cmd": display_cmd,
            "tab_state": nonsecret_tab_state(tab_key, raw_state),
        }
        with self._lock:
            entries = [e for e in self._load() if e.get("run_id") != run_id]
            entries.append(entry)
            entries = entries[-MAX_RECORDS:]
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
            except OSError:
                pass

    def get(self, run_id: str) -> dict[str, Any] | None:
        return next((e for e in self._load() if e.get("run_id") == run_id), None)

    def entries(self) -> list[dict[str, Any]]:
        return self._load()

    def ids(self) -> set[str]:
        return {e["run_id"] for e in self._load() if e.get("run_id")}


HISTORY = RunHistoryStore()
