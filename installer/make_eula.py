"""生成安装向导用的双语用户协议 EULA.rtf（GBK/cp936 编码，Inno 原生支持）。

修改文案后直接重跑本脚本即可：
    .venv\\Scripts\\python.exe installer\\make_eula.py
"""

from __future__ import annotations

import os
from pathlib import Path

OUT = Path(__file__).resolve().parent / "EULA.rtf"

SECTIONS_ZH = [
    ("Catlas 最终用户许可协议", True),
    ("重要提示：安装即表示您已阅读并同意本协议全部条款。", False),
    ("一、版权与授权", True),
    ("本软件 Copyright (c) 2026 Wing North Studio，保留全部权利。"
     "本协议授予您一项非独占、不可转让的许可：您可以免费安装并使用本软件，"
     "可以为非商业目的复制和分发本软件的原版安装包。"
     "您不得对本软件进行反向工程、反编译、反汇编，不得出租、出售或转授权本软件。", False),
    ("二、数据来源与版权归属", True),
    ("本软件通过 OpenStreetMap（OSM）及其社区服务获取地理数据。"
     "OSM 数据版权归 OpenStreetMap contributors 所有，依据 ODbL（Open Database License）授权。"
     "您基于 OSM 数据制作并公开发布的成果，须按 ODbL 要求署名"
     "「© OpenStreetMap contributors」并以相同协议共享衍生数据库。"
     "软件内置的 Esri World Imagery 等第三方底图仅用于在线浏览与位置对齐，"
     "您不得批量下载、导出或再分发这些影像数据，并须遵守其服务条款。"
     "使用本软件访问任何数据服务时，您须遵守该服务的速率限制与使用政策。", False),
    ("三、免责声明", True),
    ("本软件按「现状」提供，不附带任何明示或默示的担保，"
     "包括但不限于适销性、特定用途适用性及非侵权的担保。"
     "在任何情况下，Wing North Studio 均不对因使用或无法使用本软件而产生的"
     "任何直接或间接损失承担责任。", False),
    ("四、隐私", True),
    ("本软件不收集、不上传任何个人信息。所有配置与缓存数据仅保存在您的本机。"
     "软件发起的网络请求仅限于您配置的数据源地址。", False),
]

SECTIONS_EN = [
    ("Catlas End User License Agreement", True),
    ("IMPORTANT: Installing this software indicates that you have read and agree to all terms below.", False),
    ("1. Copyright and License", True),
    ("This software is Copyright (c) 2026 Wing North Studio. All rights reserved. "
     "This agreement grants you a non-exclusive, non-transferable license to install and use "
     "this software free of charge, and to redistribute the original installer for "
     "non-commercial purposes. You may not reverse-engineer, decompile or disassemble the "
     "software, nor rent, sell or sublicense it.", False),
    ("2. Data Sources and Attribution", True),
    ("This software fetches geodata via OpenStreetMap (OSM) and community services. "
     "OSM data is (c) OpenStreetMap contributors, licensed under ODbL. Any published work "
     "derived from OSM data must credit \"(c) OpenStreetMap contributors\" and share "
     "derived databases under the same license. Third-party basemaps such as Esri World "
     "Imagery are provided for online preview and alignment only: bulk download, export or "
     "redistribution of these images is prohibited. You must respect rate limits and terms "
     "of every data service accessed through this software.", False),
    ("3. Disclaimer of Warranty", True),
    ("The software is provided \"as is\", without warranty of any kind, express or implied, "
     "including but not limited to warranties of merchantability, fitness for a particular "
     "purpose and non-infringement. In no event shall Wing North Studio be liable for any "
     "direct or indirect damages arising from the use of or inability to use this software.", False),
    ("4. Privacy", True),
    ("This software collects and uploads no personal data. All configuration and cache data "
     "is stored locally on your machine. Network requests are made only to the data sources "
     "you configure.", False),
]


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _para(text: str, bold: bool) -> str:
    size = "\\fs32" if bold else "\\fs22"
    weight = "\\b" if bold else ""
    end = "\\b0" if bold else ""
    return f"\\pard{weight}{size} {_esc(text)}{end}\\par\\par"


def build() -> None:
    body = "".join(_para(t, b) for t, b in SECTIONS_ZH)
    body += "\\page\\par\n"
    body += "".join(_para(t, b) for t, b in SECTIONS_EN)
    rtf = (
        "{\\rtf1\\ansi\\ansicpg936\\deff0"
        "{\\fonttbl{\\f0\\fnil\\fcharset134 Microsoft YaHei;}"
        "{\\f1\\fnil\\fcharset0 Segoe UI;}}"
        "\\viewkind4\\uc1\\pard\\lang2052\\f0\n"
        + body
        + "}"
    )
    OUT.write_bytes(rtf.encode("cp936", errors="replace"))
    print(f"[OK] {OUT} ({OUT.stat().st_size} bytes, cp936)")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    build()
