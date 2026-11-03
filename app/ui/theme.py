"""主题：跟随系统的 Fluent 主题 + Mica 毛玻璃。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from qfluentwidgets import Theme, setTheme, setThemeColor
from qframelesswindow import WindowEffect


_THEMES = {"auto": Theme.AUTO, "dark": Theme.DARK, "light": Theme.LIGHT}


def apply_fluent_theme(theme: str = "auto") -> None:
    setTheme(_THEMES.get(theme, Theme.AUTO))
    setThemeColor("#0078D4")
    apply_palette()


def apply_palette() -> None:
    """让原生 Qt 控件（表单自动标签、QSpinBox 等）的文字颜色跟随 Fluent 主题。

    qfluentwidgets 的 setTheme 只改自带控件的样式表，不改 QApplication 调色板；
    系统浅色 + 应用强制深色时，原生控件会拿系统的黑色文字画在深色底上
    （反过来系统深色 + 应用浅色同理）。这里按当前生效主题显式设置调色板。
    """
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QStyleFactory
    from qfluentwidgets import isDarkTheme

    app = QApplication.instance()
    if app is None:
        return

    # 关键：Qt6 的 windowsvista 原生样式会忽略 setPalette，控件颜色永远跟随
    # Windows 系统主题——这就是“系统浅色+应用深色”文字不适配的根源。
    # 切到 Fusion 样式（完全尊重调色板），强制主题才有意义。
    style = QStyleFactory.create("Fusion")
    if style is not None:
        app.setStyle(style)

    if isDarkTheme():
        text = QColor(235, 235, 235)
        base = QColor(45, 45, 45)
        window = QColor(32, 32, 32)
        palette = QPalette()
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
            QPalette.ColorRole.ToolTipText,
            QPalette.ColorRole.HighlightedText,
        ):
            palette.setColor(role, text)
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.AlternateBase):
            palette.setColor(role, window)
        for role in (
            QPalette.ColorRole.Base,
            QPalette.ColorRole.Button,
            QPalette.ColorRole.ToolTipBase,
        ):
            palette.setColor(role, base)
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 150, 150))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
    else:
        # 浅色：必须显式构造——Qt6 的 QStyle.standardPalette() 会跟随系统
        # 配色方案（系统深色时返回深色调色板），不能用它当“标准浅色”。
        text = QColor(0, 0, 0)
        base = QColor(255, 255, 255)
        window = QColor(240, 240, 240)
        palette = QPalette()
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
            QPalette.ColorRole.ToolTipText,
        ):
            palette.setColor(role, text)
        for role in (QPalette.ColorRole.Window,):
            palette.setColor(role, window)
        for role in (QPalette.ColorRole.AlternateBase,):
            palette.setColor(role, QColor(245, 245, 245))
        for role in (
            QPalette.ColorRole.Base,
            QPalette.ColorRole.Button,
            QPalette.ColorRole.ToolTipBase,
        ):
            palette.setColor(role, base)
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(122, 122, 122))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    app.setPalette(palette)
    # Qt6 中 setPalette 不会传播给已创建的控件（PaletteChange 事件不可靠），
    # 必须显式逐个下发，否则切换主题时旧控件保留上一主题的配色。
    for widget in app.allWidgets():
        widget.setPalette(palette)


def apply_mica(window: QWidget, dark: bool = False) -> WindowEffect:
    """对顶层窗口启用 Mica 效果（Windows 11）。"""

    effect = WindowEffect(window)
    effect.setMicaEffect(int(window.winId()), isDarkMode=dark)
    return effect
