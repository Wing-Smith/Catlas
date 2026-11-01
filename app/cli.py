"""命令行入口：M1 数据管线验证与无 GUI 使用。

用法示例：
    python -m app.cli "北京市 东城区" --formats geojson png --out out/dongcheng
    python -m app.cli --bbox 39.93 116.40 39.95 116.42 --formats shp --out out/test
"""

from __future__ import annotations

import argparse
import sys
import time

from app.core import cache, tiles
from app.core.config import SETTINGS
from app.core.models import CancelToken, ExportJob, FetchJob, LayerSpec, LayerType, PipelineState
from app.core.pipeline import Pipeline


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="catlas", description="Catlas 猫图集 · OSM 地理数据抓取与制图工具（CLI）")
    src = p.add_mutually_exclusive_group()
    src.add_argument("query", nargs="?", help="地名，如：北京市 东城区")
    src.add_argument("--bbox", nargs=4, type=float, metavar=("S", "W", "N", "E"), help="坐标范围")
    p.add_argument("--layers", nargs="+", choices=[l.value for l in LayerType],
                   default=[l.value for l in LayerType], help="图层（默认全部）")
    p.add_argument("--formats", nargs="+",
                   default=["geojson"], choices=["geojson", "gpkg", "shp", "svg", "png"])
    p.add_argument("--out", default="out", help="输出目录")
    p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--max-area", type=float, default=SETTINGS.max_area_km2, help="面积上限 km²")
    p.add_argument("--cell-km", type=float, default=SETTINGS.split_cell_km, help="分块边长 km")
    p.add_argument("--basemap", default=None,
                   choices=[*tiles.PROVIDERS.keys(), "none"],
                   help="瓦片底图源（svg/png 导出时叠加），默认无底图")
    p.add_argument("--clear-cache", action="store_true", help="清空缓存（含瓦片）后退出")
    p.add_argument("-y", "--yes", action="store_true", help="跳过大面积确认")
    return p.parse_args(argv)


def _progress(fraction: float, message: str) -> None:
    bar_len = 30
    filled = int(bar_len * min(fraction, 100.0) / 100.0)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r[{bar}] {fraction:5.1f}%  {message:<50}", end="", flush=True)
    if fraction >= 100:
        print()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.clear_cache:
        print(f"已清空 {cache.clear()} 个数据缓存条目、{tiles.clear_tile_cache()} 张瓦片缓存")
        return 0

    if not args.query and not args.bbox:
        print("错误：必须提供地名或 --bbox", file=sys.stderr)
        return 2

    layer_specs = [LayerSpec(LayerType(v)) for v in args.layers]

    # 预解析面积做确认
    probe = Pipeline(progress=lambda f, m: None)
    try:
        area = probe.resolve_area(args.query, tuple(args.bbox) if args.bbox else None)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if area.area_km2 > args.max_area and not args.yes:
        print(f"范围约 {area.area_km2:.0f} km² 超过上限 {args.max_area:.0f} km²；如确认请加 --max-area 或 -y", file=sys.stderr)
        return 3

    fetch_job = FetchJob(layers=layer_specs, max_area_km2=args.max_area, split_cell_km=args.cell_km)
    export_job = ExportJob(
        out_dir=args.out,
        formats=args.formats,
        dpi=args.dpi,
        basemap=None if args.basemap in (None, "none") else args.basemap,
    )

    print(f"目标：{area.display_name} | bbox={area.bbox} | 约 {area.area_km2:.2f} km²")
    print(f"图层：{', '.join(sp.layer.label for sp in layer_specs)} | 格式：{', '.join(args.formats)}")
    t0 = time.monotonic()

    pipeline = Pipeline(progress=_progress)
    result = pipeline.run(args.query, tuple(args.bbox) if args.bbox else None, fetch_job, export_job, CancelToken())

    if result.state is not PipelineState.DONE:
        print(f"\n失败：{result.message}", file=sys.stderr)
        return 1

    print(f"\n耗时 {time.monotonic() - t0:.1f}s，要素统计：")
    for layer, gdf in result.layers.items():
        print(f"  {layer.label:　<4} {len(gdf):>6} 条")
    if result.exported:
        print("导出文件：")
        for fmt, path in result.exported.items():
            print(f"  [{fmt}] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
