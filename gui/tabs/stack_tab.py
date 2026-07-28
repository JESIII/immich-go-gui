from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget

from gui.widgets import BasePage, Card, FormSection


def build_stack_tab(host) -> QWidget:
    page = BasePage()
    host.inputs["stack"] = {}

    card = Card("Target Server")
    form = FormSection()

    t_server = QLineEdit()
    t_server.setEnabled(False)
    t_server.setText("Not Configured")
    host.inputs["stack"]["target-server"] = t_server
    form.add_row("Immich Server URL", t_server, "Update in Configuration tab.")

    card.layout.addLayout(form)
    page.addWidget(card)

    card = Card("Options")
    form = FormSection()

    c_burst = QComboBox()
    c_burst.addItems(["NoStack", "Stack", "StackKeepRaw", "StackKeepJPEG"])
    host.inputs["stack"]["manage-burst"] = c_burst
    form.add_row("Manage Bursts", c_burst)

    c_raw = QComboBox()
    c_raw.addItems(["NoStack", "KeepRaw", "KeepJPG", "StackCoverRaw", "StackCoverJPG"])
    host.inputs["stack"]["manage-raw-jpeg"] = c_raw
    form.add_row("Manage RAW+JPEG", c_raw)

    c_heic = QComboBox()
    c_heic.addItems(
        ["NoStack", "KeepHeic", "KeepJPG", "StackCoverHeic", "StackCoverJPG"]
    )
    host.inputs["stack"]["manage-heic-jpeg"] = c_heic
    form.add_row("Manage HEIC+JPEG", c_heic)

    card.layout.addLayout(form)
    page.addWidget(card)

    adv_card = host._build_advanced_flags_card("stack")
    page.addWidget(adv_card)

    page.addStretch()
    return page
