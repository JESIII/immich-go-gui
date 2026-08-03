"""Managed immich-go subprocess execution with SSE-friendly log buffering.

Replaces core.terminal_launcher for the web context: instead of opening an
external terminal, output is captured and streamed to the browser.
"""

from __future__ import annotations

import html
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.models import CommandPlan
from core.process_tracker import create_lock, release_lock

MAX_LINES = 8000


class RunInProgress(Exception):
    pass


@dataclass
class Run:
    run_id: str
    tab_key: str
    display_cmd: str
    dry_run: bool
    lock_path: Path
    proc: subprocess.Popen[Any]
    lines: deque[tuple[str, str]] = field(
        default_factory=lambda: deque(maxlen=MAX_LINES)
    )
    total: int = 0
    exit_code: int | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    stopped: bool = False
    done: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, text: str, kind: str = "out") -> None:
        with self._lock:
            self.lines.append((kind, html.escape(text.rstrip("\n"))))
            self.total += 1

    def snapshot(self, cursor: int) -> tuple[list[tuple[str, str]], int]:
        with self._lock:
            start = max(0, self.total - len(self.lines))
            idx = max(cursor, start)
            return list(self.lines)[idx - start :], self.total

    @property
    def finished(self) -> bool:
        return self.done.is_set()


class RunManager:
    def __init__(self) -> None:
        self.runs: dict[str, Run] = {}
        self.order: list[str] = []
        self.active_id: str | None = None
        self._lock = threading.Lock()

    def active(self) -> Run | None:
        r = self.runs.get(self.active_id or "")
        return r if r and not r.finished else None

    def is_busy(self) -> bool:
        return self.active() is not None

    def start(self, plan: CommandPlan, binary_path: str) -> Run:
        with self._lock:
            if self.is_busy():
                raise RunInProgress("A command is already running.")
            run_id = uuid.uuid4().hex[:8]
            lock_path = create_lock(
                tab_key=plan.tab_key,
                command_summary=" ".join(plan.argv[:3]) or plan.tab_key,
                binary_path=binary_path,
            )
            cwd = Path(tempfile.mkdtemp(prefix="immich-go-web-"))
            env = {**os.environ, **plan.env}
            proc = subprocess.Popen(
                [binary_path, *plan.argv],
                env=env,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                errors="replace",
            )
            run = Run(
                run_id=run_id,
                tab_key=plan.tab_key,
                display_cmd=" ".join(plan.display_argv),
                dry_run=plan.dry_run,
                lock_path=lock_path,
                proc=proc,
            )
            self.runs[run_id] = run
            self.order.append(run_id)
            self.order = self.order[-25:]
            self.active_id = run_id
        run.append(f"$ {' '.join(plan.display_argv)}", "cmd")
        threading.Thread(target=self._pump, args=(run, cwd), daemon=True).start()
        return run

    def _pump(self, run: Run, cwd: Path) -> None:
        assert run.proc.stdout is not None
        try:
            for line in run.proc.stdout:
                run.append(line)
        except ValueError:
            pass
        code = run.proc.wait()
        if run.stopped and code != 0:
            run.append(f"⏹ stopped by user (exit {code})", "sys")
        else:
            run.append(
                f"✔ immich-go exited with code {code}", "ok" if code == 0 else "err"
            )
        run.exit_code = code
        release_lock(run.lock_path)
        shutil.rmtree(cwd, ignore_errors=True)
        with self._lock:
            if self.active_id == run.run_id:
                self.active_id = None
        run.done.set()

    def stop(self, run_id: str) -> Run | None:
        run = self.runs.get(run_id)
        if not run or run.finished:
            return run
        run.stopped = True
        run.append("⏹ stopping…", "sys")
        run.proc.terminate()
        threading.Timer(
            5.0, lambda: run.proc.poll() is None and run.proc.kill()
        ).start()
        return run

    def reset_all(self) -> int:
        """Force-clear locks and forget runs (mirrors Qt 'Reset Run State')."""
        from core.process_tracker import reset_all_locks

        n = reset_all_locks()
        with self._lock:
            self.runs.clear()
            self.order.clear()
            self.active_id = None
        return n


RUNS = RunManager()
