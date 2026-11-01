"""路径规划页：起终点输入 + OSRM 规划 + 独立地图预览（底图 + 路线）。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
)

from app.core.i18n import tr
from app.services.job_manager import BasemapWorker, RouteWorker
from app.services.notify import notify_system
from app.ui.preview.map_canvas import MapCanvas

_PROFILE_IDS = ("car", "bike", "foot")
_PAD = 0.15  # 路线视野外扩比例


class RoutePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("routePage")
        self.setStyleSheet("background: transparent;")

        self._route_worker: RouteWorker | None = None
        self._basemap_worker: BasemapWorker | None = None
        self._route_gdf = None
        self._basemap_gen = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        # ---- 输入行 ----
        top = QHBoxLayout()
        self.title_label = StrongBodyLabel("")
        self.start_edit = LineEdit()
        self.end_edit = LineEdit()
        self.profile_combo = ComboBox()
        self.btn_plan = PrimaryPushButton("")
        self.btn_clear = PushButton("")
        self.btn_plan.clicked.connect(self._start_route)
        self.btn_clear.clicked.connect(self._clear)
        top.addWidget(self.title_label)
        top.addWidget(self.start_edit, stretch=2)
        top.addWidget(self.end_edit, stretch=2)
        top.addWidget(self.profile_combo)
        top.addWidget(self.btn_plan)
        top.addWidget(self.btn_clear)
        layout.addLayout(top)

        # ---- 地图 ----
        self.canvas = MapCanvas()
        layout.addWidget(self.canvas.make_toolbar(self), stretch=0)
        layout.addWidget(self.canvas, stretch=1)

        self.result_label = CaptionLabel("")
        layout.addWidget(self.result_label)

        self.retranslate_ui()
        self.canvas.show_message(tr("draw.none"))

    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        self.title_label.setText(tr("route.title"))
        self.start_edit.setPlaceholderText(tr("route.start_ph"))
        self.end_edit.setPlaceholderText(tr("route.end_ph"))
        current = self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for pid in _PROFILE_IDS:
            self.profile_combo.addItem(tr(f"route.{pid}"), userData=pid)
        if current in _PROFILE_IDS:
            self.profile_combo.setCurrentIndex(_PROFILE_IDS.index(current))
        self.profile_combo.blockSignals(False)
        self.btn_plan.setText(tr("route.plan"))
        self.btn_clear.setText(tr("route.clear"))
        self.btn_plan.setToolTip(
            "公共路径服务为共享资源，速度受服务器负载影响，规划可能需要几秒到几十秒"
            if tr("route.plan") != "Route"
            else "Public routing servers are shared resources; routing may take seconds"
        )

    # ------------------------------------------------------------------

    def _parse(self, edit: LineEdit) -> tuple[float, float] | None:
        parts = [p.strip() for p in edit.text().replace("，", ",").split(",")]
        if len(parts) != 2:
            return None
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            return None
        if not (-180 <= lon <= 180 and -85 <= lat <= 85):
            return None
        return (lon, lat)

    def _start_route(self) -> None:
        start, end = self._parse(self.start_edit), self._parse(self.end_edit)
        if start is None or end is None:
            notify_system("错误" if tr("route.plan") == "规划路径" else "Error", tr("route.bad_coords"))
            return

        self.btn_plan.setEnabled(False)
        self.result_label.setText(tr("route.planning"))
        self._route_worker = RouteWorker(self.profile_combo.currentData(), start, end, self)
        self._route_worker.result.connect(self._on_route)
        self._route_worker.failed.connect(self._on_failed)
        self._route_worker.start()

    def _on_route(self, data: dict) -> None:
        self.btn_plan.setEnabled(True)
        self._route_gdf = data["geometry"]
        mins = data["minutes"]
        time_text = (
            f"{int(mins // 60)} 小时 {int(mins % 60)} 分" if mins >= 60 else f"{mins:.1f} 分钟"
        )
        self.result_label.setText(f"{data['profile_label']} · {data['km']} 公里 · 约 {time_text}")
        notify_system(
            "提示" if tr("route.plan") == "规划路径" else "Info",
            f"{data['profile_label']} · {data['km']} 公里 · 约 {time_text}",
        )
        self._load_view()

    def _on_failed(self, message: str) -> None:
        self.btn_plan.setEnabled(True)
        self.result_label.setText(message)
        notify_system("错误" if tr("route.plan") == "规划路径" else "Error", message)

    def _clear(self) -> None:
        self._route_gdf = None
        self.canvas.clear_route()
        self.result_label.setText("")
        if self._basemap_data_safe() is not None:
            self._plot()

    def _basemap_data_safe(self):
        return getattr(self, "_basemap_data", None)

    def _load_view(self) -> None:
        """按路线范围取底图并绘制。"""
        minx, miny, maxx, maxy = self._route_gdf.total_bounds
        pad_x = (maxx - minx) * _PAD + 0.005
        pad_y = (maxy - miny) * _PAD + 0.005
        bbox = (miny - pad_y, minx - pad_x, maxy + pad_y, maxx + pad_x)
        self._view_bbox = bbox
        self._basemap_gen += 1
        gen = self._basemap_gen
        self._basemap_worker = BasemapWorker(bbox, "osm_de", self)

        def _done(data, _gen=gen):
            if _gen != self._basemap_gen:
                return
            self._basemap_data = data
            self._plot()

        self._basemap_worker.result.connect(_done)
        self._basemap_worker.start()

    def _plot(self) -> None:
        from app.core.export import draw_layers_on_ax

        ax = self.canvas.ax
        ax.clear()
        ax.set_axis_off()
        ax.set_aspect("equal")
        bbox = self._view_bbox
        draw_layers_on_ax(ax, {}, [], bbox, "osm_de", self._basemap_data)
        self.canvas.plot_route(self._route_gdf)
        self.canvas._draw_route()
        self.canvas.fig.tight_layout()
        self.canvas.draw_idle()
