"""栅格底图瓦片：XYZ 模板源、磁盘缓存、限速并发抓取、Web Mercator 拼接。

数据源（免 Key）：
- osm_de      标准样式 · 德国官方镜像（a/b/c 分流）
- osm_official 官方标准瓦片
- hot         HOT 人文样式（法国）
- osmfr       OSM France 样式
- seamark     航海图标注叠加层
- esri        Esri World Imagery 卫星影像（非 OSM 数据）
"""

from __future__ import annotations

import logging
import math
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import requests

from app.core.config import CACHE_ROOT_DIR, SETTINGS, USER_AGENT
from app.core.models import BBox

logger = logging.getLogger(__name__)

TILE_SIZE = 256
EARTH_RADIUS_M = 6378137.0
MAX_ZOOM = 19


@dataclass(frozen=True)
class TileProvider:
    id: str
    name: str
    url: str  # 支持 {s} 子域分流与 {z}/{x}/{y} 占位
    subdomains: tuple[str, ...] = ("",)
    attribution: str = "© OpenStreetMap contributors"
    max_zoom: int = MAX_ZOOM
    headers: dict = field(default_factory=dict)  # 额外请求头（如 Referer）
    encrypt_store: bool = False  # 落盘前加密（合规要求，如 Esri）


PROVIDERS: dict[str, TileProvider] = {
    "osm_de": TileProvider(
        "osm_de", "标准（OSM.de 镜像）",
        "https://{s}.tile.openstreetmap.de/{z}/{x}/{y}.png",
        subdomains=("a", "b", "c"),
    ),
    "osm_official": TileProvider(
        "osm_official", "官方标准",
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution="© OpenStreetMap contributors, ODbL",
    ),
    "hot": TileProvider(
        "hot", "HOT 人文",
        "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        subdomains=("a", "b"),
    ),
    "osmfr": TileProvider(
        "osmfr", "OSM France",
        "https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
    ),
    "cyclosm": TileProvider(
        "cyclosm", "CyclOSM 骑行",
        "https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
        subdomains=("a", "b", "c"),
    ),
    "waymarked_hiking": TileProvider(
        "waymarked_hiking", "Waymarked 徒步",
        "https://tile.waymarkedtrails.org/hiking/{z}/{x}/{y}.png",
    ),
    "waymarked_cycling": TileProvider(
        "waymarked_cycling", "Waymarked 骑行",
        "https://tile.waymarkedtrails.org/cycling/{z}/{x}/{y}.png",
    ),
    "waymarked_mtb": TileProvider(
        "waymarked_mtb", "Waymarked 山地车",
        "https://tile.waymarkedtrails.org/mtb/{z}/{x}/{y}.png",
    ),
    "waymarked_slopes": TileProvider(
        "waymarked_slopes", "Waymarked 坡度",
        "https://tile.waymarkedtrails.org/slopes/{z}/{x}/{y}.png",
    ),
    "waymarked_riding": TileProvider(
        "waymarked_riding", "Waymarked 骑术",
        "https://tile.waymarkedtrails.org/riding/{z}/{x}/{y}.png",
    ),
    "waymarked_skating": TileProvider(
        "waymarked_skating", "Waymarked 轮滑",
        "https://tile.waymarkedtrails.org/skating/{z}/{x}/{y}.png",
    ),
    "opensnowmap": TileProvider(
        "opensnowmap", "OpenSnowMap 雪道",
        "https://www.opensnowmap.org/tiles-pistes/{z}/{x}/{y}.png",
    ),
    "openrailwaymap": TileProvider(
        "openrailwaymap", "OpenRailwayMap 铁路",
        "https://a.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png",
        headers={"Referer": "https://www.openrailwaymap.org/"},
    ),
    "seamark": TileProvider(
        "seamark", "海图标注",
        "https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png",
        attribution="© OpenSeaMap contributors",
    ),
    "esri": TileProvider(
        "esri", "Esri 卫星影像（仅预览）",
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attribution="Esri, Maxar, Earthstar Geographics",
        encrypt_store=True,  # 合规：落盘加密，禁止导出成品
    ),
}

NONE_PROVIDER = "none"


# ------------------------------------------------------------------ 坐标换算


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2.0**z
    x = int((lon + 180.0) / 360.0 * n)
    lat = max(-85.05112878, min(85.05112878, lat))
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tile_count(bbox: BBox, z: int) -> int:
    s, w, n, e = bbox
    x1, y1 = lonlat_to_tile(w, n, z)  # 左上
    x2, y2 = lonlat_to_tile(e, s, z)  # 右下
    return (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1)


def choose_zoom(bbox: BBox, max_tiles: int = 24) -> int:
    """在瓦片数量约束内取最高缩放级。"""

    for z in range(MAX_ZOOM, 2, -1):
        if tile_count(bbox, z) <= max_tiles:
            return z
    return 3


def lonlat_to_mercator(lon: float, lat: float) -> tuple[float, float]:
    lat = max(-85.05112878, min(85.05112878, lat))
    x = EARTH_RADIUS_M * math.radians(lon)
    y = EARTH_RADIUS_M * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def mercator_to_lonlat(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / EARTH_RADIUS_M)
    lat = math.degrees(2.0 * math.atan(math.exp(y / EARTH_RADIUS_M)) - math.pi / 2.0)
    return lon, lat


def bbox_mercator_extent(bbox: BBox) -> tuple[float, float, float, float]:
    """matplotlib imshow 的 extent 顺序：(left, right, bottom, top)。"""

    s, w, n, e = bbox
    x1, y1 = lonlat_to_mercator(w, n)
    x2, y2 = lonlat_to_mercator(e, s)
    return (x1, x2, y2, y1)  # (left, right, bottom, top)


# ------------------------------------------------------------------ 抓取与缓存

TILE_CACHE = CACHE_ROOT_DIR / "tiles"
_CACHE_MAX_BYTES = 512 * 1024 * 1024

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT

_rate_lock = threading.Lock()
_rate_last = 0.0
RATE_INTERVAL_S = 0.15  # 全局 ~6-7 请求/秒，对公共瓦片服务更礼貌


def _polite_wait() -> None:
    global _rate_last
    with _rate_lock:
        elapsed = time.monotonic() - _rate_last
        if elapsed < RATE_INTERVAL_S:
            time.sleep(RATE_INTERVAL_S - elapsed)
        _rate_last = time.monotonic()


def _tile_path(provider: TileProvider, z: int, x: int, y: int) -> Path:
    # encrypt_store 的源落盘为加密文件，后缀 .enc，避免被当作普通图片直接取用
    suffix = ".enc" if provider.encrypt_store else ".png"
    return TILE_CACHE / provider.id / str(z) / str(x) / f"{y}{suffix}"


def fetch_tile(provider: TileProvider, z: int, x: int, y: int, retries: int = 1) -> Path | None:
    """下载单张瓦片（磁盘缓存，失败重试后返回 None）。

    encrypt_store 的源写盘前加密，仅软件内解密到内存使用。
    """

    path = _tile_path(provider, z, x, y)
    if path.exists() and path.stat().st_size > 0:
        return path

    url = provider.url.format(
        s=provider.subdomains[(x + y) % len(provider.subdomains)], z=z, x=x, y=y
    )
    for attempt in range(retries + 1):
        try:
            _polite_wait()
            resp = _session.get(
                url,
                timeout=min(SETTINGS.http_timeout_s, 15),
                headers={**provider.headers} or None,
            )
            if resp.status_code == 200 and len(resp.content) > 100:
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = resp.content
                if provider.encrypt_store:
                    from app.core import tilecrypto

                    payload = tilecrypto.encrypt_bytes(payload)
                path.write_bytes(payload)
                return path
            logger.warning("瓦片 HTTP %s：%s", resp.status_code, url)
        except requests.RequestException as exc:
            logger.warning("瓦片下载失败（第 %d 次）：%s — %s", attempt + 1, url, exc)
        time.sleep(0.5 * (attempt + 1))
    return None


def _cached_files() -> list[Path]:
    if not TILE_CACHE.exists():
        return []
    return [p for p in TILE_CACHE.rglob("*") if p.suffix in (".png", ".enc")]


def _prune_cache() -> None:
    entries = sorted(_cached_files(), key=lambda p: p.stat().st_mtime, reverse=True)
    total = 0
    for p in entries:
        total += p.stat().st_size
        if total > _CACHE_MAX_BYTES:
            p.unlink(missing_ok=True)


def compose_basemap(
    bbox: BBox,
    provider_id: str,
    max_tiles: int = 24,
    max_workers: int = 6,
) -> tuple["object", tuple[float, float, float, float]] | None:
    """抓取 bbox 范围内的瓦片并拼接成一张大图。

    返回 (PIL.Image, (left, right, bottom, top) Web Mercator 米制范围，
    与 matplotlib imshow 的 extent 参数一致)；完全无可用瓦片时返回 None。
    """

    from PIL import Image

    provider = PROVIDERS.get(provider_id)
    if provider is None:
        return None

    z = min(choose_zoom(bbox, max_tiles), provider.max_zoom)
    s, w, n, e = bbox
    x1, y1 = lonlat_to_tile(w, n, z)
    x2, y2 = lonlat_to_tile(e, s, z)
    xs = range(min(x1, x2), max(x1, x2) + 1)
    ys = range(min(y1, y2), max(y1, y2) + 1)

    canvas = Image.new("RGB", (len(xs) * TILE_SIZE, len(ys) * TILE_SIZE), (240, 240, 240))
    got = 0

    def _paste(x: int, y: int) -> None:
        nonlocal got
        p = fetch_tile(provider, z, x, y)
        if p is None:
            return
        try:
            if provider.encrypt_store:
                from io import BytesIO

                from app.core import tilecrypto

                tile = Image.open(BytesIO(tilecrypto.decrypt_bytes(p.read_bytes()))).convert("RGB")
            else:
                tile = Image.open(p).convert("RGB")
            canvas.paste(tile, ((x - xs.start) * TILE_SIZE, (y - ys.start) * TILE_SIZE))
            got += 1
        except Exception as exc:
            logger.warning("瓦片解码失败 %s：%s", p, exc)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(lambda xy: _paste(*xy), ((x, y) for x in xs for y in ys)))

    if got == 0:
        return None

    # 拼接图四个角对应的 Web Mercator 范围
    # 瓦片 (x1,y1) 左上角的经纬度
    def _tile_origin(x: int, y: int) -> tuple[float, float]:
        n_tiles = 2.0**z
        lon = x / n_tiles * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n_tiles))))
        return lonlat_to_mercator(lon, lat)

    left, top = _tile_origin(xs.start, ys.start)
    right, bottom = _tile_origin(xs.stop, ys.stop)
    _prune_cache()
    logger.info("basemap: provider=%s z=%d tiles=%d/%d", provider_id, z, got, len(xs) * len(ys))
    return canvas, (left, right, bottom, top)  # matplotlib extent 顺序


def clear_tile_cache() -> int:
    if not TILE_CACHE.exists():
        return 0
    count = len(_cached_files())
    shutil.rmtree(TILE_CACHE, ignore_errors=True)
    return count
