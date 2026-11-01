"""地名 → bbox 地理编码：多供应商链（Nominatim 优先，Photon 兜底）。

- 每个供应商带进程内熔断：连续失败后本次运行内跳过，避免拖慢整体；
- 结果带内存缓存；请求遵守各服务限速。
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import SETTINGS, USER_AGENT
from app.core.errors import GeocodeError
from app.core.models import BBox, GeoArea

logger = logging.getLogger(__name__)

_memory_cache: dict[str, GeoArea] = {}


class _Provider(Protocol):
    name: str

    def search(self, query: str) -> GeoArea: ...

    def search_multi(self, query: str, limit: int = 5) -> list[GeoArea]: ...


class _RateLimiter:
    def __init__(self, interval_s: float) -> None:
        self._interval = interval_s
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last = time.monotonic()


_nominatim_limiter = _RateLimiter(SETTINGS.request_interval_s)
_photon_limiter = _RateLimiter(SETTINGS.request_interval_s)


class NominatimProvider:
    name = "Nominatim"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def _get(self, query: str) -> list[dict]:
        _nominatim_limiter.wait()
        resp = requests.get(
            SETTINGS.nominatim_url,
            params={"format": "jsonv2", "limit": 1, "q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=min(SETTINGS.http_timeout_s, 20),
        )
        resp.raise_for_status()
        return resp.json()

    def search(self, query: str) -> GeoArea:
        results = self._get(query)
        if not results:
            raise GeocodeError("无匹配结果")
        top = results[0]
        bbox_raw = top["boundingbox"]  # ["s", "n", "w", "e"]
        bbox: BBox = (float(bbox_raw[0]), float(bbox_raw[2]), float(bbox_raw[1]), float(bbox_raw[3]))
        return GeoArea(bbox=bbox, display_name=top.get("display_name", query), query=query)

    def search_multi(self, query: str, limit: int = 5) -> list[GeoArea]:
        _nominatim_limiter.wait()
        resp = requests.get(
            SETTINGS.nominatim_url,
            params={"format": "jsonv2", "limit": limit, "q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=min(SETTINGS.http_timeout_s, 20),
        )
        resp.raise_for_status()
        out: list[GeoArea] = []
        for item in resp.json():
            raw = item["boundingbox"]
            bbox: BBox = (float(raw[0]), float(raw[2]), float(raw[1]), float(raw[3]))
            out.append(GeoArea(bbox=bbox, display_name=item.get("display_name", query), query=query))
        return out


class PhotonProvider:
    name = "Photon"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def _get(self, query: str) -> dict:
        _photon_limiter.wait()
        resp = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=min(SETTINGS.http_timeout_s, 20),
        )
        resp.raise_for_status()
        return resp.json()

    def search(self, query: str) -> GeoArea:
        data = self._get(query)
        features = data.get("features", [])
        if not features:
            raise GeocodeError("无匹配结果")
        return self._to_area(features[0], query)

    def search_multi(self, query: str, limit: int = 5) -> list[GeoArea]:
        _photon_limiter.wait()
        resp = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": limit},
            headers={"User-Agent": USER_AGENT},
            timeout=min(SETTINGS.http_timeout_s, 20),
        )
        resp.raise_for_status()
        return [self._to_area(f, query) for f in resp.json().get("features", [])]

    @staticmethod
    def _to_area(feature: dict, query: str) -> GeoArea:
        props = feature.get("properties", {})
        extent = props.get("extent")  # 官方为 [minLon, minLat, maxLon, maxLat]，实测顺序不稳定，做归一化
        if extent:
            lon1, lat1, lon2, lat2 = (float(v) for v in extent)
            bbox: BBox = (min(lat1, lat2), min(lon1, lon2), max(lat1, lat2), max(lon1, lon2))
        else:
            lon, lat = feature["geometry"]["coordinates"]
            bbox = (lat - 0.005, lon - 0.005, lat + 0.005, lon + 0.005)
        display = ", ".join(
            str(props.get(k)) for k in ("name", "city", "state", "country") if props.get(k)
        ) or query
        return GeoArea(bbox=bbox, display_name=display, query=query)


class _CircuitBreaker:
    """进程内熔断：连续失败 2 次后跳过该供应商。"""

    def __init__(self, provider: _Provider) -> None:
        self.provider = provider
        self.failures = 0

    def try_search(self, query: str) -> GeoArea:
        try:
            area = self.provider.search(query)
            self.failures = 0
            return area
        except Exception:
            self.failures += 1
            raise


_PROVIDERS = [_CircuitBreaker(NominatimProvider()), _CircuitBreaker(PhotonProvider())]


def _brief_reason(exc: Exception) -> str:
    """把底层网络异常翻译成用户能看懂的一句话（细节留在日志里）。"""

    if isinstance(exc, GeocodeError):
        return str(exc)
    if isinstance(exc, requests.ConnectTimeout):
        return "连接超时"
    if isinstance(exc, requests.Timeout):
        return "请求超时"
    if isinstance(exc, requests.ConnectionError):
        return "网络不可达"
    if isinstance(exc, requests.HTTPError):
        code = exc.response.status_code if exc.response is not None else "?"
        return f"服务返回错误（HTTP {code}）"
    text = str(exc).strip()
    return (text[:40] + "…") if len(text) > 40 else (text or type(exc).__name__)


def geocode(query: str) -> GeoArea:
    """按供应商链顺序解析，任一成功即返回。"""

    query = query.strip()
    if not query:
        raise GeocodeError("地名为空")
    if query in _memory_cache:
        return _memory_cache[query]

    errors: list[str] = []
    for cb in _PROVIDERS:
        if cb.failures >= 2:
            logger.info("地理编码供应商 %s 已熔断，跳过", cb.provider.name)
            continue
        try:
            area = cb.try_search(query)
            _memory_cache[query] = area
            logger.info("geocoded %r → %s (%s)", query, area.bbox, area.display_name)
            return area
        except Exception as exc:
            errors.append(f"{cb.provider.name} {_brief_reason(exc)}")
            logger.warning("供应商 %s 解析失败：%s", cb.provider.name, exc)

    detail = "；".join(errors) or "所有供应商均已熔断"
    raise GeocodeError(
        f"无法解析该地名（{detail}）。可改用「坐标范围」输入，"
        "或到「网络监测」页检查地理编码服务的连通性。"
    )


def geocode_multi(query: str, limit: int = 5) -> list[GeoArea]:
    """返回多个候选结果，供 GUI 弹消歧义选择；全部供应商失败时抛 GeocodeError。"""

    query = query.strip()
    if not query:
        raise GeocodeError("地名为空")

    errors: list[str] = []
    for cb in _PROVIDERS:
        if cb.failures >= 2:
            logger.info("地理编码供应商 %s 已熔断，跳过", cb.provider.name)
            continue
        try:
            areas = cb.provider.search_multi(query, limit)
            if not areas:
                errors.append(f"{cb.provider.name} 无匹配结果")
                continue
            return areas
        except Exception as exc:
            cb.failures += 1
            errors.append(f"{cb.provider.name} {_brief_reason(exc)}")
            logger.warning("供应商 %s 多候选解析失败：%s", cb.provider.name, exc)

    detail = "；".join(errors) or "所有供应商均已熔断"
    raise GeocodeError(
        f"无法解析该地名（{detail}）。可改用「坐标范围」输入，"
        "或到「网络监测」页检查地理编码服务的连通性。"
    )
