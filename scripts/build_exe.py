"""PyInstaller 打包脚本：调用 Catlas.spec 生成 Windows 应用。

用法（在项目根目录、虚拟环境激活后）：
    python scripts/build_exe.py

产物：dist/Catlas/Catlas.exe
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COLLECT_ALL = [
    "geopandas",
    "shapely",
    "pyogrio",
    "matplotlib",
    "qfluentwidgets",
    "qframelesswindow",
    "PySide6",
]

HIDDEN_IMPORTS = [
    "pyogrio",
    "pyarrow",
    "matplotlib.backends.backend_agg",
]


def main() -> int:
    if not (ROOT / ".venv").exists():
        print("请先创建 .venv 并安装依赖", file=sys.stderr)
        return 1

    python = ROOT / ".venv" / "Scripts" / "python.exe"
    subprocess.check_call([str(python), "-m", "pip", "install", "-q", "pyinstaller"])

    cmd = [str(python), "-m", "PyInstaller", "--noconfirm", str(ROOT / "Catlas.spec")]
    print(" ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    print(f"\n完成：{ROOT / 'dist' / 'Catlas' / 'Catlas.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
