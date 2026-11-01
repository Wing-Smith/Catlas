"""抓取结果本地缓存：bbox+图层 → SHA1 键控 parquet，LRU 容量清理。"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from pathlib import Path

import geopandas as gpd

from app.core.config import CACHE_ROOT_DIR
from app.core.models import BBox, LayerType

logger = logging.getLogger(__name__)

CACHE_ROOT = CACHE_ROOT_DIR / "overpass"
MAX_BYTES_DEFAULT = 1024 * 1024 * 1024  # 1 GiB


def _key(bbox: BBox, layers: list[LayerType]) -> str:
    s, w, n, e = (round(v, 5) for v in bbox)
    layer_str = ",".join(sorted(ly.value for ly in layers))
    raw = f"{s},{w},{n},{e}|{layer_str}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def cache_dir_for(bbox: BBox, layers: list[LayerType]) -> Path:
    return CACHE_ROOT / _key(bbox, layers)


def load(bbox: BBox, layers: list[LayerType]) -> dict[LayerType, gpd.GeoDataFrame] | None:
    """命中缓存返回图层字典，否则 None。"""

    d = cache_dir_for(bbox, layers)
    meta_file = d / "meta.json"
    if not meta_file.exists():
        return None
    try:
        result: dict[LayerType, gpd.GeoDataFrame] = {}
        for layer in layers:
            f = d / f"{layer.value}.parquet"
            if not f.exists():
                return None
            result[layer] = gpd.read_parquet(f)
        return result
    except Exception as exc:
        logger.warning("缓存读取失败 %s：%s", d, exc)
        shutil.rmtree(d, ignore_errors=True)
        return None


def save(bbox: BBox, layers: dict[LayerType, gpd.GeoDataFrame], max_bytes: int = MAX_BYTES_DEFAULT) -> None:
    d = cache_dir_for(bbox, list(layers))
    tmp = d.with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    for layer, gdf in layers.items():
        gdf.to_parquet(tmp / f"{layer.value}.parquet", index=False)
    (tmp / "meta.json").write_text(
        json.dumps(
            {"bbox": bbox, "layers": [ly.value for ly in layers], "saved_at": time.time()},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    prune(max_bytes)


def prune(max_bytes: int = MAX_BYTES_DEFAULT) -> None:
    """按修改时间 LRU 清理，控制缓存总大小。"""

    if not CACHE_ROOT.exists():
        return
    entries = sorted(CACHE_ROOT.iterdir(), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in entries)
    removed = 0
    for entry in entries:
        if total <= max_bytes:
            break
        size = entry.stat().st_size
        shutil.rmtree(entry, ignore_errors=True)
        total -= size
        removed += 1
    if removed:
        logger.info("缓存清理：移除 %d 个过期条目", removed)


def count_entries() -> int:
    """当前缓存条目数（未命中过的目录不计）。"""

    if not CACHE_ROOT.exists():
        return 0
    return sum(1 for d in CACHE_ROOT.iterdir() if d.is_dir() and (d / "meta.json").exists())


def clear() -> int:
    """清空全部缓存，返回删除的条目数。"""

    if not CACHE_ROOT.exists():
        return 0
    entries = list(CACHE_ROOT.iterdir())
    shutil.rmtree(CACHE_ROOT, ignore_errors=True)
    return len(entries)
