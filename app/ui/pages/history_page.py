"""历史页：抓取记录与书签管理。

列表显示每次抓取的区域、图层与要素数；「填入面板」把参数回填到抓取页，
书签条目防自动清理，可按书签筛选。
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    CheckBox,
    InfoBar,
    InfoBarPosition,
    PushButton,
    StrongBodyLabel,
)

from app.core import history
from app.core.i18n import tr
from app.core.models import LayerType


class HistoryPage(QWidget):
    load_requested = Signal(str)  # record_id → 主窗口回填并跳转

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyPage")
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)

        self.title_label = StrongBodyLabel("")
        layout.addWidget(self.title_label)
        self.hint_label = CaptionLabel("")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.itemDoubleClicked.connect(self._on_load)
        layout.addWidget(self.list, stretch=1)

        filter_row = QHBoxLayout()
        self.bookmarks_only = CheckBox("")
        self.bookmarks_only.setChecked(False)
        self.bookmarks_only.toggled.connect(self.refresh)
        filter_row.addWidget(self.bookmarks_only)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        btn_row = QHBoxLayout()
        self.btn_load = PushButton("")
        self.btn_bookmark = PushButton("")
        self.btn_delete = PushButton("")
        self.btn_clear = PushButton("")
        self.btn_load.clicked.connect(self._on_load)
        self.btn_bookmark.clicked.connect(self._on_bookmark)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_clear.clicked.connect(self._on_clear)
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_bookmark)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_clear)
        layout.addLayout(btn_row)

        self.retranslate_ui()
        self.refresh()

    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        self.title_label.setText(tr("hist.title"))
        self.hint_label.setText(tr("hist.hint"))
        self.bookmarks_only.setText(tr("hist.bookmarks_only"))
        self.btn_load.setText(tr("hist.refetch"))
        self.btn_bookmark.setText(tr("hist.bookmark"))
        self.btn_delete.setText(tr("hist.delete"))
        self.btn_clear.setText(tr("hist.clear"))
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        records = history.all_records()
        # 书签置顶，其余按时间新→旧
        records.sort(key=lambda r: (not r.bookmarked, -r.ts))
        if self.bookmarks_only.isChecked():
            records = [r for r in records if r.bookmarked]
        for rec in records:
            item = QListWidgetItem(self._format(rec))
            item.setData(Qt.ItemDataRole.UserRole, rec.id)
            if rec.bookmarked:
                item.setText("★ " + item.text())
            self.list.addItem(item)
        if self.list.count() == 0:
            QListWidgetItem(tr("hist.empty"), self.list)

    @staticmethod
    def _format(rec: history.HistoryRecord) -> str:
        when = time.strftime("%m-%d %H:%M", time.localtime(rec.ts))
        names = "、".join(
            tr(f"grab.layer.{LayerType(v).value}") for v in rec.layers if v in LayerType._value2member_map_
        )
        total = sum(rec.counts.values())
        counts = f"{total}" if total else tr("hist.count_none")
        extent = rec.query or (",".join(f"{v:.4f}" for v in rec.bbox) if rec.bbox else "?")
        return f"{when}  ·  {rec.area}  ·  {names}（{counts}）  ·  {extent}"

    def _selected_id(self) -> str | None:
        item = self.list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_load(self, *_args) -> None:
        rid = self._selected_id()
        if rid:
            self.load_requested.emit(rid)

    def _on_bookmark(self) -> None:
        rid = self._selected_id()
        if rid:
            history.toggle_bookmark(rid)
            self.refresh()

    def _on_delete(self) -> None:
        rid = self._selected_id()
        if rid and history.remove(rid):
            self.refresh()
            self._toast(tr("hist.deleted"))

    def _on_clear(self) -> None:
        # 默认视图：清空未加书签的；书签视图（正在看书签）：全部清空
        n = history.clear(bookmarks_only=not self.bookmarks_only.isChecked())
        self.refresh()
        self._toast(tr("hist.cleared", n=n))

    def _toast(self, message: str) -> None:
        InfoBar.success(
            title=tr("hist.title"),
            content=message,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self,
        )
