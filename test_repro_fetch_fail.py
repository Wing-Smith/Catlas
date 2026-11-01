"""复现：抓取失败（地理编码 / 后台抓取）后 GUI 忙碌状态必须复位。"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

app = QApplication([])

from app.core.errors import GeocodeError, PipelineError
from app.core.models import GeoArea
from app.ui.main_window import MainWindow

# 离屏测试绝不发真系统通知（main_window 绑的是模块内引用，需patch它）
import app.ui.main_window as _mw_mod

_mw_mod.notify_system = lambda *a, **k: True

win = MainWindow()
win.show()
win.input_panel.query_edit.setText("昆明理工大学")

passed = True


def check(cond: bool, label: str) -> None:
    global passed
    print(f"[REPRO] {label}: {'OK' if cond else 'FAIL'}")
    passed = passed and cond


def pump(ms: int = 1200) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


# ---------------- 场景 A：地名解析失败（后台线程阶段） ----------------
from app.core import geocode as geocode_mod


def fail_multi(query, limit=5):
    raise GeocodeError(
        "无法解析该地名（Nominatim 连接超时；Photon 无匹配结果）。可改用「坐标范围」输入。"
    )


geocode_mod.geocode_multi = fail_multi

win._start_fetch()
pump(800)
check(win._fetch_worker is None, "场景A: 未创建抓取 worker")
check(win.input_panel.btn_fetch.isEnabled(), "场景A: 开始抓取按钮可用")
check(not win.input_panel.btn_cancel.isEnabled(), "场景A: 取消按钮不可用")
check("抓取失败" in win.status_label.text(), "场景A: 状态栏显示抓取失败")

# ---------------- 场景 B：解析成功但后台抓取失败（worker 阶段） ----------------
geocode_mod.geocode_multi = lambda query, limit=5: [
    GeoArea(bbox=(24.8, 102.6, 25.1, 103.0), display_name="昆明市, 云南省, 中国", query=query)
]

from app.core import pipeline as pipeline_mod

_orig_fetch = pipeline_mod.Pipeline.fetch


def boom_fetch(self, area, job, token):
    raise PipelineError("模拟：所有 Overpass 数据服务均不可用")


pipeline_mod.Pipeline.fetch = boom_fetch

win._start_fetch()
pump(800)  # 等地理编码线程完成并启动抓取
if win._fetch_worker is not None:
    win._fetch_worker.wait(15000)
pump(1500)

check(win._busy is False, "场景B: busy 复位")
check(win.input_panel.btn_fetch.isEnabled(), "场景B: 开始抓取按钮恢复")
check(not win.input_panel.btn_cancel.isEnabled(), "场景B: 取消按钮复位")
check(not win.loading_overlay.isVisible(), "场景B: 遮罩已关闭")
check("抓取失败" in win.status_label.text(), "场景B: 状态栏显示抓取失败")

pipeline_mod.Pipeline.fetch = _orig_fetch

print("[REPRO] RESULT:", "PASS" if passed else "FAIL")
sys.exit(0 if passed else 1)
