"""选区地图页：本地世界底图（Natural Earth，零网络请求）+ 多工具选区编辑。

工具（本页工具栏，选中态高亮）：
- 移动：左键拖动平移 + 滚轮缩放（复用 matplotlib 工具条）
- 画笔：左键自由绘制，松开闭合
- 矩形 / 圆形：左键拖动成形
- 多边形：单击加点，双击或回车闭合，Esc 取消

选区模式：新建 / 叠加（并集） / 减去（差集），基于 shapely 运算。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    PushButton,
    StrongBodyLabel,
    ToolButton,
    isDarkTheme,
)
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from app.core.i18n import tr
from app.core.worldmap import draw_world
from app.ui.preview.map_canvas import MapCanvas

_LON_LIMIT = (-180.0, 180.0)
_LAT_LIMIT = (-85.0, 85.0)
_ZOOM_STEP = 1.25
_MAX_BRUSH_POINTS = 4000
_CIRCLE_SEGMENTS = 64
_SEL_COLOR = "#0078D4"

_TOOL_KEYS = ("move", "brush", "rect", "circle", "poly")
_MODE_KEYS = ("new", "union", "subtract")


def _shape_icon(kind: str) -> QIcon:
    """自绘形状图标（矩形 / 圆形 / 多边形），文字颜色随主题。"""
    size = 22
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QGuiApplication.palette().color(QPalette.ColorRole.Text), 1.7))
    m = 3.5
    inner = size - 2 * m
    if kind == "rect":
        p.drawRect(QRectF(m, m + 2, inner, inner - 4))
    elif kind == "circle":
        p.drawEllipse(QRectF(m, m, inner, inner))
    else:  # poly：五边形
        import math

        cx = cy = size / 2
        r = inner / 2
        pts = [
            QPointF(cx + r * math.cos(-math.pi / 2 + i * 2 * math.pi / 5),
                      cy + r * math.sin(-math.pi / 2 + i * 2 * math.pi / 5))
            for i in range(5)
        ]
        p.drawPolygon(QPolygonF(pts))
    p.end()
    return QIcon(pm)


def _clamp_lon(x: float) -> float:
    return min(max(x, _LON_LIMIT[0]), _LON_LIMIT[1])


def _clamp_lat(y: float) -> float:
    return min(max(y, _LAT_LIMIT[0]), _LAT_LIMIT[1])


def _valid_polygon(coords: list[tuple[float, float]]) -> Polygon | None:
    if len(coords) < 3:
        return None
    poly = Polygon(coords)
    if not poly.is_valid:
        poly = poly.buffer(0)  # 自交画笔等 → 修复为有效几何
    if poly.is_empty or poly.area <= 0:
        return None
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly if isinstance(poly, Polygon) else None


class DrawPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drawPage")
        self.setStyleSheet("background: transparent;")

        self._geom: Polygon | MultiPolygon | None = None  # shapely 选区（4326）
        self._tool = "brush"
        self._apply_handler = None

        # 交互状态
        self._brush: list[tuple[float, float]] = []
        self._poly_pts: list[tuple[float, float]] = []
        self._drag_start: tuple[float, float] | None = None

        # 预览图元（提交或取消后清除）
        self._preview_artists: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        # ---- 顶栏：标题 + 提示 ----
        top = QHBoxLayout()
        self.title_label = StrongBodyLabel("")
        self.hint_label = CaptionLabel("")
        self.hint_label.setWordWrap(True)
        top.addWidget(self.title_label)
        top.addStretch(1)
        top.addWidget(self.hint_label)
        layout.addLayout(top)

        # ---- 工具栏（图标按钮，选中高亮） ----
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.tool_buttons: dict[str, ToolButton] = {}
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        tool_icons = {
            "move": FIF.MOVE,
            "brush": FIF.BRUSH,
            "rect": _shape_icon("rect"),
            "circle": _shape_icon("circle"),
            "poly": _shape_icon("poly"),
        }
        for key in _TOOL_KEYS:
            btn = ToolButton(tool_icons[key])
            btn.setCheckable(True)
            btn.setChecked(key == self._tool)
            btn.setFixedSize(36, 32)
            btn.clicked.connect(lambda _=False, k=key: self._select_tool(k))
            self._tool_group.addButton(btn)
            self.tool_buttons[key] = btn
            bar.addWidget(btn)
        bar.addSpacing(10)
        self.mode_label = CaptionLabel("")
        self.mode_combo = ComboBox()
        for key in _MODE_KEYS:
            self.mode_combo.addItem("", userData=key)
        bar.addWidget(self.mode_label)
        bar.addWidget(self.mode_combo)
        bar.addStretch(1)
        layout.addLayout(bar)

        # ---- 画布（隐藏 matplotlib 工具条，本页自带工具） ----
        self.canvas = MapCanvas()
        mpl_toolbar = self.canvas.make_toolbar(self)
        mpl_toolbar.setVisible(False)  # 交互全部由本页接管，但 pan 模式仍借用它实现
        layout.addWidget(self.canvas, stretch=1)

        # ---- 底栏 ----
        bottom = QHBoxLayout()
        self.selected_label = CaptionLabel("")
        self.btn_clear = PushButton("")
        self.btn_apply = PushButton("")
        self.btn_apply.setEnabled(False)
        self.btn_clear.clicked.connect(lambda _=False: self.clear_selection())
        self.btn_apply.clicked.connect(self._apply)
        bottom.addWidget(self.selected_label, stretch=1)
        bottom.addWidget(self.btn_clear)
        bottom.addWidget(self.btn_apply)
        layout.addLayout(bottom)

        # ---- 事件 ----
        self.canvas.mpl_connect("scroll_event", self._on_wheel)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("key_press_event", self._on_key)

        self.retranslate_ui()
        self._redraw()

    # ------------------------------------------------------------------ i18n / 工具

    def refresh_theme(self) -> None:
        """主题切换后重绘底图与选区配色。"""
        self._redraw()

    def retranslate_ui(self) -> None:
        self.title_label.setText(tr("draw.title"))
        self._update_hint()
        for key, btn in self.tool_buttons.items():
            btn.setToolTip(tr(f"draw.tool_{key}"))
        self.mode_label.setText(tr("draw.mode"))
        for key in _MODE_KEYS:
            idx = self.mode_combo.findData(key)
            if idx >= 0:
                self.mode_combo.setItemText(idx, tr(f"draw.mode_{key}"))
        self.btn_clear.setText(tr("draw.btn_clear"))
        self.btn_apply.setText(tr("draw.btn_apply"))
        self._refresh_selected_label()

    def _select_tool(self, key: str) -> None:
        self._tool = key
        self.tool_buttons[key].setChecked(True)
        tb = self.canvas._toolbar
        if key == "move":
            if tb is not None:
                self._deactivate_toolbar_modes(tb)
                if not tb.mode:
                    tb.pan()
        else:
            if tb is not None:
                self._deactivate_toolbar_modes(tb)
            self._cancel_in_progress()
        self._update_hint()

    @staticmethod
    def _deactivate_toolbar_modes(tb) -> None:
        """matplotlib 3.9+ 的 mode 是枚举（NONE/PAN/ZOOM），逐一关闭激活模式。"""

        for _ in range(2):  # 最多关两个（理论上同时只有一个）
            mode = str(tb.mode).upper()
            if "ZOOM" in mode:
                tb.zoom()
            elif "PAN" in mode:
                tb.pan()
            else:
                break

    def _update_hint(self) -> None:
        if self._tool == "move":
            text = tr("draw.hint_move")
        elif self._tool == "poly":
            n = len(self._poly_pts)
            text = tr("draw.hint_poly") if not n else tr("draw.poly_points", n=n)
        else:
            text = tr("draw.hint_draw")
        self.hint_label.setText(text)

    def _toolbar_busy(self) -> bool:
        tb = self.canvas._toolbar
        return tb is not None and bool(tb.mode) and self._tool != "move"

    # ------------------------------------------------------------------ 绘制

    def _redraw(self) -> None:
        ax = self.canvas.ax
        # 保留当前视野：完成圈选/清除后不再跳回全球视图
        if getattr(self, "_has_drawn", False):
            prev_xlim, prev_ylim = ax.get_xlim(), ax.get_ylim()
        else:
            prev_xlim = prev_ylim = None
        ax.clear()
        ax.set_axis_off()
        draw_world(ax, dark=isDarkTheme())
        if prev_xlim is not None:
            ax.set_xlim(*prev_xlim)
            ax.set_ylim(*prev_ylim)
        self._preview_artists = []
        if self._geom is not None and not self._geom.is_empty:
            self._paint_selection()
        self._has_drawn = True
        self.canvas.fig.tight_layout()
        self.canvas.draw_idle()

    def _paint_selection(self) -> None:
        # 用 geopandas 渲染：matplotlib 原生 Patch 不支持多边形内环（洞），
        # geopandas 的 Path 转换能正确画出「减去」后形成的中空区域
        import geopandas as gpd

        gpd.GeoSeries([self._geom], crs="EPSG:4326").plot(
            ax=self.canvas.ax,
            facecolor=_SEL_COLOR,
            alpha=0.20,
            edgecolor=_SEL_COLOR,
            linewidth=1.6,
            zorder=6,
        )

    # ------------------------------------------------------------------ 选区运算

    def _commit_shape(self, geom) -> None:
        if geom is None or geom.is_empty:
            return
        mode = self.mode_combo.currentData() or "new"
        if mode == "new" or self._geom is None or self._geom.is_empty:
            self._geom = geom
        elif mode == "union":
            merged = unary_union([self._geom, geom]).buffer(0)
            self._geom = merged
        else:  # subtract
            diff = self._geom.difference(geom).buffer(0)
            self._geom = None if diff.is_empty else diff
        self._cancel_in_progress()
        self._redraw()
        self._refresh_selected_label()
        has = self._geom is not None and not self._geom.is_empty
        self.btn_apply.setEnabled(has)

    def clear_selection(self) -> None:
        self._geom = None
        self._cancel_in_progress()
        self.btn_apply.setEnabled(False)
        self._redraw()
        self._refresh_selected_label()

    def _cancel_in_progress(self) -> None:
        self._brush = []
        self._poly_pts = []
        self._drag_start = None
        for artist in self._preview_artists:
            try:
                artist.remove()
            except Exception:  # noqa: BLE001
                pass
        self._preview_artists = []
        self._update_hint()

    def _refresh_selected_label(self) -> None:
        if self._geom is None or self._geom.is_empty:
            self.selected_label.setText(tr("draw.selected") + "：" + tr("draw.none"))
            return
        minx, miny, maxx, maxy = self._geom.bounds
        self.selected_label.setText(
            f"{tr('draw.selected')}：{tr('draw.s')} {miny:.5f}  {tr('draw.w')} {minx:.5f}  "
            f"{tr('draw.n')} {maxy:.5f}  {tr('draw.e')} {maxx:.5f}"
        )

    def set_apply_handler(self, handler) -> None:
        self._apply_handler = handler

    def _apply(self) -> None:
        if self._geom is None or self._geom.is_empty or self._apply_handler is None:
            return
        minx, miny, maxx, maxy = self._geom.bounds
        self._apply_handler((miny, minx, maxy, maxx))

    # ------------------------------------------------------------------ 事件

    def _on_wheel(self, event) -> None:
        if self._toolbar_busy():
            return
        if event.xdata is None:
            return
        ax = self.canvas.ax
        factor = 1.0 / _ZOOM_STEP if event.button == "up" else _ZOOM_STEP
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        cx, cy = event.xdata, event.ydata
        ax.set_xlim(cx - (cx - x0) * factor, cx + (x1 - cx) * factor)
        ax.set_ylim(cy - (cy - y0) * factor, cy + (y1 - cy) * factor)
        self.canvas.draw_idle()

    def _on_press(self, event) -> None:
        if event.inaxes is None or event.xdata is None:
            return
        if self._toolbar_busy():
            return
        if self._tool == "move":
            return  # 平移/缩放完全交给 matplotlib 工具条，避免双重位移
        if event.button != 1:
            return
        x, y = _clamp_lon(event.xdata), _clamp_lat(event.ydata)
        if self._tool == "brush":
            self._brush = [(x, y)]
        elif self._tool in ("rect", "circle"):
            self._drag_start = (x, y)
        elif self._tool == "poly":
            if getattr(event, "dblclick", False):
                self._finish_poly()
            else:
                self._poly_pts.append((x, y))
                self._update_hint()

    def _on_motion(self, event) -> None:
        if event.inaxes is None or event.xdata is None:
            return
        if self._toolbar_busy():
            return
        ax = self.canvas.ax
        x, y = _clamp_lon(event.xdata), _clamp_lat(event.ydata)
        if self._tool == "brush" and event.button == 1 and self._brush:
            if len(self._brush) < _MAX_BRUSH_POINTS:
                self._brush.append((x, y))
            self._draw_preview_line(self._brush)
        elif self._tool in ("rect", "circle") and event.button == 1 and self._drag_start:
            x0, y0 = self._drag_start
            if self._tool == "rect":
                pts = [(x0, y0), (x, y0), (x, y), (x0, y), (x0, y0)]
                self._draw_preview_line(pts)
            else:
                r = max(abs(x - x0), abs(y - y0))
                if r > 0:
                    import math as _m

                    pts = [
                        (_clamp_lon(x0 + r * _m.cos(t)), _clamp_lat(y0 + r * _m.sin(t)))
                        for t in [i * 2 * _m.pi / _CIRCLE_SEGMENTS for i in range(_CIRCLE_SEGMENTS + 1)]
                    ]
                    self._draw_preview_line(pts)
        elif self._tool == "poly" and self._poly_pts:
            self._draw_preview_line([*self._poly_pts, (x, y)])

    def _on_release(self, event) -> None:
        if self._toolbar_busy():
            return
        if event.button != 1:
            return
        if self._tool == "brush" and self._brush:
            pts = self._brush
            self._brush = []
            if len(pts) >= 5:
                self._commit_shape(_valid_polygon(pts))
            else:
                self._cancel_in_progress()
                self.canvas.draw_idle()
        elif self._tool in ("rect", "circle") and self._drag_start and event.xdata is not None:
            start = self._drag_start
            self._drag_start = None
            x0, y0 = start
            x, y = _clamp_lon(event.xdata), _clamp_lat(event.ydata)
            if self._tool == "rect":
                if abs(x - x0) > 1e-6 and abs(y - y0) > 1e-6:
                    poly = Polygon([
                        (x0, y0), (x, y0), (x, y), (x0, y),
                    ])
                    self._commit_shape(poly if poly.is_valid else poly.buffer(0))
            else:
                r = max(abs(x - x0), abs(y - y0))
                if r > 1e-6:
                    import math as _m

                    pts = [
                        (_clamp_lon(x0 + r * _m.cos(t)), _clamp_lat(y0 + r * _m.sin(t)))
                        for t in [i * 2 * _m.pi / _CIRCLE_SEGMENTS for i in range(_CIRCLE_SEGMENTS)]
                    ]
                    self._commit_shape(_valid_polygon(pts))

    def _on_key(self, event) -> None:
        if self._tool == "poly":
            if event.key == "enter":
                self._finish_poly()
            elif event.key == "escape":
                self._cancel_in_progress()
                self.canvas.draw_idle()

    def _finish_poly(self) -> None:
        pts = self._poly_pts
        if len(pts) >= 3:
            self._commit_shape(_valid_polygon(pts))
        else:
            self._cancel_in_progress()
            self.canvas.draw_idle()

    def _draw_preview_line(self, pts: list[tuple[float, float]]) -> None:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if self._preview_artists:
            artist = self._preview_artists[0]
            artist.set_data(xs, ys)
        else:
            (artist,) = self.canvas.ax.plot(
                xs, ys, color=_SEL_COLOR, linewidth=1.6, zorder=7,
            )
            self._preview_artists.append(artist)
        self.canvas.draw_idle()
