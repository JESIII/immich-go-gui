from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Card, DroppableLineEdit, FormSection


def build_upload_picasa_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["upload-picasa"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    p_edit = DroppableLineEdit()
    p_edit.setPlaceholderText("/path/to/picasa-photos or /path/to/picasa.zip")
    host.inputs["upload-picasa"]["path"] = p_edit

    btn_folder = QPushButton("Select Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_folder_upload_picasa)

    btn_zip = QPushButton("Select ZIP Archive…")
    btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zip.clicked.connect(host.browse_zip_upload_picasa)

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
    picasa_err = host._make_field_error_label()
    p_layout.addWidget(picasa_err)
    host._register_field_error_label("upload-picasa", "path", picasa_err)
    host._bind_field_error_clear("upload-picasa", "path", p_edit)

    form.add_row("Picasa Collection Path", p_container)

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    c_album = QComboBox()
    c_album.addItems(["NONE", "FOLDER", "PATH"])
    host.inputs["upload-picasa"]["folder-album"] = c_album
    form.add_row("Album Organization", c_album)

    t_album = QLineEdit()
    t_album.setPlaceholderText("e.g. Picasa Archive")
    host.inputs["upload-picasa"]["into-album"] = t_album
    form.add_row("Put all into Album", t_album)

    c_burst = QComboBox()
    c_burst.addItems(["NoStack", "Stack", "StackKeepRaw", "StackKeepJPEG"])
    host.inputs["upload-picasa"]["manage-burst"] = c_burst
    form.add_row("Burst Photos", c_burst)

    c_raw = QComboBox()
    c_raw.addItems(
        ["NoStack", "KeepRaw", "KeepJPG", "StackCoverRaw", "StackCoverJPG"]
    )
    host.inputs["upload-picasa"]["manage-raw-jpeg"] = c_raw
    form.add_row("RAW + JPEG Pairs", c_raw)

    c_heic = QComboBox()
    c_heic.addItems(
        ["NoStack", "KeepHeic", "KeepJPG", "StackCoverHeic", "StackCoverJPG"]
    )
    host.inputs["upload-picasa"]["manage-heic-jpeg"] = c_heic
    form.add_row("HEIC + JPEG Pairs", c_heic)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("upload-picasa")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
