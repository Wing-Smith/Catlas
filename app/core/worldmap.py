"""本地世界底图：Natural Earth 数据（随应用打包，完全离线）。

包含国界、省界（50m）、河流、湖泊与主要城市，供选区地图页渲染。
数据文件位于 app/data/world/，PyInstaller 打包后从 sys._MEIPASS 读取。
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger(__name__)


def _data_dir() -> Path:
    from app.core.assets import data_dir

    return data_dir("world")


@lru_cache(maxsize=1)
def layers() -> dict[str, gpd.GeoDataFrame]:
    """加载全部底图图层（4326），失败图层返回空 GeoDataFrame。"""

    result: dict[str, gpd.GeoDataFrame] = {}
    specs = {
        "countries": "ne_110m_admin_0_countries.geojson",
        "admin1": "ne_50m_admin_1_states_provinces.geojson",
        "rivers": "ne_110m_rivers_lake_centerlines.geojson",
        "lakes": "ne_110m_lakes.geojson",
        "cities": "ne_110m_populated_places_simple.geojson",
    }
    for key, name in specs.items():
        path = _data_dir() / name
        try:
            result[key] = gpd.read_file(path)
        except Exception as exc:  # noqa: BLE001 - 缺图层不应导致整页崩溃
            logger.warning("本地底图图层缺失或损坏：%s — %s", path, exc)
            result[key] = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return result


# 视觉样式（暗色 / 亮色主题各一套）
_STYLES = {
    "dark": {
        "ocean": "#14181d",
        "land": "#22282f",
        "border": "#5a6672",
        "admin1": "#3a434d",
        "river": "#3d6e8f",
        "lake": "#2f5a78",
        "city": "#d7dde3",
        "city_label": "#9aa4ad",
        "selection": "#0078D4",
    },
    "light": {
        "ocean": "#dfe7ee",
        "land": "#f4f6f8",
        "border": "#8a94a0",
        "admin1": "#c3ccd4",
        "river": "#7aa8c4",
        "lake": "#a8cbe0",
        "city": "#333a41",
        "city_label": "#5a6672",
        "selection": "#0078D4",
    },
}


def draw_world(ax, dark: bool = True) -> None:
    """把世界底图画到 Axes 上（经纬度坐标，全球范围）。"""

    st = _STYLES["dark" if dark else "light"]
    data = layers()

    # 海洋背景
    ax.set_facecolor(st["ocean"])
    land = data["countries"]
    if len(land):
        land.plot(ax=ax, facecolor=st["land"], edgecolor=st["border"], linewidth=0.7, zorder=1)
    admin1 = data["admin1"]
    if len(admin1):
        admin1.plot(ax=ax, facecolor="none", edgecolor=st["admin1"], linewidth=0.4, zorder=2)
    rivers = data["rivers"]
    if len(rivers):
        rivers.plot(ax=ax, color=st["river"], linewidth=0.6, zorder=3)
    lakes = data["lakes"]
    if len(lakes):
        lakes.plot(ax=ax, facecolor=st["lake"], edgecolor=st["river"], linewidth=0.4, zorder=3)
    cities = data["cities"]
    if len(cities):
        # 只标注大人口城市，避免文字糊满屏幕
        major = cities[cities["pop_max"].fillna(0) >= 2_000_000] if "pop_max" in cities else cities
        if not len(major):
            major = cities
        major.plot(ax=ax, color=st["city"], markersize=6, zorder=4)
        for _, row in major.iterrows():
            pt = row.geometry
            ax.annotate(
                str(row.get("name", "")),
                (pt.x, pt.y),
                xytext=(3, 3),
                textcoords="offset points",
                fontsize=7,
                color=st["city_label"],
                zorder=4,
            )

    ax.set_xlim(-180, 180)
    ax.set_ylim(-85, 85)
    ax.set_aspect("equal")


def city_names(limit: int = 10) -> list[str]:
    """最大的几座城市名（主页展示用）。"""

    cities = layers()["cities"]
    if not len(cities) or "pop_max" not in cities:
        return []
    top = cities.sort_values("pop_max", ascending=False).head(limit)
    return [str(n) for n in top["name"]]
