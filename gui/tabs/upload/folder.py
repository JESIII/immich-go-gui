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


def build_upload_folder_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["upload-folder"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    host.source_path_edit = DroppableLineEdit()
    host.source_path_edit.setPlaceholderText("/path/to/files or /path/to/archive.zip")
    host.inputs["upload-folder"]["path"] = host.source_path_edit

    btn_folder = QPushButton("Select Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_folder_upload)

    btn_zip = QPushButton("Select ZIP Archive…")
    btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zip.clicked.connect(host.browse_zip_upload)

    btn_box = QHBoxLayout()
    btn_box.setContentsMargins(0, 4, 0, 0)
    btn_box.setSpacing(10)
    btn_box.addWidget(btn_folder)
    btn_box.addWidget(btn_zip)
    btn_box.addStretch()

    path_container = QWidget()
    path_layout = QVBoxLayout(path_container)
    path_layout.setContentsMargins(0, 0, 0, 0)
    path_layout.setSpacing(6)
    path_layout.addWidget(host.source_path_edit)
    path_layout.addLayout(btn_box)
    path_err = host._make_field_error_label()
    path_layout.addWidget(path_err)
    host._register_field_error_label("upload-folder", "path", path_err)
    host._bind_field_error_clear("upload-folder", "path", host.source_path_edit)

    form.add_row(
        "Folder / ZIP to upload",
        path_container,
        "Every file inside this folder will be considered. ZIP archives are also supported.",
    )

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    c_album = QComboBox()
    c_album.addItems(["NONE", "FOLDER", "PATH"])
    host.inputs["upload-folder"]["folder-album"] = c_album
    form.add_row("Album Organization", c_album)

    t_album = QLineEdit()
    t_album.setPlaceholderText("e.g. Family Archive")
    host.inputs["upload-folder"]["into-album"] = t_album
    form.add_row("Put all into Album", t_album)

    c_burst = QComboBox()
    c_burst.addItems(["NoStack", "Stack", "StackKeepRaw", "StackKeepJPEG"])
    host.inputs["upload-folder"]["manage-burst"] = c_burst
    form.add_row("Burst Photos", c_burst)

    c_raw = QComboBox()
    c_raw.addItems(["NoStack", "KeepRaw", "KeepJPG", "StackCoverRaw", "StackCoverJPG"])
    host.inputs["upload-folder"]["manage-raw-jpeg"] = c_raw
    form.add_row("RAW + JPEG Pairs", c_raw)

    c_heic = QComboBox()
    c_heic.addItems(
        ["NoStack", "KeepHeic", "KeepJPG", "StackCoverHeic", "StackCoverJPG"]
    )
    host.inputs["upload-folder"]["manage-heic-jpeg"] = c_heic
    form.add_row("HEIC + JPEG Pairs", c_heic)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("upload-folder")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
