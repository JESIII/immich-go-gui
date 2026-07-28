from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from gui.widgets import Card, DroppableLineEdit, FormSection


def build_archive_immich_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["archive-immich"] = {}

    card = Card("Source Server")
    form = FormSection()

    t_server = QLineEdit()
    t_server.setEnabled(False)
    t_server.setText("Not Configured")
    host.inputs["archive-immich"]["target-server"] = t_server
    form.add_row(
        "Source Immich Server URL",
        t_server,
        "Archive source server is configured in the Configuration tab.",
    )

    card.layout.addLayout(form)
    lay.addWidget(card)

    card = Card("Options")
    form = FormSection()

    t_write = DroppableLineEdit()
    t_write.setPlaceholderText("/backup/photos")
    host.inputs["archive-immich"]["write-to"] = t_write
    host._add_browse_action(t_write, "Select Archive Destination")
    form.add_row(
        "Destination Folder",
        host._wrap_with_field_error("archive-immich", "write-to", t_write),
    )

    d_range = QLineEdit()
    d_range.setPlaceholderText("2023-01-01,2023-12-31")
    host.inputs["archive-immich"]["from-date-range"] = d_range
    form.add_row("Date Range Filter", d_range)

    t_albums = QLineEdit()
    t_albums.setPlaceholderText("Family, Travel")
    host.inputs["archive-immich"]["from-albums"] = t_albums
    form.add_row("Specific Albums", t_albums)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("archive-immich")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
