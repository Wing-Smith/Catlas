"""领域层统一异常定义。

UI 层捕获这些异常并转换为友好提示。
"""


class PipelineError(Exception):
    """流水线基础异常。"""


class GeocodeError(PipelineError):
    """地名解析失败。"""


class FetchError(PipelineError):
    """OSM 数据抓取失败。"""


class AreaTooLargeError(FetchError):
    """查询范围超过安全阈值。"""


class CleanError(PipelineError):
    """数据清洗失败。"""


class ExportError(PipelineError):
    """数据导出失败。"""
