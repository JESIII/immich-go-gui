from PySide6.QtWidgets import (
    QHBoxLayout,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class BasePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.main_layout.addWidget(self.scroll)
        self.scroll_content = QWidget()
        self.scroll_layout = QHBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.container = QWidget()
        self.container.setMaximumWidth(1480)
        self.container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(24, 24, 24, 24)
        self.layout.setSpacing(24)
        self.scroll_layout.addStretch()
        self.scroll_layout.addWidget(self.container, 1)
        self.scroll_layout.addStretch()
        self.scroll.setWidget(self.scroll_content)

    def addWidget(self, widget):
        self.layout.addWidget(widget)

    def addStretch(self):
        self.layout.addStretch()
