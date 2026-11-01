"""离线单测：Overpass 解析器、清洗管线、网格拆分。"""

from app.core.clean import clean_layer
from app.core.fetch import parse_overpass_json, split_bbox
from app.core.models import LayerType


def _geom(pts):
    return [{"lat": lat, "lon": lon} for lon, lat in pts]


def _square(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]


class TestParse:
    def test_open_way_becomes_linestring(self):
        data = {"elements": [
            {"type": "way", "id": 1, "geometry": _geom([(116.0, 39.0), (116.001, 39.0)]),
             "tags": {"highway": "residential"}},
        ]}
        gdf = parse_overpass_json(data, LayerType.ROAD)
        assert len(gdf) == 1
        assert gdf.geometry.iloc[0].geom_type == "LineString"
        assert gdf.fclass.iloc[0] == "residential"

    def test_closed_way_becomes_polygon(self):
        data = {"elements": [
            {"type": "way", "id": 2, "geometry": _geom(_square(116.0, 39.0, 116.001, 39.001)),
             "tags": {"building": "yes"}},
        ]}
        gdf = parse_overpass_json(data, LayerType.BUILDING)
        assert gdf.geometry.iloc[0].geom_type == "Polygon"

    def test_multipolygon_relation_with_hole(self):
        rel = {"type": "relation", "id": 10,
               "tags": {"type": "multipolygon", "natural": "water"},
               "members": [
                   {"type": "way", "ref": 101, "role": "outer",
                    "geometry": _geom(_square(116.0, 39.0, 116.01, 39.01))},
                   {"type": "way", "ref": 102, "role": "inner",
                    "geometry": _geom(_square(116.002, 39.002, 116.003, 39.003))},
               ]}
        outer_dup = {"type": "way", "id": 101,
                     "geometry": _geom(_square(116.0, 39.0, 116.01, 39.01))}
        data = {"elements": [rel, outer_dup]}
        gdf = parse_overpass_json(data, LayerType.WATER)
        # 成员 way 不重复计入，只有装配结果一条
        assert len(gdf) == 1
        poly = gdf.geometry.iloc[0]
        assert poly.geom_type == "Polygon"
        assert len(poly.interiors) == 1


class TestClean:
    def test_dedup_by_osm_id(self):
        data = {"elements": [
            {"type": "way", "id": 1, "geometry": _geom([(116.0, 39.0), (116.001, 39.0)]),
             "tags": {"highway": "residential"}},
            {"type": "way", "id": 1, "geometry": _geom([(116.0, 39.0), (116.001, 39.0)]),
             "tags": {"highway": "residential"}},
        ]}
        gdf = parse_overpass_json(data, LayerType.ROAD)
        cleaned = clean_layer(gdf, LayerType.ROAD)
        assert len(cleaned) == 1

    def test_geom_type_filter(self):
        # 建筑图层混入线要素应被过滤
        data = {"elements": [
            {"type": "way", "id": 1, "geometry": _geom([(116.0, 39.0), (116.001, 39.0)]),
             "tags": {"building": "yes"}},
        ]}
        gdf = parse_overpass_json(data, LayerType.BUILDING)
        assert clean_layer(gdf, LayerType.BUILDING).empty


class TestSplit:
    def test_small_bbox_single_cell(self):
        cells = split_bbox((39.9, 116.3, 39.905, 116.305), cell_km=5.0)
        assert len(cells) == 1
        assert cells[0] == (39.9, 116.3, 39.905, 116.305)

    def test_large_bbox_splits(self):
        cells = split_bbox((39.0, 116.0, 40.0, 117.0), cell_km=20.0)
        assert len(cells) > 4
        # 所有单元不重叠且在原范围内
        for s, w, n, e in cells:
            assert 39.0 <= s < n <= 40.0
            assert 116.0 <= w < e <= 117.0
