import shlex
import subprocess
import sys

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from core import SERVER_REQUIRED_TABS
from core.network import check_preflight_server_connection


class ConfirmDialogMixin:
    def show_confirm_dialog(self, is_dry_run: bool):
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
