"""自动更新检查：对照 GitHub Releases 最新版本号，只提示、不强制。

默认检查本仓库（Wing-Smith/Catlas）的 Releases；
Settings.update_url 可填写其他 Releases API 地址作为覆盖。
超时/网络错误不会抛出到调用方（check_status），绝不影响启动。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests

from app.core.config import SETTINGS, USER_AGENT
from app.core.version import APP_VERSION

TIMEOUT_S = 8

GITHUB_REPO = "Wing-Smith/Catlas"
DEFAULT_UPDATE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"


@dataclass
class ReleaseInfo:
    version: str
    url: str  # 发布页（浏览器打开）


@dataclass
class UpdateStatus:
    """一次更新检查的完整结果，供界面展示连接状态与版本对比。"""

    connected: bool          # GitHub API 是否可达
    current: str = APP_VERSION
    latest: str | None = None   # 解析到的最新版本号；连接成功但无 Release 时为 None
    url: str = RELEASES_PAGE    # 最新版本发布页
    error: str = ""          # 连接失败原因（截断）
    checking: bool = field(default=False)  # 正在检查中（界面中间态）


def api_url() -> str:
    """实际使用的 Releases API 地址：用户自定义优先，否则用本仓库默认。"""
    return (SETTINGS.update_url or "").strip() or DEFAULT_UPDATE_API


def _parse_ver(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text)
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest: str) -> bool:
    return _parse_ver(latest) > _parse_ver(APP_VERSION)


def is_older(latest: str) -> bool:
    """本地版本比 GitHub 最新发行版还新（未发行/开发构建）。"""
    return _parse_ver(latest) < _parse_ver(APP_VERSION)


def check_latest(timeout: int = TIMEOUT_S) -> ReleaseInfo | None:
    """拉取最新发布；网络错误或解析失败返回 None（静默）。"""
    try:
        resp = requests.get(
            api_url(),
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None
    tag = (data.get("tag_name") or "").strip().lstrip("vV")
    if not tag:
        return None
    return ReleaseInfo(version=tag, url=data.get("html_url") or RELEASES_PAGE)


def check_status(timeout: int = TIMEOUT_S) -> UpdateStatus:
    """带连接状态的一次检查：异常吞掉转为 UpdateStatus.error。"""
    try:
        resp = requests.get(
            api_url(),
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return UpdateStatus(connected=False, error=str(exc)[:120])
    tag = (data.get("tag_name") or "").strip().lstrip("vV") or None
    return UpdateStatus(
        connected=True,
        latest=tag,
        url=data.get("html_url") or RELEASES_PAGE,
    )
