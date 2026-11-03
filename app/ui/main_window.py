"""主窗口：FluentWindow + Mica 毛玻璃。

导航结构（WinUI 3 NavigationView 规范）：
    顶部：主页 / 抓取与制图 / 选区地图 / 路径规划 / 网络监测
    底部：设置
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QSplitter, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon as FIF,
    FluentWindow,
    IndeterminateProgressRing,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    NavigationItemPosition,
    ProgressBar,
    SingleDirectionScrollArea,
)

from app.core import history, i18n
from app.core.assets import asset
from app.core.cateaster import cat_line
from app.core.config import SETTINGS
from app.core.export import PAPER_SIZES
from app.core.i18n import tr
from app.core.models import ExportJob, FetchJob, GeoArea, PipelineResult
from app.services.job_manager import BasemapWorker, ExportWorker, FetchWorker, GeocodeWorker
from app.services.notify import notify_system
from app.ui.loading_overlay import SLOW_TOOLTIP, LoadingOverlay
from app.ui.pages.draw_page import DrawPage
from app.ui.pages.history_page import HistoryPage
from app.ui.pages.home_page import HomePage
from app.ui.pages.log_page import LogPage
from app.ui.pages.network_page import NetworkPage
from app.ui.pages.route_page import RoutePage
from app.ui.pages.settings_page import SettingsPage
from app.ui.panels.input_panel import InputPanel
from app.ui.preview.map_canvas import MapCanvas


class _UpdateChecker(QObject):
    """后台线程跑更新检查，Signal 桥接回主线程（Qt 队列连接线程安全）。"""

    result = Signal(object)  # updater.UpdateStatus

    def start(self) -> None:
        import threading

        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        from app.core import updater

        self.result.emit(updater.check_status())


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app.title"))
        self.setWindowIcon(QIcon(str(asset("app.ico"))))
        # 小屏适配：初始尺寸不超过当前屏幕可用区域的 90% / 85%
        from PySide6.QtGui import QGuiApplication

        _screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        _avail = _screen.availableGeometry() if _screen else None
        if _avail:
            self.resize(
                min(1280, int(_avail.width() * 0.9)),
                min(800, int(_avail.height() * 0.85)),
            )
        else:
            self.resize(1280, 800)
        self.setMicaEffectEnabled(True)  # Windows 11 Mica 毛玻璃
        self.setAcceptDrops(True)  # 支持把 GeoJSON / SHP / GPKG 拖进窗口导入

        self._layers: dict | None = None
        self._fetch_worker: FetchWorker | None = None
        self._geo_worker: GeocodeWorker | None = None
        self._export_worker: ExportWorker | None = None
        self._basemap_worker: BasemapWorker | None = None
        self._basemap_gen = 0  # 底图加载代际，过期结果直接丢弃
        self._busy = False

        # ---------------- 抓取与制图页 ----------------
        body = QWidget()
        body.setObjectName("grabPage")
        body.setStyleSheet("background: transparent;")
        splitter = QSplitter(Qt.Orientation.Horizontal, body)
        splitter.setChildrenCollapsible(False)

        self.input_panel = InputPanel()
        panel_scroll = SingleDirectionScrollArea()
        panel_scroll.setWidget(self.input_panel)
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFixedWidth(320)
        panel_scroll.setStyleSheet("background: transparent; border: none;")

        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(6)

        self.canvas = MapCanvas()
        right_layout.addWidget(self.canvas.make_toolbar(right))
        right_layout.addWidget(self.canvas, stretch=1)
        self.loading_overlay = LoadingOverlay(self.canvas)  # 覆盖画布的加载遮罩

        splitter.addWidget(panel_scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        # ---------------- 底部状态栏（仅抓取页） ----------------
        self.status_label = CaptionLabel(tr("status.ready"))
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setVisible(False)
        self.indet_bar = IndeterminateProgressRing()
        self.indet_bar.setFixedSize(22, 22)
        self.indet_bar.setStrokeWidth(3)
        self.indet_bar.setVisible(False)

        status_bar = QWidget()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 4, 10, 8)
        status_layout.setSpacing(12)
        status_layout.addWidget(self.status_label, stretch=1)
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.indet_bar)

        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(splitter, stretch=1)
        outer.addWidget(status_bar)

        # ---------------- 其余页面 ----------------
        self.home_page = HomePage()
        self.draw_page = DrawPage()
        self.route_page = RoutePage()
        self.network_page = NetworkPage()
        self.history_page = HistoryPage()
        self.log_page = LogPage()
        self.settings_page = SettingsPage()

        # ---------------- 导航（设置置底） ----------------
        self._nav_keys: dict[str, str] = {}  # routeKey → i18n key
        self.addSubInterface(self.home_page, FIF.HOME, tr("nav.home"))
        self._nav_keys["homePage"] = "nav.home"
        self.addSubInterface(body, FIF.DOWNLOAD, tr("nav.grab"))
        self._nav_keys["grabPage"] = "nav.grab"
        self.addSubInterface(self.history_page, FIF.LIBRARY, tr("nav.history"))
        self._nav_keys["historyPage"] = "nav.history"
        self.addSubInterface(self.draw_page, FIF.PENCIL_INK, tr("nav.draw"))
        self._nav_keys["drawPage"] = "nav.draw"
        self.addSubInterface(self.route_page, FIF.SEND, tr("nav.route"))
        self._nav_keys["routePage"] = "nav.route"
        self.addSubInterface(self.network_page, FIF.GLOBE, tr("nav.network"))
        self._nav_keys["networkPage"] = "nav.network"
        self.addSubInterface(self.log_page, FIF.HISTORY, tr("nav.logs"))
        self._nav_keys["logPage"] = "nav.logs"
        self.stackedWidget.addWidget(self.settings_page)  # 设置页入栈，否则点不开
        self.navigationInterface.addItem(
            routeKey="settingsPage",
            icon=FIF.SETTING,
            text=tr("nav.settings"),
            onClick=lambda: self.switchTo(self.settings_page),
            position=NavigationItemPosition.BOTTOM,
        )

        # ---------------- 信号 ----------------
        self.input_panel.btn_fetch.clicked.connect(self._start_fetch)
        self.input_panel.btn_cancel.clicked.connect(self._cancel_fetch)
        self.input_panel.btn_export.clicked.connect(self._start_export)
        self.input_panel.basemap_combo.currentIndexChanged.connect(self._replot_if_data)
        self.input_panel.style_changed.connect(self._replot_if_data)
        self.draw_page.set_apply_handler(self._apply_draw_bbox)
        self.history_page.load_requested.connect(self._load_history_record)
        self.home_page.btn_start_clicked.connect(lambda: self.switchTo(body))
        self.home_page.btn_draw_clicked.connect(lambda: self.switchTo(self.draw_page))
        self._home_targets = {
            "grabPage": body,
            "drawPage": self.draw_page,
            "historyPage": self.history_page,
            "routePage": self.route_page,
            "networkPage": self.network_page,
            "settingsPage": self.settings_page,
        }
        self.home_page.navigate_requested.connect(self._on_home_navigate)
        self.settings_page.language_changed.connect(self._on_language)
        self.settings_page.theme_changed.connect(self._on_theme)
        self.settings_page.pet_toggled.connect(
            lambda visible: self.home_page.set_pet_visible(visible)
        )
        # 慢速原因悬浮提示
        self.input_panel.btn_fetch.setToolTip(SLOW_TOOLTIP)
        self.input_panel.btn_export.setToolTip(SLOW_TOOLTIP)
        self.status_label.setToolTip(SLOW_TOOLTIP)
        self.indet_bar.setToolTip(SLOW_TOOLTIP)

        self.canvas.show_message(tr("status.wait_data"))

        # 启动即开始网络探测，结果同步到主页「网络状态」卡
        self.home_page.set_net_checking()
        self.network_page.start_probe()
        if self.network_page._worker is not None:
            self.network_page._worker.finished_all.connect(
                lambda: self.home_page.set_net_results(self.network_page.last_results)
            )

        self._center_on_screen()

        # 启动 2.5s 后后台检查更新（内置默认地址，网络不通时静默记录到主页卡片）
        self._update_checker = _UpdateChecker(self)
        self._update_checker.result.connect(self._on_update_result)
        self.home_page.update_check_requested.connect(self._update_checker.start)
        QTimer.singleShot(2500, self._check_update)

    def _check_update(self) -> None:
        self._update_checker.start()

    def _on_update_result(self, status) -> None:
        from app.core.updater import UpdateStatus

        if not isinstance(status, UpdateStatus):
            return
        self.home_page.show_update_status(status)
        if not (status.connected and status.latest):
            return
        from app.core import updater

        if updater.is_older(status.latest):
            self._show_dev_build_notice()
            return
        if not updater.is_newer(status.latest):
            return
        self._notify_new_release(status)

    def _notify_new_release(self, status) -> None:
        """发现新版本：系统通知 + 主页可关闭警告横幅（每次启动默认显示）。"""
        import webbrowser

        from qfluentwidgets import InfoBar, InfoBarPosition, PushButton

        from app.services.notify import notify_system

        if not getattr(self, "_update_toast_sent", False):
            self._update_toast_sent = True
            notify_system(
                tr("update.new", v=status.latest),
                tr("update.toast", url=status.url),
            )
        if getattr(self, "_update_banner", None) is not None:
            return
        bar = InfoBar.warning(
            title=tr("update.new", v=status.latest),
            content=tr("update.banner_content"),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            duration=-1,  # 不自动消失，用户手动关闭；下次启动重新出现
            position=InfoBarPosition.TOP,
            parent=self.home_page,
        )
        btn = PushButton(tr("update.go"))
        btn.clicked.connect(lambda: webbrowser.open(status.url))
        bar.addWidget(btn)
        bar.show()
        self._update_banner = bar

    def _show_dev_build_notice(self) -> None:
        """本地版本新于 GitHub 最新发行版：弹未发行版本警告（每次启动一次）。"""
        if getattr(self, "_dev_notice_shown", False):
            return
        self._dev_notice_shown = True
        box = MessageBox(tr("update.dev.title"), tr("update.dev.content"), self)
        box.yesButton.setText(tr("update.dev.go"))
        box.cancelButton.setText(tr("update.dev.ok"))
        if box.exec():
            import webbrowser

            from app.core.updater import RELEASES_PAGE

            webbrowser.open(RELEASES_PAGE)
            self._force_quit = True  # 绕过退出确认
            self.close()

    def _on_home_navigate(self, route_key: str) -> None:
        """主页磁贴 / 卡片按钮跳转。"""
        target = self._home_targets.get(route_key)
        if target is not None:
            self.switchTo(target)

    def _center_on_screen(self) -> None:
        """每次启动把窗口放到（鼠标所在）屏幕的中心。"""

        from PySide6.QtGui import QCursor, QGuiApplication

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = self.frameGeometry()
        geo.moveCenter(screen.availableGeometry().center())
        self.move(geo.topLeft())

    def closeEvent(self, event) -> None:  # noqa: N802
        """关闭前挽留确认（未发行版引导下载等场景直接放行）。"""
        if getattr(self, "_force_quit", False):
            event.accept()
            return
        box = MessageBox(tr("exit.title"), tr("exit.content"), self)
        box.yesButton.setText(tr("exit.quit"))
        box.cancelButton.setText(tr("exit.cancel"))
        if box.exec():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------ 拖拽导入

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        from pathlib import Path as _P

        from app.core import importer

        if any(importer.is_supported(_P(u.toLocalFile()))
               for u in event.mimeData().urls()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        from pathlib import Path as _P

        from app.core import importer

        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            path = _P(f)
            if importer.is_supported(path):
                self._import_dropped(path)
                event.acceptProposedAction()
                return  # 一次只导第一个支持的文件
        super().dropEvent(event)

    def _import_dropped(self, path) -> None:
        from app.core import importer

        try:
            layers = importer.load(path)
        except Exception as exc:  # noqa: BLE001
            self._toast(tr("drop.failed", msg=str(exc)), error=True)
            return
        self._layers = layers
        counts = "，".join(f"{ly.label} {len(g)}" for ly, g in layers.items())
        self._set_busy(False, tr("drop.ok", name=path.name, counts=counts))
        self._toast(tr("drop.ok", name=path.name, counts=counts))
        self.input_panel.btn_export.setEnabled(True)
        self.home_page.set_last_fetch(tr("drop.ok", name=path.name, counts=counts))
        self._replot_if_data()

    # ------------------------------------------------------------------ 语言

    def _on_language(self, lang: str) -> None:
        i18n.set_language(lang)
        self.setWindowTitle(tr("app.title"))
        self.status_label.setText(tr("status.ready"))
        for route_key, key in self._nav_keys.items():
            item = self.navigationInterface.widget(route_key)
            if item is not None and hasattr(item, "setText"):
                item.setText(tr(key))
        settings_item = self.navigationInterface.widget("settingsPage")
        if settings_item is not None and hasattr(settings_item, "setText"):
            settings_item.setText(tr("nav.settings"))
        self.home_page.retranslate_ui()
        self.input_panel.retranslate_ui()
        self.draw_page.retranslate_ui()
        self.route_page.retranslate_ui()
        self.network_page.retranslate_ui()
        self.history_page.retranslate_ui()
        self.log_page.retranslate_ui()
        self.settings_page.retranslate_ui()

    def _on_theme(self, theme: str) -> None:
        from qfluentwidgets import setTheme

        from app.ui.theme import _THEMES

        setTheme(_THEMES.get(theme, _THEMES["auto"]))
        self.draw_page.refresh_theme()
        self.home_page.pet_area.restyle()

    # ------------------------------------------------------------------ 状态栏

    def _set_status(self, text: str) -> None:
        """状态栏文本：超长时省略显示（完整内容放悬浮提示），防止窗口被拉伸。"""

        from PySide6.QtGui import QFontMetrics

        metrics = QFontMetrics(self.status_label.font())
        self.status_label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, 800))
        self.status_label.setToolTip(text)

    def _show_determinate(self, percent: float) -> None:
        self.indet_bar.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(max(0, min(100, int(percent))))

    def _show_indeterminate(self) -> None:
        self.progress_bar.setVisible(False)
        self.indet_bar.setVisible(True)

    def _hide_progress(self) -> None:
        self.progress_bar.setVisible(False)
        self.indet_bar.setVisible(False)

    def _set_busy(self, busy: bool, status: str) -> None:
        """抓取/导出等大操作的按钮锁与进度收尾。"""

        self._busy = busy
        self.input_panel.btn_fetch.setEnabled(not busy)
        self.input_panel.btn_cancel.setEnabled(busy)
        if not busy:
            self._hide_progress()
        self._set_status(status)

    # ------------------------------------------------------------------ 选区应用

    def _apply_draw_bbox(self, bbox: tuple[float, float, float, float]) -> None:
        """选区地图「应用选区」：写入抓取面板并跳转。"""
        self.input_panel.set_bbox(bbox)
        grab = self.findChild(QWidget, "grabPage")
        if grab is not None:
            self.switchTo(grab)
        self._set_status(f"已应用选区：{bbox[0]:.5f}, {bbox[1]:.5f}, {bbox[2]:.5f}, {bbox[3]:.5f}")

    def _load_history_record(self, record_id: str) -> None:
        """历史页「填入面板」：回填参数并跳转到抓取页。"""
        rec = history.find(record_id)
        if rec is None:
            return
        self.input_panel.apply_record(rec)
        grab = self.findChild(QWidget, "grabPage")
        if grab is not None:
            self.switchTo(grab)
        self._set_status(f"已载入历史参数：{rec.area}")
        self._replot_if_data()

    # ------------------------------------------------------------------ 抓取

    def _start_fetch(self) -> None:
        query, bbox = self.input_panel.query_or_bbox()
        if query is None and bbox is None:
            self._toast(tr("grab.query_ph"), error=True)
            return
        if not self.input_panel.enabled_layers():
            self._toast("请至少勾选一个图层", error=True)
            return

        # 地名模式：后台线程解析候选（Nominatim 可能超时 20s，绝不能卡 GUI），
        # 拿到候选后再弹消歧义框 / 启动抓取
        if query is not None:
            self._set_busy(True, "正在解析地名…")
            self._show_indeterminate()
            self.loading_overlay.show_with("正在解析地名…")
            self._geo_worker = GeocodeWorker(query, self)
            self._geo_worker.results.connect(self._on_geocoded)
            self._geo_worker.failed.connect(self._on_geocode_failed)
            self._geo_worker.start()
            return

        self._launch_fetch(None, bbox, None)

    def _on_geocoded(self, candidates: list[GeoArea]) -> None:
        query = self._geo_worker.query
        self.loading_overlay.hide()
        self._set_busy(False, tr("status.ready"))
        if getattr(self._geo_worker, "cancelled", False):
            self._set_status(tr("status.ready"))
            return

        if len(candidates) > 1:
            from app.ui.candidate_dialog import CandidateDialog

            dialog = CandidateDialog(candidates, self)
            if not dialog.exec():
                self._set_status(tr("status.ready"))
                return
            resolved = dialog.selected
            self._set_status(f"已选择：{resolved.display_name}")
        else:
            resolved = candidates[0]
        self._launch_fetch(query, resolved.bbox, resolved)

    def _on_geocode_failed(self, message: str) -> None:
        self.loading_overlay.hide()
        self._set_busy(False, f"抓取失败：{message}")
        if not getattr(self._geo_worker, "cancelled", False):
            self._toast(message, error=True)

    def _launch_fetch(
        self, query: str | None, bbox: tuple | None, resolved: GeoArea | None
    ) -> None:
        """真正启动抓取流水线（地名解析已完成或直接坐标模式）。"""

        fetch_job = FetchJob(
            layers=self.input_panel.layer_specs(),
            max_area_km2=SETTINGS.max_area_km2,
            split_cell_km=SETTINGS.split_cell_km,
        )
        # 快照请求参数，供抓取成功后写入历史
        self._pending_request = {
            "query": query,
            "bbox": list(bbox) if bbox else None,
            "layers": [ly.value for ly in self.input_panel.enabled_layers()],
            "styles": self.input_panel._collect_style(),
        }
        self._fetch_worker = FetchWorker(query, bbox, fetch_job, self, resolved=resolved)
        self._fetch_worker.progress.connect(self._on_progress)
        self._fetch_worker.finished_ok.connect(self._on_fetched)
        self._fetch_worker.failed.connect(self._on_fetch_failed)
        self._fetch_worker.start()

        self._set_busy(True, "正在解析范围…")
        self._show_indeterminate()
        self.loading_overlay.show_with("正在抓取地理数据…")

    def _cancel_fetch(self) -> None:
        if self._geo_worker is not None and self._geo_worker.isRunning():
            self._geo_worker.cancelled = True  # 线程无法强杀，结果回来后丢弃
            self._set_status("正在取消…")
            return
        if self._fetch_worker:
            self._fetch_worker.token.cancel()
            self._set_status("正在取消…")

    def _on_progress(self, fraction: float, message: str) -> None:
        self._show_determinate(fraction)
        self._set_status(message)

    def _on_fetched(self, result: PipelineResult) -> None:
        self.loading_overlay.hide()
        self._layers = result.layers
        counts = "，".join(f"{ly.label} {len(g)}" for ly, g in result.layers.items() if len(g))
        self._set_busy(False, f"抓取完成：{result.message}（{counts or '无数据'}）")
        self._toast(f"抓取完成：{counts or '无数据'}\n🐾 {cat_line()}")
        self.input_panel.btn_export.setEnabled(True)
        self.home_page.set_last_fetch(f"{result.message}（{counts or '无数据'}）")
        self.home_page.refresh_stats()
        self._write_history(result)
        self._replot_if_data()

    def _write_history(self, result: PipelineResult) -> None:
        """抓取成功后写入历史记录并刷新历史页。"""
        req = getattr(self, "_pending_request", None)
        if not req:
            return
        try:
            history.add(
                area=result.message,
                query=req["query"],
                bbox=req["bbox"],
                layers=req["layers"],
                styles=req["styles"],
                counts={ly.value: len(g) for ly, g in result.layers.items()},
            )
            self.history_page.refresh()
        except Exception:  # noqa: BLE001 - 历史写入失败不影响主流程
            pass

    def _on_fetch_failed(self, message: str) -> None:
        try:
            self.loading_overlay.hide()
        finally:
            # 无论遮罩隐藏是否抛异常，都必须复位按钮与状态栏
            self._set_busy(False, f"抓取失败：{message}")
        self._toast(f"抓取失败：{message}", error=True)

    # ------------------------------------------------------------------ 预览与底图

    def _replot_if_data(self) -> None:
        """按当前参数重绘预览；有底图时先后台抓瓦片。"""

        if not self._layers or self._busy:
            return
        specs = self.input_panel.layer_specs()
        basemap = self.input_panel.basemap()
        bbox = self.canvas._layers_bbox(self._layers)
        if bbox is None:
            self.canvas.show_message("所选图层没有数据")
            return

        if not basemap:
            self.canvas.plot_layers(self._layers, specs, None, bbox)
            return

        # 后台线程抓瓦片，期间状态栏显示加载中
        self._basemap_gen += 1
        gen = self._basemap_gen
        self._show_indeterminate()
        self.loading_overlay.show_with(f"正在加载底图（{self.input_panel.basemap_combo.currentText()}）…")
        self._set_status(f"正在加载底图（{self.input_panel.basemap_combo.currentText()}）…")

        self._basemap_worker = BasemapWorker(bbox, basemap, self)

        def _done(data, _gen=gen, _specs=specs, _bbox=bbox):
            self._on_basemap_ready(_gen, data, _specs, _bbox)

        self._basemap_worker.result.connect(_done)
        self._basemap_worker.start()

    def _on_basemap_ready(self, gen: int, data, specs, bbox) -> None:
        if gen != self._basemap_gen:
            return  # 已切换到底图或新任务，丢弃过期结果
        self.loading_overlay.hide()
        self._hide_progress()
        self.canvas.plot_layers(self._layers, specs, self.input_panel.basemap(), bbox, basemap_data=data)
        if data is None:
            self._set_status("底图加载失败，仅显示矢量图层")
        else:
            self._set_status("预览就绪（可缩放平移）")

    # ------------------------------------------------------------------ 导出

    def _start_export(self) -> None:
        if not self._layers:
            self._toast("请先抓取数据", error=True)
            return
        formats = self.input_panel.selected_formats()
        if not formats:
            self._toast("请至少勾选一种导出格式", error=True)
            return
        # 合规预检：Esri 卫星影像仅允许软件内预览，禁止导出叠加成品
        # （超大幅面 PNG 走纯矢量分块渲染，不触碰瓦片，故不受限）
        poster_only = self.input_panel.poster() and set(formats) <= {"png"}
        if self.input_panel.basemap() == "esri" and any(f in ("svg", "png") for f in formats) and not poster_only:
            self._toast(
                "Esri 卫星影像仅限软件内实时预览，服务条款不允许导出叠加该底图的成品图；"
                "请改用 OSM 系底图，或取消 SVG/PNG 仅导出矢量格式。",
                error=True,
            )
            return

        export_job = ExportJob(
            out_dir=self.input_panel.out_dir(),
            formats=formats,
            dpi=self.input_panel.dpi(),
            basemap=self.input_panel.basemap(),
            poster=self.input_panel.poster(),
            poster_size=PAPER_SIZES.get(self.input_panel.paper()),
        )
        self._export_worker = ExportWorker(
            self._layers, self.canvas._layers_bbox(self._layers), self.input_panel.layer_specs(), export_job, self
        )
        self._export_worker.progress.connect(self._on_progress)
        self._export_worker.finished_ok.connect(self._on_exported)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.start()

        self._busy = True
        self.input_panel.btn_export.setEnabled(False)
        self._set_status("正在导出…")
        self._show_indeterminate()
        self.loading_overlay.show_with("正在导出…")

    def _on_exported(self, exported: dict) -> None:
        self.loading_overlay.hide()
        self._busy = False
        self._hide_progress()
        self._set_status("导出完成")
        lines = "<br>".join(f"[{fmt}] {path}" for fmt, path in exported.items())
        self._toast(f"导出完成：<br>{lines}<br>🐾 {cat_line()}")
        self.input_panel.btn_export.setEnabled(True)

    def _on_export_failed(self, message: str) -> None:
        self.loading_overlay.hide()
        self._busy = False
        self._hide_progress()
        self._set_status(f"导出失败：{message}")
        self._toast(f"导出失败：{message}", error=True)
        self.input_panel.btn_export.setEnabled(True)

    # ------------------------------------------------------------------ 杂项

    def _toast(self, message: str, error: bool = False) -> None:
        """优先弹 Windows 系统通知；系统通知不可用（旧系统/异常）时回退应用内提示。"""

        title = "错误" if error else "提示"
        if len(message) > 160:  # 超长报错只显示摘要，完整内容在状态栏悬浮提示与日志页
            message = message[:160] + "…"
        try:
            if notify_system(title, message):
                return
        except Exception:  # noqa: BLE001 - 通知失败绝不影响主流程
            pass
        try:
            (InfoBar.error if error else InfoBar.success)(
                title=title,
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
        except Exception:  # noqa: BLE001 - 兜底：提示失败只写状态栏
            self._set_status(f"{title}：{message}")
