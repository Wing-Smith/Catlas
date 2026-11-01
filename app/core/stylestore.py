"""图层样式预设：内置主题 + 用户自定义，存于 config/styles.json。

样式数据为 {layer_value: {"color": str, "width": float, "alpha": float}}。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import CONFIG_DIR
from app.core.models import LayerType

PRESET_FILE = CONFIG_DIR / "styles.json"

DEFAULT = "default"
NIGHT = "night"

# 内置预设
BUILTIN: dict[str, dict[str, dict]] = {
    DEFAULT: {
        LayerType.ROAD.value: {"color": "#8a8a8a", "width": 1.0, "alpha": 1.0},
        LayerType.WATER.value: {"color": "#aad3df", "width": 1.0, "alpha": 1.0},
        LayerType.GREEN.value: {"color": "#b6e29d", "width": 1.0, "alpha": 1.0},
        LayerType.BUILDING.value: {"color": "#d9c7b2", "width": 1.0, "alpha": 1.0},
    },
    NIGHT: {
        # 深色底图风格：亮线、低饱和面
        LayerType.ROAD.value: {"color": "#e8e8e8", "width": 1.2, "alpha": 0.95},
        LayerType.WATER.value: {"color": "#3d6e8f", "width": 1.0, "alpha": 0.85},
        LayerType.GREEN.value: {"color": "#4d7a4d", "width": 1.0, "alpha": 0.8},
        LayerType.BUILDING.value: {"color": "#8a7a66", "width": 1.0, "alpha": 0.75},
    },
}


def preset_names() -> list[str]:
    """全部预设：内置 + 用户保存的（保持插入顺序）。"""
    names = list(BUILTIN)
    names.extend(n for n in _load_user() if n not in BUILTIN)
    return names


def get(name: str) -> dict[str, dict] | None:
    """取预设内容；不存在返回 None。"""
    if name in BUILTIN:
        return BUILTIN[name]
    return _load_user().get(name)


def save(name: str, data: dict[str, dict]) -> None:
    """保存为用户预设（内置名覆盖为用户版，但不改 BUILTIN 本身）。"""
    user = _load_user()
    user[name] = data
    _save_user(user)


def remove(name: str) -> None:
    user = _load_user()
    if name in user:
        del user[name]
        _save_user(user)


def _load_user() -> dict[str, dict]:
    if not PRESET_FILE.exists():
        return {}
    try:
        return json.loads(PRESET_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - 损坏时重置
        return {}


def _save_user(data: dict[str, dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PRESET_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
