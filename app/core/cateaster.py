"""卡莉可彩蛋：加载等待与完成通知里轮换的猫言猫语。

跟随 i18n 当前语言；调用方每次取随机一条，避免顺序重复感。
"""

from __future__ import annotations

import random

from app.core import i18n

_LINES: dict[str, list[str]] = {
    "zh": [
        "Calico 正在扒拉路网…",
        "Calico 踮起脚核对建筑轮廓…",
        "Calico 盯着水面，数起了涟漪…",
        "Calico 在绿地里打了个滚…",
        "Calico 把瓦片整齐地码好…",
        "Calico 甩甩尾巴，画好了边界…",
        "Calico 闻了闻坐标，说就是这个方向…",
        "Calico 蜷在服务器上取暖，顺便等数据…",
        "数据到手，Calico 的尾巴翘起来了。",
        "Calico 把导出的文件推到你面前，喵了一声。",
        "Calico 审查完毕：这批数据很干净。",
        "Calico 伸了个懒腰，制图完成。",
    ],
    "en": [
        "Calico is pawing at the roads…",
        "Calico stands on tiptoe checking building outlines…",
        "Calico stares at the water, counting ripples…",
        "Calico rolls around on the green…",
        "Calico stacks the tiles neatly…",
        "Calico flicks her tail and draws the boundary…",
        "Calico sniffs the coordinates — this way…",
        "Calico curls up on the server, waiting for data…",
        "Data secured. Calico's tail is up.",
        "Calico pushes the exported files toward you and meows.",
        "Calico approves: this batch of data is clean.",
        "Calico stretches. Mapping done.",
    ],
}


def cat_line() -> str:
    """随机取一条猫言猫语（跟随当前语言）。"""
    lines = _LINES.get(i18n.language()) or _LINES["zh"]
    return random.choice(lines)
