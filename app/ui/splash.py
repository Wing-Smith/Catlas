"""启动画面：Photoshop / Excel 风格的浮窗闪屏。

圆角无边框浮窗，深色底：应用图标带投影淡入上浮，下方标题 + 副标语，
底部琥珀色细进度条前进，加载文案循环滚动（末尾带跳动省略号）。
完成后整体淡出并让位主窗口。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.core.assets import asset
from app.core.i18n import tr
from app.core.version import APP_VERSION


class SplashScreen(QWidget):
    """应用启动闪屏。用法：创建 → show() → 主窗口就绪后调用 finish()。"""

    BG = QColor("#1E2536")
    BORDER = QColor(255, 255, 255, 28)
    ACCENT = "#F2B33D"
    SUBTEXT = "#98A2C3"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(440, 320)

        self._fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fade)
        self._fade.setOpacity(0.0)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 32, 30, 20)
        root.setSpacing(0)

        # ---- 图标（投影已预烘焙进 PNG，见 assets/icon_shadow.png） ----
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(str(asset("icon_shadow.png"))).scaled(
            132, 124, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.icon_label.setPixmap(pix)
        self.icon_label.setFixedHeight(124)
        root.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ---- 标题 / 副标语 ----
        self.title_label = QLabel(tr("app.name"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            "color: #FFFFFF; font-size: 26px; font-weight: 600; letter-spacing: 1px; background: transparent;"
        )
        root.addWidget(self.title_label)

        self.tagline_label = QLabel(tr("app.tagline"))
        self.tagline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tagline_label.setStyleSheet(
            f"color: {self.SUBTEXT}; font-size: 12px; background: transparent; padding-top: 4px;"
        )
        root.addWidget(self.tagline_label)
        root.addStretch(1)

        # ---- 进度条（琥珀色，呼应猫眼） ----
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,20); border: none; border-radius: 2px; }"
            f"QProgressBar::chunk {{ background: {self.ACCENT}; border-radius: 2px; }}"
        )
        root.addWidget(self.bar)

        # ---- 底部：加载文案（左）+ 版本（右） ----
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 10, 0, 0)
        self.loading_label = QLabel()
        self.loading_label.setStyleSheet(
            f"color: {self.SUBTEXT}; font-size: 12px; background: transparent;"
        )
        bottom.addWidget(self.loading_label, stretch=1)
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setStyleSheet(
            f"color: {self.SUBTEXT}; font-size: 12px; background: transparent;"
        )
        bottom.addWidget(version_label)
        root.addLayout(bottom)

        # ---- 动画与定时器 ----
        self._steps = ["splash.loading1", "splash.loading2", "splash.loading3"]
        self._step_idx = 0
        self._dots = 0

        self._fade_anim = QPropertyAnimation(self._fade, b"opacity", self)
        self._fade_anim.setDuration(420)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

        self._rise_anim = QPropertyAnimation(self.icon_label, b"pos", self)
        self._rise_anim.setDuration(520)
        self._rise_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._bar_anim = QPropertyAnimation(self.bar, b"value", self)
        self._bar_anim.setDuration(3200)
        self._bar_anim.setStartValue(0)
        self._bar_anim.setEndValue(100)
        self._bar_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._bar_anim.start()

        self._text_timer = QTimer(self)
        self._text_timer.setInterval(700)
        self._text_timer.timeout.connect(self._cycle_loading_text)
        self._text_timer.start()
        self._update_loading_text()

    # ------------------------------------------------------------------ 行为

    def _update_loading_text(self) -> None:
        base = tr(self._steps[self._step_idx % len(self._steps)])
        self.loading_label.setText(base + "·" * self._dots)

    def _cycle_loading_text(self) -> None:
        self._dots += 1
        if self._dots > 3:
            self._dots = 0
            self._step_idx += 1
        self._update_loading_text()

    def finish(self) -> None:
        """主窗口已就绪：停掉动画，淡出并关闭。"""
        self._text_timer.stop()
        self._bar_anim.stop()
        self.bar.setValue(100)
        self._fade_anim.stop()
        self._fade_anim.setDuration(360)
        self._fade_anim.setStartValue(self._fade.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.close)
        self._fade_anim.start()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())
        # 图标上浮动画在窗口布局完成后开始
        end_pos = self.icon_label.pos()
        self._rise_anim.setStartValue(end_pos + QPoint(0, 14))
        self._rise_anim.setEndValue(end_pos)
        self._rise_anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self.BORDER)
        painter.setBrush(self.BG)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)
        painter.end()
