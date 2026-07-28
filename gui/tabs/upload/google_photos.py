from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Card, DroppablePlainTextEdit, FormSection


def build_upload_gp_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["upload-gp"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    host.gp_path_edit = DroppablePlainTextEdit()
    host.gp_path_edit.setPlaceholderText(
        "/path/to/takeout-*.zip\n"
        "/path/to/takeout-001.zip\n"
        "/path/to/takeout-002.zip\n"
        "…or an extracted folder path"
    )
    host.gp_path_edit.setMaximumHeight(100)
    host.inputs["upload-gp"]["path"] = host.gp_path_edit

    btn_zips = QPushButton("Select ZIP Files…")
    btn_zips.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zips.clicked.connect(host.browse_takeout_zips)

    btn_folder = QPushButton("Select Extracted Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_takeout_folder)

    gp_btn_box = QHBoxLayout()
    gp_btn_box.setContentsMargins(0, 4, 0, 0)
    gp_btn_box.setSpacing(10)
    gp_btn_box.addWidget(btn_zips)
    gp_btn_box.addWidget(btn_folder)
    gp_btn_box.addStretch()

    gp_container = QWidget()
    gp_layout = QVBoxLayout(gp_container)
    gp_layout.setContentsMargins(0, 0, 0, 0)
    gp_layout.setSpacing(6)
    gp_layout.addWidget(host.gp_path_edit)
    gp_layout.addLayout(gp_btn_box)
    gp_err = host._make_field_error_label()
    gp_layout.addWidget(gp_err)
    host._register_field_error_label("upload-gp", "path", gp_err)
    host._bind_field_error_clear("upload-gp", "path", host.gp_path_edit)

    form.add_row(
        "Takeout Source",
        gp_container,
        "Paste multiple ZIP paths (one per line) or a glob pattern like takeout-*.zip",
    )

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    chk_partner = QCheckBox("Include Partner Photos")
    chk_partner.setChecked(True)
    host.inputs["upload-gp"]["include-partner"] = chk_partner
    form.addRow("", chk_partner)

    chk_sync = QCheckBox("Sync Google Albums")
    chk_sync.setChecked(True)
    host.inputs["upload-gp"]["sync-albums"] = chk_sync
    form.addRow("", chk_sync)

    chk_archived = QCheckBox("Include Archived Photos")
    chk_archived.setChecked(True)
    host.inputs["upload-gp"]["include-archived"] = chk_archived
    form.addRow("", chk_archived)

    c_burst = QComboBox()
    c_burst.addItems(["NoStack", "Stack", "StackKeepRaw", "StackKeepJPEG"])
    host.inputs["upload-gp"]["manage-burst"] = c_burst
    form.add_row("Burst Photos", c_burst)

    c_heic = QComboBox()
    c_heic.addItems(
        ["NoStack", "KeepHeic", "KeepJPG", "StackCoverHeic", "StackCoverJPG"]
    )
    host.inputs["upload-gp"]["manage-heic-jpeg"] = c_heic
    form.add_row("HEIC + JPEG Pairs", c_heic)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("upload-gp")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
