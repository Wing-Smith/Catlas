"""自动更新检查：对照 GitHub Releases 最新版本号，只提示、不强制。

配置项 Settings.update_url 填 Releases API 地址，例如：
    https://api.github.com/repos/<owner>/<repo>/releases/latest
留空则完全关闭检查。超时/网络错误一律静默，绝不影响启动。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from app.core.config import SETTINGS, USER_AGENT
from app.core.version import APP_VERSION

TIMEOUT_S = 8


@dataclass
class ReleaseInfo:
    version: str
    url: str  # 发布页（浏览器打开）


def _parse_ver(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text)
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest: str) -> bool:
    return _parse_ver(latest) > _parse_ver(APP_VERSION)


def check_latest(timeout: int = TIMEOUT_S) -> ReleaseInfo | None:
    """拉取最新发布；未配置 update_url 或解析失败返回 None。"""
    api = (SETTINGS.update_url or "").strip()
    if not api:
        return None
    resp = requests.get(
        api,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    tag = (data.get("tag_name") or "").strip().lstrip("vV")
    if not tag:
        return None
    return ReleaseInfo(version=tag, url=data.get("html_url") or "")
