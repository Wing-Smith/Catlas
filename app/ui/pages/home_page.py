"""主页：问候页头 + 快速入口磁贴 + 最近抓取 / 网络状态 + 数据缓存 / 数据源 / 关于。

与 main_window 的公共接口保持兼容：
btn_start_clicked / btn_draw_clicked / navigate_requested(routeKey) /
retranslate_ui() / refresh_stats() / set_net_checking() / set_net_results() /
set_last_fetch(summary)
"""

from __future__ import annotations

import platform

from PySide6 import QtCore
from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    IconWidget,
    PushButton,
    SimpleCardWidget,
    StrongBodyLabel,
    TitleLabel,
)

from app.core import cache, tiles
from app.core.assets import asset
from app.core.config import CONFIG_FILE, SETTINGS
from app.core.i18n import tr
from app.core.routing import PROFILES
from app.core.tiles import PROVIDERS
from app.core.version import APP_VERSION
from app.core.worldmap import city_names
from app.ui.pet_area import PetArea


def _tile_cache_stats() -> tuple[int, int]:
    files = tiles._cached_files()
    return len(files), sum(p.stat().st_size for p in files)


class _Card(SimpleCardWidget):
    """带标题栏的圆角卡片。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)
        self.title_label = StrongBodyLabel("")
        self.title_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.title_label)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        layout.addLayout(self.body)

    def add_row(self, key_widget, value_widget) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(key_widget, stretch=2)
        row.addStretch(1)
        row.addWidget(value_widget, stretch=3)
        self.body.addLayout(row)

    def _kv(self, key: str) -> tuple[CaptionLabel, BodyLabel]:
        k = CaptionLabel(key)
        v = BodyLabel("")
        v.setWordWrap(True)
        self.add_row(k, v)
        return k, v


class _ActionTile(SimpleCardWidget):
    """可点击的功能入口磁贴：图标 + 标题 + 一行说明。"""

    clicked = QtCore.Signal()

    def __init__(self, icon, title: str = "", desc: str = "", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        self.accent = QLabel()
        self.accent.setFixedSize(3, 40)
        self.accent.setStyleSheet("background: #0078D4; border-radius: 2px;")
        root.addWidget(self.accent)

        self.icon_widget = IconWidget(icon)
        self.icon_widget.setFixedSize(26, 26)
        root.addWidget(self.icon_widget)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title_label = StrongBodyLabel(title)
        self.title_label.setStyleSheet("background: transparent;")
        self.desc_label = CaptionLabel(desc)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("background: transparent;")
        text.addWidget(self.title_label)
        text.addWidget(self.desc_label)
        root.addLayout(text, stretch=1)

    def set_text(self, title: str, desc: str) -> None:
        self.title_label.setText(title)
        self.desc_label.setText(desc)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit()
        super().mousePressEvent(event)


class HomePage(QWidget):
    btn_start_clicked = QtCore.Signal()
    btn_draw_clicked = QtCore.Signal()
    navigate_requested = QtCore.Signal(str)  # routeKey，如 "historyPage"
    update_check_requested = QtCore.Signal()  # 请求主窗口跑一次更新检查

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)

        # ---------------- 页头：Calico + 问候语 ----------------
        header = QHBoxLayout()
        header.setSpacing(18)
        self.brand_icon = QLabel()
        self.brand_icon.setFixedSize(84, 84)
        self.brand_icon.setPixmap(
            QPixmap(str(asset("icon.png"))).scaled(
                84, 84, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )
        header.addWidget(self.brand_icon)

        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        self.title_label = TitleLabel("")
        self.title_label.setStyleSheet("font-size: 30px; background: transparent;")
        self.subtitle_label = BodyLabel("")
        self.subtitle_label.setStyleSheet("font-size: 15px; background: transparent;")
        self.tagline_label = CaptionLabel("")
        self.tagline_label.setWordWrap(True)
        header_text.addStretch(1)
        header_text.addWidget(self.title_label)
        header_text.addWidget(self.subtitle_label)
        header_text.addWidget(self.tagline_label)
        header_text.addStretch(1)
        header.addLayout(header_text, stretch=1)
        layout.addLayout(header)

        # ---------------- 快速入口磁贴 3×2 ----------------
        self.tile_grab = _ActionTile(FIF.DOWNLOAD)
        self.tile_grab.clicked.connect(self.btn_start_clicked)
        self.tile_draw = _ActionTile(FIF.PENCIL_INK)
        self.tile_draw.clicked.connect(self.btn_draw_clicked)
        self.tile_history = _ActionTile(FIF.LIBRARY)
        self.tile_history.clicked.connect(lambda: self.navigate_requested.emit("historyPage"))
        self.tile_route = _ActionTile(FIF.SEND)
        self.tile_route.clicked.connect(lambda: self.navigate_requested.emit("routePage"))
        self.tile_network = _ActionTile(FIF.GLOBE)
        self.tile_network.clicked.connect(lambda: self.navigate_requested.emit("networkPage"))
        self.tile_settings = _ActionTile(FIF.SETTING)
        self.tile_settings.clicked.connect(lambda: self.navigate_requested.emit("settingsPage"))

        tile_grid = QGridLayout()
        tile_grid.setSpacing(10)
        for i, tile in enumerate(
            (self.tile_grab, self.tile_draw, self.tile_history,
             self.tile_route, self.tile_network, self.tile_settings)
        ):
            tile_grid.addWidget(tile, i // 3, i % 3)
        layout.addLayout(tile_grid)

        # ---------------- 中部：最近抓取 + 网络状态 ----------------
        mid_row = QHBoxLayout()
        mid_row.setSpacing(12)

        self.card_last = _Card()
        self.last_label = BodyLabel("")
        self.last_label.setWordWrap(True)
        self.card_last.body.addWidget(self.last_label)
        btn_row = QHBoxLayout()
        self.btn_open_history = PushButton("")
        self.btn_open_history.clicked.connect(lambda: self.navigate_requested.emit("historyPage"))
        btn_row.addWidget(self.btn_open_history)
        btn_row.addStretch(1)
        self.card_last.body.addLayout(btn_row)
        mid_row.addWidget(self.card_last, stretch=3)

        self.card_network = _Card()
        self._net_value = BodyLabel("")
        self._net_value.setWordWrap(True)
        self.card_network.body.addWidget(self._net_value)
        net_btn_row = QHBoxLayout()
        self.btn_open_network = PushButton("")
        self.btn_open_network.clicked.connect(lambda: self.navigate_requested.emit("networkPage"))
        net_btn_row.addWidget(self.btn_open_network)
        net_btn_row.addStretch(1)
        self.card_network.body.addLayout(net_btn_row)
        mid_row.addWidget(self.card_network, stretch=2)
        layout.addLayout(mid_row)

        # ---------------- 底部 3 卡：数据缓存 / 数据源 / 关于 ----------------
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.card_cache = _Card()
        bottom_row.addWidget(self.card_cache, stretch=1)

        self.card_sources = _Card()
        bottom_row.addWidget(self.card_sources, stretch=1)

        self.card_about = _Card()
        self.about_name = BodyLabel("")
        self.about_name.setStyleSheet("font-size: 15px; font-weight: 600; background: transparent;")
        self.about_line = CaptionLabel("")
        self.about_line.setWordWrap(True)
        self.about_env = CaptionLabel("")
        self.about_env.setWordWrap(True)
        self.about_copyright = CaptionLabel("")
        self.about_copyright.setWordWrap(True)
        self.card_about.body.addWidget(self.about_name)
        self.card_about.body.addWidget(self.about_line)
        self.card_about.body.addWidget(self.about_env)
        self.card_about.body.addWidget(self.about_copyright)
        about_btn_row = QHBoxLayout()
        self.btn_view_eula = PushButton("")
        self.btn_view_eula.clicked.connect(lambda: self.navigate_requested.emit("settingsPage"))
        about_btn_row.addWidget(self.btn_view_eula)
        about_btn_row.addStretch(1)
        self.card_about.body.addLayout(about_btn_row)
        bottom_row.addWidget(self.card_about, stretch=1)

        # ---------------- 更新检测：连接状态 + 版本对比 ----------------
        self.card_update = _Card()
        self.update_conn_key, self.update_conn_value = self.card_update._kv("")
        self.update_cur_key, self.update_cur_value = self.card_update._kv("")
        self.update_latest_key, self.update_latest_value = self.card_update._kv("")
        upd_btn_row = QHBoxLayout()
        self.btn_check_update = PushButton("")
        self.btn_check_update.clicked.connect(self._on_check_update_clicked)
        upd_btn_row.addWidget(self.btn_check_update)
        upd_btn_row.addStretch(1)
        self.card_update.body.addLayout(upd_btn_row)
        bottom_row.addWidget(self.card_update, stretch=1)

        layout.addLayout(bottom_row)

        # ---------------- Calico 电子宠物（默认隐藏，关于页图标连点 7 次解锁） ----------------
        self.card_pet = _Card()
        self.pet_area = PetArea()
        self.card_pet.body.addWidget(self.pet_area)
        self.card_pet.setVisible(SETTINGS.pet_corner)
        layout.addWidget(self.card_pet)

        self._last_update_status = None  # UpdateStatus | None，供 retranslate 后重绘
        self.retranslate_ui()
        self.refresh_stats()

    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        self.title_label.setText(tr("home.greet1"))
        self.subtitle_label.setText(tr("home.greet2"))
        self.tagline_label.setText(tr("app.tagline"))
        self.tile_grab.set_text(tr("nav.grab"), tr("home.desc_grab"))
        self.tile_draw.set_text(tr("nav.draw"), tr("home.desc_draw"))
        self.tile_history.set_text(tr("nav.history"), tr("home.desc_history"))
        self.tile_route.set_text(tr("nav.route"), tr("home.desc_route"))
        self.tile_network.set_text(tr("nav.network"), tr("home.desc_network"))
        self.tile_settings.set_text(tr("nav.settings"), tr("home.desc_settings"))
        self.card_last.title_label.setText(tr("home.card_last"))
        self.btn_open_history.setText(tr("home.open_history"))
        self.card_network.title_label.setText(tr("home.card_network"))
        self.btn_open_network.setText(tr("home.open_network"))
        self.card_cache.title_label.setText(tr("home.card_cache"))
        self.card_sources.title_label.setText(tr("home.card_sources"))
        self.card_about.title_label.setText(tr("home.card_about"))
        self.about_name.setText(f"{tr('app.title')}  v{APP_VERSION}")
        self.about_line.setText(tr("home.about_line"))
        self.about_env.setText(
            tr("home.env_line", py=platform.python_version(), qt=qVersion())
        )
        self.about_copyright.setText(tr("settings.copyright"))
        self.btn_view_eula.setText(tr("home.view_eula"))
        self.card_update.title_label.setText(tr("home.card_update"))
        self.update_conn_key.setText(tr("home.update_conn"))
        self.update_cur_key.setText(tr("home.update_current"))
        self.update_latest_key.setText(tr("home.update_latest"))
        self.btn_check_update.setText(tr("home.update_btn"))
        self.show_update_status(self._last_update_status)
        self.card_pet.title_label.setText(tr("home.pet.title"))
        self.pet_area.retranslate_ui()
        self._build_network_rows()
        if not self.last_label.text():
            self.last_label.setText(tr("home.fetch_none"))

    # ------------------------------------------------------------------ 更新检测卡片

    def _on_check_update_clicked(self) -> None:
        self.btn_check_update.setEnabled(False)
        self.update_conn_value.setText(tr("home.update_checking"))
        self.update_conn_value.setStyleSheet("color: #8a8a8a; background: transparent;")
        self.update_latest_value.setText("—")
        self.update_check_requested.emit()

    def show_update_status(self, status) -> None:
        """渲染一次更新检查结果（status 为 updater.UpdateStatus | None）。"""
        from app.core.updater import UpdateStatus

        self._last_update_status = status
        self.btn_check_update.setEnabled(True)
        if status is not None:
            self.update_cur_value.setText(f"v{status.current}")
        if status is None:
            self.update_conn_value.setText(tr("home.update_unknown"))
            self.update_conn_value.setStyleSheet("color: #8a8a8a; background: transparent;")
            self.update_latest_value.setText("—")
            return
        if status.checking:
            self.update_conn_value.setText(tr("home.update_checking"))
            self.update_conn_value.setStyleSheet("color: #8a8a8a; background: transparent;")
            self.btn_check_update.setEnabled(False)
            return
        if status.connected:
            self.update_conn_value.setText(tr("home.update_conn_ok"))
            self.update_conn_value.setStyleSheet("color: #2EA043; background: transparent;")
            self.update_conn_value.setToolTip("")
        else:
            self.update_conn_value.setText(tr("home.update_conn_fail"))
            self.update_conn_value.setStyleSheet("color: #E5484D; background: transparent;")
            self.update_conn_value.setToolTip(status.error or "")
        self.update_cur_value.setText(f"v{status.current}")
        self.update_latest_value.setText(f"v{status.latest}" if status.latest else "—")

    # ------------------------------------------------------------------ 卡片内容

    def _clear(self, card: _Card) -> None:
        while card.body.count():
            item = card.body.takeAt(0)
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()

    def _build_cache_rows(self) -> None:
        self._clear(self.card_cache)
        _, v1 = self.card_cache._kv(tr("home.info_cache"))
        v1.setText(str(cache.count_entries()))
        _, v2 = self.card_cache._kv(tr("home.info_tiles"))
        n_files, size = _tile_cache_stats()
        v2.setText(f"{n_files} / {size / 1024 / 1024:.1f} MB")
        _, v3 = self.card_cache._kv("config.json")
        v3.setText(str(CONFIG_FILE))

    def _build_sources_rows(self) -> None:
        self._clear(self.card_sources)
        _, v1 = self.card_sources._kv(tr("home.info_endpoints"))
        v1.setText(str(len(SETTINGS.overpass_endpoints)))
        _, v2 = self.card_sources._kv(tr("home.info_providers"))
        v2.setText(str(len(PROVIDERS)))
        _, v3 = self.card_sources._kv(tr("home.info_profiles"))
        v3.setText(str(len(PROFILES)))
        names = city_names(6)
        if names:
            _, v4 = self.card_sources._kv("Cities")
            v4.setText(" · ".join(names))

    def _build_network_rows(self) -> None:
        results = getattr(self, "_net_results", None)
        if results is None:
            self._net_value.setText(tr("home.net_waiting"))
        elif results == "checking":
            self._net_value.setText(tr("home.net_checking"))
        else:
            ok = sum(1 for _, online in results if online)
            self._net_value.setText(tr("home.net_summary", ok=ok, total=len(results)))

    # ------------------------------------------------------------------ 外部更新

    def refresh_stats(self) -> None:
        self._build_cache_rows()
        self._build_sources_rows()

    def set_net_checking(self) -> None:
        self._net_results = "checking"
        if hasattr(self, "_net_value"):
            self._net_value.setText(tr("home.net_checking"))

    def set_net_results(self, results: list[tuple[str, bool]]) -> None:
        self._net_results = results
        self._build_network_rows()

    def set_last_fetch(self, summary: str) -> None:
        self.last_label.setText(summary)

    def set_pet_visible(self, visible: bool) -> None:
        """小窝开关（关于页图标连点 7 次的彩蛋）。"""
        self.card_pet.setVisible(visible)
