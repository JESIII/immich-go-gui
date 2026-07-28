from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
)

from core import (
    AppConfig,
    SecretStore,
    default_config_path,
    get_config_load_warning,
    get_secret_with_fallback,
    load_config,
    save_config,
    save_secret_with_fallback,
    set_api_key,
)
from theme import THEME_SYSTEM, normalize_theme_mode


class PersistenceMixin:
    def collect_form_state(self) -> dict:
        secret_keys = {
            "api_key",
            "from-api-key",
            "admin_api_key",
            "from-admin-api-key",
            "target-server",
        }
        fields = {}
        for tab_key, widgets in self.inputs.items():
            tab_dict = {}
            for k, widget in widgets.items():
                if k in secret_keys:
                    continue
                if isinstance(widget, QLineEdit):
                    tab_dict[k] = widget.text()
                elif isinstance(widget, QPlainTextEdit):
                    tab_dict[k] = widget.toPlainText()
                elif isinstance(widget, QCheckBox):
                    tab_dict[k] = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    tab_dict[k] = widget.currentText()
                elif isinstance(widget, QSpinBox):
                    tab_dict[k] = widget.value()
            if tab_dict:
                fields[tab_key] = tab_dict

        adv_state = {}
        for tab_key, rows in getattr(self, "adv_rows", {}).items():
            tab_adv = {}
            for k, row in rows.items():
                if k == "from-dry-run":
                    continue
                st = row.state()
                if (getattr(row, "def_", None) and row.def_.secret_env) or (
                    k in secret_keys
                ):
                    st = {"enabled": False, "value": ""}
                tab_adv[k] = st
            if tab_adv:
                adv_state[tab_key] = tab_adv

        return {
            "fields": fields,
            "advanced": adv_state,
        }

    def apply_form_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return

        if "fields" in state or "advanced" in state:
            fields_state = state.get("fields", {})
            advanced_state = state.get("advanced", {})
        else:
            fields_state = state
            advanced_state = {}

        secret_keys = {
            "api_key",
            "from-api-key",
            "admin_api_key",
            "from-admin-api-key",
            "target-server",
        }
        for tab_key, tab_dict in fields_state.items():
            if tab_key in self.inputs and isinstance(tab_dict, dict):
                for k, val in tab_dict.items():
                    if k in secret_keys:
                        continue
                    widget = self.inputs[tab_key].get(k)
                    if widget is None:
                        continue
                    try:
                        widget.blockSignals(True)
                        if isinstance(widget, QLineEdit) and isinstance(val, str):
                            widget.setText(val)
                        elif isinstance(widget, QPlainTextEdit) and isinstance(
                            val, str
                        ):
                            widget.setPlainText(val)
                        elif isinstance(widget, QCheckBox) and isinstance(val, bool):
                            widget.setChecked(val)
                        elif isinstance(widget, QComboBox) and isinstance(val, str):
                            widget.setCurrentText(val)
                        elif isinstance(widget, QSpinBox) and isinstance(
                            val, (int, float)
                        ):
                            widget.setValue(int(val))
                    finally:
                        widget.blockSignals(False)

        if isinstance(advanced_state, dict):
            for tab_key, tab_adv in advanced_state.items():
                rows = getattr(self, "adv_rows", {}).get(tab_key, {})
                if isinstance(tab_adv, dict):
                    for k, row_state in tab_adv.items():
                        row = rows.get(k)
                        if row is not None and isinstance(row_state, dict):
                            row.set_state(row_state)

    def _collect_config_state(self) -> dict:
        c = self.inputs.get("config", {})
        return {
            "server": c.get("server").text() if c.get("server") else "",
            "api_key": c.get("api_key").text().strip() if c.get("api_key") else "",
            "admin_api_key": c.get("admin_api_key").text().strip()
            if c.get("admin_api_key")
            else "",
            "secrets_provider": c.get("secret_provider").currentData()
            if c.get("secret_provider")
            else "keyring",
            "skip-ssl": c.get("skip-ssl").isChecked() if c.get("skip-ssl") else False,
        }

    def _collect_tab_state(self, tab_key: str) -> dict:
        return self._raw_tab_state(tab_key)

    def _raw_tab_state(self, tab_key: str) -> dict:
        if tab_key not in self.inputs:
            return {}
        c = self.inputs[tab_key]

        def get_text(k: str, default: str = "") -> str:
            w = c.get(k)
            if not w:
                return default
            if hasattr(w, "text"):
                return w.text()
            if hasattr(w, "toPlainText"):
                return w.toPlainText()
            return default

        def get_bool(k: str, default: bool = False) -> bool:
            w = c.get(k)
            if not w:
                return default
            if hasattr(w, "isChecked"):
                return w.isChecked()
            return default

        def get_combo(k: str, default: str = "") -> str:
            w = c.get(k)
            if not w:
                return default
            if hasattr(w, "currentText"):
                return w.currentText()
            return default

        def get_int(k: str, default: int = 0) -> int:
            w = c.get(k)
            if not w:
                return default
            if hasattr(w, "value"):
                return w.value()
            return default

        if tab_key == "upload-folder":
            return {
                "path": get_text("path"),
                "folder-album": get_combo("folder-album", "NONE"),
                "into-album": get_text("into-album"),
                "manage-burst": get_combo("manage-burst", "NoStack"),
                "manage-raw-jpeg": get_combo("manage-raw-jpeg", "NoStack"),
                "manage-heic-jpeg": get_combo("manage-heic-jpeg", "NoStack"),
            }

        elif tab_key == "upload-gp":
            return {
                "path": get_text("path"),
                "include-partner": get_bool("include-partner", True),
                "sync-albums": get_bool("sync-albums", True),
                "include-archived": get_bool("include-archived", True),
                "manage-burst": get_combo("manage-burst", "NoStack"),
                "manage-heic-jpeg": get_combo("manage-heic-jpeg", "NoStack"),
            }

        elif tab_key == "upload-icloud":
            return {
                "path": get_text("path"),
                "manage-burst": get_combo("manage-burst", "NoStack"),
                "manage-raw-jpeg": get_combo("manage-raw-jpeg", "NoStack"),
                "manage-heic-jpeg": get_combo("manage-heic-jpeg", "NoStack"),
            }

        elif tab_key == "upload-picasa":
            return {
                "path": get_text("path"),
                "folder-album": get_combo("folder-album", "NONE"),
                "into-album": get_text("into-album"),
                "manage-burst": get_combo("manage-burst", "NoStack"),
                "manage-raw-jpeg": get_combo("manage-raw-jpeg", "NoStack"),
                "manage-heic-jpeg": get_combo("manage-heic-jpeg", "NoStack"),
            }

        elif tab_key == "upload-immich":
            return {
                "from-server": get_text("from-server"),
                "from-api-key": get_text("from-api-key"),
                "from-date-range": get_text("from-date-range"),
                "from-albums": get_text("from-albums"),
            }

        elif tab_key == "archive-folder":
            return {
                "path": get_text("path"),
                "write-to": get_text("write-to"),
            }

        elif tab_key == "archive-gp":
            return {
                "path": get_text("path"),
                "write-to": get_text("write-to"),
                "include-partner": get_bool("include-partner", True),
                "sync-albums": get_bool("sync-albums", True),
                "include-archived": get_bool("include-archived", True),
            }

        elif tab_key == "archive-icloud" or tab_key == "archive-picasa":
            return {
                "path": get_text("path"),
                "write-to": get_text("write-to"),
            }

        elif tab_key == "archive-immich":
            return {
                "write-to": get_text("write-to"),
                "from-date-range": get_text("from-date-range"),
                "from-albums": get_text("from-albums"),
            }

        elif tab_key == "stack":
            return {
                "manage-burst": get_combo("manage-burst", "NoStack"),
                "manage-raw-jpeg": get_combo("manage-raw-jpeg", "NoStack"),
                "manage-heic-jpeg": get_combo("manage-heic-jpeg", "NoStack"),
            }

        return {}

    def _collect_advanced_state(self, tab_key: str | None = None) -> dict | None:
        if not getattr(self, "is_advanced", False):
            return None
        if tab_key is not None:
            rows = getattr(self, "adv_rows", {}).get(tab_key, {})
            return {key: row.state() for key, row in rows.items()}
        return {
            tab: {key: row.state() for key, row in rows.items()}
            for tab, rows in getattr(self, "adv_rows", {}).items()
        }

    def _migrate_legacy_qsettings_to_config(self):
        cfg = AppConfig()
        cfg.server_url = self.settings.value("server_url", "")
        cfg.skip_ssl = self.settings.value("skip_ssl", False, type=bool)
        cfg.theme_mode = normalize_theme_mode(
            self.settings.value("theme_mode", THEME_SYSTEM)
        )
        save_config(cfg)
        old_key = self.settings.value("api_key", "")
        if old_key:
            set_api_key(old_key, cfg)
            self.settings.remove("api_key")
            self.settings.sync()

    def load_configuration(self):
        self.app_config = load_config()

        if not default_config_path().exists():
            self._migrate_legacy_qsettings_to_config()
            self.app_config = load_config()

        self.inputs["config"]["server"].setText(self.app_config.server_url)

        if "skip-ssl" in self.inputs["config"]:
            self.inputs["config"]["skip-ssl"].setChecked(self.app_config.skip_ssl)

        if "secret_provider" in self.inputs["config"]:
            idx = self.inputs["config"]["secret_provider"].findData(
                self.app_config.secrets_provider
            )
            if idx >= 0:
                self.inputs["config"]["secret_provider"].setCurrentIndex(idx)

        prof_name = getattr(self.app_config, "profile_name", "default")
        self.inputs["config"]["api_key"].setText(
            get_secret_with_fallback(
                profile_name=prof_name,
                key="api_key",
                provider=self.app_config.secrets_provider,
            )
        )

        if "admin_api_key" in self.inputs["config"]:
            self.inputs["config"]["admin_api_key"].setText(
                get_secret_with_fallback(
                    profile_name=prof_name,
                    key="admin_api_key",
                    provider=self.app_config.secrets_provider,
                )
            )

        if "allow_untested_updates" in self.inputs["config"]:
            self.inputs["config"]["allow_untested_updates"].setChecked(
                self.app_config.allow_untested_updates
            )

        if "preferred_terminal" in self.inputs["config"]:
            self.inputs["config"]["preferred_terminal"].setCurrentText(
                self.app_config.preferred_terminal
            )

        self.apply_form_state(self.app_config.form_state)

        self.theme_mode = normalize_theme_mode(self.app_config.theme_mode)

        if hasattr(self, "theme_mode_combo"):
            self.theme_mode_combo.blockSignals(True)
            self.theme_mode_combo.setCurrentText(self.theme_mode)
            self.theme_mode_combo.blockSignals(False)

        self.apply_theme(self.theme_mode)
        self.toggle_advanced(self.app_config.advanced_mode)

        cfg_warning = get_config_load_warning()
        if cfg_warning:
            QMessageBox.warning(self, "Configuration Reset", cfg_warning)

        self.update_window_title()
        self._update_secret_status()

    def save_configuration(self, show_popup: bool = True):
        self.app_config.server_url = self.inputs["config"]["server"].text()

        if "skip-ssl" in self.inputs["config"]:
            self.app_config.skip_ssl = self.inputs["config"]["skip-ssl"].isChecked()

        if "secret_provider" in self.inputs["config"]:
            self.app_config.secrets_provider = self.inputs["config"][
                "secret_provider"
            ].currentData()

        if "allow_untested_updates" in self.inputs["config"]:
            self.app_config.allow_untested_updates = self.inputs["config"][
                "allow_untested_updates"
            ].isChecked()

        if "preferred_terminal" in self.inputs["config"]:
            self.app_config.preferred_terminal = self.inputs["config"][
                "preferred_terminal"
            ].currentText()

        if hasattr(self, "theme_mode_combo"):
            self.app_config.theme_mode = self.theme_mode_combo.currentText()

        self.app_config.form_state = self.collect_form_state()
        save_config(self.app_config)

        prof_name = getattr(self.app_config, "profile_name", "default")
        api_key = self.inputs["config"]["api_key"].text().strip()
        admin_key = (
            self.inputs["config"]["admin_api_key"].text().strip()
            if "admin_api_key" in self.inputs["config"]
            else ""
        )

        res_api = save_secret_with_fallback(
            profile_name=prof_name,
            key="api_key",
            value=api_key,
            provider=self.app_config.secrets_provider,
        )
        res_admin = save_secret_with_fallback(
            profile_name=prof_name,
            key="admin_api_key",
            value=admin_key,
            provider=self.app_config.secrets_provider,
        )

        msg = "Configuration saved successfully."
        if res_api.message:
            msg += f"\n\nNote (API Key): {res_api.message}"
        if res_admin.message:
            msg += f"\n\nNote (Admin Key): {res_admin.message}"

        if show_popup:
            QMessageBox.information(
                self,
                "Saved",
                msg,
            )
        self._update_secret_status()

    def _probe_keyring(self) -> bool:
        """One-time check: can we actually talk to the keyring?"""
        try:
            import keyring

            keyring.get_password("immich-go-gui-probe", "probe")
            return True
        except Exception:
            return False

    def _secrets_file_has_key(self) -> bool:
        from core.config_manager import load_secrets

        return bool(load_secrets().get("api_key"))

    def _update_secret_status(self):
        """Shows whether secrets are in keyring or file fallback."""
        if not hasattr(self, "lbl_secret_status"):
            return
        prof = getattr(self.app_config, "profile_name", "default")
        provider = self.app_config.secrets_provider
        api_val = SecretStore.get_secret(prof, "api_key")
        if provider == "keyring" and api_val:
            self.lbl_secret_status.setText("Secrets stored in OS keyring")
            self.lbl_secret_status.setStyleSheet("color: #22C55E;")
        elif provider == "config" or (not api_val and self._secrets_file_has_key()):
            self.lbl_secret_status.setText(
                "Secrets stored in plaintext secrets.toml — prefer OS keyring"
            )
            self.lbl_secret_status.setStyleSheet("color: #E5C07B;")
        else:
            self.lbl_secret_status.setText("")
