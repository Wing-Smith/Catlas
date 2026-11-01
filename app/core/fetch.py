"""Overpass API 抓取：分图层查询、网格分块、镜像故障转移、限速与重试。

核心职责：
1. 按图层构造 Overpass QL 查询；
2. 大范围自动拆分为网格分块抓取后合并；
3. Overpass JSON → GeoDataFrame（含 multipolygon relation 装配）；
4. 不依赖 GUI，进度通过回调上报。
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Callable

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union

from app.core import logbus
from app.core.config import SETTINGS, USER_AGENT
from app.core.errors import AreaTooLargeError, FetchError
from app.core.models import BBox, CancelToken, LayerType

logger = logging.getLogger(__name__)

ProgressCb = Callable[[float, str], None]

# Overpass QL 模板：{bbox} = south,west,north,east
_QUERIES: dict[LayerType, str] = {
    LayerType.ROAD: """[out:json][timeout:{timeout}];
(
  way["highway"]({bbox});
);
out geom;""",
    LayerType.WATER: """[out:json][timeout:{timeout}];
(
  way["natural"="water"]({bbox});
  way["water"]({bbox});
  way["waterway"]({bbox});
  relation["natural"="water"]({bbox});
  relation["water"]({bbox});
  relation["waterway"="riverbank"]({bbox});
);
out geom;""",
    LayerType.GREEN: """[out:json][timeout:{timeout}];
(
  way["leisure"="park"]({bbox});
  way["leisure"="garden"]({bbox});
  way["landuse"="grass"]({bbox});
  way["landuse"="forest"]({bbox});
  way["landuse"="meadow"]({bbox});
  way["landuse"="recreation_ground"]({bbox});
  way["natural"="wood"]({bbox});
  way["natural"="scrub"]({bbox});
  relation["leisure"="park"]({bbox});
  relation["landuse"="forest"]({bbox});
  relation["natural"="wood"]({bbox});
);
out geom;""",
    LayerType.BUILDING: """[out:json][timeout:{timeout}];
(
  way["building"]({bbox});
  relation["building"]({bbox});
);
out geom;""",
}

# 保留的核心标签 → GeoDataFrame 列
_KEEP_TAGS = ("name", "highway", "water", "waterway", "natural", "landuse", "leisure", "building")


# ---------------------------------------------------------------- Overpass HTTP


def _overpass_query(endpoint: str, ql: str, token: CancelToken) -> dict:
    token.throw_if_cancelled()
    resp = requests.post(
        endpoint,
        data={"data": ql},
        headers={"User-Agent": USER_AGENT},
        timeout=SETTINGS.http_timeout_s + SETTINGS.overpass_timeout_s,
    )
    if resp.status_code in (429, 504):
        raise FetchError(f"Overpass 过载（HTTP {resp.status_code}），将切换镜像重试")
    resp.raise_for_status()
    text = resp.text
    # Overpass 过载/限流时可能以 HTTP 200 返回错误 XML/HTML 页面
    stripped = text.lstrip()
    if stripped.startswith("<?xml") or stripped.startswith("<html") or stripped.startswith("<osm"):
        import re as _re

        remark = _re.search(r"<remark>(.*?)</remark>", text, _re.S)
        detail = (remark.group(1) if remark else text[:150]).strip()
        raise FetchError(f"Overpass 返回错误页面：{detail}")
    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise FetchError(f"Overpass 返回非 JSON 响应：{text[:200]}") from exc


_ALIVE_ENDPOINTS: list[str] | None = None


def reset_probe_cache() -> None:
    """清除镜像探测缓存（设置页修改端点列表后调用）。"""

    global _ALIVE_ENDPOINTS
    _ALIVE_ENDPOINTS = None


# 数据探针：查伦敦市中心一栋建筑，用于验证镜像数据库是否真实可用
_PROBE_QUERY = '[out:json][timeout:25];way["building"](51.5005,-0.1250,51.5015,-0.1240);out geom 1;'


def probe_endpoints(timeout_s: float = 30.0) -> list[str]:
    """探测镜像：必须 HTTP 200 且返回非空 elements（剔除空库/陈旧镜像）。"""

    global _ALIVE_ENDPOINTS
    if _ALIVE_ENDPOINTS is not None:
        return _ALIVE_ENDPOINTS
    alive: list[str] = []
    for url in SETTINGS.overpass_endpoints:
        try:
            resp = requests.post(
                url,
                data={"data": _PROBE_QUERY},
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                timeout=timeout_s,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("elements"):
                alive.append(url)
                logger.info("Overpass 镜像可用（含数据）：%s", url)
            else:
                logger.warning("Overpass 镜像无数据或异常：%s（HTTP %s）", url, resp.status_code)
        except Exception:
            logger.warning("Overpass 镜像不可达：%s", url)
    if not alive:
        # 探测全部失败时退回完整列表，由执行层自己处理超时/重试
        alive = list(SETTINGS.overpass_endpoints)
        logger.warning("镜像探测全部失败，退回完整列表")
    _ALIVE_ENDPOINTS = alive
    return alive


class _MirrorPool:
    """顺序尝试可用的 Overpass 镜像；过载时指数退避重试同一镜像再切换。"""

    # 过载退避：10s、20s
    _BACKOFFS = (10.0, 20.0)

    def __init__(self) -> None:
        self._endpoints = probe_endpoints()
        self._idx = 0
        self._last_ts = 0.0

    def execute(self, ql: str, token: CancelToken) -> dict:
        last_err: Exception | None = None
        tried: set[str] = set()
        # 每个镜像最多尝试 1 + len(_BACKOFFS) 次；全部轮完则失败
        while len(tried) < len(self._endpoints):
            endpoint = self._endpoints[self._idx % len(self._endpoints)]
            if endpoint in tried:
                break
            self._idx += 1
            backoff_round = 0
            while True:
                try:
                    self._polite_wait()
                    logbus.debug(f"Overpass 请求 → {endpoint}（{len(ql)} 字节）")
                    return _overpass_query(endpoint, ql, token)
                except FetchError as exc:
                    # 429/504 等过载：退避后同镜像重试
                    last_err = exc
                    if backoff_round < len(self._BACKOFFS):
                        wait_s = self._BACKOFFS[backoff_round]
                        backoff_round += 1
                        logger.warning("镜像 %s 过载（%s），%.0fs 后重试", endpoint, exc, wait_s)
                        logbus.warn(f"镜像过载（{exc}），{wait_s:.0f}s 后重试：{endpoint}")
                        for _ in range(int(wait_s * 2)):
                            token.throw_if_cancelled()
                            time.sleep(0.5)
                        continue
                    tried.add(endpoint)
                    logger.warning("镜像 %s 重试后仍失败，切换镜像", endpoint)
                    logbus.warn(f"镜像重试后仍失败，切换镜像：{endpoint}")
                    break
                except requests.RequestException as exc:
                    last_err = exc
                    tried.add(endpoint)
                    logger.warning("镜像 %s 请求异常：%s，切换镜像", endpoint, exc)
                    logbus.warn(f"镜像请求异常（{exc}），切换镜像：{endpoint}")
                    break
        raise FetchError(
            "所有 Overpass 数据服务均不可用（连接超时或网络不可达）。"
            "可到「网络监测」页查看各镜像连通性，或稍后重试。"
        ) from last_err

    def _polite_wait(self) -> None:
        elapsed = time.monotonic() - self._last_ts
        if elapsed < SETTINGS.request_interval_s:
            time.sleep(SETTINGS.request_interval_s - elapsed)
        self._last_ts = time.monotonic()


# ------------------------------------------------------- OSM JSON → GeoDataFrame


def _classify(tags: dict, layer: LayerType) -> str:
    """提取主分类字段（fclass）。"""

    priority = {
        LayerType.ROAD: ("highway",),
        LayerType.WATER: ("natural", "water", "waterway"),
        LayerType.GREEN: ("leisure", "landuse", "natural"),
        LayerType.BUILDING: ("building",),
    }[layer]
    for key in priority:
        if tags.get(key):
            return str(tags[key])
    return ""


def _assemble_multipolygon(outer_lines: list[LineString], inner_lines: list[LineString]) -> Polygon | MultiPolygon | None:
    """把 outer/inner 成员线装配成（多重）多边形。"""

    outers = list(polygonize([ln for ln in outer_lines if len(ln.coords) >= 4]))
    inners = list(polygonize([ln for ln in inner_lines if len(ln.coords) >= 4]))
    if not outers:
        return None
    if inners:
        holes_by_outer: list[list] = [[] for _ in outers]
        for hole in inners:
            pt = hole.representative_point()
            for i, poly in enumerate(outers):
                if poly.covers(pt):
                    holes_by_outer[i].append(hole.exterior)
                    break
        outers = [Polygon(o.exterior, holes=h) for o, h in zip(outers, holes_by_outer)]
    merged = unary_union(outers)
    if merged.is_empty:
        return None
    return merged


def parse_overpass_json(data: dict, layer: LayerType) -> gpd.GeoDataFrame:
    """Overpass JSON → GeoDataFrame（EPSG:4326）。

    way 闭合 → Polygon，开放 → LineString；multipolygon relation 装配 outer/inner 环。
    """

    nodes: dict[int, tuple[float, float]] = {}
    ways: dict[int, dict] = {}
    relations: dict[int, dict] = {}
    for el in data.get("elements", []):
        etype = el.get("type")
        if etype == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif etype == "way":
            ways[el["id"]] = el
        elif etype == "relation":
            relations[el["id"]] = el

    # relation 成员 way 会以独立 way 元素重复出现在响应里，
    # 装配 multipolygon 时必须排除，否则会与关系几何重复
    member_way_ids: set[int] = set()
    for rel in relations.values():
        if rel.get("tags", {}).get("type", "multipolygon") != "multipolygon":
            continue
        for member in rel.get("members", []):
            if member.get("type") == "way" and "ref" in member:
                member_way_ids.add(member["ref"])

    rows: list[dict] = []

    def _way_coords(way: dict) -> list[tuple[float, float]]:
        geom = way.get("geometry")
        if geom:
            return [(pt["lon"], pt["lat"]) for pt in geom]
        coords = []
        for nid in way.get("nodes", []):
            if nid in nodes:
                coords.append(nodes[nid])
        return coords

    for wid, way in ways.items():
        if wid in member_way_ids:
            continue
        coords = _way_coords(way)
        if len(coords) < 2:
            continue
        tags = way.get("tags", {})
        closed = len(coords) >= 4 and coords[0] == coords[-1]
        if closed and layer is not LayerType.ROAD:
            geom: object = Polygon(coords)
        else:
            geom = LineString(coords)
        rows.append(
            _make_row("way", wid, tags, geom, layer)
        )

    for rid, rel in relations.items():
        tags = rel.get("tags", {})
        if tags.get("type", "multipolygon") != "multipolygon":
            continue
        outers, inners = [], []
        for member in rel.get("members", []):
            if member.get("type") != "way":
                continue
            line = member.get("geometry")
            if not line or len(line) < 2:
                continue
            coords = [(pt["lon"], pt["lat"]) for pt in line]
            role = member.get("role", "outer")
            (outers if role == "outer" else inners).append(LineString(coords))
        if not outers:
            continue
        geom = _assemble_multipolygon(outers, inners)
        if geom is not None and not geom.is_empty:
            rows.append(_make_row("relation", rid, tags, geom, layer))

    if not rows:
        return gpd.GeoDataFrame(
            {c: [] for c in ("osm_type", "osm_id", "name", "fclass")},
            geometry=gpd.GeoSeries([], crs="EPSG:4326"),
        )

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gdf


def _make_row(osm_type: str, osm_id: int, tags: dict, geom: object, layer: LayerType) -> dict:
    row = {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "name": str(tags.get("name", "")),
        "fclass": _classify(tags, layer),
        "geometry": geom,
    }
    for key in _KEEP_TAGS:
        if key in tags:
            row[key] = str(tags[key])
    return row


# ------------------------------------------------------------------ 网格分块


def split_bbox(bbox: BBox, cell_km: float) -> list[BBox]:
    """把 bbox 按近似公里网格拆分。"""

    s, w, n, e = bbox
    lat_mid = math.radians((s + n) / 2)
    km_per_lat = math.pi / 180 * 6371.0
    km_per_lon = km_per_lat * math.cos(lat_mid)
    step_lat = cell_km / km_per_lat
    step_lon = cell_km / km_per_lon if km_per_lon > 1e-6 else 360.0

    cells: list[BBox] = []
    lat = s
    while lat < n:
        lon = w
        next_lat = min(lat + step_lat, n)
        while lon < e:
            next_lon = min(lon + step_lon, e)
            cells.append((lat, lon, next_lat, next_lon))
            lon = next_lon
        lat = next_lat
    return cells


# ------------------------------------------------------------------ 对外 API


def fetch_layer(
    layer: LayerType,
    bbox: BBox,
    token: CancelToken,
    progress: ProgressCb | None = None,
    split_cell_km: float | None = None,
) -> gpd.GeoDataFrame:
    """抓取单个图层；范围过大时自动网格分块。"""

    cell_km = split_cell_km or SETTINGS.split_cell_km
    cells = split_bbox(bbox, cell_km)
    if len(cells) > 64:
        raise AreaTooLargeError(f"范围过大：拆分为 {len(cells)} 块（上限 64），请缩小范围")

    pool = _MirrorPool()
    template = _QUERIES[layer]
    parts: list[gpd.GeoDataFrame] = []

    total = max(len(cells), 1)
    logbus.info(f"开始抓取 {layer.label}：{total} 个分块")
    for i, cell in enumerate(cells):
        token.throw_if_cancelled()
        s, wgt, n, e = cell
        ql = template.format(bbox=f"{s},{wgt},{n},{e}", timeout=SETTINGS.overpass_timeout_s)
        t0 = time.monotonic()
        data = pool.execute(ql, token)
        elapsed = time.monotonic() - t0
        gdf = parse_overpass_json(data, layer)
        if len(gdf):
            parts.append(gdf)
        if progress:
            progress((i + 1) / total, f"{layer.label}：第 {i + 1}/{total} 块")
        logbus.info(
            f"{layer.label} 分块 {i + 1}/{total} 完成：{len(gdf)} 要素 · {elapsed:.1f}s"
        )
        logger.info("fetched %s cell %d/%d → %d features", layer.value, i + 1, total, len(gdf))

    if not parts:
        return parse_overpass_json({"elements": []}, layer)

    merged = gpd.GeoDataFrame(
        pd.concat(parts, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    return merged
