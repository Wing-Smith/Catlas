"""运行时日志总线：core 层的事件流，跨线程订阅，GUI 日志页消费。

纯 Python 实现，不依赖 Qt；订阅回调在产生日志的线程中被调用，
GUI 侧应通过 Qt 信号转发（emit 本身是线程安全的，AutoConnection 会排队到 GUI 线程）。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

Subscriber = Callable[[str, str], None]  # (level, message)

_LOCK = threading.Lock()
_SUBS: list[Subscriber] = []
_BUFFER: list[tuple[float, str, str]] = []
_BUFFER_MAX = 500

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")


def subscribe(fn: Subscriber) -> None:
    with _LOCK:
        _SUBS.append(fn)


def unsubscribe(fn: Subscriber) -> None:
    with _LOCK:
        if fn in _SUBS:
            _SUBS.remove(fn)


def log(level: str, message: str) -> None:
    if level not in LEVELS:
        level = "INFO"
    with _LOCK:
        _BUFFER.append((time.time(), level, message))
        if len(_BUFFER) > _BUFFER_MAX:
            del _BUFFER[: len(_BUFFER) - _BUFFER_MAX]
        subs = list(_SUBS)
    for fn in subs:
        try:
            fn(level, message)
        except Exception:
            pass  # 日志消费失败不影响主流程


def debug(message: str) -> None:
    log("DEBUG", message)


def info(message: str) -> None:
    log("INFO", message)


def warn(message: str) -> None:
    log("WARN", message)


def error(message: str) -> None:
    log("ERROR", message)


def recent(limit: int = 200) -> list[tuple[float, str, str]]:
    """取最近的缓冲记录（新→旧）。"""
    with _LOCK:
        return list(reversed(_BUFFER[-limit:]))


def clear_buffer() -> None:
    with _LOCK:
        _BUFFER.clear()
