"""抓取历史与书签：增删、书签保护、容量淘汰。"""

from __future__ import annotations

import time

from app.core import history


def _add(area: str, bookmarked_via_toggle: bool = False, **kw):
    rec = history.add(
        area=area,
        query=kw.get("query"),
        bbox=kw.get("bbox"),
        layers=kw.get("layers", ["road"]),
        styles=kw.get("styles", {}),
        counts=kw.get("counts", {"road": 10}),
    )
    if bookmarked_via_toggle:
        history.toggle_bookmark(rec.id)
    return rec


class TestHistory:
    def test_add_and_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
        _add("区域A", query="kunming")
        _add("区域B", bbox=[24, 102, 26, 104])
        records = history.all_records()
        assert len(records) == 2
        assert records[0].area in ("区域A", "区域B")  # 新→旧

    def test_bookmark_toggle_and_find(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
        rec = _add("区域A")
        assert history.toggle_bookmark(rec.id) is True
        found = history.find(rec.id)
        assert found is not None and found.bookmarked
        assert history.toggle_bookmark(rec.id) is False

    def test_bookmarks_survive_cleanup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
        monkeypatch.setattr(history, "MAX_ENTRIES", 3)
        kept = _add("书签区", bookmarked_via_toggle=True)
        for i in range(5):
            _add(f"临时{i}")
            time.sleep(0.01)  # 保证 ts 严格递增
        records = history.all_records()
        assert len(records) == 3
        ids = {r.id for r in records}
        assert kept.id in ids  # 书签必然保留
        assert history.find(kept.id).bookmarked

    def test_remove_and_clear(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
        a = _add("区域A")
        b = _add("区域B", bookmarked_via_toggle=True)
        c = _add("区域C")
        assert history.remove(a.id) is True
        assert history.remove("不存在") is False
        assert len(history.all_records()) == 2

        # 保留书签的清空：删掉 c，留下 b
        n = history.clear(bookmarks_only=True)
        assert n == 1
        remaining = history.all_records()
        assert [r.id for r in remaining] == [b.id]

        # 全清
        n = history.clear()
        assert n == 1
        assert history.all_records() == []
