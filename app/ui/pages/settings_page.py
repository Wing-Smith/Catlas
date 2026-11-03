"""设置页：限流/超时/范围阈值参数、Overpass 端点列表、缓存管理。"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPropertyAnimation, Signal, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    TextEdit,
)

from app.core import cache, fetch, tiles
from app.core.assets import asset
from app.core.config import CONFIG_FILE, SETTINGS, Settings
from app.core.i18n import tr
from app.ui.pages.home_page import APP_VERSION
from app.ui.widgets import style_native_spin


def _dspin(value: float, lo: float, hi: float, step: float, decimals: int = 1) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    style_native_spin(s)
    return s


def _ispin(value: int, lo: int, hi: int, step: int = 1) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setValue(value)
    style_native_spin(s)
    return s


# 连点 7 次判定：相邻两次点击间隔超过该值则重新计数
_EASTER_GAP_MS = 1500
_EASTER_CLICKS = 7


class _AboutIcon(QLabel):
    """关于页图标：按压动效 + 点击信号（连点 7 次是 Calico 小窝的开关彩蛋）。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._pulse()
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def _pulse(self) -> None:
        """按压反馈：透明度快速压暗后回弹。"""
        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.35, 0.45)
        anim.setKeyValueAt(1.0, 1.0)
        anim.start()
        # 动画对象随自身销毁，避免被 GC 回收
        self._anim = anim


class SettingsPage(QWidget):
    language_changed = Signal(str)
    theme_changed = Signal(str)
    pet_toggled = Signal(bool)
    update_status_ready = Signal(object)  # updater.UpdateStatus，检查线程回投

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        self.section_net = StrongBodyLabel("")
        layout.addWidget(self.section_net)

        form = QFormLayout()
        form.setSpacing(8)
        self._form = form

        self.spin_interval = _dspin(SETTINGS.request_interval_s, 0.2, 10.0, 0.2)
        self.spin_http_timeout = _ispin(SETTINGS.http_timeout_s, 5, 180, 5)
        self.spin_overpass_timeout = _ispin(SETTINGS.overpass_timeout_s, 10, 600, 10)
        self.spin_max_area = _dspin(SETTINGS.max_area_km2, 1.0, 10000.0, 10.0)
        self.spin_cell_km = _dspin(SETTINGS.split_cell_km, 0.5, 50.0, 0.5)
        self.spin_cache_mb = _ispin(SETTINGS.cache_max_mb, 64, 102400, 256)
        form.addRow("请求间隔（秒）", self.spin_interval)
        form.addRow("HTTP 超时（秒）", self.spin_http_timeout)
        form.addRow("Overpass 超时（秒）", self.spin_overpass_timeout)
        form.addRow("面积上限（km²）", self.spin_max_area)
        form.addRow("分块边长（km）", self.spin_cell_km)
        form.addRow("数据缓存上限（MB）", self.spin_cache_mb)

        self.language_combo = ComboBox()
        self.language_combo.addItem("简体中文", userData="zh")
        self.language_combo.addItem("English", userData="en")
        lang_index = self.language_combo.findData(SETTINGS.language)
        if lang_index >= 0:
            self.language_combo.setCurrentIndex(lang_index)
        self.language_combo.currentIndexChanged.connect(self._on_language)
        form.addRow("界面语言", self.language_combo)

        self.theme_combo = ComboBox()
        for key in ("auto", "dark", "light"):
            self.theme_combo.addItem("", userData=key)
        theme_index = self.theme_combo.findData(SETTINGS.theme)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)
        self.theme_combo.currentIndexChanged.connect(self._on_theme)
        form.addRow("主题模式", self.theme_combo)
        layout.addLayout(form)

        self.section_eps = StrongBodyLabel("")
        layout.addWidget(self.section_eps)
        self.endpoints_edit = TextEdit()
        self.endpoints_edit.setPlainText("\n".join(SETTINGS.overpass_endpoints))
        self.endpoints_edit.setMaximumHeight(120)
        layout.addWidget(self.endpoints_edit)

        self.update_edit = LineEdit()
        self.update_edit.setPlaceholderText(
            "留空 = 内置地址（github.com/Wing-Smith/Catlas）"
        )
        self.update_edit.setText(SETTINGS.update_url)
        self.update_edit.setClearButtonEnabled(True)
        form.addRow("", self.update_edit)

        # 手动检查更新：按钮 + 状态文字
        self.btn_check_update = PushButton("")
        self.btn_check_update.clicked.connect(self._check_update_now)
        self.update_status_label = CaptionLabel("")
        self.update_status_label.setWordWrap(True)
        upd_row_widget = QWidget()
        upd_row_widget.setStyleSheet("background: transparent;")
        upd_row = QHBoxLayout(upd_row_widget)
        upd_row.setContentsMargins(0, 0, 0, 0)
        upd_row.setSpacing(10)
        upd_row.addWidget(self.btn_check_update)
        upd_row.addWidget(self.update_status_label, stretch=1)
        form.addRow("", upd_row_widget)
        self.update_status_ready.connect(self._on_update_status)

        self.hint = CaptionLabel("")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        # ---------------- 按钮区 ----------------
        btn_row = QHBoxLayout()
        self.btn_save = PrimaryPushButton("")
        self.btn_reset = PushButton("")
        self.btn_clear_data = PushButton("")
        self.btn_clear_tiles = PushButton("")
        self.btn_save.clicked.connect(self._save)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_clear_data.clicked.connect(self._clear_data_cache)
        self.btn_clear_tiles.clicked.connect(self._clear_tile_cache)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_clear_data)
        btn_row.addWidget(self.btn_clear_tiles)
        layout.addLayout(btn_row)

        # ---------------- 关于（含 ODbL 署名，置于页底） ----------------
        self.section_about = StrongBodyLabel("")
        layout.addWidget(self.section_about)
        about_row = QHBoxLayout()
        about_row.setSpacing(12)
        self.about_icon = _AboutIcon()
        self.about_icon.setFixedSize(44, 44)
        self.about_icon.setPixmap(
            QPixmap(str(asset("icon.png"))).scaled(
                44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )
        self.about_icon.clicked.connect(self._on_about_icon)
        self._icon_gap_clock = QElapsedTimer()
        self._icon_clicks = 0
        about_row.addWidget(self.about_icon)
        about_col = QVBoxLayout()
        about_col.setSpacing(2)
        self.about_name = StrongBodyLabel(f"Catlas · 猫图集  v{APP_VERSION}")
        self.about_name.setStyleSheet("background: transparent;")
        self.about_text = CaptionLabel("")
        self.about_text.setWordWrap(True)
        self.about_copyright = CaptionLabel("")
        self.about_copyright.setStyleSheet("background: transparent;")
        about_col.addWidget(self.about_name)
        about_col.addWidget(self.about_text)
        about_col.addWidget(self.about_copyright)
        about_row.addLayout(about_col, stretch=1)

        about_btns = QVBoxLayout()
        about_btns.addStretch(1)
        self.btn_eula = PushButton("")
        self.btn_eula.clicked.connect(self._show_eula)
        about_btns.addWidget(self.btn_eula)
        about_btns.addStretch(1)
        about_row.addLayout(about_btns)
        layout.addLayout(about_row)

        layout.addStretch(1)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.section_net.setText(tr("settings.section_net"))
        labels = (
            tr("settings.interval"), tr("settings.http_timeout"), tr("settings.overpass_timeout"),
            tr("settings.max_area"), tr("settings.cell_km"), tr("settings.cache_mb"),
            tr("settings.language"), tr("settings.theme"), tr("settings.update_url"),
        )
        widgets = (
            self.spin_interval, self.spin_http_timeout, self.spin_overpass_timeout,
            self.spin_max_area, self.spin_cell_km, self.spin_cache_mb, self.language_combo,
            self.theme_combo, self.update_edit,
        )
        for text, w in zip(labels, widgets):
            lbl = self._form.labelForField(w)
            if lbl is not None:
                lbl.setText(text)
        self.section_eps.setText(tr("settings.section_eps"))
        for key in ("auto", "dark", "light"):
            idx = self.theme_combo.findData(key)
            if idx >= 0:
                self.theme_combo.setItemText(idx, tr(f"settings.theme_{key}"))
        self.hint.setText(f"config.json：{CONFIG_FILE}")
        self.btn_save.setText(tr("settings.save"))
        self.btn_reset.setText(tr("settings.reset"))
        self.btn_clear_data.setText(tr("settings.clear_data"))
        self.btn_clear_tiles.setText(tr("settings.clear_tiles"))
        self.section_about.setText(tr("settings.about"))
        self.about_text.setText(tr("settings.about_text"))
        self.about_copyright.setText(tr("settings.copyright"))
        self.btn_eula.setText(tr("settings.eula"))
        self.btn_check_update.setText(tr("update.check_now"))

    # ------------------------------------------------------------------ 更新检查

    def _check_update_now(self) -> None:
        self.btn_check_update.setEnabled(False)
        self.update_status_label.setStyleSheet("color: #8a8a8a; background: transparent;")
        self.update_status_label.setText(tr("update.checking"))
        import threading

        threading.Thread(target=self._run_update_check, daemon=True).start()

    def _run_update_check(self) -> None:
        from app.core import updater

        self.update_status_ready.emit(updater.check_status())

    def _on_update_status(self, status) -> None:
        from app.core import updater

        self.btn_check_update.setEnabled(True)
        if not status.connected:
            self.update_status_label.setStyleSheet("color: #E5484D; background: transparent;")
            self.update_status_label.setText(tr("update.failed", err=status.error or "?"))
            self.update_status_label.setToolTip(status.error or "")
            return
        self.update_status_label.setToolTip("")
        if status.latest and updater.is_newer(status.latest):
            self.update_status_label.setStyleSheet("color: #B26A00; background: transparent;")
            self.update_status_label.setText(tr("update.found", v=status.latest))
            import webbrowser

            webbrowser.open(status.url)
        else:
            self.update_status_label.setStyleSheet("color: #2EA043; background: transparent;")
            self.update_status_label.setText(tr("update.latest", v=status.latest or APP_VERSION))

    def _on_language(self) -> None:
        lang = self.language_combo.currentData()
        SETTINGS.language = lang
        SETTINGS.save()
        self.language_changed.emit(lang)

    def _on_theme(self) -> None:
        theme = self.theme_combo.currentData()
        SETTINGS.theme = theme
        SETTINGS.save()
        self.theme_changed.emit(theme)

    def _on_about_icon(self) -> None:
        """彩蛋：连点 7 次切换 Calico 的小窝显隐，结果持久化。"""
        if self._icon_gap_clock.isValid() \
                and self._icon_gap_clock.elapsed() <= _EASTER_GAP_MS:
            self._icon_clicks += 1
        else:
            self._icon_clicks = 1
        self._icon_gap_clock.start()
        if self._icon_clicks < _EASTER_CLICKS:
            return
        self._icon_clicks = 0
        SETTINGS.pet_corner = not SETTINGS.pet_corner
        SETTINGS.save()
        self.pet_toggled.emit(SETTINGS.pet_corner)
        key = "home.pet.enabled" if SETTINGS.pet_corner else "home.pet.disabled"
        self._toast(tr(key))

    # ------------------------------------------------------------------

    def _save(self) -> None:
        SETTINGS.request_interval_s = self.spin_interval.value()
        SETTINGS.http_timeout_s = self.spin_http_timeout.value()
        SETTINGS.overpass_timeout_s = self.spin_overpass_timeout.value()
        SETTINGS.max_area_km2 = self.spin_max_area.value()
        SETTINGS.split_cell_km = self.spin_cell_km.value()
        SETTINGS.cache_max_mb = self.spin_cache_mb.value()
        endpoints = [ln.strip() for ln in self.endpoints_edit.toPlainText().splitlines() if ln.strip()]
        if endpoints:
            SETTINGS.overpass_endpoints = endpoints
        SETTINGS.update_url = self.update_edit.text().strip()
        SETTINGS.save()
        fetch.reset_probe_cache()  # 端点变了，重新探测镜像
        self._toast(tr("settings.saved"))

    def _reset(self) -> None:
        defaults = Settings()
        self.spin_interval.setValue(defaults.request_interval_s)
        self.spin_http_timeout.setValue(defaults.http_timeout_s)
        self.spin_overpass_timeout.setValue(defaults.overpass_timeout_s)
        self.spin_max_area.setValue(defaults.max_area_km2)
        self.spin_cell_km.setValue(defaults.split_cell_km)
        self.spin_cache_mb.setValue(defaults.cache_max_mb)
        self.endpoints_edit.setPlainText("\n".join(defaults.overpass_endpoints))
        self.update_edit.setText(defaults.update_url)
        self._toast(tr("settings.reset_hint"))

    def _clear_data_cache(self) -> None:
        n = cache.clear()
        self._toast(tr("settings.data_cleared", n=n))

    def _clear_tile_cache(self) -> None:
        n = tiles.clear_tile_cache()
        self._toast(tr("settings.tiles_cleared", n=n))

    def _toast(self, message: str) -> None:
        InfoBar.success(
            title="设置",
            content=message,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def _show_eula(self) -> None:
        """用户协议弹窗（跟随当前语言）。"""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("settings.eula"))
        dialog.resize(560, 480)
        box = QVBoxLayout(dialog)
        box.setContentsMargins(12, 12, 12, 12)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            "QTextBrowser { background: rgba(128,128,128,24); border: 1px solid rgba(128,128,128,60);"
            " border-radius: 8px; padding: 10px; font-size: 13px; }"
        )
        browser.setPlainText(tr("settings.eula_text"))
        box.addWidget(browser, stretch=1)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = PushButton("OK")
        btn_close.setFixedWidth(96)
        btn_close.clicked.connect(dialog.accept)
        btn_row.addWidget(btn_close)
        box.addLayout(btn_row)
        dialog.exec()
