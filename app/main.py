"""GUI 入口：python -m app.main"""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.core import i18n
from app.core.assets import asset
from app.core.config import SETTINGS
from app.ui.main_window import MainWindow
from app.ui.splash import SplashScreen
from app.ui.theme import apply_fluent_theme


def _install_crash_hooks() -> None:
    """未捕获异常 → LogBus + 崩溃文件（exe 无控制台时的唯一取证途径）。"""

    import threading
    import traceback
    from pathlib import Path

    from app.core import logbus

    def _write_crash(text: str) -> None:
        logbus.error(text.splitlines()[0] if text else "unknown error")
        try:
            from app.core.config import CONFIG_DIR

            target = Path(CONFIG_DIR) / "catlas_crash.log"
            target.write_text(text, encoding="utf-8", errors="replace")
        except Exception:
            pass

    def _hook(exc_type, exc, tb) -> None:
        _write_crash("".join(traceback.format_exception(exc_type, exc, tb)))

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        _write_crash("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

    sys.excepthook = _hook
    threading.excepthook = _thread_hook


_SINGLE_INSTANCE_MEM = None  # 必须常驻，被 GC 会释放共享内存导致单实例锁失效


def _activate_existing_instance() -> None:
    """已有实例在运行：把它的窗口拉到前台，然后本进程退出。"""

    try:
        import win32con
        import win32gui

        def _enum(hwnd, _extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title.startswith("Catlas"):  # 标题随语言变化，只匹配前缀
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)

        win32gui.EnumWindows(_enum, None)
    except Exception:
        pass  # 找不到窗口就静默退出


def _ensure_single_instance() -> bool:
    """返回 True 表示本进程可以继续启动；False 表示已有实例在运行。"""

    global _SINGLE_INSTANCE_MEM
    from PySide6.QtCore import QSharedMemory

    mem = QSharedMemory("Catlas-SingleInstance-v1")
    if mem.attach():  # 已存在 → 旧实例还活着（Windows 下进程退出会自动释放）
        mem.detach()
        return False
    if not mem.create(1):
        return False
    _SINGLE_INSTANCE_MEM = mem  # 常驻引用，直到进程退出
    return True


def main() -> int:
    _install_crash_hooks()
    if not _ensure_single_instance():
        _activate_existing_instance()
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName("Catlas")
    app.setApplicationDisplayName("Catlas")
    app.setOrganizationName("Catlas")
    app.setWindowIcon(QIcon(str(asset("app.ico"))))
    i18n.set_language(SETTINGS.language)  # 启动前应用已保存的语言
    apply_fluent_theme(SETTINGS.theme)

    splash = SplashScreen()
    splash.show()

    def _show_main() -> None:
        window = MainWindow()
        window.show()
        splash.finish()  # 主窗口已就绪，闪屏淡出
        if SETTINGS.first_run:
            QTimer.singleShot(350, lambda: _show_first_run_guide(window))

    def _show_first_run_guide(window: MainWindow) -> None:
        from app.ui.first_run import FirstRunGuide

        guide = FirstRunGuide(window)
        guide.exec()
        SETTINGS.first_run = False
        SETTINGS.save()

    QTimer.singleShot(1400, _show_main)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
