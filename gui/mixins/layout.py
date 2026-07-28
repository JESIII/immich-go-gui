from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.advanced_flags import ADVANCED_FLAGS
from gui.tabs.config_tab import build_config_tab
from gui.tabs.stack_tab import build_stack_tab
from gui.tabs.upload.folder import build_upload_folder_tab
from gui.tabs.upload.google_photos import build_upload_gp_tab
from gui.tabs.upload.icloud import build_upload_icloud_tab
from gui.tabs.upload.immich import build_upload_immich_tab
from gui.tabs.upload.picasa import build_upload_picasa_tab
from gui.tabs.archive.folder import build_archive_folder_tab
from gui.tabs.archive.google_photos import build_archive_gp_tab
from gui.tabs.archive.icloud import build_archive_icloud_tab
from gui.tabs.archive.immich import build_archive_immich_tab
from gui.tabs.archive.picasa import build_archive_picasa_tab
from gui.widgets import (
    AdvancedFlagRow,
    BasePage,
    Card,
    FormSection,
    NavGroup,
    NavItem,
    StatusCard,
    SwitchButton,
)
from theme import load_themed_icon


class LayoutMixin:
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
