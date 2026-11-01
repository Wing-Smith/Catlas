"""统一导出面：GeoJSON / GeoPackage / Shapefile / SVG / PNG。

- 矢量格式走 geopandas（pyogrio 引擎）；
- SVG / PNG 用 matplotlib 的 Agg Canvas 直接渲染，不依赖全局 backend，
  因此不会与 GUI 的 QtAgg 预览冲突；
- 绘制逻辑抽成 draw_map()，GUI 预览复用同一套渲染。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from matplotlib import rcParams

from app.core.errors import ExportError
from app.core.models import BBox, LayerSpec, LayerType

logger = logging.getLogger(__name__)

VECTOR_FORMATS = ("geojson", "gpkg", "shp")

_FONTS_READY = False


def _setup_fonts() -> None:
    """图例中文显示：优先微软雅黑/黑体。"""

    global _FONTS_READY
    if _FONTS_READY:
        return
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "sans-serif"]
    rcParams["axes.unicode_minus"] = False
    _FONTS_READY = True


def _ensure_dir(out_dir: str | Path) -> Path:
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slim(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """导出用精简列，避免标签杂项撑爆 Shapefile。"""

    keep = [c for c in ("name", "fclass", "osm_type", "osm_id") if c in gdf.columns]
    return gdf[keep + ["geometry"]]


def project_layers(
    layers: dict[LayerType, gpd.GeoDataFrame],
    specs: list[LayerSpec],
    target_crs: str | None = None,
) -> dict[LayerType, gpd.GeoDataFrame]:
    """投影图层；target_crs 缺省用本地 UTM，失败退回经纬度。返回仅含启用且有数据的图层。"""

    enabled = [sp for sp in specs if sp.enabled and sp.layer in layers and len(layers[sp.layer])]
    if not enabled:
        return {}
    combined = gpd.GeoDataFrame(
        pd.concat([layers[sp.layer] for sp in enabled], ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    try:
        crs = target_crs or combined.estimate_utm_crs()
        return {sp.layer: layers[sp.layer].to_crs(crs) for sp in enabled}
    except Exception:
        logger.warning("投影估算失败，退回经纬度坐标渲染")
        return {sp.layer: layers[sp.layer] for sp in enabled}


def draw_map(ax, layers: dict[LayerType, gpd.GeoDataFrame], specs: list[LayerSpec], legend: bool = True) -> None:
    """把启用图层画到 matplotlib Axes 上（投影后的图层）。"""

    _setup_fonts()
    from matplotlib.colors import to_rgba
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    enabled = [sp for sp in specs if sp.enabled and sp.layer in layers and len(layers[sp.layer])]
    handles = []
    for sp in sorted(enabled, key=lambda x: x.layer.zorder):
        gdf = layers[sp.layer]
        color = sp.effective_color
        alpha = max(0.05, min(1.0, sp.alpha))
        if sp.layer is LayerType.ROAD:
            gdf.plot(ax=ax, color=color, linewidth=0.6 * max(0.2, sp.linewidth), zorder=sp.layer.zorder)
            handles.append(Line2D([0], [0], color=color, lw=2, label=sp.layer.label))
        else:
            gdf.plot(
                ax=ax,
                facecolor=to_rgba(color, alpha),
                edgecolor=to_rgba("#666666", min(1.0, alpha + 0.15)),
                linewidth=0.15 * max(0.5, sp.linewidth),
                zorder=sp.layer.zorder,
            )
            handles.append(Patch(facecolor=color, edgecolor="#666666", label=sp.layer.label))
    if legend:
        ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.8)


# ------------------------------------------------------------ 矢量导出


def export_geojson(layers: dict[LayerType, gpd.GeoDataFrame], out_dir: str | Path, merged: bool = True) -> str:
    out = _ensure_dir(out_dir)
    enabled = {k: v for k, v in layers.items() if not v.empty}
    if not enabled:
        raise ExportError("没有可导出的数据")
    merged_path = out / "all_layers.geojson"
    if merged:
        parts = []
        for layer, gdf in enabled.items():
            g = _slim(gdf).copy()
            g["layer"] = layer.value
            parts.append(g)
        combined = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs="EPSG:4326")
        combined.to_file(merged_path, driver="GeoJSON", engine="pyogrio")
    for layer, gdf in enabled.items():
        _slim(gdf).to_file(out / f"{layer.value}.geojson", driver="GeoJSON", engine="pyogrio")
    return str(merged_path)


def export_gpkg(layers: dict[LayerType, gpd.GeoDataFrame], out_dir: str | Path) -> str:
    out = _ensure_dir(out_dir)
    path = out / "osm_data.gpkg"
    for layer, gdf in layers.items():
        if gdf.empty:
            continue
        _slim(gdf).to_file(path, layer=layer.value, driver="GPKG", engine="pyogrio")
    return str(path)


def _shp_safe_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Shapefile 兼容：字段名 ≤10 字符、无非法字符。"""

    g = _slim(gdf).copy()
    rename = {}
    for col in g.columns:
        if col == "geometry":
            continue
        safe = re.sub(r"[^A-Za-z0-9_]", "_", col)[:10]
        rename[col] = safe or "field"
    return g.rename(columns=rename)


def export_shp(layers: dict[LayerType, gpd.GeoDataFrame], out_dir: str | Path) -> str:
    base = _ensure_dir(out_dir) / "shapefile"
    base.mkdir(exist_ok=True)
    for layer, gdf in layers.items():
        if gdf.empty:
            continue
        # 混合 LineString/Polygon 会让 Shapefile 写出失败，按类型拆分
        lines = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])]
        polys = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(polys):
            _shp_safe_columns(polys).to_file(base / f"{layer.value}_poly.shp", driver="ESRI Shapefile", engine="pyogrio")
        if len(lines):
            _shp_safe_columns(lines).to_file(base / f"{layer.value}_line.shp", driver="ESRI Shapefile", engine="pyogrio")
    return str(base)


# ------------------------------------------------------------ 制图渲染


def _figsize_for(bbox: BBox, figsize_in: tuple[float, float] | None) -> tuple[float, float]:
    if figsize_in:
        return figsize_in
    s, w, n, e = bbox
    ratio = max((e - w) / max(n - s, 1e-9), 1e-9)
    if ratio >= 1:
        return (10.0, 10.0 / ratio)
    return (10.0 * ratio, 10.0)


def draw_layers_on_ax(
    ax,
    layers: dict[LayerType, gpd.GeoDataFrame],
    specs: list[LayerSpec],
    bbox: BBox,
    basemap: str | None = None,
    basemap_data: tuple | None = None,
    pad: float = 0.02,
    legend: bool = True,
) -> None:
    """把底图（可选）+ 矢量图层画到指定 Axes；坐标系统一为 Web Mercator（有底图）或 UTM。

    basemap_data 允许调用方在别的线程预先 compose 好的 (image, extent)，
    避免在 GUI 线程里联网抓瓦片。
    """

    if basemap:
        from app.core import tiles

        result = basemap_data if basemap_data is not None else tiles.compose_basemap(bbox, basemap)
        if result is not None:
            image, extent = result
            ax.imshow(image, extent=extent, zorder=0, interpolation="bilinear")
            projected = project_layers(layers, specs, target_crs="EPSG:3857")
        else:
            logger.warning("底图抓取失败，仅绘制矢量图层")
            projected = project_layers(layers, specs)
    else:
        projected = project_layers(layers, specs)

    if projected:
        draw_map(ax, projected, specs, legend=legend)

    if basemap:
        left, right, bottom, top = tiles.bbox_mercator_extent(bbox)
        ax.set_xlim(left, right)
        ax.set_ylim(bottom, top)
    elif projected:
        combined = gpd.GeoDataFrame(
            pd.concat(list(projected.values()), ignore_index=True),
            geometry="geometry",
            crs=list(projected.values())[0].crs,
        )
        minx, miny, maxx, maxy = combined.total_bounds
        pad_x = (maxx - minx) * pad
        pad_y = (maxy - miny) * pad
        ax.set_xlim(minx - pad_x, maxx + pad_x)
        ax.set_ylim(miny - pad_y, maxy + pad_y)


def render_map(
    layers: dict[LayerType, gpd.GeoDataFrame],
    bbox: BBox,
    specs: list[LayerSpec],
    out_path: str | Path,
    dpi: int = 300,
    figsize_in: tuple[float, float] | None = None,
    basemap: str | None = None,
) -> str:
    """把启用的图层渲染为 SVG 或 PNG（按扩展名决定）。"""

    # 合规约束：Esri 卫星影像服务条款仅允许软件内实时浏览预览，
    # 禁止将叠加该底图的成品图导出 / 分发，因此在导出环节硬拦截。
    if basemap == "esri":
        raise ExportError(
            "Esri 卫星影像仅限软件内实时预览（用于位置对齐），"
            "服务条款不允许导出叠加该底图的成品图。请改用 OSM 系底图后导出。"
        )

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    _setup_fonts()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig = Figure(figsize=_figsize_for(bbox, figsize_in))
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_aspect("equal")

    draw_layers_on_ax(ax, layers, specs, bbox, basemap)

    if out_path.suffix.lower() == ".svg":
        fig.savefig(out_path, format="svg")
    elif out_path.suffix.lower() == ".png":
        fig.savefig(out_path, format="png", dpi=dpi)
    else:
        raise ExportError(f"不支持的制图格式：{out_path.suffix}（仅 .svg / .png）")
    return str(out_path)


# ------------------------------------------------------------ 超大幅面分块渲染

# ISO 216 纸张（英寸，长边 × 短边）
PAPER_SIZES = {
    "a4": (11.69, 8.27),
    "a3": (16.54, 11.69),
    "a2": (23.39, 16.54),
    "a1": (33.11, 23.39),
    "a0": (46.81, 33.11),
}
POSTER_MAX_TILE_PX = 6000  # 单块像素上限，防内存爆炸


def render_map_poster(
    layers: dict[LayerType, gpd.GeoDataFrame],
    bbox: BBox,
    specs: list[LayerSpec],
    out_path: str | Path,
    dpi: int = 300,
    paper: str = "a0",
    max_tile_px: int = POSTER_MAX_TILE_PX,
) -> str:
    """超大幅面 PNG：把范围切成网格逐块渲染，再用 PIL 无缝拼接。

    仅矢量图层（不叠加瓦片底图，避免高清场景下瓦片量爆炸）。
    """

    from io import BytesIO

    from PIL import Image
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    if not any(sp.enabled and sp.layer in layers and len(layers[sp.layer]) for sp in specs):
        raise ExportError("没有可渲染的数据")

    paper_in = PAPER_SIZES.get(paper.lower(), PAPER_SIZES["a0"])
    s, w, n, e = bbox
    ratio = max((e - w) / max(n - s, 1e-9), 1e-9)
    long_side = max(paper_in)
    if ratio >= 1:
        total_in = (long_side, long_side / ratio)
    else:
        total_in = (long_side * ratio, long_side)

    w_px, h_px = int(total_in[0] * dpi), int(total_in[1] * dpi)
    nx = max(1, -(-w_px // max_tile_px))
    ny = max(1, -(-h_px // max_tile_px))
    tile_in = (total_in[0] / nx, total_in[1] / ny)
    tile_px = (-(-w_px // nx), -(-h_px // ny))

    logger.info(
        "超大幅面渲染：%dx%d px，%dx%d 块分块（单块约 %dx%d）",
        w_px, h_px, nx, ny, tile_px[0], tile_px[1],
    )

    canvas = Image.new("RGB", (w_px, h_px), "white")
    for row in range(ny):
        for col in range(nx):
            lon0 = w + (e - w) * col / nx
            lon1 = w + (e - w) * (col + 1) / nx
            lat1 = n - (n - s) * row / ny  # 图像 y 向下
            lat0 = n - (n - s) * (row + 1) / ny
            tile_bbox: BBox = (lat0, lon0, lat1, lon1)

            fig = Figure(figsize=tile_in)
            FigureCanvasAgg(fig)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            ax.set_aspect("equal")
            draw_layers_on_ax(ax, layers, specs, tile_bbox, pad=0.0, legend=False)

            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=dpi)
            buf.seek(0)
            tile = Image.open(buf).convert("RGB")
            if tile.size != tile_px:  # 舍入差一像素时对齐
                tile = tile.resize(tile_px, Image.LANCZOS)
            canvas.paste(tile, (col * tile_px[0], row * tile_px[1]))
            fig.clf()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")
    return str(out_path)
