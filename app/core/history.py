"""抓取历史与书签：记录每次抓取的参数与成果，支持一键重抓。

记录存于 config/history.json，最多保留 50 条；超出时优先淘汰未加书签的旧记录。
书签只是记录上的一个标记，用于筛选与防清理。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.core.config import CONFIG_DIR
from app.core.logbus import debug, warn

HISTORY_FILE = CONFIG_DIR / "history.json"
MAX_ENTRIES = 50


@dataclass
class HistoryRecord:
    id: str
    ts: float  # 抓取完成时间戳
    area: str  # 区域显示名（地理编码结果）
    query: str | None
    bbox: list[float] | None  # [s, w, n, e]
    layers: list[str]  # 启用的图层 value 列表
    styles: dict[str, dict] = field(default_factory=dict)  # 当时的配色/线宽/透明度
    counts: dict[str, int] = field(default_factory=dict)  # layer_value → 要素数
    bookmarked: bool = False


def _load() -> list[HistoryRecord]:
    if not HISTORY_FILE.exists():
        return []
    try:
        raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return [HistoryRecord(**item) for item in raw]
    except Exception as exc:  # noqa: BLE001 - 损坏时重置
        warn(f"历史记录读取失败，已重置：{exc}")
        return []


def _save(records: list[HistoryRecord]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def all_records() -> list[HistoryRecord]:
    """全部记录，新→旧。"""
    return sorted(_load(), key=lambda r: r.ts, reverse=True)


def add(
    *,
    area: str,
    query: str | None,
    bbox: list[float] | None,
    layers: list[str],
    styles: dict[str, dict],
    counts: dict[str, int],
) -> HistoryRecord:
    """新增一条记录并落盘。"""
    rec = HistoryRecord(
        id=uuid.uuid4().hex[:12],
        ts=time.time(),
        area=area,
        query=query,
        bbox=bbox,
        layers=layers,
        styles=styles,
        counts=counts,
    )
    records = _load()
    records.append(rec)
    # 超限：先删未书签的最旧记录
    while len(records) > MAX_ENTRIES:
        victim = next((r for r in sorted(records, key=lambda r: r.ts) if not r.bookmarked), None)
        if victim is None:  # 全是书签，放弃最旧的书签
            victim = min(records, key=lambda r: r.ts)
        records.remove(victim)
    _save(records)
    debug(f"历史记录已写入：{area}")
    return rec


def remove(record_id: str) -> bool:
    records = _load()
    kept = [r for r in records if r.id != record_id]
    if len(kept) == len(records):
        return False
    _save(kept)
    return True


def toggle_bookmark(record_id: str) -> bool | None:
    """切换书签状态，返回新状态；记录不存在返回 None。"""
    records = _load()
    for r in records:
        if r.id == record_id:
            r.bookmarked = not r.bookmarked
            _save(records)
            return r.bookmarked
    return None


def clear(bookmarks_only: bool = False) -> int:
    """清空记录。bookmarks_only=True 时只清空未加书签的，返回删除条数。"""
    records = _load()
    if bookmarks_only:
        kept = [r for r in records if r.bookmarked]
        n = len(records) - len(kept)
        _save(kept)
        return n
    n = len(records)
    _save([])
    return n


def find(record_id: str) -> HistoryRecord | None:
    for r in _load():
        if r.id == record_id:
            return r
    return None
