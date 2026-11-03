"""版本号单一来源。发新版只改这里；打包脚本从此读取。"""

from __future__ import annotations

APP_NAME = "Catlas"
APP_VERSION = "1.2.9"
APP_VERSION_TUPLE = (1, 2, 9)  # Windows 资源文件需要数字元组


def version_str() -> str:
    return APP_VERSION
