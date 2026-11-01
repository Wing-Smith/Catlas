"""半透明加载遮罩：覆盖在预览画布上，防止用户误以为程序卡死。

悬停时通过 tooltip 解释公共 OSM 服务较慢的原因。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    IndeterminateProgressRing,
    StrongBodyLabel,
)

from app.core.cateaster import cat_line

SLOW_TOOLTIP = (
    "正在访问公共 OSM 服务（Overpass / 瓦片 / 路径），这些是共享的免费服务，"
    "速度取决于服务器当前负载与排队情况，大范围查询可能需要几十秒到几分钟，属正常现象。"
)


class LoadingOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(20, 20, 20, 140);")
        self.setToolTip(SLOW_TOOLTIP)

        box = QVBoxLayout(self)
        box.addStretch(1)
        center = QHBoxLayout()
        center.addStretch(1)
        inner = QVBoxLayout()
        inner.setSpacing(14)
        self.ring = IndeterminateProgressRing()
        self.ring.setFixedSize(72, 72)
        self.ring.setStrokeWidth(6)
        self.ring.setToolTip(SLOW_TOOLTIP)
        self.title = StrongBodyLabel("处理中，请稍候…")
        self.title.setStyleSheet("color: white; background: transparent;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = CaptionLabel("公共 OSM 服务为共享资源，速度受服务器负载影响")
        self.hint.setStyleSheet("color: rgba(255,255,255,180); background: transparent;")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(self.hint, alignment=Qt.AlignmentFlag.AlignCenter)
        center.addLayout(inner)
        center.addStretch(1)
        box.addLayout(center)
        box.addStretch(1)

        # 卡莉可彩蛋：等待期间轮换猫言猫语
        self._cat_timer = QTimer(self)
        self._cat_timer.setInterval(2600)
        self._cat_timer.timeout.connect(lambda: self.hint.setText(cat_line()))

        self.hide()

    def show_with(self, title: str) -> None:
        self.title.setText(title)
        self.hint.setText(cat_line())
        self._fit()
        self.show()
        self.raise_()
        self._cat_timer.start()

    def hide(self) -> None:  # type: ignore[override]
        self._cat_timer.stop()
        super().hide()

    def _fit(self) -> None:
        """把遮罩对齐父控件当前可视区域。"""
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            parent.installEventFilter(self)  # 父控件全屏/拉伸时同步尺寸
        self._fit()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self._fit()
        return super().eventFilter(obj, event)
