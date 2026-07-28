from PySide6.QtWidgets import QMessageBox

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
        from core.profile_manager import migrate_single_config_to_default

        migrate_single_config_to_default()
        self.app_config = load_config()

        if not default_config_path().exists():
            legacy_root = default_config_dir() / "config.toml"
            if not legacy_root.exists():
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
        cfg_path = default_config_path(
            getattr(self.app_config, "profile_name", "default")
        )
        try:
            save_config(self.app_config)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not write configuration to:\n{cfg_path}\n\n{exc}",
            )
            return

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

        msg = f"Configuration saved to:\n{cfg_path}"
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
