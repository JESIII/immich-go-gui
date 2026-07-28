from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Card, DroppableLineEdit, DroppablePlainTextEdit, FormSection


def build_archive_gp_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["archive-gp"] = {}

    card = Card("Source Configuration", required=True)
    form = FormSection()

    host.archive_gp_path_edit = DroppablePlainTextEdit()
    host.archive_gp_path_edit.setPlaceholderText(
        "/path/to/takeout-*.zip\n"
        "/path/to/takeout-001.zip\n"
        "…or an extracted folder path"
    )
    host.archive_gp_path_edit.setMaximumHeight(100)
    host.inputs["archive-gp"]["path"] = host.archive_gp_path_edit

    btn_zips = QPushButton("Select ZIP Files…")
    btn_zips.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_zips.clicked.connect(host.browse_archive_gp_zips)

    btn_folder = QPushButton("Select Extracted Folder…")
    btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_folder.clicked.connect(host.browse_archive_gp_folder)

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
    gp_layout.addWidget(host.archive_gp_path_edit)
    gp_layout.addLayout(gp_btn_box)
    gp_err = host._make_field_error_label()
    gp_layout.addWidget(gp_err)
    host._register_field_error_label("archive-gp", "path", gp_err)
    host._bind_field_error_clear("archive-gp", "path", host.archive_gp_path_edit)

    form.add_row("Takeout Source", gp_container)

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    t_write = DroppableLineEdit()
    t_write.setPlaceholderText("/organized-takeout")
    host.inputs["archive-gp"]["write-to"] = t_write
    host._add_browse_action(t_write, "Select Archive Destination")
    form.add_row(
        "Destination Folder",
        host._wrap_with_field_error("archive-gp", "write-to", t_write),
    )

    chk_partner = QCheckBox("Include Partner Photos")
    chk_partner.setChecked(True)
    host.inputs["archive-gp"]["include-partner"] = chk_partner
    form.addRow("", chk_partner)

    chk_sync = QCheckBox("Sync Google Albums")
    chk_sync.setChecked(True)
    host.inputs["archive-gp"]["sync-albums"] = chk_sync
    form.addRow("", chk_sync)

    chk_archived = QCheckBox("Include Archived Photos")
    chk_archived.setChecked(True)
    host.inputs["archive-gp"]["include-archived"] = chk_archived
    form.addRow("", chk_archived)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("archive-gp")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
