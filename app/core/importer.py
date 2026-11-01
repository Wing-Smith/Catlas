"""拖拽导入：把外部矢量文件读成预览图层。

支持 .geojson / .json / .shp / .gpkg（GeoPackage 逐层读取后按几何类型归并）。
外部文件没有 OSM 标签，按几何类型归类：面 → 建筑，线 → 路网；
点要素忽略。原始 .osm XML 需要 osmium 依赖，暂不支持。
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from app.core.models import LayerType

SUPPORTED_EXTS = {".geojson", ".json", ".shp", ".gpkg"}


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTS


def _split_by_geometry(gdf: gpd.GeoDataFrame) -> list[tuple[LayerType, gpd.GeoDataFrame]]:
    """把混合几何的图层按行拆开：面 → 建筑，线 → 路网；点忽略。"""
    geom = gdf.geometry.geom_type
    parts = [
        (LayerType.BUILDING,
         gdf[geom.isin(["Polygon", "MultiPolygon"])]),
        (LayerType.ROAD,
         gdf[geom.isin(["LineString", "MultiLineString", "LinearRing"])]),
    ]
    return [(ly, part) for ly, part in parts if len(part)]


def load(path: Path) -> dict[LayerType, gpd.GeoDataFrame]:
    """读取文件并返回 {LayerType: GeoDataFrame}；无可用要素时抛 ValueError。"""
    path = Path(path)
    if not path.exists():
        raise ValueError(f"文件不存在：{path}")

    frames: list[gpd.GeoDataFrame] = []
    if path.suffix.lower() == ".gpkg":
        import pyogrio

        for layer_name, _geom in pyogrio.list_layers(path):
            frames.append(gpd.read_file(path, layer=layer_name, engine="pyogrio"))
    else:
        frames.append(gpd.read_file(path, engine="pyogrio"))

    merged: dict[LayerType, gpd.GeoDataFrame] = {}
    for gdf in frames:
        if gdf is None or gdf.empty:
            continue
        for layer, part in _split_by_geometry(gdf):
            if layer in merged:
                merged[layer] = gpd.GeoDataFrame(
                    pd.concat([merged[layer], part], ignore_index=True),
                    crs=part.crs,
                )
            else:
                merged[layer] = part

    if not merged:
        raise ValueError("文件中没有可用的面或线要素")
    return merged
