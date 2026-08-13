import os
from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QStyleFactory

THEME_SYSTEM = "System"
THEME_LIGHT = "Light"
THEME_DARK = "Dark"


def normalize_theme_mode(mode):
    m = str(mode).strip().lower()
    if m == "system":
        return THEME_SYSTEM
    if m == "light":
        return THEME_LIGHT
    if m == "dark":
        return THEME_DARK
    return THEME_SYSTEM


def set_fusion_style():
    app = QApplication.instance()
    if not app:
        return
    style = QStyleFactory.create("Fusion")
    if style:
        app.setStyle(style)


def detect_system_theme() -> str:
    try:
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorScheme"):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
            if scheme == Qt.ColorScheme.Light:
                return "light"
    except Exception:
        pass

    app = QApplication.instance()
    if app is None:
        return "dark"
    pal = app.palette()
    bg = pal.color(QPalette.ColorRole.Window)
    fg = pal.color(QPalette.ColorRole.WindowText)
    return "dark" if fg.lightness() > bg.lightness() else "light"


@lru_cache(maxsize=8)
def theme_tokens(theme: str) -> dict:
    if theme == "dark":
        return {
            "bg": "#0E1113",
            "sidebar": "#121619",
            "surface": "#151A1E",
            "surface_alt": "#1B2126",
            "input_bg": "#1B2126",
            "input_focus_bg": "#20272D",
            "border": "#262D34",
            "border_strong": "#343C43",
            "text": "#E8ECEF",
            "text_muted": "#97A1AA",
            "text_faint": "#6B757D",
            "accent": "#4FB3A4",
            "accent_hover": "#6FD6C5",
            "accent_subtle": "#17332F",
            "primary": "#E1512E",
            "primary_hover": "#F1603D",
            "primary_subtle": "#3A1D15",
            "on_primary": "#FFFFFF",
            "warning": "#E5C07B",
            "button_bg": "#20262B",
            "button_hover": "#2A3238",
            "scrollbar": "#0E1113",
            "scrollbar_handle": "#3A434B",
            "terminal_bg": "#0B0D0E",
            "terminal_text": "#ECE7DD",
        }
    return {
        "bg": "#F5F7F9",
        "sidebar": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface_alt": "#F8FAFC",
        "input_bg": "#F8FAFC",
        "input_focus_bg": "#FFFFFF",
        "border": "#D8DEE4",
        "border_strong": "#C7CED6",
        "text": "#18222C",
        "text_muted": "#5D6B7A",
        "text_faint": "#7C8794",
        "accent": "#0F766E",
        "accent_hover": "#14B8A6",
        "accent_subtle": "#E4F5F2",
        "primary": "#C2410C",
        "primary_hover": "#EA580C",
        "primary_subtle": "#FFEDD5",
        "on_primary": "#FFFFFF",
        "warning": "#B45309",
        "button_bg": "#EEF1F4",
        "button_hover": "#E2E7EC",
        "scrollbar": "#EEF1F4",
        "scrollbar_handle": "#AEB8C2",
        "terminal_bg": "#111827",
        "terminal_text": "#F9FAFB",
    }


_QSS_TEMPLATE: str | None = None


def build_stylesheet(theme: str) -> str:
    global _QSS_TEMPLATE
    if _QSS_TEMPLATE is None:
        qss_path = os.path.join(os.path.dirname(__file__), "assets", "theme.qss")
        with open(qss_path, encoding="utf-8") as f:
            _QSS_TEMPLATE = f.read()
    t = theme_tokens(theme)
    check_icon = os.path.join(
        os.path.dirname(__file__), "assets", "icons", "check.svg"
    ).replace("\\", "/")
    return _QSS_TEMPLATE.format(**t, check_icon=check_icon)


def apply_base_palette(theme: str):
    app = QApplication.instance()
    if app is None:
        return
    t = theme_tokens(theme)
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(t["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(t["input_bg"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(t["surface_alt"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(t["button_bg"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(t["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(t["on_primary"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["surface"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Link, QColor(t["accent"]))
    pal.setColor(QPalette.ColorRole.LinkVisited, QColor(t["accent"]))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["text_faint"]))
    pal.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(t["text_faint"])
    )
    pal.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(t["text_faint"]),
    )
    pal.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(t["text_faint"]),
    )
    app.setPalette(pal)


def apply_application_theme(mode: str) -> str:
    mode = normalize_theme_mode(mode)
    resolved = detect_system_theme() if mode == THEME_SYSTEM else mode.lower()
    app = QApplication.instance()
    if app is None:
        return resolved
    app.setProperty("theme", resolved)
    apply_base_palette(resolved)
    app.setStyleSheet(build_stylesheet(resolved))
    return resolved


def connect_system_theme_changes(callback):
    try:
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: callback())
            return True
    except Exception:
        pass
    return False


_ICON_CACHE: dict[tuple[str, str, float], QIcon] = {}


def _primary_device_pixel_ratio() -> float:
    try:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            return float(screen.devicePixelRatio())
    except Exception:
        pass
    return 1.0


def _render_themed_pixmap(svg_content: str, logical_size: int, dpr: float) -> QPixmap:
    pixmap = QPixmap(int(logical_size * dpr), int(logical_size * dpr))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def load_themed_icon(icon_name: str, theme: str) -> QIcon:
    """Loads an SVG icon from assets/icons and colors it based on the theme."""
    dpr = _primary_device_pixel_ratio()
    key = (icon_name, theme, round(dpr, 2))
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached

    if icon_name == "app-monochrome":
        color = "#FFFFFF" if theme == "dark" else "#121619"
    else:
        t = theme_tokens(theme)
        color = t["text_muted"]

    svg_path = os.path.join(
        os.path.dirname(__file__), "assets", "icons", f"{icon_name}.svg"
    )

    if not os.path.exists(svg_path):
        icon = QIcon()
        _ICON_CACHE[key] = icon
        return icon

    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read().replace("currentColor", color)

    icon = QIcon()
    ratios = sorted({1.0, 2.0, dpr})
    for ratio in ratios:
        pixmap = _render_themed_pixmap(svg_content, 20, ratio)
        icon.addPixmap(pixmap)

    _ICON_CACHE[key] = icon
    return icon


def connect_screen_changes(callback) -> bool:
    """Connect a callback when display DPI / screen geometry changes."""
    try:
        app = QGuiApplication.instance()
        if app is None:
            return False
        for screen in app.screens():
            screen.devicePixelRatioChanged.connect(lambda *_: callback())
        return True
    except Exception:
        return False


def clear_icon_cache() -> None:
    _ICON_CACHE.clear()
