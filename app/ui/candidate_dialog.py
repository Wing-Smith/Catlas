"""地名消歧义对话框：一个地名命中多个候选时，让用户挑一个。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ListWidget, MessageBoxBase, SubtitleLabel

from app.core.models import GeoArea


class CandidateDialog(MessageBoxBase):
    """候选地点列表，确认后通过 selected 取回用户的选择。"""

    def __init__(self, candidates: list[GeoArea], parent: QWidget | None = None):
        super().__init__(parent)
        self.candidates = candidates
        self.selected: GeoArea | None = None

        self.titleLabel = SubtitleLabel("找到多个匹配地点，请选择：")
        self.list_widget = ListWidget()
        self.list_widget.setFixedHeight(min(320, 56 * len(candidates) + 20))
        for area in candidates:
            self.list_widget.addItem(f"{area.display_name}　（约 {area.area_km2:.1f} km²）")
        self.list_widget.setCurrentRow(0)

        hint = BodyLabel("双击或选中后点「确定」")
        hint.setStyleSheet("color: rgba(255,255,255,140);")

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.list_widget)
        self.viewLayout.addWidget(hint)

        self.list_widget.itemDoubleClicked.connect(self._pick_and_accept)

    def _pick_and_accept(self, _item) -> None:
        self.selected = self.candidates[self.list_widget.currentRow()]
        self.accept()

    def accept(self) -> None:  # noqa: D102
        self.selected = self.candidates[self.list_widget.currentRow()]
        super().accept()
