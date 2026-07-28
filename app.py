# nuitka-project: --assume-yes-for-downloads
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --include-data-files=immich-go-gui.png=immich-go-gui.png
# nuitka-project: --include-data-files=core/flags.toml=core/flags.toml
# nuitka-project: --include-data-dir=core/fixtures=core/fixtures

# nuitka-project-if: {OS} == "Windows":
#   nuitka-project: --standalone
#   nuitka-project: --windows-console-mode=disable
#   nuitka-project: --windows-icon-from-ico=immich-go-gui.ico
#   nuitka-project: --company-name="Shitan198u"
#   nuitka-project: --product-name="Immich-Go GUI"
#   nuitka-project: --file-description="Immich-Go Graphical User Interface"
#   nuitka-project: --copyright="MIT License"

# nuitka-project-if: {OS} == "Darwin":
#   nuitka-project: --macos-create-app-bundle

# nuitka-project-if: {OS} == "Linux":
#   nuitka-project: --standalone

import sys
import os
import subprocess
import shlex
import webbrowser
import logging
import traceback
import zipfile
import tomllib
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version as _pkg_version

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QPushButton,
    QFileDialog,
    QPlainTextEdit,
    QStackedWidget,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QMessageBox,
    QDialog,
    QProgressBar,
    QSpinBox,
    QStyle,
    QLayout,
    QFormLayout,
    QToolButton,
    QTabWidget,
)
from PySide6.QtGui import (
    QAction,
    QPainter,
    QPen,
    QColor,
    QBrush,
    QFont,
    QIcon,
    QDesktopServices,
)
from PySide6.QtCore import Qt, QEvent, QTimer, QSettings, QThread, Signal, QSize, QUrl

SP = QStyle.StandardPixmap

from theme import (
    THEME_SYSTEM,
    THEME_LIGHT,
    THEME_DARK,
    normalize_theme_mode,
    set_fusion_style,
    apply_application_theme,
    connect_system_theme_changes,
    connect_screen_changes,
    load_themed_icon,
    clear_icon_cache,
)
from gui.tabs.config_tab import build_config_tab
from gui.tabs.stack_tab import build_stack_tab
from gui.tabs.upload.folder import build_upload_folder_tab
from gui.tabs.upload.google_photos import build_upload_gp_tab
from gui.tabs.upload.immich import build_upload_immich_tab
from gui.tabs.upload.icloud import build_upload_icloud_tab
from gui.tabs.upload.picasa import build_upload_picasa_tab
from gui.tabs.archive.folder import build_archive_folder_tab
from gui.tabs.archive.google_photos import build_archive_gp_tab
from gui.tabs.archive.icloud import build_archive_icloud_tab
from gui.tabs.archive.picasa import build_archive_picasa_tab
from gui.tabs.archive.immich import build_archive_immich_tab

from core.network import (
    test_immich_connection,
    check_preflight_server_connection,
    normalize_server_url,
)
from core.profile_manager import (
    list_profiles,
    active_profile_name,
    set_active_profile_name,
    create_profile,
    rename_profile,
    duplicate_profile,
    delete_profile,
    validate_profile_name,
)
from core.process_tracker import (
    create_lock,
    release_lock,
    is_lock_active,
    scan_locks,
    cleanup_stale_locks,
)
from core.terminal_launcher import launch_external_terminal
from core.flag_registry import REGISTRY
from core.advanced_flags import ADVANCED_FLAGS
from core.logging_config import setup_logging
from core import (
    AppConfig,
    BINARY_BASE_DIR,
    METADATA_PATH,
    TESTED_IMMICH_GO_VERSION,
    SERVER_REQUIRED_TABS,
    BinaryManager,
    CommandPlan,
    SecretStore,
    ValidationResult,
    build_environment,
    build_plan_from_state,
    clean_version,
    collect_safety_warnings,
    default_config_dir,
    default_config_path,
    default_secrets_path,
    get_binary_path,
    get_config_load_warning,
    get_secret_with_fallback,
    load_binary_metadata,
    load_config,
    save_binary_metadata,
    save_config,
    save_secret_with_fallback,
    set_api_key,
    validate_state,
    validate_state_light,
)
from core.config_manager import SecretStore, get_config_load_warning
from core.command_builder import (
    collect_paths,
    mask_command_for_display,
    build_environment,
    validate_date_range,
)
from core.models import CommandPlan


def _gui_version() -> str:
    try:
        return _pkg_version("immich-go-gui")
    except PackageNotFoundError:
        return "dev"


def _install_exception_hook(log: logging.Logger | None = None) -> None:
    """Log unhandled exceptions and show a non-blocking error dialog."""
    logger = log or logging.getLogger("immich_go_gui")
    default_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        if exc_type is KeyboardInterrupt:
            default_hook(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        try:
            if QApplication.instance() is not None:

                def _show_dialog():
                    QMessageBox.critical(
                        None,
                        "Unexpected Error",
                        "An unexpected error occurred.\n\nSee the log file for details.",
                    )

                QTimer.singleShot(0, _show_dialog)
        except Exception:
            pass
        default_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


_SENSITIVE_FIELD_KEYS = frozenset(
    {
        "api_key",
        "api-key",
        "admin_api_key",
        "admin-api-key",
        "from-api-key",
        "from-admin-api-key",
    }
)


def _redact_diagnostics_toml(text: str) -> str:
    """Return TOML text with secret-like values redacted for diagnostics export."""
    try:
        data = tomllib.loads(text)
    except Exception:
        return "# [unparseable config omitted]\n"

    form_state = data.get("form_state")
    if isinstance(form_state, dict):

        def _redact_mapping(mapping: dict) -> None:
            for key, value in list(mapping.items()):
                key_l = str(key).lower()
                if any(s in key_l for s in ("api", "secret", "password", "token")):
                    mapping[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    _redact_mapping(value)

        _redact_mapping(form_state)

    try:
        import tomli_w

        return tomli_w.dumps(data)
    except Exception:
        return "# [config redaction failed]\n"


from gui.browse_dialogs import BrowseDialogsMixin
from gui.widgets import (
    DroppableLineEdit,
    DroppablePlainTextEdit,
    SwitchButton,
    AdvancedFlagRow,
    Card,
    FormSection,
    ElidingLabel,
    BasePage,
    NavItem,
    NavGroup,
    StatusCard,
)



# ==========================================================
# MAIN APPLICATION
# ==========================================================


class ImmichGoGUI(QMainWindow, BrowseDialogsMixin):

    TAB_KEYS = [
        "config",
        "upload",
        "archive",
        "stack",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Immich Go GUI")
        self.resize(1250, 750)
        self.setMinimumSize(900, 600)

        self.log = setup_logging()
        self.log.info("GUI started, profile=%s", active_profile_name())

        self.binary_manager = BinaryManager()
        self.app_config = load_config()
        self.settings = QSettings("Shitan198u", "ImmichGoGUI")

        # FIX Phase 1 #6: migrate old plain-text API key to keychain
        SecretStore.migrate_from_qsettings(self.settings)

        from core.terminal_launcher import cleanup_stale_temp_dirs

        cleanup_stale_temp_dirs()
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.timeout.connect(
            lambda: cleanup_stale_temp_dirs(max_age_hours=24)
        )
        self._cleanup_timer.start(6 * 3600 * 1000)  # 6 hours

        self._status_debounce = QTimer(self)
        self._status_debounce.setSingleShot(True)
        self._status_debounce.setInterval(150)
        self._status_debounce.timeout.connect(self._do_update_status)

        self.theme_mode = normalize_theme_mode(
            self.settings.value("theme_mode", THEME_SYSTEM)
        )
        apply_application_theme(self.theme_mode)

        self.is_advanced = False
        self.adv_rows = {}

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.inputs = {}
        self.adv_frames = []
        self._field_error_labels: dict[tuple[str, str], QLabel] = {}

        self._build_sidebar()
        self._build_content_area()
        self.create_menu_bar()

        self.config_tab = self._build_config_tab()
        self.upload_page = self._build_upload_page()
        self.archive_page = self._build_archive_page()
        self.stack_tab = self._build_stack_tab()

        self.stacked_widget.addWidget(self.config_tab)
        self.stacked_widget.addWidget(self.upload_page)
        self.stacked_widget.addWidget(self.archive_page)
        self.stacked_widget.addWidget(self.stack_tab)

        self.stacked_widget.setCurrentIndex(0)
        self.update_header_crumb("configuration")
        self.footer.setVisible(False)

        self.check_binary_version()
        self.load_configuration()
        self.apply_theme(self.theme_mode)
        connect_system_theme_changes(self.on_system_theme_changed)
        connect_screen_changes(self._on_screen_changed)

        if not self._probe_keyring() and self.app_config.secrets_provider == "keyring":
            QMessageBox.warning(
                self,
                "Keyring Unavailable",
                "The OS keyring is not available on this system.\n\n"
                "API keys will be stored in plaintext in secrets.toml.\n"
                "Consider installing a Secret Service provider "
                "(GNOME Keyring, KWallet) for secure storage.",
            )

        cleanup_stale_locks()
        active_locks = scan_locks()
        self.active_lock_paths = {lock.lock_path for lock in active_locks}
        self.active_lock_path = active_locks[0].lock_path if active_locks else None
        self.running_process = bool(self.active_lock_paths)
        if self.active_lock_path:
            self._start_process_timer()

        self.stacked_widget.currentChanged.connect(lambda: self.update_status())

        for tab_dict in self.inputs.values():
            for widget in tab_dict.values():
                if isinstance(widget, QLineEdit):
                    widget.textChanged.connect(
                        lambda _, w=widget: self._schedule_status_update()
                    )
                elif isinstance(widget, QCheckBox):
                    widget.toggled.connect(
                        lambda _, w=widget: self._schedule_status_update()
                    )
                elif isinstance(widget, QComboBox):
                    widget.currentIndexChanged.connect(
                        lambda _, w=widget: self._schedule_status_update()
                    )
                elif isinstance(widget, QSpinBox):
                    widget.valueChanged.connect(
                        lambda _, w=widget: self._schedule_status_update()
                    )
                elif isinstance(widget, QPlainTextEdit):
                    widget.textChanged.connect(
                        lambda w=widget: self._schedule_status_update()
                    )

        self.update_status()

    def _get_active_tab_key(self) -> str:
        idx = self.stacked_widget.currentIndex()
        if idx == 0:
            return "config"
        elif idx == 1:
            u_idx = (
                self.upload_tabs.currentIndex() if hasattr(self, "upload_tabs") else 0
            )
            if u_idx == 0:
                return "upload-folder"
            elif u_idx == 1:
                return "upload-gp"
            elif u_idx == 2:
                return "upload-icloud"
            elif u_idx == 3:
                return "upload-picasa"
            else:
                return "upload-immich"
        elif idx == 2:
            a_idx = (
                self.archive_tabs.currentIndex() if hasattr(self, "archive_tabs") else 0
            )
            if a_idx == 0:
                return "archive-folder"
            elif a_idx == 1:
                return "archive-gp"
            elif a_idx == 2:
                return "archive-icloud"
            elif a_idx == 3:
                return "archive-picasa"
            else:
                return "archive-immich"
        elif idx == 3:
            return "stack"
        return "config"

    def _build_advanced_flags_card(self, tab_key: str):
        card = Card("Advanced Flags")
        form = FormSection()

        hint = QLabel(
            "Advanced flags are disabled by default. "
            "Check the box next to a flag to enable it and pass it to immich-go."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form.addRow("", hint)

        if not hasattr(self, "adv_rows"):
            self.adv_rows = {}
        self.adv_rows[tab_key] = {}

        for def_ in ADVANCED_FLAGS.get(tab_key, ()):
            row = AdvancedFlagRow(def_)
            row.enable.toggled.connect(lambda _, r=row: self._schedule_status_update())
            if hasattr(row.value_widget, "textChanged"):
                row.value_widget.textChanged.connect(
                    lambda *_, r=row: self._schedule_status_update()
                )
            elif hasattr(row.value_widget, "currentIndexChanged"):
                row.value_widget.currentIndexChanged.connect(
                    lambda _, r=row: self._schedule_status_update()
                )
            elif hasattr(row.value_widget, "valueChanged"):
                row.value_widget.valueChanged.connect(
                    lambda _, r=row: self._schedule_status_update()
                )
            self.adv_rows[tab_key][def_.key] = row
            form.addRow("", row)

        card.layout.addLayout(form)
        card.setVisible(False)
        self.adv_frames.append(card)
        return card

    # ==========================================================
    # THEME METHODS
    # ==========================================================

    def apply_theme(self, mode=None):
        if mode is None:
            mode = getattr(self, "theme_mode", THEME_SYSTEM)
        mode = normalize_theme_mode(mode)
        self.theme_mode = mode
        if hasattr(self, "settings"):
            self.settings.setValue("theme_mode", mode)
        if hasattr(self, "theme_mode_combo"):
            self.theme_mode_combo.blockSignals(True)
            self.theme_mode_combo.setCurrentText(mode)
            self.theme_mode_combo.blockSignals(False)
        resolved = apply_application_theme(mode)
        clear_icon_cache()
        for widget in self.findChildren(QWidget):
            try:
                widget.update()
            except TypeError:
                pass
        self.refresh_sidebar_icons(resolved)
        self.update()

    def refresh_sidebar_icons(self, theme: str):
        if not hasattr(self, "btn_config"):
            return
        nav_buttons = [
            self.btn_config,
            self.btn_upload,
            self.btn_archive,
            self.btn_stack,
        ]
        for btn in nav_buttons:
            if hasattr(btn, "icon_name") and btn.icon_name:
                btn.setIcon(load_themed_icon(btn.icon_name, theme))
                btn.setIconSize(QSize(18, 18))
        for action in self.findChildren(QAction):
            if hasattr(action, "icon_name") and action.icon_name:
                action.setIcon(load_themed_icon(action.icon_name, theme))

    def on_system_theme_changed(self):
        if getattr(self, "theme_mode", THEME_SYSTEM) == THEME_SYSTEM:
            QTimer.singleShot(0, lambda: self.apply_theme(THEME_SYSTEM))

    def _on_screen_changed(self):
        clear_icon_cache()
        resolved = apply_application_theme(self.theme_mode)
        self.refresh_sidebar_icons(resolved)

    def _make_field_error_label(self) -> QLabel:
        lbl = QLabel("")
        lbl.setObjectName("FieldError")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #E06C75; font-size: 12px;")
        lbl.hide()
        return lbl

    def _register_field_error_label(
        self, tab_key: str, field_key: str, label: QLabel
    ) -> None:
        self._field_error_labels[(tab_key, field_key)] = label

    def _wrap_with_field_error(
        self, tab_key: str, field_key: str, widget: QWidget
    ) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(widget)
        err = self._make_field_error_label()
        layout.addWidget(err)
        self._register_field_error_label(tab_key, field_key, err)
        self._bind_field_error_clear(tab_key, field_key, widget)
        return container

    def _bind_field_error_clear(self, tab_key: str, field_key: str, widget) -> None:
        def clear_error(*_args):
            self._clear_field_error(tab_key, field_key)

        if hasattr(widget, "textChanged"):
            widget.textChanged.connect(clear_error)
        elif hasattr(widget, "plainTextChanged"):
            widget.plainTextChanged.connect(clear_error)

    def _clear_field_error(self, tab_key: str, field_key: str) -> None:
        lbl = self._field_error_labels.get((tab_key, field_key))
        if lbl is not None:
            lbl.clear()
            lbl.hide()

    def _apply_field_errors(
        self, tab_key: str, field_errors: dict[str, str] | None
    ) -> None:
        field_errors = field_errors or {}
        for (label_tab, field_key), lbl in self._field_error_labels.items():
            if field_key in ("server", "api_key"):
                msg = field_errors.get(field_key, "")
            elif label_tab == tab_key:
                msg = field_errors.get(field_key, "")
            else:
                msg = ""
            if msg:
                lbl.setText(msg)
                lbl.show()
            else:
                lbl.clear()
                lbl.hide()

    def event(self, e):
        if e.type() == QEvent.Type.ThemeChange:
            if getattr(self, "theme_mode", THEME_SYSTEM) == THEME_SYSTEM:
                QTimer.singleShot(0, lambda: self.apply_theme(THEME_SYSTEM))
        return super().event(e)

    # ==========================================================
    # UI STRUCTURE BUILDERS
    # ==========================================================

    def _add_ssl_skip_row(
        self,
        form: FormSection,
        tab_dict: dict,
        key: str = "skip-ssl",
        label_text: str = "Skip SSL Verification",
    ):
        chk_ssl = QCheckBox(label_text)
        tab_dict[key] = chk_ssl
        container = QVBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(4)
        container.addWidget(chk_ssl)
        warn_lbl = QLabel(
            "⚠️ Skipping SSL verification reduces security. "
            "Use only for trusted self-hosted servers with self-signed certificates."
        )
        warn_lbl.setObjectName("WarningHint")
        warn_lbl.setWordWrap(True)
        warn_lbl.setVisible(False)
        container.addWidget(warn_lbl)
        chk_ssl.toggled.connect(warn_lbl.setVisible)
        form.addRow("", container)
        return chk_ssl

    # FIX Phase 3 #32: helper to add trailing browse action on a QLineEdit
    def _add_browse_action(self, line_edit: QLineEdit, title: str):
        theme = getattr(self, "theme_mode", "dark")
        action = line_edit.addAction(
            load_themed_icon("folder", theme), QLineEdit.ActionPosition.TrailingPosition
        )
        action.icon_name = "folder"
        action.triggered.connect(lambda: self._browse_into(line_edit, title))
        for child in line_edit.findChildren(QToolButton):
            child.setAutoRaise(True)
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _browse_into(self, line_edit: QLineEdit, title: str):
        folder = QFileDialog.getExistingDirectory(
            self,
            title,
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            line_edit.setText(folder)

    def _build_upload_page(self):
        page = BasePage()
        self.upload_tabs = QTabWidget()
        self.upload_tabs.setDocumentMode(True)

        self.upload_folder_tab = self._build_upload_folder_tab()
        self.upload_gp_tab = self._build_upload_gp_tab()
        self.upload_icloud_tab = self._build_upload_icloud_tab()
        self.upload_picasa_tab = self._build_upload_picasa_tab()
        self.upload_immich_tab = self._build_upload_immich_tab()

        self.upload_tabs.addTab(self.upload_folder_tab, "From Folder")
        self.upload_tabs.addTab(self.upload_gp_tab, "Google Takeout")
        self.upload_tabs.addTab(self.upload_icloud_tab, "iCloud")
        self.upload_tabs.addTab(self.upload_picasa_tab, "Picasa")
        self.upload_tabs.addTab(self.upload_immich_tab, "From Immich")

        page.addWidget(self.upload_tabs)
        self.upload_tabs.currentChanged.connect(self._on_upload_tab_changed)
        self._on_upload_tab_changed(self.upload_tabs.currentIndex())
        return page

    def _on_upload_tab_changed(self, index: int):
        crumbs = {
            0: "upload · from-folder",
            1: "upload · from-google-photos",
            2: "upload · from-icloud",
            3: "upload · from-picasa",
            4: "upload · from-immich",
        }
        self.update_header_crumb(crumbs.get(index, "upload"))
        self.update_status()

    def _build_archive_page(self):
        page = BasePage()
        self.archive_tabs = QTabWidget()
        self.archive_tabs.setDocumentMode(True)

        self.archive_folder_tab = self._build_archive_folder_tab()
        self.archive_gp_tab = self._build_archive_gp_tab()
        self.archive_icloud_tab = self._build_archive_icloud_tab()
        self.archive_picasa_tab = self._build_archive_picasa_tab()
        self.archive_immich_tab = self._build_archive_immich_tab()

        self.archive_tabs.addTab(self.archive_folder_tab, "From Folder")
        self.archive_tabs.addTab(self.archive_gp_tab, "Google Takeout")
        self.archive_tabs.addTab(self.archive_icloud_tab, "iCloud")
        self.archive_tabs.addTab(self.archive_picasa_tab, "Picasa")
        self.archive_tabs.addTab(self.archive_immich_tab, "From Immich")

        page.addWidget(self.archive_tabs)
        self.archive_tabs.currentChanged.connect(self._on_archive_tab_changed)
        self._on_archive_tab_changed(self.archive_tabs.currentIndex())
        return page

    def _on_archive_tab_changed(self, index: int):
        crumbs = {
            0: "archive · from-folder",
            1: "archive · from-google-photos",
            2: "archive · from-icloud",
            3: "archive · from-picasa",
            4: "archive · from-immich",
        }
        self.update_header_crumb(crumbs.get(index, "archive"))
        self.update_status()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)

        self.btn_config = NavItem("Configuration", None)
        self.btn_config.icon_name = "settings"
        self.btn_config.setChecked(True)
        self.btn_config.clicked.connect(
            lambda: self.switch_tab(0, "configuration", self.btn_config)
        )
        sidebar_layout.addWidget(NavGroup("", [self.btn_config]))

        self.btn_upload = NavItem("Upload", None)
        self.btn_upload.icon_name = "upload"
        self.btn_upload.clicked.connect(
            lambda: self.switch_tab(1, "upload", self.btn_upload)
        )
        sidebar_layout.addWidget(NavGroup("UPLOAD", [self.btn_upload]))

        self.btn_archive = NavItem("Archive", None)
        self.btn_archive.icon_name = "archive"
        self.btn_archive.clicked.connect(
            lambda: self.switch_tab(2, "archive", self.btn_archive)
        )
        sidebar_layout.addWidget(NavGroup("ARCHIVE", [self.btn_archive]))

        self.btn_stack = NavItem("Stack Assets", None)
        self.btn_stack.icon_name = "layers"
        self.btn_stack.clicked.connect(
            lambda: self.switch_tab(3, "stack", self.btn_stack)
        )
        sidebar_layout.addWidget(NavGroup("ORGANIZE", [self.btn_stack]))

        sidebar_layout.addStretch()

        self.status_card = StatusCard()
        sidebar_layout.addWidget(self.status_card)

        self.main_layout.addWidget(sidebar)

    def _build_content_area(self):
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("HeaderFrame")
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        title_box = QVBoxLayout()
        self.lbl_app_name = QLabel("Immich Go GUI")
        self.lbl_app_name.setObjectName("AppName")
        self.lbl_crumb = QLabel("configuration")
        self.lbl_crumb.setObjectName("Crumb")
        title_box.addWidget(self.lbl_app_name)
        title_box.addWidget(self.lbl_crumb)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        adv_box = QHBoxLayout()
        self.lbl_mode = QLabel("Simple")
        self.lbl_mode.setObjectName("ModeLabel")
        self.lbl_mode.setToolTip(
            "Simple mode hides advanced options and excludes them from the generated command."
        )
        adv_box.addWidget(self.lbl_mode)
        self.switch_advanced = SwitchButton()
        self.switch_advanced.setToolTip(
            "Simple mode hides advanced options and excludes them from the generated command."
        )
        self.switch_advanced.toggled.connect(self.toggle_advanced)
        adv_box.addWidget(self.switch_advanced)
        header_layout.addLayout(adv_box)

        content_layout.addWidget(header)

        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        self.footer = QFrame()
        self.footer.setObjectName("FooterFrame")
        self.footer.setFixedHeight(70)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(24, 0, 24, 0)

        self.lbl_running_warning = QLabel(
            "⚠️ Immich-Go is currently running in a terminal. "
            "Close the terminal to run another command."
        )
        self.lbl_running_warning.setObjectName("RunningWarning")
        self.lbl_running_warning.setStyleSheet("color: #EAB308; font-weight: 500;")
        self.lbl_running_warning.setVisible(False)
        footer_layout.addWidget(self.lbl_running_warning)
        footer_layout.addStretch()

        self.btn_dry_run = QPushButton("Preview (Dry Run)")
        self.btn_dry_run.setObjectName("BtnPreview")
        self.btn_dry_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dry_run.clicked.connect(lambda: self.show_confirm_dialog(True))
        footer_layout.addWidget(self.btn_dry_run)

        self.btn_run = QPushButton("Run Command")
        self.btn_run.setObjectName("BtnRun")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.clicked.connect(lambda: self.show_confirm_dialog(False))
        footer_layout.addWidget(self.btn_run)

        content_layout.addWidget(self.footer)
        self.main_layout.addWidget(content_frame)

    def _build_config_tab(self):
        return build_config_tab(self)

    def _build_upload_folder_tab(self):
        return build_upload_folder_tab(self)

    def _build_upload_gp_tab(self):
        return build_upload_gp_tab(self)

    def _build_upload_immich_tab(self):
        return build_upload_immich_tab(self)

    def _build_upload_icloud_tab(self):
        return build_upload_icloud_tab(self)

    def _build_upload_picasa_tab(self):
        return build_upload_picasa_tab(self)

    def _build_archive_folder_tab(self):
        return build_archive_folder_tab(self)

    def _build_archive_gp_tab(self):
        return build_archive_gp_tab(self)

    def _build_archive_icloud_tab(self):
        return build_archive_icloud_tab(self)

    def _build_archive_picasa_tab(self):
        return build_archive_picasa_tab(self)

    def _build_archive_immich_tab(self):
        return build_archive_immich_tab(self)

    def _build_stack_tab(self):
        return build_stack_tab(self)

    def _on_manual_binary_changed(self, text: str = ""):
        meta = load_binary_metadata()
        meta["manual_path"] = self.manual_binary_edit.text().strip()
        save_binary_metadata(meta)
        self.binary_path = get_binary_path(meta)
        self.check_binary_version()

    # ==========================================================
    # UI INTERACTIONS & LOGIC
    # ==========================================================

    def toggle_advanced(self, checked):
        self.is_advanced = checked
        if hasattr(self, "app_config"):
            self.app_config.advanced_mode = checked
        if hasattr(self, "switch_advanced"):
            self.switch_advanced.blockSignals(True)
            self.switch_advanced.setChecked(checked)
            self.switch_advanced.blockSignals(False)
        if hasattr(self, "btn_mode"):
            self.btn_mode.blockSignals(True)
            self.btn_mode.setChecked(checked)
            self.btn_mode.blockSignals(False)
        if hasattr(self, "lbl_mode"):
            self.lbl_mode.setText("Advanced" if checked else "Simple")
        for w in getattr(self, "adv_frames", []):
            w.setVisible(checked)

    def switch_tab(self, index, crumb, btn):
        self.stacked_widget.setCurrentIndex(index)
        if index == 1 and hasattr(self, "upload_tabs"):
            u_crumbs = {
                0: "upload · from-folder",
                1: "upload · from-google-photos",
                2: "upload · from-icloud",
                3: "upload · from-picasa",
                4: "upload · from-immich",
            }
            crumb = u_crumbs.get(self.upload_tabs.currentIndex(), "upload")
        elif index == 2 and hasattr(self, "archive_tabs"):
            a_crumbs = {
                0: "archive · from-folder",
                1: "archive · from-google-photos",
                2: "archive · from-icloud",
                3: "archive · from-picasa",
                4: "archive · from-immich",
            }
            crumb = a_crumbs.get(self.archive_tabs.currentIndex(), "archive")
        self.update_header_crumb(crumb)
        for w in [
            self.btn_config,
            self.btn_upload,
            self.btn_archive,
            self.btn_stack,
        ]:
            w.setChecked(False)
        btn.setChecked(True)
        self.footer.setVisible(index != 0)
        tab_key = self._get_active_tab_key()
        if tab_key in self.inputs and "target-server" in self.inputs[tab_key]:
            srv_edit = self.inputs.get("config", {}).get("server")
            srv = srv_edit.text() if srv_edit else ""
            self.inputs[tab_key]["target-server"].setText(
                srv if srv else "Not Configured"
            )

    def update_header_crumb(self, text):
        self.lbl_crumb.setText(text)

    def update_window_title(self):
        active = active_profile_name()
        self.setWindowTitle(f"Immich Go GUI — {active}")

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        save_action = QAction("Save Configuration", self)
        save_action.triggered.connect(lambda: self.save_configuration())
        file_menu.addAction(save_action)
        load_action = QAction("Load Configuration", self)
        load_action.triggered.connect(self.load_configuration)
        file_menu.addAction(load_action)

        reset_action = QAction("Reset Run State", self)
        reset_action.triggered.connect(self.on_reset_run_state_clicked)
        file_menu.addAction(reset_action)

        reset_adv_action = QAction("Reset Advanced Flags", self)
        reset_adv_action.triggered.connect(self._confirm_reset_advanced_flags)
        file_menu.addAction(reset_adv_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        self.profiles_menu = menu_bar.addMenu("Profiles")
        self.update_profiles_menu()

        help_menu = menu_bar.addMenu("Help")
        compat_action = QAction("Check CLI Compatibility", self)
        compat_action.triggered.connect(self.show_cli_compatibility_dialog)
        help_menu.addAction(compat_action)

        help_menu.addSeparator()

        cli_repo_action = QAction("Immich-Go CLI GitHub", self)
        cli_repo_action.triggered.connect(self.open_immich_go_cli_link)
        help_menu.addAction(cli_repo_action)

        gui_repo_action = QAction("Immich-Go GUI GitHub", self)
        gui_repo_action.triggered.connect(self.open_immich_go_gui_link)
        help_menu.addAction(gui_repo_action)

        help_menu.addSeparator()

        open_config_action = QAction("Open Config Folder", self)
        open_config_action.triggered.connect(self.open_config_folder)
        help_menu.addAction(open_config_action)

        open_log_action = QAction("Open Log Folder", self)
        open_log_action.triggered.connect(self.open_log_folder)
        help_menu.addAction(open_log_action)

        export_diag_action = QAction("Export Diagnostics…", self)
        export_diag_action.triggered.connect(self.export_diagnostics)
        help_menu.addAction(export_diag_action)

        help_menu.addSeparator()

        about_action = QAction("About Immich-Go GUI", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_cli_compatibility_dialog(self):
        from core.cli_contract import check_fixtures, check_binary_help
        from core.binary_manager import (
            get_binary_path,
            load_binary_metadata,
            TESTED_IMMICH_GO_VERSION,
        )

        meta = load_binary_metadata()
        bin_path = Path(get_binary_path(meta))

        report = check_fixtures(TESTED_IMMICH_GO_VERSION)
        if bin_path.exists():
            live_report = check_binary_help(bin_path, TESTED_IMMICH_GO_VERSION)
        else:
            live_report = None

        # Merge fixture + live-binary results
        missing: dict[str, set[str]] = {
            tab: set(flags) for tab, flags in report.missing_flags_by_tab.items()
        }
        unknown: dict[str, set[str]] = {
            tab: set(flags) for tab, flags in report.unknown_flags_by_tab.items()
        }

        supported = bool(report.supported)
        notes: list[str] = [report.notes] if report.notes else []

        if live_report:
            supported = supported and bool(live_report.supported)
            if live_report.notes:
                notes.append(live_report.notes)
            for tab, flags in live_report.missing_flags_by_tab.items():
                missing.setdefault(tab, set()).update(flags)
            for tab, flags in live_report.unknown_flags_by_tab.items():
                unknown.setdefault(tab, set()).update(flags)

        fully_compatible = supported and not any(missing.values())

        msg = [f"Tested Immich-Go Version: v{report.version}\n"]

        if live_report and fully_compatible:
            msg.append("Status: Fully Compatible with fixtures and live binary")
        elif fully_compatible:
            msg.append("Status: Fully Compatible with target schema")
        else:
            msg.append("Status: Compatibility Warning")

        if notes:
            msg.append("\nVersion Notes:")
            for note in notes:
                msg.append(note)

        if missing:
            msg.append("\nMissing CLI Flags:")
            for tab, flags in missing.items():
                if flags:
                    msg.append(f"  [{tab}]")
                    for flag in sorted(flags):
                        msg.append(f"    - {flag}")

        if unknown:
            msg.append("\nNew Upstream CLI Flags Detected:")
            for tab, flags in unknown.items():
                if flags:
                    msg.append(f"  [{tab}]")
                    for flag in sorted(flags):
                        msg.append(f"    - {flag}")

        QMessageBox.information(
            self,
            "Immich-Go CLI Compatibility",
            "\n".join(msg),
        )

    def on_reset_run_state_clicked(self):
        reply = QMessageBox.question(
            self,
            "Reset Run State",
            "Are you sure you want to reset all active run locks and clear running status?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from core.process_tracker import reset_all_locks

            reset_all_locks()
            self.active_lock_path = None
            self.running_process = False
            if hasattr(self, "check_process_timer"):
                self.check_process_timer.stop()
            self.lbl_running_warning.setVisible(False)
            self.update_status()

    def update_profiles_menu(self):
        if not hasattr(self, "profiles_menu"):
            return
        self.profiles_menu.clear()

        new_act = QAction("New Profile…", self)
        new_act.triggered.connect(self.on_new_profile_clicked)
        self.profiles_menu.addAction(new_act)

        dup_act = QAction("Duplicate Active Profile…", self)
        dup_act.triggered.connect(self.on_duplicate_profile_clicked)
        self.profiles_menu.addAction(dup_act)

        ren_act = QAction("Rename Active Profile…", self)
        ren_act.triggered.connect(self.on_rename_profile_clicked)
        self.profiles_menu.addAction(ren_act)

        del_act = QAction("Delete Active Profile…", self)
        del_act.triggered.connect(self.on_delete_profile_clicked)
        self.profiles_menu.addAction(del_act)

        self.profiles_menu.addSeparator()

        active = active_profile_name()
        for pinfo in list_profiles():
            act = QAction(pinfo.name, self)
            act.setCheckable(True)
            if pinfo.name == active:
                act.setChecked(True)
            act.triggered.connect(
                lambda checked, name=pinfo.name: self.switch_profile(name)
            )
            self.profiles_menu.addAction(act)

    def switch_profile(self, target_name: str):
        active = active_profile_name()
        if target_name == active:
            return

        reply = QMessageBox.question(
            self,
            "Switch Profile",
            f"Save changes to current profile '{active}' before switching?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            self.update_profiles_menu()
            return
        elif reply == QMessageBox.StandardButton.Save:
            self.save_configuration()

        try:
            set_active_profile_name(target_name)
            self.load_configuration()
            self.update_profiles_menu()
            self.update_window_title()
        except Exception as e:
            QMessageBox.critical(self, "Error Switching Profile", str(e))

    def on_new_profile_clicked(self):
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "New Profile", "Enter profile name:")
        if ok and name.strip():
            clean_n = name.strip()
            existing = [p.name for p in list_profiles()]
            valid, err = validate_profile_name(clean_n, existing)
            if not valid:
                QMessageBox.warning(
                    self, "Invalid Name", err or "Invalid profile name."
                )
                return
            try:
                create_profile(clean_n)
                self.switch_profile(clean_n)
            except Exception as e:
                QMessageBox.critical(self, "Error Creating Profile", str(e))

    def on_duplicate_profile_clicked(self):
        from PySide6.QtWidgets import QInputDialog

        active = active_profile_name()
        name, ok = QInputDialog.getText(
            self, "Duplicate Profile", f"Enter name for duplicate of '{active}':"
        )
        if ok and name.strip():
            clean_n = name.strip()
            existing = [p.name for p in list_profiles()]
            valid, err = validate_profile_name(clean_n, existing)
            if not valid:
                QMessageBox.warning(
                    self, "Invalid Name", err or "Invalid profile name."
                )
                return
            try:
                duplicate_profile(active, clean_n)
                self.switch_profile(clean_n)
            except Exception as e:
                QMessageBox.critical(self, "Error Duplicating Profile", str(e))

    def on_rename_profile_clicked(self):
        from PySide6.QtWidgets import QInputDialog

        active = active_profile_name()
        if active == "default":
            QMessageBox.warning(
                self, "Cannot Rename", "The 'default' profile cannot be renamed."
            )
            return

        name, ok = QInputDialog.getText(
            self,
            "Rename Profile",
            f"Enter new name for profile '{active}':",
            text=active,
        )
        if ok and name.strip() and name.strip() != active:
            clean_n = name.strip()
            existing = [p.name for p in list_profiles() if p.name != active]
            valid, err = validate_profile_name(clean_n, existing)
            if not valid:
                QMessageBox.warning(
                    self, "Invalid Name", err or "Invalid profile name."
                )
                return
            try:
                rename_profile(active, clean_n)
                self.update_profiles_menu()
                self.update_window_title()
            except Exception as e:
                QMessageBox.critical(self, "Error Renaming Profile", str(e))

    def on_delete_profile_clicked(self):
        active = active_profile_name()
        if active == "default":
            QMessageBox.warning(
                self, "Cannot Delete", "The 'default' profile cannot be deleted."
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Are you sure you want to permanently delete profile '{active}' and all its saved settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_profile(active)
                self.load_configuration()
                self.update_profiles_menu()
                self.update_window_title()
            except Exception as e:
                QMessageBox.critical(self, "Error Deleting Profile", str(e))

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

    def _confirm_reset_advanced_flags(self):
        reply = QMessageBox.question(
            self,
            "Reset Advanced Flags",
            "Reset all advanced flags to defaults for all tabs?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_advanced_flags()

    def reset_advanced_flags(self, tab_key: str | None = None):
        """Resets advanced flag enable checkboxes to False and values to defaults."""
        tabs = [tab_key] if tab_key else list(getattr(self, "adv_rows", {}).keys())

        for t in tabs:
            for row in getattr(self, "adv_rows", {}).get(t, {}).values():
                row.set_state(
                    {
                        "enabled": False,
                        "value": row.def_.default,
                    }
                )

        self.update_status()



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

        elif tab_key == "archive-icloud":
            return {
                "path": get_text("path"),
                "write-to": get_text("write-to"),
            }

        elif tab_key == "archive-picasa":
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

    def validate_inputs(self) -> ValidationResult:
        tab_key = self._get_active_tab_key()
        if tab_key == "config":
            return ValidationResult()

        config_state = self._collect_config_state()
        tab_state = self._collect_tab_state(tab_key)
        advanced_state = self._collect_advanced_state(tab_key)

        base = validate_state(
            tab_key=tab_key,
            config_state=config_state,
            tab_state=tab_state,
        )

        from core.advanced_flags import validate_advanced_state

        adv = validate_advanced_state(tab_key, advanced_state)

        base.errors.extend(adv.errors)
        base.warnings.extend(adv.warnings)
        return base

    def validate_inputs_light(self) -> ValidationResult:
        tab_key = self._get_active_tab_key()
        if tab_key == "config":
            return ValidationResult()

        config_state = self._collect_config_state()
        tab_state = self._collect_tab_state(tab_key)
        advanced_state = self._collect_advanced_state(tab_key)

        base = validate_state_light(
            tab_key=tab_key,
            config_state=config_state,
            tab_state=tab_state,
        )

        from core.advanced_flags import validate_advanced_state

        adv = validate_advanced_state(tab_key, advanced_state)

        base.errors.extend(adv.errors)
        base.warnings.extend(adv.warnings)
        base.warnings.extend(
            collect_safety_warnings(tab_key, config_state, advanced_state)
        )
        return base

    def _reset_conn_test_state(self):
        self._last_conn_test_ok = None
        self._schedule_status_update()

    def _auto_test_connection(self):
        """Silent background test — updates status card only, no popup."""
        srv = self.server_url_edit.text().strip()
        key = self.api_key_edit.text().strip()
        if not srv or not key:
            self._last_conn_test_ok = None
            self.update_status()
            return
        skip_ssl = self.inputs["config"].get("skip-ssl", QCheckBox()).isChecked()
        res = test_immich_connection(srv, key, skip_ssl=skip_ssl, timeout=4.0)
        self._last_conn_test_ok = res.ok
        self.update_status()

    def on_test_connection_clicked(self):
        srv_widget = self.inputs.get("config", {}).get("server")
        api_widget = self.inputs.get("config", {}).get("api_key")
        ssl_widget = self.inputs.get("config", {}).get("skip-ssl")

        server_url = srv_widget.text().strip() if srv_widget else ""
        api_key = api_widget.text().strip() if api_widget else ""
        skip_ssl = ssl_widget.isChecked() if ssl_widget else False

        if not server_url:
            QMessageBox.warning(
                self, "Test Connection", "Please enter a Server URL first."
            )
            return
        if not api_key:
            QMessageBox.warning(
                self, "Test Connection", "Please enter an API Key first."
            )
            return

        res = test_immich_connection(server_url, api_key, skip_ssl=skip_ssl)
        if res.ok:
            self._last_conn_test_ok = True
            QMessageBox.information(self, "Test Connection Succeeded", res.message)
        else:
            self._last_conn_test_ok = False
            QMessageBox.warning(self, "Test Connection Failed", res.message)
        self.update_status()

    def _schedule_status_update(self):
        self._status_debounce.start()

    def update_status(self):
        """Immediate status refresh for programmatic calls (tab switches, run state)."""
        self._do_update_status()

    def _do_update_status(self):
        active_paths = getattr(self, "active_lock_paths", set())
        if not active_paths and getattr(self, "active_lock_path", None):
            active_paths = {self.active_lock_path}
        is_running = any(is_lock_active(p) for p in active_paths) or (
            getattr(self, "running_process", False) is True
        )
        validation = self.validate_inputs_light()
        active_tab = self._get_active_tab_key()
        self._apply_field_errors(active_tab, validation.field_errors)

        if is_running:
            self.lbl_running_warning.setVisible(True)
            self.btn_run.setEnabled(False)
            self.btn_dry_run.setEnabled(False)
        else:
            self.lbl_running_warning.setVisible(False)

        last_test = getattr(self, "_last_conn_test_ok", None)

        if last_test is False and active_tab in ("config", *SERVER_REQUIRED_TABS):
            self.status_card.set_server("err", "Server: Connection Failed")
            if not is_running and active_tab in SERVER_REQUIRED_TABS:
                self.btn_run.setEnabled(False)
                self.btn_dry_run.setEnabled(False)
        elif last_test is True and active_tab == "config":
            self.status_card.set_server("ok", "Server: Connected")
        elif active_tab == "config":
            srv_widget = self.inputs.get("config", {}).get("server")
            api_widget = self.inputs.get("config", {}).get("api_key")
            srv_text = srv_widget.text().strip() if srv_widget else ""
            key_text = api_widget.text().strip() if api_widget else ""
            if srv_text and key_text:
                self.status_card.set_server("ok", "Server: Configured")
            else:
                self.status_card.set_server("err", "Server: Not Set")
        elif validation.warnings and not validation.errors:
            self.status_card.set_server("warn", validation.warnings[0])
            if not is_running:
                self.btn_run.setEnabled(True)
                self.btn_dry_run.setEnabled(True)
        elif validation.is_valid:
            self.status_card.set_server("ok", "Server: Ready")
            if not is_running:
                self.btn_run.setEnabled(True)
                self.btn_dry_run.setEnabled(True)
        else:
            first_error = (
                validation.errors[0] if validation.errors else "Server: Not Set"
            )
            self.status_card.set_server("err", f"Server: {first_error}")
            if not is_running:
                self.btn_run.setEnabled(False)
                self.btn_dry_run.setEnabled(False)

        srv_edit = self.inputs.get("config", {}).get("server")
        srv = normalize_server_url(srv_edit.text()) if srv_edit else ""
        for t in ["archive-immich", "stack"]:
            if t in self.inputs and "target-server" in self.inputs[t]:
                self.inputs[t]["target-server"].setText(
                    srv if srv else "Not Configured"
                )

    def build_plan(self, dry_run: bool) -> CommandPlan:
        tab_key = self._get_active_tab_key()
        if tab_key == "config":
            return CommandPlan(errors=["No executable tab selected."], tab_key=tab_key)

        config_state = self._collect_config_state()
        tab_state = self._collect_tab_state(tab_key)
        advanced_state = self._collect_advanced_state(tab_key)

        binary_path = getattr(self, "binary_path", "")
        if not binary_path:
            binary_path = get_binary_path(load_binary_metadata()) or "./immich-go"

        return build_plan_from_state(
            tab_key=tab_key,
            config_state=config_state,
            tab_state=tab_state,
            binary_path=binary_path,
            dry_run=dry_run,
            advanced_state=advanced_state,
        )

    def build_command(self, dry_run: bool) -> list[str]:
        """Backwards-compatible wrapper returning plan.argv."""
        return self.build_plan(dry_run).argv

    def show_confirm_dialog(self, is_dry_run):
        if self.stacked_widget.currentIndex() == 0:
            return

        ready, msg = self.check_binary_ready()
        if not ready:
            reply = QMessageBox.question(
                self,
                "Binary Not Ready",
                f"{msg}\n\nDo you want to download it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if not self.update_binary(force_download=True):
                    return
                ready, msg = self.check_binary_ready()
                if not ready:
                    QMessageBox.critical(self, "Error", msg)
                    return
            else:
                return

        validation = self.validate_inputs()
        active_tab = self._get_active_tab_key()
        self._apply_field_errors(active_tab, validation.field_errors)
        if validation.errors:
            QMessageBox.warning(
                self,
                "Validation Errors",
                "\n".join(f"• {e}" for e in validation.errors),
            )
            return

        plan = self.build_plan(dry_run=is_dry_run)
        if plan.errors:
            QMessageBox.critical(
                self, "Command Build Errors", "\n".join(f"• {e}" for e in plan.errors)
            )
            return

        if plan.tab_key in SERVER_REQUIRED_TABS:
            config_state = self._collect_config_state()
            tab_state = self._collect_tab_state(plan.tab_key)
            conn_res = check_preflight_server_connection(
                plan.tab_key, config_state, tab_state, timeout=3.0
            )
            if not conn_res.ok:
                reply = QMessageBox.warning(
                    self,
                    "Server Unreachable",
                    f"Immich server connection check failed:\n\n{conn_res.message}\n\n"
                    f"Running immich-go will likely fail because the server cannot be reached.\n\n"
                    f"Do you want to proceed anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                plan.warnings.insert(
                    0, f"Server pre-flight check failed: {conn_res.message}"
                )

        if validation.warnings:
            for w in validation.warnings:
                if w not in plan.warnings:
                    plan.warnings.insert(0, w)

        dlg = QDialog(self)
        dlg.setWindowTitle("Confirm Execution")
        dlg.setModal(True)
        dlg.resize(680, 520)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        kicker = QLabel("Dry run" if is_dry_run else "Live execution")
        kicker.setObjectName("DlgKicker")
        layout.addWidget(kicker)

        title = QLabel("This is what will run")
        title.setObjectName("DlgTitle")
        layout.addWidget(title)

        desc = QLabel(
            "A dry run simulates the action. No files are changed."
            if is_dry_run
            else "This executes the real command in an external terminal."
        )
        desc.setObjectName("DlgDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        lbl_binary = QLabel("Binary")
        lbl_binary.setObjectName("Subhead")
        layout.addWidget(lbl_binary)

        binary_edit = QLineEdit(plan.binary_path)
        binary_edit.setReadOnly(True)
        layout.addWidget(binary_edit)

        lbl_cmd = QLabel("Command")
        lbl_cmd.setObjectName("Subhead")
        layout.addWidget(lbl_cmd)

        if sys.platform.startswith("win"):
            cmd_str = subprocess.list2cmdline(plan.display_argv)
        else:
            cmd_str = " ".join(shlex.quote(p) for p in plan.display_argv)

        cmd_block = QPlainTextEdit()
        cmd_block.setObjectName("CmdBlock")
        cmd_block.setPlainText(cmd_str)
        cmd_block.setReadOnly(True)
        cmd_block.setMaximumHeight(110)
        layout.addWidget(cmd_block)

        immich_env = {k: v for k, v in plan.env.items() if k.startswith("IMMICH_GO_")}
        if immich_env:
            lbl_env = QLabel("Environment Variables")
            lbl_env.setObjectName("Subhead")
            layout.addWidget(lbl_env)

            env_lines = []
            secret_env_keys = {"API_KEY", "FROM_API_KEY", "ADMIN_API_KEY"}
            for k, v in sorted(immich_env.items()):
                is_secret = any(s in k for s in secret_env_keys)
                display_v = "********" if is_secret else v
                env_lines.append(f"{k}={display_v}")

            env_block = QPlainTextEdit()
            env_block.setObjectName("CmdBlock")
            env_block.setPlainText("\n".join(env_lines))
            env_block.setReadOnly(True)
            env_block.setMaximumHeight(75)
            layout.addWidget(env_block)

        if plan.emission_log:
            lbl_src = QLabel("Flag Sources")
            lbl_src.setObjectName("Subhead")
            layout.addWidget(lbl_src)
            src_lines = []
            for entry in plan.emission_log:
                src_lines.append(f"{entry['flag']}  ←  {entry['source']}")
            src_block = QPlainTextEdit()
            src_block.setObjectName("CmdBlock")
            src_block.setPlainText("\n".join(src_lines))
            src_block.setReadOnly(True)
            src_block.setMaximumHeight(90)
            layout.addWidget(src_block)

        if plan.warnings:
            lbl_warn = QLabel("Warnings")
            lbl_warn.setObjectName("Subhead")
            layout.addWidget(lbl_warn)

            for w in plan.warnings:
                warn_lbl = QLabel(f"⚠️ {w}")
                warn_lbl.setObjectName("WarningHint")
                warn_lbl.setWordWrap(True)
                warn_lbl.setStyleSheet(
                    "background-color: rgba(229,192,123,0.12); padding: 8px; "
                    "border-radius: 6px; border: 1px solid #E5C07B;"
                )
                layout.addWidget(warn_lbl)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_copy = QPushButton("Copy Command")
        btn_copy.setObjectName("BtnPreview")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(cmd_str))
        btn_row.addWidget(btn_copy)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("BtnPreview")
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)

        btn_confirm = QPushButton("Run preview" if is_dry_run else "Start execution")
        btn_confirm.setObjectName("BtnRun")
        btn_confirm.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_confirm)

        layout.addLayout(btn_row)

        if dlg.exec():
            self.run_command(plan)

    # ==========================================================
    # BACKEND LOGIC
    # ==========================================================

    def get_latest_release_info(self) -> str | None:
        return self.binary_manager.get_latest_version()

    def get_download_url(self, version: str | None = None) -> str | None:
        return self.binary_manager.get_download_url(version)

    def check_binary_ready(self) -> tuple[bool, str]:
        """Check that the binary exists and is executable."""
        status = self.binary_manager.check_binary()
        if status.state == "err":
            return False, status.message
        return True, "Binary ready."

    def check_binary_version(self):
        status = self.binary_manager.check_binary()
        self.binary_path = self.binary_manager.resolve_binary_path()
        self.current_version = status.version_text

        self._set_binary_status(
            status.state,
            status.card_text,
            status.version_text,
        )
        if hasattr(self, "btn_check_updates"):
            if status.state == "err":
                self.btn_check_updates.setText("Download Immich-Go")
            else:
                self.btn_check_updates.setText("Check for Updates")

    def _set_binary_status(self, state: str, card_text: str, version_text: str):
        if hasattr(self, "status_card"):
            self.status_card.set_binary(state, card_text)
        if hasattr(self, "lbl_binary_version"):
            self.lbl_binary_version.setText(f"Current Version: {version_text}")
        if hasattr(self, "lbl_binary_path"):
            self.lbl_binary_path.setText(getattr(self, "binary_path", ""))

    def check_for_updates(self):
        self.check_binary_version()

        latest_version = self.binary_manager.get_latest_version()
        if not latest_version:
            QMessageBox.warning(
                self,
                "Update Check",
                "Failed to fetch the latest version information from GitHub.",
            )
            return

        current_version = getattr(self, "current_version", "Unknown")

        if clean_version(current_version) == clean_version(latest_version):
            QMessageBox.information(
                self,
                "Update Check",
                f"You are already on the latest version ({current_version}).",
            )
            return

        release_notes = self.binary_manager.get_release_notes(latest_version)
        allow_untested = (
            getattr(self.app_config, "allow_untested_updates", False)
            if hasattr(self, "app_config")
            else False
        )

        decision = self.binary_manager.evaluate_update(
            current_version=current_version,
            latest_version=latest_version,
            allow_untested=allow_untested,
            release_notes=release_notes,
        )

        if not decision.allowed:
            QMessageBox.warning(
                self,
                "Update Not Allowed",
                decision.message,
            )
            return

        if decision.requires_confirmation:
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"Latest version: {latest_version}\n"
                f"Current version: {current_version}\n\n"
                f"{decision.message}\n\n"
                f"Do you want to download and install {latest_version}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        self.update_binary(version=latest_version, force_download=True)

    def _select_version(self, version: str, binary_path: str):
        self.binary_manager.select_version(version, binary_path)
        self.binary_path = binary_path
        self.check_binary_version()

    def update_binary(
        self, version: str | None = None, force_download: bool = False
    ) -> bool:
        if version is None:
            version = self.get_latest_release_info()
            if not version:
                QMessageBox.critical(
                    self, "Error", "Could not determine latest version."
                )
                return False

        clean_v = version.lstrip("v")
        binary_filename = (
            "immich-go.exe" if sys.platform.startswith("win") else "immich-go"
        )
        binary_path = os.path.join(BINARY_BASE_DIR, clean_v, binary_filename)

        if os.path.exists(binary_path) and not force_download:
            if self.binary_manager.verify_extracted_binary(binary_path):
                self._select_version(clean_v, binary_path)
                return True

        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Downloading Immich-Go")
        progress_dialog.setFixedWidth(400)
        layout = QVBoxLayout(progress_dialog)
        status_label = QLabel(f"Downloading Immich-Go v{clean_v}...")
        layout.addWidget(status_label)
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        layout.addWidget(progress_bar)
        cancel_button = QPushButton("Cancel")
        layout.addWidget(cancel_button)
        progress_dialog.setWindowFlags(
            progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )

        cancelled = False

        def on_cancel():
            nonlocal cancelled
            cancelled = True
            progress_dialog.reject()

        cancel_button.clicked.connect(on_cancel)

        result_box = {"success": False, "message": ""}

        class InstallWorker(QThread):
            progress = Signal(int)
            finished = Signal(bool, str)

            def __init__(self, manager, ver, cancel_fn):
                super().__init__()
                self.manager = manager
                self.ver = ver
                self.cancel_fn = cancel_fn

            def run(self):
                ok, msg = self.manager.download_and_install(
                    version=self.ver,
                    progress_cb=self.progress.emit,
                    cancel_check=self.cancel_fn,
                )
                self.finished.emit(ok, msg)

        worker = InstallWorker(self.binary_manager, clean_v, lambda: cancelled)
        worker.progress.connect(progress_bar.setValue)

        def on_finished(ok, msg):
            result_box["success"] = ok
            result_box["message"] = msg
            progress_dialog.accept()

        worker.finished.connect(on_finished)
        worker.start()
        progress_dialog.exec()
        worker.wait()

        success = result_box["success"]
        message = result_box["message"]

        if success:
            self.binary_path = self.binary_manager.resolve_binary_path()
            self.check_binary_version()
        elif cancelled:
            QMessageBox.information(self, "Cancelled", "Download was cancelled.")
        else:
            QMessageBox.critical(
                self, "Update Failed", message or "Download/installation failed."
            )

        return success

    def build_environment(self, tab_key: str = None) -> dict:
        if tab_key is None:
            tab_key = self._get_active_tab_key()
        server = (
            self.inputs.get("config", {}).get("server").text().strip()
            if self.inputs.get("config", {}).get("server")
            else ""
        )
        api_key = (
            self.inputs.get("config", {}).get("api_key").text().strip()
            if self.inputs.get("config", {}).get("api_key")
            else ""
        )
        from_server = (
            self.inputs.get("upload-immich", {}).get("from-server").text().strip()
            if self.inputs.get("upload-immich", {}).get("from-server")
            else ""
        )
        from_api_key = (
            self.inputs.get("upload-immich", {}).get("from-api-key").text().strip()
            if self.inputs.get("upload-immich", {}).get("from-api-key")
            else ""
        )
        return build_environment(tab_key, server, api_key, from_server, from_api_key)

    def _start_process_timer(self):
        if not hasattr(self, "check_process_timer"):
            self.check_process_timer = QTimer(self)
            self.check_process_timer.timeout.connect(self._check_lock_file)
        if not self.check_process_timer.isActive():
            self.check_process_timer.start(1000)

    def _check_lock_file(self):
        active_locks = scan_locks()
        self.active_lock_paths = {lock.lock_path for lock in active_locks}
        self.active_lock_path = active_locks[0].lock_path if active_locks else None

        if not self.active_lock_paths:
            if hasattr(self, "check_process_timer"):
                self.check_process_timer.stop()
            self.running_process = False
            self.update_status()
            return

        self.running_process = True
        self.update_status()

    def check_if_process_running(self):
        """Backward compatible alias for _check_lock_file."""
        self._check_lock_file()

    def closeEvent(self, event):
        # Tests set this to tear down without modal Save/Discard prompts.
        if getattr(self, "_force_close", False):
            if hasattr(self, "log"):
                self.log.info("GUI closed")
            event.accept()
            return

        active_locks = scan_locks()
        active_paths = getattr(self, "active_lock_paths", set())
        if active_locks or active_paths:
            reply = QMessageBox.question(
                self,
                "Running Command Detected",
                "A command appears to still be running in an external terminal.\n\nClose the GUI anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        reply = QMessageBox.question(
            self,
            "Save Configuration",
            "Save current configuration before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if reply == QMessageBox.StandardButton.Save:
            self.save_configuration(show_popup=False)

        if hasattr(self, "log"):
            self.log.info("GUI closed")
        event.accept()

    def run_command(self, plan: CommandPlan):
        if plan.errors:
            QMessageBox.critical(
                self, "Command Build Errors", "\n".join(f"• {e}" for e in plan.errors)
            )
            return

        binary_path = plan.binary_path or getattr(self, "binary_path", "./immich-go")
        try:
            resolved = Path(binary_path).expanduser().resolve()
            if resolved.is_file():
                binary_path = str(resolved)
        except OSError:
            resolved = Path(binary_path)

        if not os.path.isfile(binary_path):
            if not self.update_binary():
                QMessageBox.critical(
                    self, "Error", "Immich-Go binary is missing or not executable."
                )
                return

        if not sys.platform.startswith("win") and not os.access(binary_path, os.X_OK):
            QMessageBox.critical(
                self, "Error", "Immich-Go binary exists but is not executable."
            )
            return

        plan.binary_path = binary_path

        if hasattr(self, "log"):
            self.log.info(
                "Launching: tab=%s argv=%s env_keys=%s",
                plan.tab_key,
                plan.display_argv,
                sorted(plan.env.keys()),
            )

        summary = f"{plan.tab_key}"
        if plan.argv:
            summary = " ".join(plan.argv[:3])

        lock_path = create_lock(
            tab_key=plan.tab_key,
            command_summary=summary,
            binary_path=binary_path,
        )

        pref_term = getattr(self.app_config, "preferred_terminal", "auto")
        full_cmd = [binary_path] + plan.argv

        res = launch_external_terminal(
            command=full_cmd,
            env=plan.env,
            lock_path=lock_path,
            preferred_terminal=pref_term,
        )

        if not res.ok:
            release_lock(lock_path)
            QMessageBox.critical(self, "Error Launching Terminal", res.message)
            self.btn_run.setEnabled(True)
            self.btn_dry_run.setEnabled(True)
            return

        self.active_lock_paths = {lock_path}
        self.active_lock_path = lock_path
        self.running_process = True
        self.btn_run.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self._start_process_timer()
        self.update_status()

    # ==========================================================
    # PERSISTENCE
    # ==========================================================

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

    def open_immich_go_cli_link(self):
        webbrowser.open("https://github.com/simulot/immich-go")

    def open_immich_go_gui_link(self):
        webbrowser.open("https://github.com/shitan198u/immich-go-gui")

    def open_config_folder(self):
        cfg_dir = default_config_dir()
        cfg_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(cfg_dir)))

    def open_log_folder(self):
        log_dir = default_config_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))

    def export_diagnostics(self):
        from core.profile_manager import global_profiles_path

        default_name = f"immich-go-diagnostics-{_gui_version()}.zip"
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostics",
            default_name,
            "Zip Archives (*.zip)",
        )
        if not dest:
            return
        if not dest.endswith(".zip"):
            dest += ".zip"

        cfg_dir = default_config_dir()
        log_dir = cfg_dir / "logs"
        meta_path = Path(METADATA_PATH)

        try:
            with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                summary = [
                    f"gui_version={_gui_version()}",
                    f"cli_target_version={TESTED_IMMICH_GO_VERSION}",
                ]
                warning = get_config_load_warning()
                if warning:
                    summary.append(f"config_load_warning={warning}")
                zf.writestr("summary.txt", "\n".join(summary) + "\n")

                cfg_path = default_config_path()
                if cfg_path.is_file():
                    zf.writestr(
                        "config.toml",
                        _redact_diagnostics_toml(cfg_path.read_text(encoding="utf-8")),
                    )

                profiles_path = global_profiles_path()
                if profiles_path.is_file():
                    zf.write(profiles_path, arcname="profiles.toml")

                if meta_path.is_file():
                    zf.write(meta_path, arcname="binary_metadata.json")

                if log_dir.is_dir():
                    logs = sorted(
                        log_dir.glob("*.log"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if logs:
                        tail = logs[0].read_text(encoding="utf-8", errors="replace")
                        if len(tail) > 200_000:
                            tail = tail[-200_000:]
                        zf.writestr("log_tail.txt", tail)

            QMessageBox.information(
                self,
                "Diagnostics Exported",
                f"Diagnostics package saved to:\n{dest}",
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not write diagnostics package:\n{exc}",
            )

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "About Immich-Go GUI",
            "<h3>Immich-Go GUI</h3>"
            "<p>A modern PySide6 desktop interface for <b>immich-go</b>.</p>"
            f"<p><b>Version:</b> {_gui_version()} (CLI Target: v{TESTED_IMMICH_GO_VERSION})</p>"
            "<hr/>"
            "<p><b>Immich-Go GUI Repository:</b><br/>"
            "<a href='https://github.com/shitan198u/immich-go-gui'>https://github.com/shitan198u/immich-go-gui</a></p>"
            "<p><b>Immich-Go CLI Engine:</b><br/>"
            "<a href='https://github.com/simulot/immich-go'>https://github.com/simulot/immich-go</a></p>",
        )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        try:
            from core.flag_registry import REGISTRY

            if not REGISTRY.tabs:
                print("self-test: flag registry empty", file=sys.stderr)
                sys.exit(1)

            plan = build_plan_from_state(
                tab_key="upload-folder",
                config_state={
                    "server": "http://localhost:2283",
                    "api_key": "test-key",
                    "skip-ssl": False,
                },
                tab_state={"path": "/tmp"},
                binary_path="./immich-go",
                dry_run=True,
            )
            if plan.errors:
                print(f"self-test: plan errors: {plan.errors}", file=sys.stderr)
                sys.exit(1)

            cfg_dir = default_config_dir()
            cfg_dir.mkdir(parents=True, exist_ok=True)
            probe = cfg_dir / ".self-test-write"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            print("self-test: ok")
            sys.exit(0)
        except Exception as exc:
            print(f"self-test failed: {exc}", file=sys.stderr)
            sys.exit(1)

    log = setup_logging()
    _install_exception_hook(log)

    app = QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent / "immich-go-gui.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    set_fusion_style()
    base_font = QFont()
    base_font.setFamilies(
        [
            "Segoe UI",
            "Segoe UI Emoji",
            "Helvetica Neue",
            "Apple Color Emoji",
            "Noto Sans",
            "Noto Color Emoji",
            "DejaVu Sans",
            "Ubuntu",
            "sans-serif",
        ]
    )
    base_font.setPointSize(10)
    app.setFont(base_font)
    window = ImmichGoGUI()
    window.show()
    sys.exit(app.exec())
