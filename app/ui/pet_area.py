"""主页底部的 Calico 电子宠物 —— 一只真正「活着」的小猫。

画面细腻度：
- 行走是 8 帧完整四足步态循环（触地→承重→收腿→提起 × 左右两侧），
  相邻帧在渲染层做 60Hz 交叉淡化，帧与帧之间不是硬切；
- 起身 / 坐下 / 扑跃蹲伏都有专门的过渡帧，状态切换不再跳变；
- 发呆时随机眨眼、歪头、抖耳、摆尾；行走是对角小跑节奏，双跳与脚步同步；
- 被撸时坐着做表情反应（满足眯眼 / 好奇歪头 / 抖耳）+ 飘爱心 + 说语录；
- 双击扑跃不变；睡觉呼吸起伏、飘 Zzz。
- 16ms 精确计时器 + elapsed-time 驱动，渲染管线 60Hz。
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QEvent, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import isDarkTheme

from app.core.assets import asset
from app.core.pet_quotes import pet_line

# 状态常量
_IDLE, _WALK, _SLEEP, _POUNCE, _STRETCH = range(5)
_STANDUP, _SITDOWN, _CROUCH = range(6, 9)

_CAT_W = 104
_CAT_H = 94
_TICK_MS = 16          # ~60Hz 精确计时器
_MAX_DT = 0.05         # 卡顿补偿上限，防止切后台后跳变
_WALK_SPEED = 48.0     # px/s
_POUNCE_SPEED = 400.0
_POUNCE_HOP = 26.0
_WALK_FRAME_S = 0.11   # 8 帧循环，每帧 110ms，全程 0.88s
_WALK_BOB = 4.2        # 行走弹跳幅度（px），小跑双跳节奏

# 8 帧四足步态：左触地 → 左承重 → 收腿 → 左提起 → 右触地 → 右承重 → 收腿 → 右提起
_WALK_CYCLE = ("step1", "step2", "walk3", "step3", "step4", "step5", "walk3", "step6")
_SIDE_FRAMES = {"walk1", "walk2", "walk3", "walk4", "step1", "step2", "step3",
                "step4", "step5", "step6", "standup", "sitdown", "crouch",
                "stretch", "pounce"}
_BLEND_START = 0.55    # 每帧的后 45% 与下一帧交叉淡化


class _PetView(QLabel):
    """负责显示小猫当前帧，并转发点按事件。"""

    petted = Signal()
    pounced = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(_CAT_W, _CAT_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent;")
        self._press_count = 0

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # 只统计真正的按下；Qt 会把未接受的双击改投递成 press，需用类型过滤
        if event.type() == QEvent.Type.MouseButtonPress \
                and event.button() == Qt.MouseButton.LeftButton:
            self._press_count += 1
            if self._press_count == 1:
                # 用系统双击间隔判定：间隔内出现第二次按下则由
                # mouseDoubleClickEvent 取消本次单击
                QTimer.singleShot(
                    QApplication.doubleClickInterval(), self._dispatch_click
                )
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._press_count = 0
        self.pounced.emit()
        event.accept()
        # 注意：不能调用 super()——QWidget 默认实现会忽略事件，
        # Qt 随后把未接受的双击转换成 press 再次投递，打乱单击计数

    def _dispatch_click(self) -> None:
        if self._press_count == 1:
            self.petted.emit()
        self._press_count = 0


class PetArea(QWidget):
    """电子宠物区。对外接口：retranslate_ui() / restyle()。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("petArea")
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(170)

        # 预载全部姿态帧（按统一高度缩放，所有帧同尺寸，底部即脚底）
        self._frames: dict[str, QPixmap] = {}
        for name in ("idle", "blink", "look", "ear", "tail1", "tail2",
                     "walk1", "walk2", "walk3", "walk4",
                     "step1", "step2", "step3", "step4", "step5", "step6",
                     "standup", "sitdown", "crouch",
                     "sleep", "happy", "happy2", "stretch", "pounce"):
            raw = QPixmap(str(asset(f"pet/pet_{name}.png")))
            self._frames[name] = raw.scaledToHeight(
                _CAT_H - 6, Qt.TransformationMode.SmoothTransformation
            )

        # 小猫与气泡都是自由定位的子控件
        self.cat = _PetView(self)
        self.cat.petted.connect(self._on_pet)
        self.cat.pounced.connect(self._on_pounce)
        self.bubble = QLabel(self)
        self.bubble.setWordWrap(False)
        self.bubble.setVisible(False)
        self.bubble.setStyleSheet("background: transparent;")
        self.bubble.adjustSize()

        # 右侧留白（原提示/计数文案已删除，保留少量边距）
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)

        # 状态机
        self._state = _IDLE
        self._after = _IDLE          # 过渡状态（起身/坐下/蹲伏）结束后进入的状态
        self._x = 30.0
        self._dir = 1
        self._state_time = 0.0
        self._zzz_time = 0.0
        self._blink_left = 0.0
        self._next_blink = random.uniform(2.0, 5.0)
        self._look_left = 0.0
        self._next_look = random.uniform(8.0, 16.0)
        self._tail_left = 0.0
        self._next_tail = random.uniform(5.0, 12.0)
        self._ear_left = 0.0
        self._next_ear = random.uniform(7.0, 15.0)
        self._hop = 0.0
        self._breath = 0.0
        self._pounce_from = 0.0
        self._pounce_target = 0.0
        self._state_duration = random.uniform(5.0, 10.0)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()
        self._timer.start(_TICK_MS)
        self._clock.start()

        self.retranslate_ui()
        self.restyle()

    # ------------------------------------------------------------------ 文案与主题

    def retranslate_ui(self) -> None:
        pass

    def restyle(self) -> None:
        if isDarkTheme():
            self.bubble.setStyleSheet(
                "QLabel { background: rgba(255,255,255,0.12); color: #f0f0f0;"
                " border: 1px solid rgba(255,255,255,0.14); border-radius: 10px;"
                " padding: 5px 10px; }"
            )
        else:
            self.bubble.setStyleSheet(
                "QLabel { background: rgba(255,255,255,0.94); color: #202020;"
                " border: 1px solid rgba(0,0,0,0.08); border-radius: 10px;"
                " padding: 5px 10px; }"
            )

    # ------------------------------------------------------------------ 几何

    def _ground_y(self) -> int:
        return self.height() - self.cat.height() - 4

    def _min_x(self) -> float:
        return 6.0

    def _max_x(self) -> float:
        return max(self._min_x(), self.width() - self.cat.width() - 6)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._x = max(self._min_x(), min(self._x, self._max_x()))
        self._render()

    # ------------------------------------------------------------------ 主循环

    def _tick(self, dt: float | None = None) -> None:
        # 用真实 elapsed time 驱动；测试可注入 dt
        if dt is None:
            dt = min(self._clock.restart() / 1000.0, _MAX_DT)
        else:
            self._clock.restart()
        self._state_time += dt
        self._breath += dt

        if self._state_time >= self._state_duration:
            self._advance()

        if self._state == _WALK:
            ramp = min(self._state_time / 0.35,
                       (self._state_duration - self._state_time) / 0.35, 1.0)
            speed = _WALK_SPEED * max(0.25, ramp)
            self._x += self._dir * speed * dt
            if self._x <= self._min_x():
                self._x = self._min_x()
                self._dir = 1
            elif self._x >= self._max_x():
                self._x = self._max_x()
                self._dir = -1
        elif self._state == _POUNCE:
            step = _POUNCE_SPEED * dt
            dist = self._pounce_target - self._x
            if abs(dist) <= step:
                self._x = self._pounce_target
                self._hop = 12.0
                self._set_state(_STRETCH, random.uniform(1.2, 1.6))
            else:
                self._x += step if dist > 0 else -step
                span = abs(self._pounce_target - self._pounce_from) or 1.0
                prog = 1.0 - min(1.0, abs(dist) / span)
                self._hop = math.sin(prog * math.pi) * _POUNCE_HOP
        elif self._state == _SLEEP:
            self._zzz_time += dt
            if self._zzz_time >= 1.8:
                self._zzz_time = 0.0
                self._spawn_float("Z", "#8ab4f8", 18)

        if self._state == _IDLE:
            self._update_idle_timers(dt)

        if self._state != _POUNCE and self._hop > 0:
            self._hop = max(0.0, self._hop - 90.0 * dt)

        self._render()

    def _update_idle_timers(self, dt: float) -> None:
        if self._blink_left > 0:
            self._blink_left -= dt
        else:
            self._next_blink -= dt
            if self._next_blink <= 0:
                self._next_blink = random.uniform(2.5, 6.0)
                self._blink_left = 0.2
        if self._look_left > 0:
            self._look_left -= dt
        else:
            self._next_look -= dt
            if self._next_look <= 0:
                self._next_look = random.uniform(9.0, 18.0)
                self._look_left = random.uniform(1.8, 3.0)
        if self._tail_left > 0:
            self._tail_left -= dt
        else:
            self._next_tail -= dt
            if self._next_tail <= 0:
                self._next_tail = random.uniform(6.0, 14.0)
                self._tail_left = random.uniform(1.6, 2.8)
        if self._ear_left > 0:
            self._ear_left -= dt
        else:
            self._next_ear -= dt
            if self._next_ear <= 0:
                self._next_ear = random.uniform(8.0, 16.0)
                self._ear_left = random.uniform(0.8, 1.4)

    def _advance(self) -> None:
        """状态到时：过渡态进入 _after，其余重新决策。"""
        if self._state in (_STANDUP, _SITDOWN, _CROUCH):
            nxt, self._after = self._after, _IDLE
            if nxt == _WALK:
                self._dir = self._pending_dir
                self._set_state(_WALK, random.uniform(2.5, 7.0))
            elif nxt == _POUNCE:
                self._pounce_from = self._x
                self._set_state(_POUNCE, 6.0)
            else:
                self._set_state(nxt, random.uniform(4.0, 9.0))
            return
        roll = random.random()
        if roll < 0.55:
            self._pending_dir = random.choice((-1, 1))
            if self._state == _WALK:
                # 继续走路不必重新起身：换个方向延续
                self._dir = self._pending_dir
                self._set_state(_WALK, random.uniform(2.5, 7.0))
            else:
                self._after = _WALK
                self._set_state(_STANDUP, 0.22)
        elif roll < 0.8:
            self._set_state(_SLEEP, random.uniform(14.0, 28.0))
        else:
            self._set_state(_IDLE, random.uniform(4.0, 9.0))

    def _set_state(self, state: int, duration: float) -> None:
        # 行走平静地结束才先进「坐下」过渡；兴奋反应（开心/懒腰）直接切
        if self._state == _WALK and state in (_IDLE, _SLEEP):
            self._state = _SITDOWN
            self._state_time = 0.0
            self._state_duration = 0.28
            self._after = state
            self._render()
            return
        self._state = state
        self._state_time = 0.0
        self._state_duration = duration
        self._zzz_time = 0.0
        if state == _SLEEP:
            self.show_bubble(pet_line(), 4000)
        self._render()

    # ------------------------------------------------------------------ 渲染

    def _compose(self, name_a: str, name_b: str | None = None, t: float = 0.0) -> QPixmap:
        """把姿态帧画到画布上；t>0 时按透明度叠入下一帧（交叉淡化）。"""
        a = self._frames[name_a]
        canvas = QPixmap(a.size())
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawPixmap(0, 0, a)
        if name_b is not None and t > 0.0:
            painter.setOpacity(t)
            painter.drawPixmap(0, 0, self._frames[name_b])
        painter.end()
        # 侧面帧向右走时整体镜像
        if name_a in _SIDE_FRAMES and self._dir > 0:
            canvas = canvas.transformed(QTransform().scale(-1, 1))
        return canvas

    def _render(self) -> None:
        bob = 0.0
        frame = None
        if self._state == _WALK:
            # 连续步态相位 → 帧号 + 交叉淡化
            progress = self._state_time / _WALK_FRAME_S
            idx = int(progress) % len(_WALK_CYCLE)
            frac = progress - int(progress)
            nxt = (idx + 1) % len(_WALK_CYCLE)
            blend = min(1.0, max(0.0, (frac - _BLEND_START) / (1.0 - _BLEND_START)))
            pm = self._compose(_WALK_CYCLE[idx], _WALK_CYCLE[nxt], blend)
            period = _WALK_FRAME_S * len(_WALK_CYCLE)
            # 对角小跑：每个步态周期两次腾空，弹跳与脚步同步，
            # 避免「帧差异小 → 像在平移」的幻灯片感
            half = period / 2.0
            cyc = (self._state_time % half) / half
            bob = -_WALK_BOB * math.sin(math.pi * cyc)
            self._apply_frame(pm, bob)
            return
        if self._state == _POUNCE:
            frame = "pounce"
        elif self._state == _STRETCH:
            frame = "stretch"
        elif self._state == _STANDUP:
            frame = "standup"
        elif self._state == _SITDOWN:
            frame = "sitdown"
        elif self._state == _CROUCH:
            frame = "crouch"
        elif self._state == _SLEEP:
            frame = "sleep"
        elif self._blink_left > 0:
            frame = "blink"
        elif self._look_left > 0:
            frame = "look"
        elif self._tail_left > 0:
            frame = "tail1" if int(self._tail_left / 0.45) % 2 == 0 else "tail2"
        elif self._ear_left > 0:
            frame = "ear"
        else:
            frame = "idle"

        pm = self._frames[frame]
        if frame == "sleep":
            s = 1.0 + 0.018 * math.sin(self._breath * math.pi * 2 / 2.4)
            pm = pm.transformed(QTransform().scale(s, s))
        elif frame in _SIDE_FRAMES and self._dir > 0:
            pm = pm.transformed(QTransform().scale(-1, 1))
        self._apply_frame(pm, bob)

    def _apply_frame(self, pm: QPixmap, bob: float) -> None:
        self.cat.setPixmap(pm)
        y = int(round(self._ground_y() - self._hop + bob))
        self.cat.move(int(self._x), y)
        bw = self.bubble.width()
        bx = int(max(4, min(self._x + self.cat.width() / 2 - bw / 2,
                            self.width() - bw - 4)))
        by = max(0, y - self.bubble.height() - 4)
        self.bubble.move(bx, by)

    # ------------------------------------------------------------------ 互动

    def _on_pet(self) -> None:
        was_sleeping = self._state == _SLEEP
        self._hop = 8.0
        self._spawn_float("♥", "#F4648C", 16)
        self._spawn_float("♥", "#F4648C", 20)
        self._spawn_float("🐾", "#F4648C", 18)
        self.show_bubble(pet_line(), 3200)
        if was_sleeping:
            self._set_state(_STRETCH, random.uniform(1.4, 1.8))
            return
        if self._state != _IDLE:
            # 行走/过渡中不强行打断，爱心和语录已足够
            return
        # 坐姿表情反应（不起立）：满足眯眼 / 好奇歪头 / 抖耳 随机三选一
        expr = random.random()
        if expr < 0.45:
            self._blink_left = random.uniform(0.8, 1.3)
            self._next_blink = random.uniform(2.5, 6.0)
        elif expr < 0.8:
            self._look_left = random.uniform(1.4, 2.2)
            self._next_look = random.uniform(9.0, 18.0)
        else:
            self._ear_left = random.uniform(1.0, 1.6)
            self._next_ear = random.uniform(8.0, 16.0)

    def _on_pounce(self) -> None:
        self._dir = random.choice((-1, 1))
        self._pounce_target = random.uniform(self._min_x(), self._max_x())
        # 先蹲伏蓄势 0.3 秒再冲刺
        self._after = _POUNCE
        self._set_state(_CROUCH, 0.3)
        self.show_bubble(pet_line(), 2600)

    # ------------------------------------------------------------------ 飘字

    def _spawn_float(self, symbol: str, color: str, size: int) -> None:
        label = QLabel(symbol, self)
        label.setStyleSheet(
            f"color: {color}; background: transparent; font-size: {size}px;"
            " font-weight: 600;"
        )
        label.adjustSize()
        anchor = self.cat.pos()
        start = anchor + QPoint(
            random.randint(10, max(11, self.cat.width() - 20)),
            random.randint(0, 12),
        )
        label.move(start)
        label.show()
        target = start + QPoint(random.randint(-16, 16), -70)

        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)

        rise = QPropertyAnimation(label, b"pos", self)
        rise.setDuration(1000)
        rise.setEasingCurve(QEasingCurve.Type.OutQuad)
        rise.setStartValue(start)
        rise.setEndValue(target)
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(1000)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        rise.finished.connect(label.deleteLater)
        rise.start()
        fade.start()

    # ------------------------------------------------------------------ 气泡

    def show_bubble(self, text: str, duration_ms: int = 3000) -> None:
        self.restyle()
        self.bubble.setText(text)
        self.bubble.adjustSize()
        self.bubble.setVisible(True)
        QTimer.singleShot(duration_ms, self.bubble.hide)
