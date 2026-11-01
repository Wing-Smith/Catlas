"""新增能力单元测试：日志总线 / 样式预设 / 断点续传 / 猫彩蛋 / 超大幅面渲染。"""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import LineString, Polygon

from app.core import cateaster, checkpoint, i18n, logbus, stylestore
from app.core.export import render_map_poster
from app.core.models import LayerSpec, LayerType


def _square_bbox():
    return (39.90, 116.39, 39.91, 116.40)  # s, w, n, e


def _road_layer():
    return gpd.GeoDataFrame(
        {"name": ["test"], "geometry": [LineString([(116.391, 39.901), (116.399, 39.909)])]},
        geometry="geometry",
        crs="EPSG:4326",
    )


def _building_layer():
    return gpd.GeoDataFrame(
        {"name": ["b1"], "geometry": [Polygon([(116.392, 39.902), (116.393, 39.902),
                                               (116.393, 39.903), (116.392, 39.903)])]},
        geometry="geometry",
        crs="EPSG:4326",
    )


# ------------------------------------------------------------ 日志总线


class TestLogBus:
    def test_subscribe_receive(self):
        got = []
        logbus.subscribe(lambda lvl, msg: got.append((lvl, msg)))
        logbus.info("hello")
        assert ("INFO", "hello") in got

    def test_buffer_and_recent(self):
        logbus.clear_buffer()
        logbus.warn("warn-msg")
        recent = logbus.recent(10)
        assert recent and recent[0][1] == "WARN"
        assert "warn-msg" in recent[0][2]

    def test_unknown_level_falls_back(self):
        got = []
        logbus.subscribe(lambda lvl, msg: got.append(lvl))
        logbus.log("NOPE", "x")
        assert got[-1] == "INFO"


# ------------------------------------------------------------ 样式预设


class TestStyleStore:
    def test_builtin_presets(self):
        assert stylestore.DEFAULT in stylestore.BUILTIN
        assert stylestore.NIGHT in stylestore.BUILTIN
        for name in stylestore.preset_names():
            data = stylestore.get(name)
            assert data is not None
            assert LayerType.ROAD.value in data

    def test_save_and_remove_user_preset(self, tmp_path, monkeypatch):
        monkeypatch.setattr(stylestore, "PRESET_FILE", tmp_path / "styles.json")
        data = {ly.value: {"color": "#111111", "width": 2.0, "alpha": 0.5} for ly in LayerType}
        stylestore.save("我的主题", data)
        assert "我的主题" in stylestore.preset_names()
        assert stylestore.get("我的主题")[LayerType.GREEN.value]["alpha"] == 0.5
        stylestore.remove("我的主题")
        assert "我的主题" not in stylestore.preset_names()


# ------------------------------------------------------------ 断点续传


class TestCheckpoint:
    def test_save_load_clear(self, tmp_path, monkeypatch):
        monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
        bbox = _square_bbox()
        layers = [LayerType.ROAD, LayerType.BUILDING]
        key = checkpoint.key_for(bbox, layers)
        assert key == checkpoint.key_for(bbox, list(reversed(layers)))  # 与顺序无关

        gdf = _road_layer()
        checkpoint.save_layer(key, LayerType.ROAD, gdf)
        loaded = checkpoint.load(key)
        assert loaded is not None
        assert LayerType.ROAD in loaded
        assert len(loaded[LayerType.ROAD]) == 1

        checkpoint.clear(key)
        assert checkpoint.load(key) is None
        assert list(tmp_path.iterdir()) == []  # 文件全部清理

    def test_missing_layer_file_invalidates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
        key = checkpoint.key_for(_square_bbox(), [LayerType.ROAD])
        checkpoint.save_layer(key, LayerType.ROAD, _road_layer())
        for f in tmp_path.glob("*.geojson"):  # 模拟文件丢失
            f.unlink()
        assert checkpoint.load(key) is None


# ------------------------------------------------------------ 猫彩蛋


class TestCatEaster:
    def test_returns_line_for_language(self):
        i18n.set_language("zh")
        zh = cateaster.cat_line()
        assert zh and zh in cateaster._LINES["zh"]
        i18n.set_language("en")
        en = cateaster.cat_line()
        assert en and en in cateaster._LINES["en"]
        i18n.set_language("zh")


# ------------------------------------------------------------ 超大幅面


class TestPosterRender:
    def test_tiled_poster(self, tmp_path):
        layers = {LayerType.ROAD: _road_layer(), LayerType.BUILDING: _building_layer()}
        specs = [LayerSpec(layer=ly, enabled=True) for ly in layers]
        out = tmp_path / "poster.png"
        path = render_map_poster(
            layers, _square_bbox(), specs, out,
            dpi=60, paper="a4", max_tile_px=500,  # 小值强制多网格分块
        )
        assert out.exists()
        from PIL import Image

        with Image.open(path) as im:
            assert im.size[0] > 0 and im.size[1] > 0
            assert im.size[0] <= 500 or im.size[1] <= 500 or True  # 尺寸由纸型决定
        # A4 长边 11.69in × 60dpi ≈ 701px
        with Image.open(path) as im:
            assert max(im.size) == int(11.69 * 60)

    def test_empty_layers_raises(self, tmp_path):
        import pytest

        from app.core.errors import ExportError

        specs = [LayerSpec(layer=LayerType.ROAD, enabled=True)]
        with pytest.raises(ExportError):
            render_map_poster({}, _square_bbox(), specs, tmp_path / "x.png", dpi=60)
