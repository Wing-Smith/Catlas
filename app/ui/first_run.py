"""首次启动引导：三步导览弹窗，只显示一次（guide 看完即关，配置落盘）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import BodyLabel, MessageBoxBase, PushButton, SubtitleLabel

from app.core.i18n import tr

_STEPS = 3


class FirstRunGuide(MessageBoxBase):
    """三步导览：抓取 → 圈选与样式 → 导出。最后一步「开始体验」结束。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._idx = 0

        self.step_title = SubtitleLabel("")
        self.step_title.setStyleSheet("background: transparent;")
        self.step_body = BodyLabel("")
        self.step_body.setWordWrap(True)
        self.step_body.setMinimumWidth(420)
        self.step_body.setStyleSheet("background: transparent;")
        self.dots = QLabel("")
        self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dots.setStyleSheet("background: transparent; letter-spacing: 6px;")

        self.viewLayout.addWidget(self.step_title)
        self.viewLayout.addWidget(self.step_body)
        self.viewLayout.addWidget(self.dots)

        # 上一步插到确定按钮前面
        self.btn_prev = PushButton("")
        self.btn_prev.clicked.connect(self._prev)
        self.buttonLayout.insertWidget(
            self.buttonLayout.indexOf(self.yesButton), self.btn_prev
        )
        self.yesButton.clicked.connect(self._next)
        self.cancelButton.clicked.connect(self.reject)

        self._render()

    def _render(self) -> None:
        self.setWindowTitle(tr("guide.title"))
        self.step_title.setText(tr(f"guide.s{self._idx + 1}.t"))
        self.step_body.setText(tr(f"guide.s{self._idx + 1}.b"))
        self.dots.setText(" ".join(
            "●" if i == self._idx else "○" for i in range(_STEPS)
        ))
        self.btn_prev.setVisible(self._idx > 0)
        last = self._idx == _STEPS - 1
        self.yesButton.setText(tr("guide.start") if last else tr("guide.next"))
        self.cancelButton.setText(tr("guide.skip"))

    def _next(self) -> None:
        if self._idx < _STEPS - 1:
            self._idx += 1
            self._render()
        else:
            self.accept()

    def _prev(self) -> None:
        if self._idx > 0:
            self._idx -= 1
            self._render()
