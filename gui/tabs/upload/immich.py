from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from gui.widgets import Card, FormSection


def build_upload_immich_tab(host) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(24)
    host.inputs["upload-immich"] = {}

    banner = QLabel(
        "ℹ️ Destination Immich Server is configured in the Configuration tab. Source Immich Server is configured below."
    )
    banner.setWordWrap(True)
    banner.setStyleSheet(
        "background-color: rgba(97, 175, 239, 0.12); padding: 10px 14px; "
        "border-radius: 6px; border: 1px solid #61AFEF; font-size: 13px;"
    )
    lay.addWidget(banner)

    card = Card("Source Configuration", required=True)
    form = FormSection()

    t_server = QLineEdit()
    t_server.setPlaceholderText("http://old-server:2283")
    host.inputs["upload-immich"]["from-server"] = t_server
    form.add_row(
        "Source Server URL",
        host._wrap_with_field_error("upload-immich", "from-server", t_server),
    )

    t_api = QLineEdit()
    t_api.setEchoMode(QLineEdit.EchoMode.Password)
    t_api.setPlaceholderText("Source API Key")
    host.inputs["upload-immich"]["from-api-key"] = t_api
    form.add_row(
        "Source API Key",
        host._wrap_with_field_error("upload-immich", "from-api-key", t_api),
    )

    d_range = QLineEdit()
    d_range.setPlaceholderText("2023-01-01,2023-12-31")
    host.inputs["upload-immich"]["from-date-range"] = d_range
    form.add_row("Date Range Filter", d_range)

    t_albums = QLineEdit()
    t_albums.setPlaceholderText("Family, Travel")
    host.inputs["upload-immich"]["from-albums"] = t_albums
    form.add_row("Filter by Albums", t_albums)

    card.layout.addLayout(form)
    lay.addWidget(card)

    adv_card = host._build_advanced_flags_card("upload-immich")
    lay.addWidget(adv_card)

    lay.addStretch()
    return page
