"""OSRM 路径规划（FOSSGIS 托管实例，免 Key）。

支持汽车 / 自行车 / 步行三种模式，返回 GeoJSON LineString（EPSG:4326）与
距离、时长摘要。坐标一律为 (经度, 纬度)。
"""

from __future__ import annotations

import logging

import geopandas as gpd
import requests
from shapely.geometry import LineString

from app.core.config import SETTINGS, USER_AGENT

logger = logging.getLogger(__name__)

BASE = "https://routing.openstreetmap.de"

PROFILES: dict[str, tuple[str, str]] = {
    "car": ("汽车", "routed-car"),
    "bike": ("自行车", "routed-bike"),
    "foot": ("步行", "routed-foot"),
}


class RoutingError(RuntimeError):
    pass


def route(profile: str, start: tuple[float, float], end: tuple[float, float]) -> dict:
    """规划 start → end 的路径。

    返回 {"geometry": GeoDataFrame(4326), "km": float, "minutes": float,
          "profile": profile, "profile_label": str}；失败抛 RoutingError。
    """

    if profile not in PROFILES:
        raise RoutingError(f"未知出行模式：{profile}")
    label, routed = PROFILES[profile]
    lon1, lat1 = start
    lon2, lat2 = end
    url = (
        f"{BASE}/{routed}/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
        "?overview=full&geometries=geojson"
    )
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=SETTINGS.http_timeout_s)
    except requests.RequestException as exc:
        raise RoutingError(f"路径服务无响应：{exc}") from exc
    if resp.status_code != 200:
        raise RoutingError(f"路径服务返回 HTTP {resp.status_code}")
    data = resp.json()
    routes = data.get("routes") or []
    if not routes:
        raise RoutingError(data.get("message") or "未找到可行路径（两点可能不相连）")

    best = min(routes, key=lambda r: r.get("distance", float("inf")))
    coords = best["geometry"]["coordinates"]
    if len(coords) < 2:
        raise RoutingError("路径几何数据异常")

    gdf = gpd.GeoDataFrame(
        [{"profile": profile}], geometry=[LineString(coords)], crs="EPSG:4326"
    )
    return {
        "geometry": gdf,
        "km": round(best.get("distance", 0.0) / 1000.0, 2),
        "minutes": round(best.get("duration", 0.0) / 60.0, 1),
        "profile": profile,
        "profile_label": label,
    }
