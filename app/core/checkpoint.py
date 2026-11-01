"""抓取检查点：按图层落盘，崩溃 / 取消 / 失败后下次自动续传。

检查点保存在 config 目录的 checkpoint/ 下，按 bbox + 图层集合哈希分键，
每个完成的图层单独存 GeoJSON，附带 24 小时有效期。
任务成功完成后立即清除；失败或取消则保留，供下次启动时恢复。
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import geopandas as gpd

from app.core.config import CONFIG_DIR
from app.core.logbus import info, warn
from app.core.models import BBox, LayerType

CKPT_DIR = CONFIG_DIR / "checkpoint"
MAX_AGE_H = 24.0


def key_for(bbox: BBox, layers: list[LayerType]) -> str:
    """同一 bbox + 同一图层集合 → 同一检查点键。"""
    raw = "|".join(f"{v:.6f}" for v in bbox) + "|" + ",".join(sorted(ly.value for ly in layers))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _state_path(key: str) -> Path:
    return CKPT_DIR / f"{key}.json"


def _layer_path(key: str, layer: LayerType) -> Path:
    return CKPT_DIR / f"{key}_{layer.value}.geojson"


def load(key: str) -> dict[LayerType, gpd.GeoDataFrame] | None:
    """加载已完成的图层；过期 / 损坏则整体作废。"""
    state_file = _state_path(key)
    if not state_file.exists():
        return None
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if time.time() - state.get("updated", 0) > MAX_AGE_H * 3600:
            warn("检查点已过期（>24h），放弃恢复")
            clear(key)
            return None
        result: dict[LayerType, gpd.GeoDataFrame] = {}
        for name, fname in state.get("files", {}).items():
            fpath = CKPT_DIR / fname
            if not fpath.exists():
                clear(key)
                return None
            gdf = gpd.read_file(fpath, engine="pyogrio")
            result[LayerType(name)] = gdf
        if result:
            names = "、".join(ly.label for ly in result)
            info(f"从检查点恢复 {len(result)} 个图层：{names}")
        return result or None
    except Exception as exc:  # noqa: BLE001 - 检查点损坏不阻断抓取
        warn(f"检查点读取失败，重新抓取：{exc}")
        clear(key)
        return None


def save_layer(key: str, layer: LayerType, gdf: gpd.GeoDataFrame) -> None:
    """标记某图层已完成（落盘 + 更新状态文件）。"""
    if gdf.empty:
        return
    try:
        CKPT_DIR.mkdir(parents=True, exist_ok=True)
        fname = f"{key}_{layer.value}.geojson"
        gdf.to_file(CKPT_DIR / fname, driver="GeoJSON", engine="pyogrio")
        state_file = _state_path(key)
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
        else:
            state = {"files": {}}
        state["files"][layer.value] = fname
        state["updated"] = time.time()
        state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        warn(f"检查点写入失败（不影响本次结果）：{exc}")


def clear(key: str) -> None:
    state_file = _state_path(key)
    files = []
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            files = list(state.get("files", {}).values())
        except Exception:  # noqa: BLE001
            pass
        state_file.unlink(missing_ok=True)
    for fname in files:
        (CKPT_DIR / fname).unlink(missing_ok=True)
