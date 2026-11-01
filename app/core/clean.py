"""数据清洗：几何修复、去重、字段标准化、坐标精度控制。"""

from __future__ import annotations

import logging

import geopandas as gpd
import shapely
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon

from app.core.errors import CleanError
from app.core.models import LayerType

logger = logging.getLogger(__name__)

# 各图层允许的 Geometry 类型
_ALLOWED: dict[LayerType, tuple[type, ...]] = {
    LayerType.ROAD: (LineString, MultiLineString),
    LayerType.WATER: (LineString, MultiLineString, Polygon, MultiPolygon),
    LayerType.GREEN: (Polygon, MultiPolygon),
    LayerType.BUILDING: (Polygon, MultiPolygon),
}


def clean_layer(gdf: gpd.GeoDataFrame, layer: LayerType) -> gpd.GeoDataFrame:
    """清洗单个图层。"""

    if gdf.empty:
        return gdf

    try:
        gdf = gdf.copy()
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        if gdf.empty:
            return gdf

        # 几何有效性修复
        invalid = ~gdf.geometry.is_valid
        if invalid.any():
            fixed = shapely.make_valid(gdf.geometry[invalid])
            gdf.loc[invalid, "geometry"] = gpd.GeoSeries(fixed, index=gdf.index[invalid])

        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        if gdf.empty:
            return gdf

        # 类型过滤（make_valid 可能产出 GeometryCollection）
        allowed = _ALLOWED[layer]
        gdf = gdf[gdf.geometry.geom_type.isin([t.__name__ for t in allowed])]
        if gdf.empty:
            return gdf

        # 分块结果合并后按 (osm_type, osm_id) 去重
        gdf = gdf.drop_duplicates(subset=["osm_type", "osm_id"])

        # 坐标精度 6 位小数（约 0.1m），显著减小文件体积
        gdf.geometry = gpd.GeoSeries(
            shapely.set_precision(gdf.geometry, grid_size=1e-6), index=gdf.index, crs=gdf.crs
        )

        return gdf.reset_index(drop=True)
    except Exception as exc:
        raise CleanError(f"{layer.label} 清洗失败：{exc}") from exc


def clean_all(layers: dict[LayerType, gpd.GeoDataFrame]) -> dict[LayerType, gpd.GeoDataFrame]:
    return {layer: clean_layer(gdf, layer) for layer, gdf in layers.items()}
