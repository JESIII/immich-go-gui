from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from gui.widgets import Card, DroppableLineEdit, FormSection


def build_archive_picasa_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["archive-picasa"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    p_edit = DroppableLineEdit()
    p_edit.setPlaceholderText("/path/to/picasa-photos or /path/to/picasa.zip")
    host.inputs["archive-picasa"]["path"] = p_edit

    btn_folder = QPushButton("Select Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_folder_archive_picasa)

    btn_zip = QPushButton("Select ZIP Archive…")
    btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zip.clicked.connect(host.browse_zip_archive_picasa)

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
    arch_picasa_err = host._make_field_error_label()
    p_layout.addWidget(arch_picasa_err)
    host._register_field_error_label("archive-picasa", "path", arch_picasa_err)
    host._bind_field_error_clear("archive-picasa", "path", p_edit)

    form.add_row("Picasa Collection Path", p_container)

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    t_write = DroppableLineEdit()
    t_write.setPlaceholderText("/organized-picasa")
    host.inputs["archive-picasa"]["write-to"] = t_write
    host._add_browse_action(t_write, "Select Archive Destination")
    form.add_row(
        "Destination Folder",
        host._wrap_with_field_error("archive-picasa", "write-to", t_write),
    )

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("archive-picasa")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
