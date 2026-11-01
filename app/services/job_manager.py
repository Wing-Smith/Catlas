"""后台任务线程：抓取流水线 / 导出，进度通过 Qt 信号上报。"""

from __future__ import annotations

import requests
from PySide6.QtCore import QThread, Signal

from app.core.models import CancelToken, ExportJob, FetchJob, LayerSpec, PipelineResult, PipelineState
from app.core.pipeline import Pipeline


class FetchWorker(QThread):
    """在后台线程跑完整抓取流水线。"""

    progress = Signal(float, str)  # 百分比, 阶段消息
    finished_ok = Signal(object)  # PipelineResult
    failed = Signal(str)

    def __init__(
        self,
        query: str | None,
        bbox: tuple | None,
        fetch_job: FetchJob,
        parent=None,
        resolved: "GeoArea | None" = None,
    ):
        super().__init__(parent)
        self._query = query
        self._bbox = bbox
        self._fetch_job = fetch_job
        self._resolved = resolved
        self.token = CancelToken()

    def run(self) -> None:  # noqa: D102 (QThread 入口)
        try:
            pipeline = Pipeline(progress=lambda f, m: self.progress.emit(f, m))
            result = pipeline.run(
                self._query, self._bbox, self._fetch_job, None, self.token, resolved=self._resolved
            )
        except Exception as exc:  # 兜底：任何未预期异常都必须通知 GUI 复位
            from app.core import logbus

            logbus.error(f"抓取任务内部错误：{type(exc).__name__}: {exc}")
            self.failed.emit(f"内部错误（{type(exc).__name__}），详见日志页")
            return
        if result.state is PipelineState.DONE:
            self.finished_ok.emit(result)
        elif result.state is PipelineState.CANCELLED:
            self.failed.emit("任务已取消")
        else:
            self.failed.emit(result.message or "未知错误")


class GeocodeWorker(QThread):
    """后台解析地名候选（多供应商链可能耗时数十秒，严禁在 GUI 线程跑）。"""

    results = Signal(list)  # list[GeoArea]
    failed = Signal(str)

    def __init__(self, query: str, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self) -> None:  # noqa: D102 (QThread 入口)
        from app.core import logbus
        from app.core.geocode import geocode_multi

        try:
            self.results.emit(geocode_multi(self.query))
        except Exception as exc:  # noqa: BLE001
            logbus.warn(f"地名解析失败：{exc}")
            self.failed.emit(str(exc))


class NetworkProbeWorker(QThread):
    """并发探测各网络服务端点的连通性与延迟（一次全部同时尝试）。"""

    targets_ready = Signal(list)  # [(名称, 地址)]
    result = Signal(str, str, bool, float, str)  # 名称, 地址, 是否可用, 延迟ms, 失败原因
    finished_all = Signal()

    PROBE_TIMEOUT = 10.0
    MAX_WORKERS = 12

    def run(self) -> None:
        from app.core.config import SETTINGS, USER_AGENT
        from app.core.tiles import PROVIDERS

        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        targets: list[tuple[str, str, str, dict]] = []
        for ep in SETTINGS.overpass_endpoints:
            host = ep.split("//", 1)[-1].split("/", 1)[0]  # 用主机名区分同名镜像
            targets.append((f"Overpass · {host}", ep, "overpass", {}))
        targets.append((
            "Nominatim 地理编码",
            f"{SETTINGS.nominatim_url}?q=kunming&format=jsonv2&limit=1",
            "http", {},
        ))
        targets.append(("Photon 地理编码", "https://photon.komoot.io/api/?q=kunming&limit=1", "http", {}))
        for provider in PROVIDERS.values():
            # 用低缩放级样例瓦片探测，保证全球任何角落都有图
            url = provider.url.format(
                s=provider.subdomains[0] if provider.subdomains else "", z=2, x=1, y=1
            )
            targets.append((f"瓦片 · {provider.name}", url, "http", dict(provider.headers)))
        # 路径规划（OSRM 三种模式，用柏林一小段真实路由探测）
        for label, routed, profile in (
            ("汽车", "routed-car", "driving"),
            ("自行车", "routed-bike", "cycling"),
            ("步行", "routed-foot", "foot"),
        ):
            targets.append((
                f"路径规划 · OSRM {label}",
                f"https://routing.openstreetmap.de/{routed}/route/v1/{profile}/"
                "13.4,52.5;13.41,52.51?overview=false",
                "http",
                {},
            ))
        # 矢量瓦片源（仅探测可用性，未接入渲染）
        targets.append(("矢量瓦片 · OpenFreeMap", "https://tiles.openfreemap.org/planet", "http", {}))

        self.targets_ready.emit([(name, url) for name, url, _, _ in targets])

        from concurrent.futures import ThreadPoolExecutor, as_completed

        workers = min(self.MAX_WORKERS, len(targets))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._probe, kind, url, {**headers, **extra}): (name, url)
                for name, url, kind, extra in targets
            }
            for fut in as_completed(futures):
                name, url = futures[fut]
                try:
                    ok, latency, err = fut.result()
                except Exception as exc:
                    ok, latency, err = False, self.PROBE_TIMEOUT * 1000, str(exc)
                if not ok and err:
                    from app.core import logbus

                    logbus.warn(f"探测失败：{name} -- {err}")
                self.result.emit(name, url, ok, latency, err)
        self.finished_all.emit()

    def _probe(self, kind: str, url: str, headers: dict) -> tuple[bool, float, str]:
        import time

        t0 = time.monotonic()
        try:
            if kind == "overpass":
                resp = requests.post(
                    url, data={"data": "[out:json];node(1);out;"}, headers=headers, timeout=self.PROBE_TIMEOUT
                )
            else:
                resp = requests.get(url, headers=headers, timeout=self.PROBE_TIMEOUT)
            latency = (time.monotonic() - t0) * 1000
            if resp.status_code == 429:
                return True, latency, ""  # 限流 = 服务在线但忙，视为可用
            if 200 <= resp.status_code < 300:
                return True, latency, ""
            return False, latency, f"HTTP {resp.status_code}"
        except requests.Timeout:
            return False, (time.monotonic() - t0) * 1000, "连接/读取超时"
        except requests.ConnectionError as exc:
            text = str(exc)
            if "NameResolutionError" in text or "Failed to resolve" in text:
                reason = "DNS 解析失败"
            elif "refused" in text.lower():
                reason = "连接被拒绝"
            else:
                reason = f"网络不可达（{type(exc).__name__}）"
            return False, (time.monotonic() - t0) * 1000, reason
        except requests.RequestException as exc:
            return False, (time.monotonic() - t0) * 1000, f"{type(exc).__name__}"
        except Exception as exc:  # noqa: BLE001 - SSL 等底层错误也原样带出
            return False, (time.monotonic() - t0) * 1000, f"{type(exc).__name__}: {str(exc)[:80]}"


class BasemapWorker(QThread):
    """在后台线程拼接瓦片底图，避免卡 GUI。"""

    result = Signal(object)  # (image, extent) 或 None

    def __init__(self, bbox: tuple, provider_id: str, parent=None):
        super().__init__(parent)
        self._bbox = bbox
        self._provider_id = provider_id

    def run(self) -> None:
        from app.core import tiles

        try:
            self.result.emit(tiles.compose_basemap(self._bbox, self._provider_id))
        except Exception:
            self.result.emit(None)


class RouteWorker(QThread):
    """在后台线程跑 OSRM 路径规划。"""

    result = Signal(object)  # routing.route() 的返回 dict
    failed = Signal(str)

    def __init__(self, profile: str, start: tuple, end: tuple, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._start = start
        self._end = end

    def run(self) -> None:
        from app.core import routing

        try:
            self.result.emit(routing.route(self._profile, self._start, self._end))
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWorker(QThread):
    """在后台线程跑导出（矢量 + 制图）。"""

    progress = Signal(float, str)
    finished_ok = Signal(dict)  # 格式 → 路径
    failed = Signal(str)

    def __init__(
        self,
        layers: dict,
        bbox: tuple,
        specs: list[LayerSpec],
        export_job: ExportJob,
        parent=None,
    ):
        super().__init__(parent)
        self._layers = layers
        self._bbox = bbox
        self._specs = specs
        self._export_job = export_job
        self.token = CancelToken()

    def run(self) -> None:
        from app.core.models import GeoArea

        pipeline = Pipeline(progress=lambda f, m: self.progress.emit(f, m))
        try:
            exported = pipeline.export(
                self._layers, GeoArea(bbox=self._bbox), self._export_job, self._specs, self.token
            )
            self.finished_ok.emit(exported)
        except Exception as exc:
            self.failed.emit(str(exc))
