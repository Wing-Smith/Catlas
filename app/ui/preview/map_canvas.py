"""matplotlib Qt 预览画布：抓取完成后叠加显示各图层，支持缩放平移。"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from matplotlib import use as mpl_use

mpl_use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from app.core.export import _setup_fonts, draw_layers_on_ax  # noqa: E402
from app.core.models import BBox, LayerSpec  # noqa: E402

_setup_fonts()


class MapCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(6, 6), tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)
        self._toolbar = None
        self._route_gdf = None  # EPSG:4326 的规划路线，重绘时叠加显示

    def plot_route(self, route_gdf) -> None:
        """设置要在预览上叠加显示的规划路线（EPSG:4326）。"""
        self._route_gdf = route_gdf

    def clear_route(self) -> None:
        self._route_gdf = None
        self._draw_route()

    def _draw_route(self) -> None:
        """按当前 Axes 坐标系把路线画上去（仅重绘 overlay，不动底图）。"""

        if self._route_gdf is None or self._route_gdf.empty:
            return
        gdf = self._route_gdf
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        # Web Mercator 坐标范围远大于经纬度，据此判断当前投影
        if abs(xlim[1]) > 1000 or abs(ylim[1]) > 1000:
            gdf = gdf.to_crs("EPSG:3857")
        else:
            try:
                gdf = gdf.to_crs(gdf.estimate_utm_crs())
            except Exception:
                pass
        gdf.plot(ax=self.ax, color="#0078D4", linewidth=2.2, zorder=5, solid_capstyle="round")
        self.draw_idle()

    def make_toolbar(self, parent) -> NavigationToolbar2QT:
        if self._toolbar is None:
            self._toolbar = NavigationToolbar2QT(self, parent)
        return self._toolbar

    def show_message(self, text: str) -> None:
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=12, color="#888888")
        self.draw_idle()

    @staticmethod
    def _layers_bbox(layers: dict) -> BBox | None:
        non_empty = [g for g in layers.values() if len(g)]
        if not non_empty:
            return None
        combined = gpd.GeoDataFrame(
            pd.concat(non_empty, ignore_index=True), geometry="geometry", crs="EPSG:4326"
        )
        minx, miny, maxx, maxy = combined.total_bounds
        return (float(miny), float(minx), float(maxy), float(maxx))

    def plot_layers(
        self,
        layers: dict,
        specs: list[LayerSpec],
        basemap: str | None = None,
        bbox: BBox | None = None,
        basemap_data: tuple | None = None,
    ) -> None:
        bbox = bbox or self._layers_bbox(layers)
        if bbox is None:
            self.show_message("所选图层没有数据")
            return
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_aspect("equal")
        draw_layers_on_ax(self.ax, layers, specs, bbox, basemap, basemap_data)
        self._draw_route()
        self.fig.tight_layout()
        self.draw_idle()
