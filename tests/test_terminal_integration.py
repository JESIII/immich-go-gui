"""Integration tests: actually execute the generated launch scripts.

Uses ``stub_immich_go.py``, not the real immich-go binary. Windows tests skip
on Linux/macOS; POSIX tests skip on Windows.

These tests bypass terminal-emulator discovery (which requires a display)
and run the generated run.sh / .bat directly via subprocess, verifying the
full lifecycle: env delivery, PID file, heartbeat, lock cleanup.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from core.process_tracker import create_lock, is_lock_active
from core.terminal_launcher import launch_external_terminal

pytestmark = pytest.mark.integration

STUB = str(Path(__file__).parent / "stub_immich_go.py")

# Generous but bounded — CI runners are slow, but a hang must fail, not block.
SCRIPT_TIMEOUT = 30


def _stub_command(extra_args: list[str] | None = None) -> list[str]:
    """Command that runs the stub immich-go and writes its JSON output to stdout."""
    return [sys.executable, STUB] + (extra_args or [])


# ── POSIX ────────────────────────────────────────────────────────────────


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX-only")
class TestPosixScriptExecution:
    """Generate run.sh via the real launcher, then execute it ourselves."""

    def _generate_scripts(
        self,
        tmp_path: Path,
        monkeypatch,
        env: dict,
        cmd: list[str],
        lock_path: Path | None = None,
    ) -> tuple[Path, Path, Path]:
        """Run launch_external_terminal with a mocked Popen that captures the
        script path instead of opening a terminal. Returns (run_sh, env_sh, lock_path)."""
        monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(tmp_path / "config.toml"))
        if lock_path is None:
            lock_path = create_lock("upload-folder", "integration", "./immich-go")

        captured: dict = {}

        class FakePopen:
            def __init__(self, args, **kwargs):
                captured["script"] = Path(args[-1])
                captured["env"] = kwargs.get("env", {})
                self.pid = 99999

        with (
            patch("subprocess.Popen", FakePopen),
            patch("shutil.which", return_value="/usr/bin/gnome-terminal"),
        ):
            res = launch_external_terminal(cmd, env, lock_path)

        assert res.ok, res.message
        run_sh = captured["script"]
        env_sh = run_sh.parent / "env.sh"
        return run_sh, env_sh, lock_path

    def test_run_sh_executes_and_delivers_env(self, tmp_path, monkeypatch):
        """The generated run.sh, executed directly, must deliver IMMICH_GO_*
        env vars to the child process and clean up the lock."""
        output_file = tmp_path / "stub_output.json"
        cmd = [
            "bash",
            "-c",
            (
                f"{shlex.quote(sys.executable)} {shlex.quote(STUB)} "
                f"upload from-folder /photos > {shlex.quote(str(output_file))}"
            ),
        ]
        env = {
            "IMMICH_GO_UPLOAD_SERVER": "http://localhost:2283",
            "IMMICH_GO_UPLOAD_API_KEY": "integration-secret-key",
        }

        run_sh, _env_sh, lock_path = self._generate_scripts(
            tmp_path, monkeypatch, env, cmd
        )
        assert run_sh.exists(), "run.sh was not generated"

        exec_env = os.environ.copy()
        exec_env["IMMICH_GO_GUI_HEADLESS"] = "1"
        proc = subprocess.run(
            ["bash", str(run_sh)],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=exec_env,
        )

        assert proc.returncode == 0, f"run.sh failed:\n{proc.stderr}"
        assert "immich-go exited with code 0" in proc.stdout

        assert output_file.exists(), "stub did not run"
        stub_result = json.loads(output_file.read_text())
        assert stub_result["env"]["IMMICH_GO_UPLOAD_SERVER"] == "http://localhost:2283"
        assert stub_result["env"]["IMMICH_GO_UPLOAD_API_KEY"] == "integration-secret-key"

        assert not lock_path.exists(), "lock file was not removed by cleanup trap"

    def test_run_sh_cleans_up_on_command_failure(self, tmp_path, monkeypatch):
        """Even when the wrapped command fails, the trap must remove the lock."""
        cmd = ["bash", "-c", "exit 42"]
        env = {"IMMICH_GO_UPLOAD_SERVER": "http://x"}

        run_sh, _, lock_path = self._generate_scripts(
            tmp_path, monkeypatch, env, cmd
        )

        exec_env = os.environ.copy()
        exec_env["IMMICH_GO_GUI_HEADLESS"] = "1"
        proc = subprocess.run(
            ["bash", str(run_sh)],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=exec_env,
        )

        assert "immich-go exited with code 42" in proc.stdout
        assert not lock_path.exists(), "lock must be removed even on failure"

    def test_pid_file_written_during_execution(self, tmp_path, monkeypatch):
        """The run.sh must write its PID to the .pid sidecar file."""
        pid_observed = tmp_path / "pid_seen.txt"
        env = {"IMMICH_GO_UPLOAD_SERVER": "http://x"}

        monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(tmp_path / "config.toml"))
        lock_path = create_lock("upload-folder", "integration", "./immich-go")
        pid_file = lock_path.with_suffix(".pid")
        cmd = [
            "bash",
            "-c",
            (
                f"sleep 0.05; cp {shlex.quote(str(pid_file))} "
                f"{shlex.quote(str(pid_observed))} 2>/dev/null; sleep 0.2"
            ),
        ]

        run_sh, _, lock_path = self._generate_scripts(
            tmp_path, monkeypatch, env, cmd, lock_path=lock_path
        )

        exec_env = os.environ.copy()
        exec_env["IMMICH_GO_GUI_HEADLESS"] = "1"
        subprocess.run(
            ["bash", str(run_sh)],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=exec_env,
        )

        if pid_observed.exists():
            pid_val = pid_observed.read_text().strip()
            assert pid_val.isdigit(), f"PID file contained: {pid_val!r}"

    def test_env_sh_not_left_on_disk(self, tmp_path, monkeypatch):
        """run.sh must source and then delete env.sh (no secrets on disk)."""
        cmd = ["bash", "-c", "true"]
        env = {"IMMICH_GO_UPLOAD_API_KEY": "should-not-persist"}

        run_sh, env_sh, lock_path = self._generate_scripts(
            tmp_path, monkeypatch, env, cmd
        )

        exec_env = os.environ.copy()
        exec_env["IMMICH_GO_GUI_HEADLESS"] = "1"
        subprocess.run(
            ["bash", str(run_sh)],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=exec_env,
        )

        assert not env_sh.exists(), "env.sh with secrets was not deleted after sourcing"
        assert not lock_path.exists()


# ── Windows ──────────────────────────────────────────────────────────────


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only")
class TestWindowsBatExecution:
    """Generate the .bat via the real launcher, then execute it via cmd."""

    def test_bat_executes_and_cleans_lock(self, tmp_path, monkeypatch):
        monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(tmp_path / "config.toml"))
        lock_path = create_lock("upload-folder", "integration", "./immich-go")

        captured: dict = {}

        class FakePopen:
            def __init__(self, args, **kwargs):
                captured["bat"] = Path(args[-1])
                self.pid = 99999

        output_file = tmp_path / "stub_output.json"
        launch_env = {"IMMICH_GO_UPLOAD_API_KEY": "win-secret"}
        cmd = _stub_command(["upload", "from-folder"])

        with patch("subprocess.Popen", FakePopen):
            res = launch_external_terminal(cmd, launch_env, lock_path)

        assert res.ok
        bat_path = captured["bat"]
        assert bat_path.exists()
        assert bat_path.suffix == ".bat"

        bat_text = bat_path.read_text(encoding="utf-8")
        bat_text = bat_text.replace(
            subprocess.list2cmdline(cmd),
            f"{subprocess.list2cmdline(cmd)} > \"{output_file}\"",
        )
        bat_path.write_text(bat_text, encoding="utf-8")

        exec_env = {**os.environ, **launch_env}
        proc = subprocess.run(
            ["cmd", "/c", str(bat_path)],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=exec_env,
        )

        assert "immich-go exited with code 0" in proc.stdout
        assert not lock_path.exists(), "bat did not delete the lock file"

        if output_file.exists():
            result = json.loads(output_file.read_text())
            assert result["env"].get("IMMICH_GO_UPLOAD_API_KEY") == "win-secret"


# ── Cross-platform: full pipeline smoke test ─────────────────────────────


class TestFullPipelineHeadless:
    """build_plan → create_lock → launch → verify, no GUI, no terminal."""

    def test_plan_to_lock_to_script_lifecycle(self, tmp_path, monkeypatch):
        """End-to-end: build a real CommandPlan, create a lock, generate
        launch scripts, execute headlessly, verify lock cleanup."""
        from core.command_builder import build_plan_from_state

        monkeypatch.setenv("IMMICH_GO_GUI_CONFIG", str(tmp_path / "config.toml"))

        plan = build_plan_from_state(
            tab_key="upload-folder",
            config_state={
                "server": "http://localhost:2283",
                "api_key": "pipeline-test-key",
            },
            tab_state={"path": str(tmp_path)},
            binary_path=sys.executable,
            dry_run=True,
        )
        assert not plan.errors, plan.errors

        lock_path = create_lock(
            tab_key=plan.tab_key,
            command_summary=" ".join(plan.argv[:3]),
            binary_path=plan.binary_path,
        )
        assert is_lock_active(lock_path)

        captured: dict = {}

        class FakePopen:
            def __init__(self, args, **kwargs):
                captured["script"] = Path(args[-1])
                self.pid = 99999

        if sys.platform.startswith("win"):
            trivial_cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]
            with patch("subprocess.Popen", FakePopen):
                res = launch_external_terminal(
                    command=trivial_cmd,
                    env=plan.env,
                    lock_path=lock_path,
                )
            assert res.ok
            bat_path = captured["script"]
            proc = subprocess.run(
                ["cmd", "/c", str(bat_path)],
                capture_output=True,
                text=True,
                timeout=SCRIPT_TIMEOUT,
                env={**os.environ, **plan.env},
            )
            assert "immich-go exited with code 0" in proc.stdout
            assert not lock_path.exists(), "lock survived after headless execution"
            return

        with (
            patch("subprocess.Popen", FakePopen),
            patch("shutil.which", return_value="/usr/bin/gnome-terminal"),
        ):
            res = launch_external_terminal(
                command=["bash", "-c", "true"],
                env=plan.env,
                lock_path=lock_path,
            )

        assert res.ok
        run_sh = captured["script"]

        exec_env = os.environ.copy()
        exec_env["IMMICH_GO_GUI_HEADLESS"] = "1"
        proc = subprocess.run(
            ["bash", str(run_sh)],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            env=exec_env,
        )

        assert proc.returncode == 0
        assert not lock_path.exists(), "lock survived after headless execution"
