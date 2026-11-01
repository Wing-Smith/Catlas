"""领域模型定义：bbox、图层、任务、状态机。"""

from __future__ import annotations

import enum
import math
import threading
from dataclasses import dataclass, field

#  (south, west, north, east) —— Overpass / osmnx 惯例
BBox = tuple[float, float, float, float]

EARTH_RADIUS_KM = 6371.0


class LayerType(enum.Enum):
    """目标数据图层。"""

    ROAD = "road"
    WATER = "water"
    GREEN = "green"
    BUILDING = "building"

    @property
    def label(self) -> str:
        return {
            LayerType.ROAD: "路网",
            LayerType.WATER: "水域",
            LayerType.GREEN: "绿地",
            LayerType.BUILDING: "建筑",
        }[self]

    @property
    def default_color(self) -> str:
        """matplotlib 颜色。"""

        return {
            LayerType.ROAD: "#8a8a8a",
            LayerType.WATER: "#aad3df",
            LayerType.GREEN: "#b6e29d",
            LayerType.BUILDING: "#d9c7b2",
        }[self]

    @property
    def zorder(self) -> int:
        """渲染顺序（小的先画）。"""

        return {
            LayerType.WATER: 1,
            LayerType.GREEN: 2,
            LayerType.BUILDING: 3,
            LayerType.ROAD: 4,
        }[self]


@dataclass(frozen=True)
class LayerSpec:
    """单个图层的导出/渲染参数。"""

    layer: LayerType
    enabled: bool = True
    color: str | None = None  # None → 使用 LayerType.default_color
    linewidth: float = 1.0  # 线宽倍率（1.0 = 默认）
    alpha: float = 1.0  # 不透明度 0.05–1.0

    @property
    def effective_color(self) -> str:
        return self.color or self.layer.default_color


@dataclass
class GeoArea:
    """解析后的地理范围。"""

    bbox: BBox
    display_name: str = ""
    query: str = ""

    @property
    def area_km2(self) -> float:
        s, w, n, e = self.bbox
        lat_mid = math.radians((s + n) / 2.0)
        h = math.radians(n - s) * EARTH_RADIUS_KM
        wd = math.radians(e - w) * EARTH_RADIUS_KM * math.cos(lat_mid)
        return abs(h * wd)


class PipelineState(enum.Enum):
    IDLE = "idle"
    GEOCODING = "geocoding"
    FETCHING = "fetching"
    CLEANING = "cleaning"
    EXPORTING = "exporting"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CancelToken:
    """协作式取消令牌，跨线程使用。"""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def throw_if_cancelled(self) -> None:
        from app.core.errors import PipelineError

        if self.cancelled:
            raise PipelineError("任务已取消")


@dataclass
class FetchJob:
    """一次抓取任务。"""

    layers: list[LayerSpec]
    max_area_km2: float = 200.0
    split_cell_km: float = 5.0
    timeout_s: int = 180


@dataclass
class ExportJob:
    """一次导出任务。"""

    out_dir: str
    formats: list[str] = field(default_factory=lambda: ["geojson"])  # geojson/gpkg/shp/svg/png
    dpi: int = 300
    figsize_in: tuple[float, float] | None = None  # None → 按 bbox 长宽比自动
    basemap: str | None = None  # 瓦片底图源 id（tiles.PROVIDERS），None → 无底图
    poster: bool = False  # PNG 走超大幅面分块渲染（仅矢量图层）
    poster_size: tuple[float, float] | None = None  # 幅面英寸 (长边, 短边)，None → A0


@dataclass
class PipelineResult:
    """流水线产物。"""

    state: PipelineState
    layers: dict[LayerType, "object"] = field(default_factory=dict)  # LayerType → GeoDataFrame
    exported: dict[str, str] = field(default_factory=dict)  # 格式 → 文件路径
    message: str = ""


# 类型提示占位：core 内部使用 geopandas.GeoDataFrame，避免在类型层面硬依赖。
GDF = "geopandas.GeoDataFrame"
