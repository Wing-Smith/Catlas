"""打包资源定位：兼容源码运行与打包运行（PyInstaller / Nuitka）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def asset(name: str) -> Path:
    """返回 assets 目录内文件的绝对路径。

    依次尝试：PyInstaller 临时目录 / Nuitka onefile 解包目录 /
    exe 同级目录（standalone）/ 源码目录。
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)  # PyInstaller 与 Nuitka onefile 均提供
    if meipass:
        candidates.append(Path(meipass) / "app" / "assets" / name)
    candidates.append(Path(sys.executable).parent / "app" / "assets" / name)
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / name)
    for path in candidates:
        if path.exists():
            return path
    return candidates[-1]


def data_dir(*parts: str) -> Path:
    """返回 app/data 下的目录（世界底图等），规则同 asset()。"""
    rel = Path("app", "data", *parts)
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / rel)
    candidates.append(Path(sys.executable).parent / rel)
    candidates.append((Path(__file__).resolve().parent.parent / "data").joinpath(*parts))
    for path in candidates:
        if path.exists():
            return path
    return candidates[-1]
