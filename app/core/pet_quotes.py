"""Calico 电子宠物专属语录库。

语料在 app/data/pet_quotes_{zh,en}.txt（由 scripts/gen_pet_quotes.py 生成，
与 cateaster 的加载文案相互独立）。运行时按当前语言取随机一条，
并避免与最近 N 条重复。
"""

from __future__ import annotations

import random

from app.core import i18n
from app.core.assets import data_dir

_NO_REPEAT = 50

_cache: dict[str, list[str]] = {}
_recent: list[str] = []


def _lines() -> list[str]:
    lang = "en" if i18n.language() == "en" else "zh"
    if lang not in _cache:
        path = data_dir(f"pet_quotes_{lang}.txt")
        try:
            _cache[lang] = [
                line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except OSError:
            _cache[lang] = ["喵。" if lang == "zh" else "Meow."]
    return _cache[lang]


def pet_line() -> str:
    """随机取一条宠物语录（跟随当前语言，尽量避免近期重复）。"""
    lines = _lines()
    if len(lines) <= len(_recent):
        _recent.clear()
    candidates = [s for s in lines if s not in _recent] or lines
    line = random.choice(candidates)
    _recent.append(line)
    del _recent[:-_NO_REPEAT]
    return line
