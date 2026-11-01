"""主题：跟随系统的 Fluent 主题 + Mica 毛玻璃。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from qfluentwidgets import Theme, setTheme, setThemeColor
from qframelesswindow import WindowEffect


_THEMES = {"auto": Theme.AUTO, "dark": Theme.DARK, "light": Theme.LIGHT}


def apply_fluent_theme(theme: str = "auto") -> None:
    setTheme(_THEMES.get(theme, Theme.AUTO))
    setThemeColor("#0078D4")


def apply_mica(window: QWidget, dark: bool = False) -> WindowEffect:
    """对顶层窗口启用 Mica 效果（Windows 11）。"""

    effect = WindowEffect(window)
    effect.setMicaEffect(int(window.winId()), isDarkMode=dark)
    return effect
