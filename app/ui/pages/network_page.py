"""网络监测页：并发探测 Overpass / 地理编码 / 瓦片源 的连通性与延迟。

结果以小块（卡片）网格呈现：绿色 = 可达，红色 = 不可达，灰色 = 检测中。
卡片动效：淡入、状态色渐变过渡、结果到达时边框微光脉冲、鼠标跟随灯光。
"""

from __future__ import annotations

import time

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QPointF, QTimer, QVariantAnimation, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    IndeterminateProgressBar,
    PushButton,
    SingleDirectionScrollArea,
    StrongBodyLabel,
)

from app.core.i18n import tr
from app.services.job_manager import NetworkProbeWorker

_COLS = 3  # 网格列数

_GREEN = "#6CCB5F"
_RED = "#E81123"
_GRAY = "rgba(255,255,255,140)"

_PENDING = QColor(255, 255, 255, 90)  # 检测中：半透明白
_BG = QColor(255, 255, 255, 10)  # 卡片底色
_SPOT_RADIUS = 150.0  # 灯光半径


class _ProbeTile(QFrame):
    """单个服务端点的小卡片：自绘 + 淡入 + 状态色渐变 + 鼠标跟随灯光。"""

    def __init__(self, name: str, url: str, parent=None):
        super().__init__(parent)
        self._url = url
        self.setObjectName("probeTile")
        self.setMinimumHeight(86)
        self.setMouseTracking(True)

        # 状态色（当前值 → 动画渐变到目标值）
        self._accent = QColor(_PENDING)
        self._accent_target = QColor(_PENDING)
        # 边框微光强度 0~1（pending 也保持可见的微光底）
        self._glow = 0.25
        # 鼠标灯光（插值位置 + 透明度）
        self._spot = QPointF(-1000, -1000)
        self._spot_target = QPointF(-1000, -1000)
        self._spot_alpha = 0.0
        self._spot_alpha_target = 0.0

        # 灯光插值定时器（16ms ≈ 60fps， settled 后自动停）
        self._lerp_timer = QTimer(self)
        self._lerp_timer.setInterval(16)
        self._lerp_timer.timeout.connect(self._lerp_step)

        # 入场淡入
        self._fade_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fade_effect)
        self._fade_effect.setOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self._fade_effect, b"opacity", self)
        self._fade_anim.setDuration(380)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self.dot = QFrame()
        self.dot.setFixedSize(9, 9)
        self.dot.setObjectName("dot")
        self.dot.setStyleSheet(f"background: {_GRAY}; border-radius: 4.5px;")
        top.addWidget(self.dot)
        self.name_label = BodyLabel(name)
        top.addWidget(self.name_label, stretch=1)
        top.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(top)

        self.latency_label = CaptionLabel(tr("net.checking"))
        layout.addWidget(self.latency_label)
        self.setToolTip(url)

    # ---------------------------------------------------------------- 动画属性

    def get_glow(self) -> float:
        return self._glow

    def set_glow(self, value: float) -> None:
        self._glow = value
        self.update()

    glow = Property(float, get_glow, set_glow)

    # ---------------------------------------------------------------- 交互

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._spot_target = event.position()
        self._spot_alpha_target = 1.0
        if not self._lerp_timer.isActive():
            self._lerp_timer.start()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._spot_alpha_target = 0.0
        if not self._lerp_timer.isActive():
            self._lerp_timer.start()
        super().leaveEvent(event)

    def _lerp_step(self) -> None:
        """灯光位置/透明度向目标插值，逼近后停表省电。"""
        self._spot += (self._spot_target - self._spot) * 0.22
        self._spot_alpha += (self._spot_alpha_target - self._spot_alpha) * 0.16
        if (
            (self._spot_target - self._spot).manhattanLength() < 0.5
            and abs(self._spot_alpha_target - self._spot_alpha) < 0.02
        ):
            self._spot = self._spot_target
            self._spot_alpha = self._spot_alpha_target
            self._lerp_timer.stop()
        self.update()

    # ---------------------------------------------------------------- 状态

    def _pulse(self, target: float) -> None:
        """边框微光：冲到 1 再回落到 resting 值。"""
        self._pulse_up = QPropertyAnimation(self, b"glow", self)
        self._pulse_up.setDuration(220)
        self._pulse_up.setStartValue(self._glow)
        self._pulse_up.setEndValue(1.0)
        self._pulse_up.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _settle() -> None:
            self._pulse_down = QPropertyAnimation(self, b"glow", self)
            self._pulse_down.setDuration(600)
            self._pulse_down.setStartValue(1.0)
            self._pulse_down.setEndValue(target)
            self._pulse_down.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._pulse_down.start()

        self._pulse_up.finished.connect(_settle)
        self._pulse_up.start()

    def _crossfade_accent(self, color: QColor) -> None:
        self._accent_target = QColor(color)
        anim = QVariantAnimation(self)
        anim.setDuration(450)
        anim.setStartValue(self._accent)
        anim.setEndValue(self._accent_target)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def _apply(v) -> None:
            self._accent = QColor(v)
            self.update()

        anim.valueChanged.connect(_apply)
        anim.finished.connect(lambda: setattr(self, "_accent", QColor(self._accent_target)))
        anim.start()
        self._accent_anim = anim  # 保活

    def set_result(self, ok: bool, latency_ms: float, err: str = "") -> None:
        accent = QColor(_GREEN if ok else _RED)
        self._crossfade_accent(accent)
        self._pulse(0.55)
        self.dot.setStyleSheet(
            f"background: {_GREEN if ok else _RED}; border-radius: 4.5px;"
        )
        if ok:
            self.latency_label.setText(tr("net.online", ms=latency_ms))
            self.latency_label.setStyleSheet(f"color: {_GREEN};")
        else:
            reason = f" · {err}" if err else ""
            self.latency_label.setText(f"{tr('net.offline')}{reason}")
            self.latency_label.setStyleSheet(f"color: {_RED};")
        self.setToolTip(self._url)

    # ---------------------------------------------------------------- 自绘

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        # 底色
        painter.fillPath(path, _BG)

        # 鼠标灯光：径向渐变，颜色随状态色
        if self._spot_alpha > 0.01:
            grad = QRadialGradient(self._spot, _SPOT_RADIUS)
            highlight = QColor(self._accent)
            highlight.setAlpha(int(34 * self._spot_alpha))
            edge = QColor(self._accent)
            edge.setAlpha(0)
            grad.setColorAt(0.0, highlight)
            grad.setColorAt(1.0, edge)
            painter.fillPath(path, grad)

        # 边框：微光驱动透明度
        pen_color = QColor(self._accent)
        pen_color.setAlpha(int(35 + 175 * self._glow))
        painter.strokePath(path, QPen(pen_color, 1))

        painter.end()
        super().paintEvent(event)


class NetworkPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("networkPage")
        self.setStyleSheet("background: transparent;")
        self._worker: NetworkProbeWorker | None = None
        self._last_check: str | None = None
        self._tiles: dict[str, _ProbeTile] = {}  # url → 卡片（同名端点靠 URL 区分）
        self.last_results: list[tuple[str, bool]] = []  # (名称, 是否在线)，主页摘要用

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.title_label = StrongBodyLabel("")
        self.last_check_label = CaptionLabel("")
        self.retry_button = PushButton("")
        self.retry_button.clicked.connect(self.start_probe)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.last_check_label)
        header.addWidget(self.retry_button)
        layout.addLayout(header)

        self.progress = IndeterminateProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(10)
        self.grid.setContentsMargins(0, 0, 0, 0)

        scroll = SingleDirectionScrollArea()
        scroll.setWidget(self.container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(scroll, stretch=1)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.title_label.setText(tr("net.title"))
        self.retry_button.setText(tr("net.retry"))
        if self._worker is not None and self._worker.isRunning():
            self.last_check_label.setText(tr("net.checking"))
        elif self._last_check is None:
            self.last_check_label.setText(tr("net.never"))
        else:
            self.last_check_label.setText(tr("net.last", t=self._last_check))

    def showEvent(self, event) -> None:  # noqa: N802 (Qt 约定)
        super().showEvent(event)
        if not self._tiles:
            self.start_probe()

    def start_probe(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # 已有探测在跑（如启动自动探测），避免重复
        # 清空旧结果
        self.last_results = []
        for tile in self._tiles.values():
            tile.deleteLater()
        self._tiles = {}
        while self.grid.count():
            self.grid.takeAt(0)
        self.last_check_label.setText(tr("net.checking"))
        self.progress.setVisible(True)
        self.retry_button.setEnabled(False)

        self._worker = NetworkProbeWorker(self)
        self._worker.targets_ready.connect(self._on_targets)
        self._worker.result.connect(self._on_result)
        self._worker.finished_all.connect(self._on_finished)
        self._worker.start()

    def _on_targets(self, targets: list[tuple[str, str]]) -> None:
        """探测目标清单到手：立即铺出全部灰色占位卡片。"""
        for index, (name, url) in enumerate(targets):
            tile = _ProbeTile(name, url)
            self._tiles[url] = tile
            self.grid.addWidget(tile, index // _COLS, index % _COLS)

    def _on_result(self, name: str, url: str, ok: bool, latency_ms: float, err: str = "") -> None:
        self.last_results.append((name, ok))
        tile = self._tiles.get(url)
        if tile is None:  # 防御：targets_ready 之前的早期结果
            tile = _ProbeTile(name, url)
            self._tiles[url] = tile
            index = len(self._tiles) - 1
            self.grid.addWidget(tile, index // _COLS, index % _COLS)
        tile.set_result(ok, latency_ms, err)

    def _on_finished(self) -> None:
        self.progress.setVisible(False)
        self.retry_button.setEnabled(True)
        self._last_check = time.strftime("%H:%M:%S")
        self.last_check_label.setText(tr("net.last", t=self._last_check))
