from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class NavItem(QPushButton):
    def __init__(self, text, icon, parent=None):
        super().__init__(text, parent)
        self.setObjectName("NavBtn")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon is not None and not icon.isNull():
            self.setIcon(icon)
            self.setIconSize(QSize(16, 16))


class NavGroup(QWidget):
    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(4)
        if title:
            lbl = QLabel(title)
            lbl.setObjectName("NavTitle")
            layout.addWidget(lbl)
        for item in items:
            layout.addWidget(item)
