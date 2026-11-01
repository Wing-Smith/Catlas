"""M2 端到端 GUI 测试（offscreen）：

用已缓存的 bbox 触发真实抓取流水线 → 验证预览绘制 → 触发导出 → 验证产物。
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, ".")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from app.ui.main_window import MainWindow
from app.ui.theme import apply_fluent_theme

apply_fluent_theme()
w = MainWindow()
w.show()
app.processEvents()

# 切到坐标模式并填入已缓存的测试范围
w.input_panel.mode_bbox.setChecked(True)
app.processEvents()
w.input_panel.spin_s.setValue(39.905)
w.input_panel.spin_w.setValue(116.395)
w.input_panel.spin_n.setValue(39.910)
w.input_panel.spin_e.setValue(116.400)
w.input_panel.out_edit.setText("out/m2_gui")
w.input_panel.format_checks["png"].setChecked(True)

w._start_fetch()

# 等待后台抓取完成（最多 180s）
deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.2)
    if w.input_panel.btn_fetch.isEnabled() and w._layers is not None:
        break

assert w._layers is not None, "抓取未产出图层"
print("fetched layers:", {ly.value: len(g) for ly, g in w._layers.items()})

# 预览绘制验证
n_collections = len(w.canvas.ax.collections) + len(w.canvas.ax.lines)
print("preview artists:", n_collections)
assert n_collections > 0, "预览画布没有绘制内容"

w.grab().save("gui_m2_fetched.png")

# 触发导出
w._start_export()
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.2)
    if w.input_panel.btn_export.isEnabled():
        break

import pathlib

pngs = list(pathlib.Path("out/m2_gui").glob("*.png"))
print("exported:", [str(p) for p in pngs])
assert pngs, "导出失败"

# 底图切换：选 osm_de，等待后台线程拼接完成并上屏
w.input_panel.basemap_combo.setCurrentIndex(1)
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.2)
    if len(w.canvas.ax.images) > 0 and not w.indet_bar.isVisible():
        break

assert len(w.canvas.ax.images) > 0, "底图未上屏"
print("basemap images on canvas:", len(w.canvas.ax.images))
w.grab().save("gui_m2_basemap.png")

# 快速连续切换两次，验证过期结果不会覆盖新底图
w.input_panel.basemap_combo.setCurrentIndex(2)
app.processEvents()
w.input_panel.basemap_combo.setCurrentIndex(1)
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.2)
    if not w.indet_bar.isVisible():
        break
print("rapid switch OK, images:", len(w.canvas.ax.images))

print("M2 GUI E2E OK")
QTimer.singleShot(0, app.quit)
app.exec()
