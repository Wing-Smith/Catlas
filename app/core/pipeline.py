"""流水线编排：geocode → fetch → clean → export，带进度与取消。

core 层不依赖 Qt；进度通过 Callable[[float, str], None] 上报。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd

from app.core import cache, checkpoint, clean, export, fetch, logbus
from app.core.errors import PipelineError
from app.core.geocode import geocode
from app.core.models import (
    CancelToken,
    ExportJob,
    FetchJob,
    GeoArea,
    LayerSpec,
    LayerType,
    PipelineResult,
    PipelineState,
)

logger = logging.getLogger(__name__)

ProgressCb = Callable[[float, str], None]


def _noop_progress(fraction: float, message: str) -> None:
    pass


class Pipeline:
    """一次完整的抓取→清洗→导出流程。"""

    # 各阶段进度权重
    _WEIGHTS = {"fetch": 0.70, "clean": 0.15, "export": 0.15}

    def __init__(self, progress: ProgressCb | None = None) -> None:
        self._progress = progress or _noop_progress
        self.state = PipelineState.IDLE

    # ------------------------------------------------------------------ geocode

    def resolve_area(
        self,
        query: str | None,
        bbox: tuple | None,
        resolved: GeoArea | None = None,
    ) -> GeoArea:
        self.state = PipelineState.GEOCODING
        if resolved is not None:
            area = resolved
        elif bbox is not None:
            s, w, n, e = (float(v) for v in bbox)
            if not (-90 <= s < n <= 90 and -180 <= w < e <= 180):
                raise PipelineError(f"坐标范围非法：{bbox}（应为 south west north east）")
            area = GeoArea(bbox=(s, w, n, e), display_name="自定义范围", query=f"{s},{w},{n},{e}")
        elif query:
            area = geocode(query)
        else:
            raise PipelineError("必须提供地名或坐标范围")
        self._progress(0.02, f"范围确定：{area.display_name}（约 {area.area_km2:.1f} km²）")
        return area

    # ------------------------------------------------------------------ fetch

    def fetch(self, area: GeoArea, job: FetchJob, token: CancelToken) -> dict[LayerType, gpd.GeoDataFrame]:
        self.state = PipelineState.FETCHING
        enabled = [sp for sp in job.layers if sp.enabled]
        if not enabled:
            raise PipelineError("未选择任何图层")
        layer_types = [sp.layer for sp in enabled]

        if area.area_km2 > job.max_area_km2:
            from app.core.errors import AreaTooLargeError

            raise AreaTooLargeError(
                f"范围约 {area.area_km2:.0f} km²，超过安全上限 {job.max_area_km2:.0f} km²，"
                "请缩小范围或调高上限"
            )

        cached = cache.load(area.bbox, layer_types)
        if cached is not None:
            self._progress(0.70, "命中本地缓存")
            logbus.info("抓取命中本地缓存")
            return cached

        result: dict[LayerType, gpd.GeoDataFrame] = {}
        ckpt_key = checkpoint.key_for(area.bbox, layer_types)
        done = checkpoint.load(ckpt_key) or {}
        result.update(done)
        remaining = [ly for ly in layer_types if ly not in done]
        if done:
            self._progress(
                len(done) / len(layer_types) * self._WEIGHTS["fetch"] * 100,
                f"从断点恢复 {len(done)}/{len(layer_types)} 个图层",
            )
        if not remaining:
            checkpoint.clear(ckpt_key)

        n = len(remaining)
        for i, layer in enumerate(remaining):
            base = (len(done) + i) / len(layer_types) * self._WEIGHTS["fetch"]

            def cell_progress(frac: float, msg: str, _base=base, _n=len(layer_types)) -> None:
                overall = (_base + frac / _n * self._WEIGHTS["fetch"]) * 100
                self._progress(overall, msg)

            token.throw_if_cancelled()
            gdf = fetch.fetch_layer(layer, area.bbox, token, cell_progress, job.split_cell_km)
            result[layer] = gdf
            checkpoint.save_layer(ckpt_key, layer, gdf)

        try:
            cache.save(area.bbox, result)
            checkpoint.clear(ckpt_key)  # 完整成功后清除断点
        except Exception as exc:
            logger.warning("缓存写入失败（不影响结果）：%s", exc)
        return result

    # ------------------------------------------------------------------ clean

    def clean(self, layers: dict[LayerType, gpd.GeoDataFrame], token: CancelToken) -> dict:
        self.state = PipelineState.CLEANING
        token.throw_if_cancelled()
        self._progress(72.0, "几何修复与去重…")
        result = clean.clean_all(layers)
        counts = {ly.label: len(g) for ly, g in result.items() if len(g)}
        self._progress(85.0, f"清洗完成：{counts}")
        return result

    # ------------------------------------------------------------------ export

    def export(
        self,
        layers: dict,
        area: GeoArea,
        job: ExportJob,
        specs: list[LayerSpec],
        token: CancelToken,
    ) -> dict[str, str]:
        self.state = PipelineState.EXPORTING
        out: dict[str, str] = {}
        out_dir = Path(job.out_dir)
        enabled = [sp for sp in specs if sp.enabled]

        for fmt in job.formats:
            token.throw_if_cancelled()
            if fmt == "geojson":
                out["geojson"] = export.export_geojson(layers, out_dir)
            elif fmt == "gpkg":
                out["gpkg"] = export.export_gpkg(layers, out_dir)
            elif fmt == "shp":
                out["shp"] = export.export_shp(layers, out_dir)
            elif fmt == "svg":
                out["svg"] = export.render_map(
                    layers, area.bbox, enabled, out_dir / "map.svg",
                    dpi=job.dpi, figsize_in=job.figsize_in, basemap=job.basemap,
                )
            elif fmt == "png":
                if job.poster:
                    paper = "a0"
                    if job.poster_size is not None:
                        # 按长边匹配最接近的纸型
                        target = max(job.poster_size)
                        paper = min(
                            export.PAPER_SIZES,
                            key=lambda k: abs(max(export.PAPER_SIZES[k]) - target),
                        )
                    out["png_poster"] = export.render_map_poster(
                        layers, area.bbox, enabled, out_dir / "map_poster.png",
                        dpi=job.dpi, paper=paper,
                    )
                else:
                    out["png"] = export.render_map(
                        layers, area.bbox, enabled, out_dir / "map.png",
                        dpi=job.dpi, figsize_in=job.figsize_in, basemap=job.basemap,
                    )
            else:
                raise PipelineError(f"未知导出格式：{fmt}")
            self._progress(85.0 + 15.0 * (list(job.formats).index(fmt) + 1) / len(job.formats), f"已导出 {fmt}")
        return out

    # ------------------------------------------------------------------ run

    def run(
        self,
        query: str | None,
        bbox: tuple | None,
        fetch_job: FetchJob,
        export_job: ExportJob | None,
        token: CancelToken | None = None,
        resolved: GeoArea | None = None,
    ) -> PipelineResult:
        token = token or CancelToken()
        logbus.info(f"任务开始：{query or bbox}")
        try:
            area = self.resolve_area(query, bbox, resolved)
            raw = self.fetch(area, fetch_job, token)
            layers = self.clean(raw, token)
            exported: dict[str, str] = {}
            if export_job is not None:
                exported = self.export(layers, area, export_job, fetch_job.layers, token)
            self.state = PipelineState.DONE
            self._progress(100.0, "完成")
            logbus.info(f"任务完成：{area.display_name}")
            return PipelineResult(state=self.state, layers=layers, exported=exported, message=area.display_name)
        except PipelineError as exc:
            self.state = PipelineState.CANCELLED if token.cancelled else PipelineState.FAILED
            logbus.warn(f"任务{'取消' if token.cancelled else '失败'}：{exc}")
            return PipelineResult(state=self.state, message=str(exc))
