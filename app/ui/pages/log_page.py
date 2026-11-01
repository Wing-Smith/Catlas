"""日志页：显示抓取 / 导出全过程的运行日志。

core 层的 LogBus 在工作线程产生记录，本页自行订阅后经 entry 信号
（QueuedConnection）汇总到只读文本框。
"""

from __future__ import annotations

import time

from PySide6 import QtCore
from PySide6.QtWidgets import QHBoxLayout, QTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, PushButton, StrongBodyLabel

from app.core import logbus
from app.core.i18n import tr

_LEVEL_COLORS = {
    "DEBUG": "#8a8a8a",
    "INFO": "#3a9e58",
    "WARN": "#c98a1b",
    "ERROR": "#d64545",
}


class LogPage(QWidget):
    entry = QtCore.Signal(str, str, str)  # 时间, 级别, 消息

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPage")
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        self.title_label = StrongBodyLabel("")
        layout.addWidget(self.title_label)

        self.hint_label = CaptionLabel("")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet(
            "QTextEdit { background: rgba(128,128,128,24); border: 1px solid rgba(128,128,128,60);"
            " border-radius: 8px; font-family: Consolas, 'Courier New', monospace; font-size: 12px; }"
        )
        layout.addWidget(self.text, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_clear = PushButton("")
        self.btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(self.btn_clear)
        layout.addLayout(btn_row)

        self.entry.connect(self._append)
        logbus.subscribe(self._forward)  # 回调在产生日志的线程执行，emit 会排队回 GUI 线程
        self.retranslate_ui()
        self.load_recent()

    # ------------------------------------------------------------------

    def _forward(self, level: str, msg: str) -> None:
        """LogBus 订阅回调（任意线程）：经信号回到本页（GUI 线程）。"""
        self.entry.emit(logbus_time(time.time()), level, msg)

    def retranslate_ui(self) -> None:
        self.title_label.setText(tr("logs.title"))
        self.hint_label.setText(tr("logs.hint"))
        self.btn_clear.setText(tr("logs.clear"))

    def load_recent(self) -> None:
        """启动时回填缓冲里的历史记录（旧→新）。"""
        for ts, level, msg in reversed(logbus.recent(200)):
            self._append(logbus_time(ts), level, msg)

    def _append(self, t: str, level: str, msg: str) -> None:
        color = _LEVEL_COLORS.get(level, "#888888")
        self.text.append(
            f'<span style="color:#888;">[{t}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level}</span> '
            f"<span>{escape_html(msg)}</span>"
        )
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear(self) -> None:
        self.text.clear()
        logbus.clear_buffer()


def logbus_time(ts: float) -> str:
    import time

    return time.strftime("%H:%M:%S", time.localtime(ts))


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
