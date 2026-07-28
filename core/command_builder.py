"""Pure command-building and state validation logic for Immich-Go.

This module contains pure command generation logic and MUST NOT import PySide6 or Qt.
It operates entirely on plain Python dictionaries and primitive types.
"""

import glob
import os
import re
from typing import Any

from .models import CommandPlan, ValidationResult
from .cli_schema import (
    ENV_KEY_MAP,
    SECRET_FLAGS,
    SERVER_REQUIRED_TABS,
    SERVERLESS_TABS,
    TAB_COMMANDS,
    UPLOAD_TABS,
    flag_allowed_for_tab,
)
from .validation import (
    clean_date_range,
    normalize_extensions_csv,
    normalize_list_csv,
    validate_date_range as validate_date_range_func,
    validate_server_url,
    expand_source_paths,
    validate_destination_folder,
)


STRUCTURAL_KEYS = frozenset({"server", "skip-ssl", "dry-run"})
POSITIONAL_OWNED_KEYS = frozenset({"from-server", "from-date-range", "from-albums", "write-to"})


class FlagEmitter:
    """Helper class that checks per-tab flag allowlists before emitting CLI options."""

    def __init__(self, tab_key: str, strict: bool = False, plan: CommandPlan | None = None):
        self.tab_key = tab_key
        self.strict = strict
        self.opts: list[str] = []
        self.errors: list[str] = []
        self._plan = plan

    def _flag_name_from_arg(self, arg: str) -> str:
        a = arg.lstrip("-")
        return a.split("=", 1)[0]

    def _log(self, arg: str, source: str, key: str = "") -> None:
        if self._plan is not None:
            self._plan.emission_log.append({
                "flag": arg,
                "source": source,
                "key": key or self._flag_name_from_arg(arg),
            })

    def add_option(self, flag_name: str, value: Any, *, source: str = "advanced") -> bool:
        clean_name = str(flag_name).lstrip("-")
        val_str = str(value)
        if not val_str:
            return False
        if not flag_allowed_for_tab(self.tab_key, clean_name):
            err = f"Flag '--{clean_name}' is not allowed for tab '{self.tab_key}'"
            if self.strict:
                raise ValueError(err)
            self.errors.append(err)
            return False
        arg = f"--{clean_name}={val_str}"
        self.opts.append(arg)
        self._log(arg, source, clean_name)
        return True

    def add_flag(self, flag_name: str, enabled: bool = True, *, source: str = "advanced") -> bool:
        clean_name = str(flag_name).lstrip("-")
        if not enabled:
            return False
        if not flag_allowed_for_tab(self.tab_key, clean_name):
            err = f"Flag '--{clean_name}' is not allowed for tab '{self.tab_key}'"
            if self.strict:
                raise ValueError(err)
            self.errors.append(err)
            return False
        arg = f"--{clean_name}"
        self.opts.append(arg)
        self._log(arg, source, clean_name)
        return True

    def add_raw_checked(self, arg: str, *, source: str = "advanced") -> None:
        """Append a pre-formatted CLI arg that has already passed allowlist checks."""
        self.opts.append(arg)
        self._log(arg, source)

    def add_bool_val(self, flag_name: str, value: bool, *, source: str = "advanced") -> bool:
        clean_name = str(flag_name).lstrip("-")
        if not flag_allowed_for_tab(self.tab_key, clean_name):
            err = f"Flag '--{clean_name}' is not allowed for tab '{self.tab_key}'"
            if self.strict:
                raise ValueError(err)
            self.errors.append(err)
            return False
        arg = f"--{clean_name}={'true' if value else 'false'}"
        self.opts.append(arg)
        self._log(arg, source, clean_name)
        return True


def emit_bool_flag(
    emitter: FlagEmitter,
    flag_name: str,
    value: bool,
    default: bool = False,
    *,
    source: str = "advanced",
) -> None:
    """Emits boolean CLI options respecting CLI default value.
    - Default True: emits --<flag>=false if value is False.
    - Default False: emits --<flag> if value is True.
    """
    if default:
        if not value:
            emitter.add_bool_val(flag_name, False, source=source)
    else:
        if value:
            emitter.add_flag(flag_name, source=source)


def emit_if_not_default(
    emitter: FlagEmitter,
    flag_name: str,
    value: Any,
    default: Any = "",
    *,
    source: str = "advanced",
) -> None:
    """Emits CLI option if value is not equal to default and is non-empty."""
    if value != default and value not in ("", None):
        emitter.add_option(flag_name, value, source=source)


def _simple_value_is_default(value: Any, default: Any) -> bool:
    if value is None or value == "":
        return True
    return value == default


def _emit_simple_flag(
    emitter: FlagEmitter,
    flag_def: Any,
    value: Any,
    plan: CommandPlan,
) -> None:
    """Emit a simple-mode flag using its kind to format the CLI arg."""
    if flag_def.secret_env:
        if value:
            plan.env[flag_def.secret_env] = str(value).strip()
        return

    from .advanced_flags import advanced_flag_args

    args = advanced_flag_args(flag_def, value)
    for arg in args:
        emitter.add_raw_checked(arg, source="simple")
    warning = flag_def.warn_values.get(value)
    if warning:
        plan.warnings.append(warning)


def _emit_positional_owned_flags(
    tab_key: str,
    tab_state: dict,
    config_state: dict,
    emitter: FlagEmitter,
) -> None:
    """Emit flags owned by positional handler (not the path suffix)."""
    if tab_key == "upload-immich":
        from_server = tab_state.get("from-server", "")
        if from_server:
            emitter.add_option(
                "from-server", normalize_server_url(from_server), source="simple",
            )
    elif tab_key == "archive-immich":
        from_srv = tab_state.get("from-server", "") or config_state.get("server", "")
        if from_srv:
            emitter.add_option(
                "from-server", normalize_server_url(from_srv), source="simple",
            )

    write_to = tab_state.get("write-to")
    if write_to:
        abspath = os.path.abspath(os.path.expanduser(str(write_to).strip()))
        emitter.add_option("write-to-folder", abspath, source="simple")

    if tab_key in ("upload-immich", "archive-immich"):
        dr = str(tab_state.get("from-date-range", "")).strip()
        if dr:
            emitter.add_option("from-date-range", clean_date_range(dr), source="simple")
        for album in normalize_list_csv(tab_state.get("from-albums", "")):
            emitter.add_option("from-albums", album, source="simple")


def _collect_path_positional_args(tab_state: dict) -> list[str]:
    """Return trailing path positional args only."""
    path_opt: list[str] = []
    raw_path = str(tab_state.get("path", "")).strip()
    if raw_path:
        path_opt.extend(collect_paths(raw_path))
    return path_opt


_DATE_RANGE_RE = re.compile(
    r"^\d{4}(-\d{2}(-\d{2})?)?"
    r"(,\d{4}(-\d{2}(-\d{2})?)?)?$"
)


def normalize_server_url(url: str) -> str:
    """Normalize a server URL for CLI consumption."""
    url = url.strip()
    if not url:
        return ""

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    return url.rstrip("/")


def collect_paths(raw_text: str) -> list[str]:
    """Expands glob patterns, expands user tildes (~), and converts relative paths to absolute paths."""
    paths = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        expanded_user = os.path.expanduser(line)
        expanded = glob.glob(expanded_user, recursive=True)
        if expanded:
            for p in expanded:
                paths.append(os.path.abspath(p))
        else:
            paths.append(os.path.abspath(expanded_user))
    return paths


def validate_date_range(text: str) -> bool:
    """Validate immich-go date range format."""
    valid, _ = validate_date_range_func(text)
    return valid


def mask_command_for_display(command_parts: list[str]) -> list[str]:
    """Obfuscates secrets in command previews."""
    masked = []
    skip_next = False
    for part in command_parts:
        if skip_next:
            masked.append("********")
            skip_next = False
            continue

        if part in SECRET_FLAGS:
            masked.append(part)
            skip_next = True
            continue

        if "=" in part:
            flag, val = part.split("=", 1)
            if flag in SECRET_FLAGS:
                masked.append(f"{flag}=********")
                continue

        masked.append(part)

    return masked


def build_environment(
    tab_key: str,
    server: str,
    api_key: str,
    from_server: str = "",
    from_api_key: str = "",
    from_admin_api_key: str = "",
    admin_api_key: str = "",
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Builds a secure environment dict to pass secrets without CLI exposure."""
    if base_env is not None:
        env = base_env.copy()
    else:
        env = os.environ.copy()

    mapping = ENV_KEY_MAP.get(tab_key, {})

    srv_key = mapping.get("server")
    if srv_key and server:
        env[srv_key] = server

    from_srv_key = mapping.get("from_server")
    target_srv = from_server or server
    if from_srv_key and target_srv:
        env[from_srv_key] = target_srv

    api_key_name = mapping.get("api_key")
    if api_key_name and api_key:
        env[api_key_name] = api_key

    from_api_key_name = mapping.get("from_api_key")
    target_api_key = from_api_key or api_key
    if from_api_key_name and target_api_key:
        env[from_api_key_name] = target_api_key

    if tab_key == "upload-immich":
        if from_server:
            env["IMMICH_GO_UPLOAD_FROM_IMMICH_FROM_SERVER"] = from_server
        if from_api_key:
            env["IMMICH_GO_UPLOAD_FROM_IMMICH_FROM_API_KEY"] = from_api_key
        if from_admin_api_key:
            env["IMMICH_GO_UPLOAD_FROM_IMMICH_FROM_ADMIN_API_KEY"] = from_admin_api_key

    if admin_api_key:
        if tab_key in UPLOAD_TABS:
            env["IMMICH_GO_UPLOAD_ADMIN_API_KEY"] = admin_api_key
        elif tab_key == "stack":
            env["IMMICH_GO_STACK_ADMIN_API_KEY"] = admin_api_key
        elif tab_key == "archive-immich":
            env["IMMICH_GO_ARCHIVE_FROM_IMMICH_FROM_ADMIN_API_KEY"] = admin_api_key

    return env


def validate_state(
    tab_key: str,
    config_state: dict,
    tab_state: dict,
) -> ValidationResult:
    """Validates full input state for a tab."""
    res = ValidationResult()

    if tab_key in SERVER_REQUIRED_TABS:
        srv = config_state.get("server", "").strip()
        key = config_state.get("api_key", "").strip()
        if not srv:
            if tab_key == "archive-immich":
                res.errors.append("Source server URL is required. Configure it in the Configuration tab.")
            elif tab_key == "stack":
                res.errors.append("Immich server URL is required. Configure it in the Configuration tab.")
            else:
                res.errors.append("Server URL is required. Configure it in the Configuration tab.")
        else:
            ok, err = validate_server_url(srv)
            if not ok and err:
                res.errors.append(err)

        if not key:
            res.errors.append("API Key is required. Configure it in the Configuration tab.")

    if tab_key == "upload-folder":
        p = tab_state.get("path", "").strip()
        if not p:
            res.errors.append("Source folder path is required.")
        else:
            _, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)

    elif tab_key == "upload-gp":
        p = tab_state.get("path", "").strip()
        if not p:
            res.errors.append("Google Photos takeout source path is required.")
        else:
            _, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)

    elif tab_key == "upload-immich":
        fs = tab_state.get("from-server", "").strip()
        fk = tab_state.get("from-api-key", "").strip()
        if not fs:
            res.errors.append("Source Immich Server URL is required.")
        else:
            ok, err = validate_server_url(fs)
            if not ok and err:
                res.errors.append(f"Source {err}")
        if not fk:
            res.errors.append("Source Immich API Key is required.")

    elif tab_key == "upload-icloud":
        p = tab_state.get("path", "").strip()
        if not p:
            res.errors.append("iCloud export path is required.")
        else:
            _, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)

    elif tab_key == "upload-picasa":
        p = tab_state.get("path", "").strip()
        if not p:
            res.errors.append("Picasa collection path is required.")
        else:
            _, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)

    elif tab_key == "archive-folder":
        p = tab_state.get("path", "").strip()
        w = tab_state.get("write-to", "").strip()
        if not p:
            res.errors.append("Source folder path is required.")
        if not w:
            res.errors.append("Destination folder is required.")
        if p and w:
            expanded_sources, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)
            res.warnings.extend(validate_destination_folder(w, expanded_sources))

    elif tab_key == "archive-gp":
        p = tab_state.get("path", "").strip()
        w = tab_state.get("write-to", "").strip()
        if not p:
            res.errors.append("Google Photos takeout source path is required.")
        if not w:
            res.errors.append("Destination folder is required.")
        if p and w:
            expanded_sources, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)
            res.warnings.extend(validate_destination_folder(w, expanded_sources))

    elif tab_key == "archive-icloud":
        p = tab_state.get("path", "").strip()
        w = tab_state.get("write-to", "").strip()
        if not p:
            res.errors.append("iCloud export path is required.")
        if not w:
            res.errors.append("Destination folder is required.")
        if p and w:
            expanded_sources, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)
            res.warnings.extend(validate_destination_folder(w, expanded_sources))

    elif tab_key == "archive-picasa":
        p = tab_state.get("path", "").strip()
        w = tab_state.get("write-to", "").strip()
        if not p:
            res.errors.append("Picasa collection path is required.")
        if not w:
            res.errors.append("Destination folder is required.")
        if p and w:
            expanded_sources, path_warns = expand_source_paths(p)
            res.warnings.extend(path_warns)
            res.warnings.extend(validate_destination_folder(w, expanded_sources))

    elif tab_key == "archive-immich":
        w = tab_state.get("write-to", "").strip()
        if not w:
            res.errors.append("Destination folder is required.")
        else:
            res.warnings.extend(validate_destination_folder(w, []))

    # Date range validation across tabs
    for key in ("date-range", "from-date-range"):
        if key in tab_state and tab_state[key].strip():
            valid, err = validate_date_range_func(tab_state[key])
            if not valid:
                res.errors.append(f"Invalid date range format: {err}")

    return res


def build_plan_from_state(
    tab_key: str,
    config_state: dict,
    tab_state: dict,
    binary_path: str = "./immich-go",
    dry_run: bool = False,
    base_env: dict[str, str] | None = None,
    strict_schema: bool = False,
    advanced_state: dict | None = None,
) -> CommandPlan:
    """Converts configuration state, tab input state, and opt-in advanced state into a CommandPlan."""
    from .flag_registry import REGISTRY

    plan = CommandPlan()
    plan.tab_key = tab_key
    plan.dry_run = dry_run
    plan.binary_path = binary_path

    cmd_parts = TAB_COMMANDS.get(tab_key, [])
    if not cmd_parts:
        plan.errors.append(f"Unknown tab key: '{tab_key}'")
        return plan

    emitter = FlagEmitter(tab_key, strict=strict_schema, plan=plan)

    server = config_state.get("server", "")
    api_key = config_state.get("api_key", "")
    admin_api_key = config_state.get("admin_api_key", "")
    from_server = tab_state.get("from-server", "")
    from_api_key = tab_state.get("from-api-key", "")
    from_admin_api_key = tab_state.get("from-admin-api-key", "")

    plan.env = build_environment(
        tab_key=tab_key,
        server=normalize_server_url(server) if server else "",
        api_key=api_key,
        from_server=normalize_server_url(from_server) if from_server else "",
        from_api_key=from_api_key,
        from_admin_api_key=from_admin_api_key,
        admin_api_key=admin_api_key,
        base_env=base_env,
    )

    # ── 1. Structural flags ──────────────────────────────────
    if tab_key not in SERVERLESS_TABS and tab_key != "archive-immich":
        if server:
            emitter.add_option("server", normalize_server_url(server), source="always")

        if config_state.get("skip-ssl"):
            emitter.add_flag("skip-verify-ssl", source="always")
            plan.warnings.append(
                "SSL verification is disabled. "
                "Use only on trusted networks or self-hosted test servers."
            )

    # ── 2. Simple-mode widgets (emit if ≠ default) ─────────────
    for flag_def in REGISTRY.flags.get(tab_key, ()):
        if flag_def.mode != "simple":
            continue
        if (
            not flag_def.flag
            or flag_def.kind == "path"
            or flag_def.key in STRUCTURAL_KEYS
            or flag_def.key in POSITIONAL_OWNED_KEYS
        ):
            continue
        value = tab_state.get(flag_def.key)
        if _simple_value_is_default(value, flag_def.default):
            continue
        _emit_simple_flag(emitter, flag_def, value, plan)

    # ── 2b. Positional-owned flags (before advanced / dry-run) ─
    _emit_positional_owned_flags(tab_key, tab_state, config_state, emitter)

    # ── 3. Advanced rows (emit ONLY if enabled) ────────────────
    if advanced_state is not None:
        from .advanced_flags import apply_advanced_flags_to_plan
        apply_advanced_flags_to_plan(
            plan=plan,
            emitter=emitter,
            tab_key=tab_key,
            advanced_state=advanced_state,
        )

    # ── 4. Dry-run (trailing, before positional suffix) ────────
    if dry_run:
        emitter.add_flag("dry-run", source="button")
        if tab_key in ("upload-immich", "archive-immich"):
            emitter.add_flag("from-dry-run", source="button")

    # ── 5. Path positional suffix ──────────────────────────────
    path_opt = _collect_path_positional_args(tab_state)

    # ── 6. Safety: pause-jobs without admin key ────────────────
    if tab_key in UPLOAD_TABS or tab_key == "stack":
        has_pause = any("pause-immich-jobs" in o for o in emitter.opts)
        if not has_pause and not admin_api_key:
            emitter.add_bool_val("pause-immich-jobs", False, source="safety")
            plan.warnings.append(
                "Job pausing disabled: no Admin API Key is configured. "
                "Set an Admin API Key in the Configuration tab to enable "
                "pausing of Immich background jobs during upload."
            )

    if emitter.errors:
        plan.errors.extend(emitter.errors)

    plan.argv = cmd_parts + emitter.opts + path_opt
    plan.display_argv = mask_command_for_display([binary_path] + plan.argv)
    return plan
