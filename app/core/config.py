"""全局配置：Overpass 镜像、限流、缓存上限。

可从 platformdirs 配置目录下的 config.json 覆盖默认值。
便携模式：exe 同级（或源码根目录）放置 portable.flag，
配置/缓存/历史全部重定向到程序目录下的 CatlasData/。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_cache_path, user_config_dir

_APP_NAME = "osm-map-tool"


def _portable_root() -> Path | None:
    """检测便携模式标记文件 portable.flag 所在目录。"""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass))
    candidates.append(Path(sys.executable).parent)
    candidates.append(Path(__file__).resolve().parent.parent.parent)
    for root in candidates:
        if (root / "portable.flag").exists():
            return root
    return None


_PORTABLE_ROOT = _portable_root()
PORTABLE = _PORTABLE_ROOT is not None


def _config_dir() -> Path:
    if _PORTABLE_ROOT is not None:
        return _PORTABLE_ROOT / "CatlasData" / "config"
    return Path(user_config_dir(_APP_NAME))


def _cache_dir() -> Path:
    if _PORTABLE_ROOT is not None:
        return _PORTABLE_ROOT / "CatlasData" / "cache"
    return user_cache_path(_APP_NAME)


CONFIG_DIR = _config_dir()
CACHE_ROOT_DIR = _cache_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_OVERPASS_ENDPOINTS = [
    # .de 独立后端（主入口背后的两台服务器，限流各自独立，故障时可直连）
    "https://gall.openstreetmap.de/api/interpreter",
    "https://lambert.openstreetmap.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]

DEFAULT_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

USER_AGENT = "Catlas/1.3.2 (OSM geodata tool)"


@dataclass
class Settings:
    overpass_endpoints: list[str] = field(default_factory=lambda: list(DEFAULT_OVERPASS_ENDPOINTS))
    nominatim_url: str = DEFAULT_NOMINATIM_URL
    # Overpass 公共实例建议间隔 ≥1s；多镜像间也要间隔
    request_interval_s: float = 1.2
    http_timeout_s: int = 60
    overpass_timeout_s: int = 180
    cache_max_mb: int = 1024
    # 超过该面积必须二次确认（GUI）或显式允许（CLI）
    max_area_km2: float = 200.0
    # 分块抓取的单格边长（km）
    split_cell_km: float = 5.0
    # 界面语言：zh / en
    language: str = "zh"
    # 主题：auto / dark / light
    theme: str = "auto"
    # Calico 的小窝（关于页图标连点 7 次解锁/关闭，持久化）
    pet_corner: bool = False
    # 首次启动引导（看完即置 False，不再显示）
    first_run: bool = True
    # 自动更新检查：GitHub Releases API 地址，留空则用内置默认（本仓库）
    update_url: str = ""

    @classmethod
    def load(cls) -> "Settings":
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
                return cls(**{k: v for k, v in data.items() if k in known})
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
        )


SETTINGS = Settings.load()
