"""共享 UI 小组件。

注意：qfluentwidgets 的 SpinBox/DoubleSpinBox 与 PySide6 6.12 不兼容
（内部行编辑框宽度塌缩为 1px），数值输入一律用原生 QSpinBox/QDoubleSpinBox + 本模块配色。
"""

from __future__ import annotations

from qfluentwidgets import isDarkTheme


def style_native_spin(sp) -> None:
    """按 Fluent 主题给原生 QSpinBox/QDoubleSpinBox 配色。"""

    if isDarkTheme():
        sp.setStyleSheet(
            "QSpinBox, QDoubleSpinBox {"
            " background: rgba(255,255,255,0.06); color: white;"
            " border: 1px solid rgba(255,255,255,0.1); border-radius: 5px;"
            " padding: 4px 6px; selection-background-color: #29a2ff; }"
            "QSpinBox::up-button, QDoubleSpinBox::up-button,"
            " QSpinBox::down-button, QDoubleSpinBox::down-button { width: 16px; }"
        )
    else:
        sp.setStyleSheet(
            "QSpinBox, QDoubleSpinBox {"
            " border: 1px solid rgba(0,0,0,0.15); border-radius: 5px; padding: 4px 6px; }"
            "QSpinBox::up-button, QDoubleSpinBox::up-button,"
            " QSpinBox::down-button, QDoubleSpinBox::down-button { width: 16px; }"
        )
