"""左侧输入面板：地名/坐标、图层与配色、样式预设、导出设置。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    CheckBox,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    isDarkTheme,
)

from app.core import stylestore
from app.core.i18n import tr
from app.core.models import LayerSpec, LayerType
from app.core.tiles import PROVIDERS
from app.ui.widgets import style_native_spin as _style_native_spin

# 海报幅面（英寸，长边 × 短边），与 core/export.PAPER_SIZES 对齐
PAPER_CHOICES = ("a0", "a1", "a2", "a3", "a4")


class ColorDotButton(PushButton):
    """显示当前颜色、点击弹 QColorDialog 的小按钮。"""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(28, 22)
        self.setStyleSheet(f"background-color: {color}; border-radius: 4px; border: 1px solid #888;")
        self.clicked.connect(self._pick)

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self.color), self, "选择颜色")
        if c.isValid():
            self.color = c.name()
            self.setStyleSheet(
                f"background-color: {self.color}; border-radius: 4px; border: 1px solid #888;"
            )


class InputPanel(QWidget):
    """收集全部抓取/导出参数。"""

    style_changed = Signal()  # 配色 / 线宽 / 不透明度变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layer_checks: dict[LayerType, CheckBox] = {}
        self.layer_colors: dict[LayerType, ColorDotButton] = {}
        self.layer_widths: dict[LayerType, QDoubleSpinBox] = {}
        self.layer_alphas: dict[LayerType, QDoubleSpinBox] = {}
        self.format_checks: dict[str, CheckBox] = {}
        self._loading_presets = False

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ---- 范围输入 ----
        self.section_range = StrongBodyLabel("")
        layout.addWidget(self.section_range)
        self.mode_query = QRadioButton("")
        self.mode_query.setChecked(True)
        self.mode_bbox = QRadioButton("")
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.mode_query)
        mode_row.addWidget(self.mode_bbox)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        self.query_edit = LineEdit()
        layout.addWidget(self.query_edit)

        bbox_widget = QWidget()
        form = QFormLayout(bbox_widget)
        form.setContentsMargins(0, 0, 0, 0)
        self.spin_s = self._coord_spin(39.905)
        self.spin_w = self._coord_spin(116.395)
        self.spin_n = self._coord_spin(39.910)
        self.spin_e = self._coord_spin(116.400)
        form.addRow("南 S", self.spin_s)
        form.addRow("西 W", self.spin_w)
        form.addRow("北 N", self.spin_n)
        form.addRow("东 E", self.spin_e)
        layout.addWidget(bbox_widget)
        self.bbox_widget = bbox_widget

        # ---- 图层 ----
        self.section_layers = StrongBodyLabel("")
        layout.addWidget(self.section_layers)
        for layer in LayerType:
            row = QHBoxLayout()
            row.setSpacing(6)
            cb = CheckBox(layer.label)  # 初始中文，retranslate_ui 里按语言覆盖
            cb.setChecked(True)
            dot = ColorDotButton(layer.default_color)
            dot.setToolTip("颜色")
            w_spin = QDoubleSpinBox()
            w_spin.setRange(0.2, 8.0)
            w_spin.setDecimals(1)
            w_spin.setSingleStep(0.2)
            w_spin.setValue(1.0)
            w_spin.setFixedWidth(58)
            w_spin.setToolTip(tr("grab.style.width_tip"))
            a_spin = QDoubleSpinBox()
            a_spin.setRange(0.05, 1.0)
            a_spin.setDecimals(2)
            a_spin.setSingleStep(0.05)
            a_spin.setValue(1.0)
            a_spin.setFixedWidth(58)
            a_spin.setToolTip(tr("grab.style.alpha_tip"))
            _style_native_spin(w_spin)
            _style_native_spin(a_spin)
            w_spin.valueChanged.connect(self._on_style_touched)
            a_spin.valueChanged.connect(self._on_style_touched)
            dot.clicked.connect(self._on_style_touched)
            row.addWidget(cb)
            row.addStretch(1)
            row.addWidget(dot)
            row.addWidget(w_spin)
            row.addWidget(a_spin)
            layout.addLayout(row)
            self.layer_checks[layer] = cb
            self.layer_colors[layer] = dot
            self.layer_widths[layer] = w_spin
            self.layer_alphas[layer] = a_spin

        # ---- 样式预设 ----
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        self.preset_combo = ComboBox()
        self.preset_combo.setMinimumWidth(120)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.btn_save_preset = PushButton("")
        self.btn_save_preset.clicked.connect(self._save_preset)
        preset_row.addWidget(self.preset_combo, stretch=1)
        preset_row.addWidget(self.btn_save_preset)
        layout.addLayout(preset_row)

        # ---- 底图 ----
        self.section_basemap = StrongBodyLabel("")
        layout.addWidget(self.section_basemap)
        self.basemap_combo = ComboBox()
        for pid, provider in PROVIDERS.items():
            self.basemap_combo.addItem(provider.name, userData=pid)
        layout.addWidget(self.basemap_combo)

        # ---- 导出 ----
        self.section_export = StrongBodyLabel("")
        layout.addWidget(self.section_export)
        fmt_grid = QGridLayout()
        for i, fmt in enumerate(("geojson", "gpkg", "shp", "svg", "png")):
            cb = CheckBox(fmt.upper())
            cb.setChecked(fmt == "geojson")
            fmt_grid.addWidget(cb, i // 3, i % 3)
            self.format_checks[fmt] = cb
        layout.addLayout(fmt_grid)

        dpi_form = QFormLayout()
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        _style_native_spin(self.dpi_spin)
        self.dpi_form = dpi_form
        self._dpi_label = "PNG DPI"
        dpi_form.addRow(self._dpi_label, self.dpi_spin)
        layout.addLayout(dpi_form)

        # ---- 超大幅面 PNG ----
        self.poster_check = CheckBox("")
        layout.addWidget(self.poster_check)
        paper_row = QHBoxLayout()
        self.paper_label = CaptionLabel("")
        self.paper_combo = ComboBox()
        for key in PAPER_CHOICES:
            self.paper_combo.addItem(key.upper(), userData=key)
        self.poster_check.toggled.connect(self._toggle_poster)
        self._toggle_poster(False)
        paper_row.addWidget(self.paper_label)
        paper_row.addWidget(self.paper_combo)
        paper_row.addStretch(1)
        layout.addLayout(paper_row)

        dir_row = QHBoxLayout()
        self.out_edit = LineEdit()
        self.out_edit.setText("out/export")
        self.btn_dir = PushButton("")
        self.btn_dir.clicked.connect(self._pick_dir)
        dir_row.addWidget(self.out_edit, stretch=1)
        dir_row.addWidget(self.btn_dir)
        layout.addLayout(dir_row)

        # ---- 操作 ----
        self.btn_fetch = PrimaryPushButton("")
        self.btn_cancel = PushButton("")
        self.btn_cancel.setEnabled(False)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_fetch)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self.btn_export = PushButton("")
        self.btn_export.setEnabled(False)
        layout.addWidget(self.btn_export)

        layout.addStretch(1)

        self.mode_query.toggled.connect(self._switch_mode)
        self._switch_mode(True)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """按当前语言刷新全部文案。"""
        self.section_range.setText(tr("grab.range"))
        self.mode_query.setText(tr("grab.mode_query"))
        self.mode_bbox.setText(tr("grab.mode_bbox"))
        self.query_edit.setPlaceholderText(tr("grab.query_ph"))
        self.section_layers.setText(tr("grab.layers"))
        for layer, cb in self.layer_checks.items():
            cb.setText(tr(f"grab.layer.{layer.value}"))
        self._reload_presets()
        self.btn_save_preset.setText(tr("grab.style.save"))
        self.section_basemap.setText(tr("grab.basemap"))
        none_index = self.basemap_combo.findData(None)
        if none_index >= 0:
            self.basemap_combo.setItemText(none_index, tr("grab.basemap_none"))
        else:
            self.basemap_combo.insertItem(0, tr("grab.basemap_none"), userData=None)
        self.section_export.setText(tr("grab.export"))
        self.dpi_form.labelForField(self.dpi_spin).setText(tr("grab.dpi"))
        self.poster_check.setText(tr("grab.poster"))
        self.paper_label.setText(tr("grab.paper"))
        self.btn_dir.setText(tr("grab.browse"))
        self.btn_fetch.setText(tr("grab.start"))
        self.btn_cancel.setText(tr("grab.cancel"))
        self.btn_export.setText(tr("grab.export_btn"))

    def set_bbox(self, bbox: tuple[float, float, float, float]) -> None:
        """外部（选区地图）写入坐标范围并切到坐标模式。"""
        s, w, n, e = bbox
        self.mode_bbox.setChecked(True)
        self.spin_s.setValue(s)
        self.spin_w.setValue(w)
        self.spin_n.setValue(n)
        self.spin_e.setValue(e)

    @staticmethod
    def _coord_spin(value: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(-180.0, 180.0)
        s.setDecimals(6)
        s.setSingleStep(0.001)
        s.setValue(value)
        _style_native_spin(s)
        return s

    def _switch_mode(self, query_mode: bool) -> None:
        self.query_edit.setVisible(query_mode)
        self.bbox_widget.setVisible(not query_mode)

    def _toggle_poster(self, on: bool) -> None:
        self.paper_label.setVisible(on)
        self.paper_combo.setVisible(on)

    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择导出目录", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    # ------------------------------------------------------------ 样式预设

    def _preset_display(self, name: str) -> str:
        return tr(f"grab.preset.{name}") if name in stylestore.BUILTIN else name

    def _reload_presets(self, select: str | None = None) -> None:
        """重建预设下拉（语言切换 / 保存新预设后调用）。"""
        self._loading_presets = True
        try:
            current = select or self.preset_combo.currentData() or stylestore.DEFAULT
            self.preset_combo.clear()
            for name in stylestore.preset_names():
                self.preset_combo.addItem(self._preset_display(name), userData=name)
            self.preset_combo.addItem(tr("grab.style.custom"), userData="custom")
            idx = self.preset_combo.findData(current)
            self.preset_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._loading_presets = False

    @staticmethod
    def _set_dot_color(dot: ColorDotButton, color: str) -> None:
        dot.color = color
        dot.setStyleSheet(
            f"background-color: {color}; border-radius: 4px; border: 1px solid #888;"
        )

    def apply_record(self, rec) -> None:
        """把历史记录的范围、图层、样式填回面板。"""
        if rec.query:
            self.mode_query.setChecked(True)
            self.query_edit.setText(rec.query)
        elif rec.bbox:
            self.set_bbox(tuple(rec.bbox))
        for ly in LayerType:
            self.layer_checks[ly].setChecked(ly.value in rec.layers)
            st = (rec.styles or {}).get(ly.value)
            if st:
                self._set_dot_color(self.layer_colors[ly], st["color"])
                self.layer_widths[ly].setValue(float(st.get("width", 1.0)))
                self.layer_alphas[ly].setValue(float(st.get("alpha", 1.0)))
        idx = self.preset_combo.findData("custom")
        if idx >= 0:
            self._loading_presets = True
            self.preset_combo.setCurrentIndex(idx)
            self._loading_presets = False
        self.style_changed.emit()

    def _apply_preset(self) -> None:
        if self._loading_presets:
            return
        name = self.preset_combo.currentData()
        if not name or name == "custom":
            return
        data = stylestore.get(name)
        if not data:
            return
        for layer in LayerType:
            st = data.get(layer.value)
            if not st:
                continue
            self._set_dot_color(self.layer_colors[layer], st["color"])
            self.layer_widths[layer].setValue(float(st.get("width", 1.0)))
            self.layer_alphas[layer].setValue(float(st.get("alpha", 1.0)))
        self.style_changed.emit()

    def _collect_style(self) -> dict:
        return {
            ly.value: {
                "color": self.layer_colors[ly].color,
                "width": self.layer_widths[ly].value(),
                "alpha": self.layer_alphas[ly].value(),
            }
            for ly in LayerType
        }

    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, tr("grab.style.save"), tr("grab.style.preset") + "：")
        name = name.strip()
        if not ok or not name:
            return
        if name in stylestore.BUILTIN:
            name = f"{name} *"
        stylestore.save(name, self._collect_style())
        self._reload_presets(select=name)
        self.style_changed.emit()

    def _on_style_touched(self, *_args) -> None:
        """手动改动任何样式控件 → 下拉显示「自定义」，并通知预览刷新。"""
        if not self._loading_presets:
            idx = self.preset_combo.findData("custom")
            if idx >= 0 and self.preset_combo.currentIndex() != idx:
                self._loading_presets = True
                self.preset_combo.setCurrentIndex(idx)
                self._loading_presets = False
        self.style_changed.emit()

    # ------------------------------------------------------------ 读取参数

    def query_or_bbox(self) -> tuple[str | None, tuple | None]:
        if self.mode_query.isChecked():
            text = self.query_edit.text().strip()
            return (text or None), None
        bbox = (
            self.spin_s.value(),
            self.spin_w.value(),
            self.spin_n.value(),
            self.spin_e.value(),
        )
        return None, bbox

    def layer_specs(self) -> list[LayerSpec]:
        return [
            LayerSpec(
                layer=ly,
                enabled=self.layer_checks[ly].isChecked(),
                color=self.layer_colors[ly].color,
                linewidth=self.layer_widths[ly].value(),
                alpha=self.layer_alphas[ly].value(),
            )
            for ly in LayerType
        ]

    def enabled_layers(self) -> list[LayerType]:
        return [ly for ly, cb in self.layer_checks.items() if cb.isChecked()]

    def selected_formats(self) -> list[str]:
        return [fmt for fmt, cb in self.format_checks.items() if cb.isChecked()]

    def dpi(self) -> int:
        return self.dpi_spin.value()

    def poster(self) -> bool:
        return self.poster_check.isChecked()

    def paper(self) -> str:
        return self.paper_combo.currentData() or "a0"

    def basemap(self) -> str | None:
        return self.basemap_combo.currentData()

    def out_dir(self) -> str:
        return self.out_edit.text().strip() or "out"
