"""系统级通知（Windows Toast）：抓取完成 / 导出完成 / 错误等。

优先走 WinRT ToastNotificationManager（windows-toasts），失败时回退为
应用内 InfoBar，保证任何环境下都有反馈。
"""

from __future__ import annotations

import logging
import re
import threading

logger = logging.getLogger(__name__)


def _plain(message: str) -> str:
    """InfoBar 文案里的 HTML 换行换成纯文本换行，供系统通知使用。"""

    return re.sub(r"<br\s*/?>", "\n", message).strip()


def notify_system(title: str, message: str) -> bool:
    """尝试弹 Windows 系统通知；成功返回 True。后台线程调用，绝不阻塞 GUI。"""

    def _show() -> None:
        try:
            from windows_toasts import Toast, ToastImage, WindowsToaster

            from app.core.assets import asset

            toaster = WindowsToaster("Catlas")
            toast = Toast([title, _plain(message)])
            # 绿色软件无 AUMID 快捷方式，系统查不到应用图标——
            # 改为把图标内嵌进通知内容区，任何环境下都显示猫图标
            icon = asset("icon.png")
            if icon.exists():
                toast.AddImage(ToastImage(str(icon)))
            toaster.show_toast(toast)
        except Exception as exc:  # noqa: BLE001 - 通知失败不应影响主流程
            logger.warning("系统通知发送失败：%s", exc)

    try:
        threading.Thread(target=_show, daemon=True, name="notify").start()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("系统通知线程启动失败：%s", exc)
        return False
