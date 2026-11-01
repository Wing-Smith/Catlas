"""生成 Calico 专属语录库（zh / en 各约 1466 条）。

槽位组合展开 + 确定性打散，输出到 app/data/pet_quotes_zh.txt / pet_quotes_en.txt。
语料与 app/core/cateaster.py 的加载文案完全独立。
"""

from __future__ import annotations

import itertools
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = 1466

ZH_WHO = [
    "Calico", "本喵", "小猫咪 Calico", "黑猫大人", "Calico 酱", "喵",
    "本猫", "Calico 小姐", "一只路过的黑猫", "地图房常驻猫",
]
ZH_ADV = [
    "刚刚", "偷偷", "优雅地", "认真地", "慢吞吞地", "轻手轻脚地", "理直气壮地",
    "趁没人注意", "一边伸懒腰一边", "打着哈欠", "眯着眼睛", "翘着尾巴",
    "故作镇定地", "高高兴兴地",
]
ZH_VERB = [
    "巡视了", "检查了", "踩过了", "蹲在了", "打量着", "对比了", "数了一遍",
    "收藏了", "标注了", "画了个圈在", "闻了闻", "蹭了蹭", "拍了拍", "守着",
    "研究起", "评估了",
]
ZH_OBJ = [
    "新抓的路网", "刚导出的 SVG", "缓存的瓦片", "刚才的选区", "世界地图",
    "昆明的水系", "那条骑行路线", "底图配色", "日志文件", "书签列表",
    "数据文件夹", "今天的坐标", "等高线", "行政区边界",
]
ZH_TAIL = [
    "。",
    "，满意地喵了一声。",
    "，看来没毛病。",
    "，这才是地图嘛。",
    "，尾巴翘得老高。",
    "，奖励自己一根小鱼干。",
    "，嗯，数据味道不错。",
    "，就按这个方向走。",
    "，人类学着点。",
    "，喵。",
    "，回头记得署名 OSM。",
    "，比昨天的更漂亮。",
]

EN_WHO = [
    "Calico", "This cat", "Your mascot", "Calico the cat", "The little cartographer",
    "Madame Calico", "A certain black cat", "The purrfessional",
]
EN_ADV = [
    "just", "secretly", "elegantly", "carefully", "slowly", "quietly", "smugly",
    "while yawning", "half-asleep", "tail held high", "pretending to be busy", "happily",
]
EN_VERB = [
    "inspected", "walked across", "sat on", "counted", "reviewed", "marked",
    "circled", "sniffed", "nudged", "guarded", "studied", "approved",
]
EN_OBJ = [
    "the fresh road network", "the exported SVG", "the cached tiles", "your latest selection",
    "the world map", "the river data", "that bike route", "the basemap colors",
    "the log file", "the bookmark list", "the data folder", "today's coordinates",
]
EN_TAIL = [
    ".",
    " and purred approvingly.",
    " — looks purrfect.",
    ", tail up.",
    ", earning a fish treat.",
    ". Meow.",
    ", as a true professional would.",
    ". Data smells good today.",
    ", noting to credit OSM.",
    ", nicer than yesterday's.",
]


def build_zh() -> list[str]:
    lines = [
        f"{w}{a}{v}{o}{t}"
        for w, a, v, o, t in itertools.product(
            ZH_WHO, ZH_ADV, ZH_VERB, ZH_OBJ, ZH_TAIL
        )
    ]
    return lines[:TARGET]


def build_en() -> list[str]:
    lines = [
        f"{w} {a} {v} {o}{t}"
        for w, a, v, o, t in itertools.product(
            EN_WHO, EN_ADV, EN_VERB, EN_OBJ, EN_TAIL
        )
    ]
    return lines[:TARGET]


def shuffle(lines: list[str], seed: int) -> list[str]:
    lines = lines[:]
    random.Random(seed).shuffle(lines)
    return lines


def main() -> None:
    zh = shuffle(build_zh(), seed=20261101)
    en = shuffle(build_en(), seed=20261101)
    out_dir = ROOT / "app" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pet_quotes_zh.txt").write_text("\n".join(zh) + "\n", encoding="utf-8")
    (out_dir / "pet_quotes_en.txt").write_text("\n".join(en) + "\n", encoding="utf-8")
    print(f"zh: {len(zh)} lines, unique={len(set(zh))}")
    print(f"en: {len(en)} lines, unique={len(set(en))}")


if __name__ == "__main__":
    main()
