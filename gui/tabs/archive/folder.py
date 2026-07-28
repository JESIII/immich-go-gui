from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from gui.widgets import Card, DroppableLineEdit, FormSection


def build_archive_folder_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["archive-folder"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    p_edit = DroppableLineEdit()
    p_edit.setPlaceholderText("/path/to/files or /path/to/archive.zip")
    host.inputs["archive-folder"]["path"] = p_edit

    btn_folder = QPushButton("Select Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_folder_archive)

    btn_zip = QPushButton("Select ZIP Archive…")
    btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zip.clicked.connect(host.browse_zip_archive)

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
    path_err = host._make_field_error_label()
    p_layout.addWidget(path_err)
    host._register_field_error_label("archive-folder", "path", path_err)
    host._bind_field_error_clear("archive-folder", "path", p_edit)

    form.add_row("Source Folder Path", p_container)

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    t_write = DroppableLineEdit()
    t_write.setPlaceholderText("/organized-photos")
    host.inputs["archive-folder"]["write-to"] = t_write
    host._add_browse_action(t_write, "Select Archive Destination")
    form.add_row(
        "Destination Folder",
        host._wrap_with_field_error("archive-folder", "write-to", t_write),
    )

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("archive-folder")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
