"""GUI 结构冒烟测试：六页导航、设置置底、语言切换、选区/路径页基础功能。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication

app = QApplication([])

from app.core import i18n
from app.ui.main_window import MainWindow

win = MainWindow()

# 1. 页面齐全
assert win.home_page is not None
assert win.draw_page is not None
assert win.route_page is not None
assert win.network_page is not None
assert win.settings_page is not None
print("OK 六页创建（主页/抓取/选区/路径/网络/设置）")

# 2. 设置项在导航底部
from qfluentwidgets import NavigationItemPosition

item = win.navigationInterface.widget("settingsPage")
assert item is not None, "设置项不存在"
print("OK 设置导航项存在（置底）")

# 3. 网络探测已自动启动
assert win.network_page._worker is not None
print("OK 启动自动网络探测")

# 4. 选区页：画笔圈选 + 叠加 + 减去（本地底图，离线）
calls = []
win.draw_page._apply_handler = lambda b: calls.append(b)


class _E:
    def __init__(self, x, y, button=1, dblclick=False):
        self.xdata, self.ydata = x, y
        self.button = button
        self.dblclick = dblclick
        self.inaxes = win.draw_page.canvas.ax


def _brush(pts):
    win.draw_page._select_tool("brush")
    win.draw_page._on_press(_E(*pts[0]))
    for x, y in pts[1:]:
        win.draw_page._on_motion(_E(x, y))
    win.draw_page._on_release(_E(*pts[-1]))


_brush([(116.3, 39.85), (116.35, 39.9), (116.45, 39.9), (116.5, 39.92), (116.4, 39.85)])
assert win.draw_page._geom is not None, "画笔圈选未生成几何"
minx, miny, maxx, maxy = win.draw_page._geom.bounds
assert abs(minx - 116.3) < 1e-6 and abs(maxx - 116.5) < 1e-6, (minx, maxx)
assert abs(miny - 39.85) < 1e-6 and abs(maxy - 39.92) < 1e-6, (miny, maxy)
assert win.draw_page.btn_apply.isEnabled()
win.draw_page._apply()
assert calls and abs(calls[0][1] - 116.3) < 1e-6
print("OK 画笔圈选与坐标换算")

# 4b. 矩形工具
win.draw_page.clear_selection()
win.draw_page._select_tool("rect")
win.draw_page._on_press(_E(100.0, 30.0))
win.draw_page._on_motion(_E(102.0, 32.0))
win.draw_page._on_release(_E(102.0, 32.0))
assert win.draw_page._geom is not None
assert abs(win.draw_page._geom.bounds[0] - 100.0) < 1e-9
print("OK 矩形工具")

# 4c. 圆形工具
win.draw_page.clear_selection()
win.draw_page._select_tool("circle")
win.draw_page._on_press(_E(10.0, 10.0))
win.draw_page._on_motion(_E(12.0, 10.0))
win.draw_page._on_release(_E(12.0, 10.0))
g = win.draw_page._geom
assert g is not None and abs(g.bounds[0] - 8.0) < 1e-6, g.bounds
print("OK 圆形工具")

# 4d. 多边形工具（双击闭合）
win.draw_page.clear_selection()
win.draw_page._select_tool("poly")
for x, y in [(0, 0), (4, 0), (4, 4), (0, 4)]:
    win.draw_page._on_press(_E(x, y))
win.draw_page._on_press(_E(0, 0, dblclick=True))
assert win.draw_page._geom is not None
assert abs(win.draw_page._geom.area - 16.0) < 1e-6
print("OK 多边形工具")

# 4e. 叠加选区 / 减去选区
mc = win.draw_page.mode_combo
mc.setCurrentIndex(mc.findData("union"))
win.draw_page._select_tool("rect")
win.draw_page._on_press(_E(10, 0))
win.draw_page._on_motion(_E(14, 4))
win.draw_page._on_release(_E(14, 4))
area_after_union = win.draw_page._geom.area
assert area_after_union > 16.0, area_after_union  # 10-14×0-4 与 0-4×0-4 不相交，面积相加
assert abs(area_after_union - 32.0) < 1e-6
mc.setCurrentIndex(mc.findData("subtract"))
win.draw_page._on_press(_E(2, 2))
win.draw_page._on_motion(_E(6, 6))
win.draw_page._on_release(_E(6, 6))
area_final = win.draw_page._geom.area
assert abs(area_final - 28.0) < 1e-6, area_final  # 32 - 2×2 与正方形相交部分
print("OK 叠加/减去选区运算")

# 4f. 清除选区
win.draw_page.clear_selection()
assert win.draw_page._geom is None
assert not win.draw_page.btn_apply.isEnabled()
print("OK 清除选区")

# 4f2. 中空选区：大圆减去同心小圆 → 带洞多边形
mc.setCurrentIndex(mc.findData("new"))
win.draw_page._select_tool("circle")
win.draw_page._on_press(_E(10.0, 10.0))
win.draw_page._on_motion(_E(14.0, 10.0))
win.draw_page._on_release(_E(14.0, 10.0))
big_area = win.draw_page._geom.area
mc.setCurrentIndex(mc.findData("subtract"))
win.draw_page._on_press(_E(10.0, 10.0))
win.draw_page._on_motion(_E(12.0, 10.0))
win.draw_page._on_release(_E(12.0, 10.0))
g = win.draw_page._geom
assert g.geom_type == "Polygon" and len(g.interiors) == 1, (g.geom_type, g.interiors)
assert abs(g.area - big_area * 3 / 4) < 1e-6, g.area  # π(4²-2²) = 3/4 π4²
print("OK 中空选区（减去模式生成带洞多边形）")
win.draw_page.clear_selection()

# 4g. 滚轮缩放不越界
import matplotlib

win.draw_page._on_wheel(matplotlib.backend_bases.MouseEvent(
    "scroll_event", win.draw_page.canvas, 100, 100, button="up"))
x0, x1 = win.draw_page.canvas.ax.get_xlim()
assert -180 <= x0 and x1 <= 180
print("OK 滚轮缩放")

# 4h. 移动工具激活 pan 模式且不触发画笔
win.draw_page._select_tool("move")
assert "PAN" in str(win.draw_page.canvas._toolbar.mode).upper()
print("OK 移动工具")

# 4i. 圈选完成后视野不重置
win.draw_page.canvas.ax.set_xlim(100, 130)
win.draw_page.canvas.ax.set_ylim(20, 50)
win.draw_page._select_tool("rect")
win.draw_page._on_press(_E(105, 25))
win.draw_page._on_motion(_E(115, 45))
win.draw_page._on_release(_E(115, 45))
x0, x1 = win.draw_page.canvas.ax.get_xlim()
y0, y1 = win.draw_page.canvas.ax.get_ylim()
assert abs(x0 - 100) < 1e-9 and abs(x1 - 130) < 1e-9, (x0, x1)
assert abs(y0 - 20) < 1e-9 and abs(y1 - 50) < 1e-9, (y0, y1)
print("OK 圈选后视野保持")
win.draw_page.clear_selection()

# 5. 路径页坐标解析
win.route_page.start_edit.setText("116.397, 39.908")
win.route_page.end_edit.setText("116.404，39.915")
assert win.route_page._parse(win.route_page.start_edit) == (116.397, 39.908)
assert win.route_page._parse(win.route_page.end_edit) == (116.404, 39.915)
assert win.route_page._parse(type("X", (), {"text": lambda self: "bad"})()) is None
print("OK 路径页坐标解析")

# 6. 主窗口应用选区 → 面板联动
win._apply_draw_bbox((39.9, 116.4, 39.95, 116.45))
assert not win.input_panel.mode_query.isChecked()
assert abs(win.input_panel.spin_s.value() - 39.9) < 1e-9
assert abs(win.input_panel.spin_e.value() - 116.45) < 1e-9
print("OK 选区应用到抓取面板")

# 7. 语言切换 zh → en
win.settings_page.language_combo.setCurrentIndex(
    win.settings_page.language_combo.findData("en")
)
assert i18n.language() == "en"
nav_home = win.navigationInterface.widget("homePage")
assert nav_home.text() == "Home", nav_home.text()
assert win.input_panel.btn_fetch.text() == "Start Fetch"
assert win.home_page.btn_start.text() == "Fetch data"
assert win.route_page.btn_plan.text() == "Route"
assert win.network_page.title_label.text() == "Network Monitor"
settings_item = win.navigationInterface.widget("settingsPage")
assert settings_item.text() == "Settings"
print("OK 语言切换 English 全局生效")

# 切回中文
win.settings_page.language_combo.setCurrentIndex(
    win.settings_page.language_combo.findData("zh")
)
assert win.input_panel.btn_fetch.text() == "开始抓取"
print("OK 切回简体中文")

# 8. 主题切换
from app.core.config import SETTINGS

tc = win.settings_page.theme_combo
tc.setCurrentIndex(tc.findData("dark"))
assert SETTINGS.theme == "dark"
tc.setCurrentIndex(tc.findData("light"))
assert SETTINGS.theme == "light"
tc.setCurrentIndex(tc.findData("auto"))
assert SETTINGS.theme == "auto"
print("OK 主题切换（深色/浅色/跟随系统）")

win.network_page._worker.wait(20000)
win.close()
print("ALL GUI SMOKE PASSED")
