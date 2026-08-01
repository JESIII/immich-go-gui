"""Invariant: serverless archive tabs must never emit server-related flags.

This enforces the architectural rule from AGENTS.md §3: serverless archive
tabs (archive-folder, archive-gp, archive-icloud, archive-picasa) must never
emit ``--server``, ``--api-key``, ``--admin-api-key``, or ``--client-timeout``.
"""

import pytest

from core.command_builder import build_plan_from_state
from core.flag_registry import REGISTRY

SERVER_FLAGS = ("--server", "--api-key", "--admin-api-key", "--client-timeout")


@pytest.mark.parametrize("tab_key", sorted(REGISTRY.serverless_tabs))
def test_serverless_tab_never_emits_server_flags(tab_key, tmp_path):
    """Even when server/api-key are present in config, serverless tabs must
    not emit any server-related CLI flag."""
    plan = build_plan_from_state(
        tab_key=tab_key,
        config_state={
            "server": "http://should-not-appear:2283",
            "api_key": "should-not-appear-key",
            "admin_api_key": "should-not-appear-admin",
            "skip-ssl": False,
            "client_timeout_minutes": 60,
        },
        tab_state={
            "path": str(tmp_path / "src"),
            "write-to": str(tmp_path / "out"),
        },
        binary_path="./immich-go",
        base_env={},
    )
    assert not plan.errors, plan.errors
    joined = " ".join(plan.argv)
    for flag in SERVER_FLAGS:
        assert flag not in joined, (
            f"Serverless tab {tab_key} emitted {flag}: {plan.argv}"
        )


@pytest.mark.parametrize("tab_key", sorted(REGISTRY.serverless_tabs))
def test_serverless_tab_starts_with_archive_command(tab_key, tmp_path):
    """Every serverless plan must start with the archive subcommand."""
    from core.cli_schema import TAB_COMMANDS

    plan = build_plan_from_state(
        tab_key=tab_key,
        config_state={},
        tab_state={
            "path": str(tmp_path / "src"),
            "write-to": str(tmp_path / "out"),
        },
        binary_path="./immich-go",
        base_env={},
    )
    assert not plan.errors, plan.errors
    expected = TAB_COMMANDS[tab_key]
    assert plan.argv[: len(expected)] == expected, (
        f"{tab_key}: expected prefix {expected}, got {plan.argv}"
    )
