from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Card, DroppableLineEdit, FormSection


def build_upload_icloud_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["upload-icloud"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    p_edit = DroppableLineEdit()
    p_edit.setPlaceholderText("/path/to/icloud-export or /path/to/icloud.zip")
    host.inputs["upload-icloud"]["path"] = p_edit

    btn_folder = QPushButton("Select Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_folder_upload_icloud)

    btn_zip = QPushButton("Select ZIP Archive…")
    btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zip.clicked.connect(host.browse_zip_upload_icloud)

    btn_box = QHBoxLayout()
    btn_box.setContentsMargins(0, 4, 0, 0)
    btn_box.setSpacing(10)
    btn_box.addWidget(btn_folder)
    btn_box.addWidget(btn_zip)
    btn_box.addStretch()

    p_container = QWidget()
    p_layout = QVBoxLayout(p_container)
    p_layout.setContentsMargins(0, 0, 0, 0)
    p_layout.setSpacing(6)
    p_layout.addWidget(p_edit)
    p_layout.addLayout(btn_box)
    icloud_err = host._make_field_error_label()
    p_layout.addWidget(icloud_err)
    host._register_field_error_label("upload-icloud", "path", icloud_err)
    host._bind_field_error_clear("upload-icloud", "path", p_edit)

    form.add_row("iCloud Export Path", p_container)

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    c_burst = QComboBox()
    c_burst.addItems(["NoStack", "Stack", "StackKeepRaw", "StackKeepJPEG"])
    host.inputs["upload-icloud"]["manage-burst"] = c_burst
    form.add_row("Burst Photos", c_burst)

    c_raw = QComboBox()
    c_raw.addItems(["NoStack", "KeepRaw", "KeepJPG", "StackCoverRaw", "StackCoverJPG"])
    host.inputs["upload-icloud"]["manage-raw-jpeg"] = c_raw
    form.add_row("RAW + JPEG Pairs", c_raw)

    c_heic = QComboBox()
    c_heic.addItems(
        ["NoStack", "KeepHeic", "KeepJPG", "StackCoverHeic", "StackCoverJPG"]
    )
    host.inputs["upload-icloud"]["manage-heic-jpeg"] = c_heic
    form.add_row("HEIC + JPEG Pairs", c_heic)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("upload-icloud")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
