# Catlas（猫图集）— OSM 地理数据自动抓取与制图工具

[![Release](https://img.shields.io/github/v/release/Wing-Smith/Catlas)](https://github.com/Wing-Smith/Catlas/releases)
[![Platform](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-ODbL%20data-blue)](https://www.openstreetmap.org/copyright)

输入任意地名或坐标范围，自动从 OpenStreetMap 抓取**路网、水域、绿地、建筑**数据，
清洗后导出 GeoJSON / GeoPackage / Shapefile，并渲染为 SVG / PNG 地图。

- GUI：PySide6 + PySide6-Fluent-Widgets，Windows 11 Mica 毛玻璃
- 数据：Overpass API 多镜像探测 + 过载退避重试 + 网格分块 + 本地 parquet 缓存
- 纯 Python 3.14（Windows），core 层零 GUI 依赖，可独立做二次开发

## 下载

**[最新版 v1.2.7 已发布 → Releases 页面](https://github.com/Wing-Smith/Catlas/releases/latest)**

下载 `Catlas-Setup-1.2.7.exe` 双击安装即可（Windows 10 1809+，64 位）。
应用内置自动更新检测，新版本发布后会自动提醒。

> 地图数据 © OpenStreetMap contributors（ODbL）；Esri World Imagery 卫星底图仅限软件内在线预览，禁止导出。

## 安装

```bash
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -i https://pypi.org/simple -r requirements.txt
```

> 国内网络装 GUI 包慢时，PySide6 相关包可改用阿里云镜像：
> `.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ PySide6-Essentials PySideSix-Frameless-Window PySide6-Fluent-Widgets darkdetect pywin32`

## 使用

GUI：

```bash
.venv\Scripts\python.exe -m app.main
```

CLI（同一份 core 管线）：

```bash
# 地名 → 抓取 → 导出 GeoJSON + PNG
.venv\Scripts\python.exe -m app.cli "北京故宫" --formats geojson png --out out/gugong

# 坐标范围 → 全格式导出
.venv\Scripts\python.exe -m app.cli --bbox 39.905 116.395 39.910 116.400 \
    --formats geojson gpkg shp svg png --out out/test

# 指定图层 / 叠加瓦片底图（osm_de / osm_official / hot / osmfr / seamark / esri）
.venv\Scripts\python.exe -m app.cli "上海 外滩" --layers road building --formats svg --basemap osm_de
.venv\Scripts\python.exe -m app.cli --clear-cache
```

打包（需先装好全部依赖）：

```powershell
# Nuitka standalone 编译（MVSC，jobs 按机器调整）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_nuitka.ps1
# Inno Setup 安装包（需先安装 Inno Setup 7）
# 用 Inno 打开 installer\catlas.iss 编译，产物 Release\installer\Catlas-Setup-x.y.z.exe
```

在程序目录或 exe 旁放置 `portable.flag` 可启用便携模式（数据写入 `CatlasData/`，不写注册表目录）。

## 架构

```
app/
├─ core/        # 领域层（无 GUI 依赖）：geocode / fetch / clean / export / cache / pipeline
├─ services/    # 应用层：QThread 后台任务封装
├─ ui/          # 表现层：main_window / input_panel / map_canvas / theme(Mica)
├─ cli.py       # CLI 入口
└─ main.py      # GUI 入口
```

- 地理编码：Nominatim 优先、Photon 兜底，供应商熔断
- 抓取：镜像健康探测（剔除空库镜像）、429/504 指数退避、>5 km² 自动网格分块（上限 64 块）
- 缓存：bbox+图层 SHA1 键控 parquet + 瓦片磁盘缓存，LRU 容量清理
- 底图：免 Key 瓦片源（标准/官方/HOT/OSM France/海图标注/Esri 卫星影像），
  预览与 PNG/SVG 制图叠加，Web Mercator 对齐矢量图层
- 渲染：UTM/Web Mercator 投影保证比例，图例中文自动适配

## 测试

```bash
.venv\Scripts\python.exe -m pytest tests/ -q
```
