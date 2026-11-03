"""轻量 i18n：zh / en 双语字典，切换语言时各页面调用 retranslate_ui()。

静态状态栏文案暂不翻译（占比小），所有页面级控件均已覆盖。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "app.title": "Catlas · 猫图集",
        "app.name": "Catlas",
        "app.tagline": "猫图集 · OpenStreetMap 地理数据抓取与制图",
        "splash.loading1": "正在唤醒 Calico…",
        "splash.loading2": "正在整理地图数据…",
        "splash.loading3": "正在连接 OSM 服务…",
        "nav.home": "主页",
        "nav.grab": "抓取与制图",
        "nav.draw": "选区地图",
        "nav.history": "历史",
        "nav.route": "路径规划",
        "nav.network": "网络监测",
        "nav.logs": "日志",
        "nav.settings": "设置",
        "status.ready": "就绪：输入地名或坐标范围，点击「开始抓取」",
        "status.wait_data": "等待数据",
        "exit.title": "确认退出程序？",
        "exit.content": "未保存的工作将不会保留。",
        "exit.quit": "退出",
        "exit.cancel": "再想想",
        "guide.title": "欢迎来到 Catlas",
        "guide.s1.t": "① 抓取数据",
        "guide.s1.b": "在「抓取与制图」页输入地名或坐标范围，一键获取路网、水域、绿地与建筑等 OpenStreetMap 数据。",
        "guide.s2.t": "② 圈选与样式",
        "guide.s2.b": "在「选区地图」页用画笔圈定抓取范围；抓取面板里可以调整每个图层的配色、线宽与不透明度，并存为预设。",
        "guide.s3.t": "③ 导出成图",
        "guide.s3.b": "导出为 SVG / PNG 用于可视化或二次开发；勾选海报模式可输出 A0 级 300DPI 大幅面，失败的任务支持断点续传。",
        "guide.next": "下一步",
        "guide.prev": "上一步",
        "guide.start": "开始体验",
        "guide.skip": "跳过",
        "drop.ok": "已导入 {name}：{counts}",
        "drop.unsupported": "不支持的文件类型 {ext}（支持 GeoJSON / Shapefile / GeoPackage）",
        "drop.failed": "导入失败：{msg}",
        "settings.update_url": "更新检查地址",
        "update.new": "发现新版本 v{v}",
        "update.go": "前往下载",
        "update.check_now": "检查更新",
        "update.checking": "正在检查…",
        "update.latest": "已是最新版本 v{v}",
        "update.found": "发现新版本 v{v}",
        "update.failed": "连接失败：{err}",
        "home.card_update": "更新",
        "home.update_conn": "连接状态",
        "home.update_conn_ok": "已连接 GitHub",
        "home.update_conn_fail": "不可达",
        "home.update_current": "当前版本",
        "home.update_latest": "GitHub 最新",
        "home.update_btn": "检查更新",
        "home.update_checking": "检查中…",
        "home.update_unknown": "未检查",
        "update.dev.title": "未发行版本提醒",
        "update.dev.content": "当前您使用的是还未发行的版本，可能存在问题与错误，请您谨慎使用。"
            "相关问题可以提交到 GitHub 仓库的 Issues 并标注好版本号，"
            "给您带来的不便敬请谅解。\n\nhttps://github.com/Wing-Smith/Catlas/issues",
        "update.dev.ok": "好",
        "update.dev.go": "前往发行版本页面下载发行版本",
        "update.banner_content": "新版本已发布，点击下方按钮前往下载；关闭本横幅不会影响下次启动提醒。",
        "update.toast": "Catlas 新版本已发布，点击打开下载页面。\n{url}",
        # 主页
        "home.greet1": "Hey there!",
        # 问候语保持英文原味，不随界面语言切换
        "home.greet2": "Pick a corner of the world — let's map it.",
        "home.subtitle": "从 OpenStreetMap 抓取路网、水域、绿地、建筑等地理数据，"
        "清洗转换为结构化 GeoJSON / Shapefile，并导出 SVG / PNG 用于可视化。",
        "home.section_quick": "快速开始",
        "home.btn_start": "去抓取数据",
        "home.btn_draw": "在地图上框选区域",
        "home.section_info": "运行信息",
        "home.info_python": "Python 版本",
        "home.info_qt": "Qt / PySide6",
        "home.info_cache": "数据缓存条目",
        "home.info_tiles": "瓦片缓存（文件 / 大小）",
        "home.info_endpoints": "Overpass 端点",
        "home.info_providers": "可用底图源",
        "home.info_profiles": "路径规划模式",
        "home.section_last": "最近抓取",
        "home.none": "暂无",
        "home.fetch_none": "尚未抓取数据",
        "home.card_app": "应用",
        "home.card_last": "最近抓取",
        "home.card_env": "运行环境",
        "home.card_cache": "数据与缓存",
        "home.card_sources": "数据源",
        "home.card_network": "网络状态",
        "home.info_platform": "操作系统",
        "home.info_version": "应用版本",
        "home.net_summary": "{ok} / {total} 项服务在线",
        "home.net_checking": "检测中…",
        "home.net_waiting": "等待首次探测结果",
        "home.desc_grab": "输入地名或坐标范围，抓取 OSM 数据并导出地图",
        "home.desc_draw": "在本地世界地图上用画笔圈选抓取范围",
        "home.desc_history": "查看、复用已抓取的数据与书签",
        "home.desc_route": "驾车 / 骑行 / 步行多模式路径规划",
        "home.desc_network": "并发探测各服务连通性与延迟",
        "home.desc_settings": "主题、语言、缓存目录与用户协议",
        "home.open_history": "查看历史",
        "home.open_network": "打开网络监测",
        "home.view_eula": "查看用户协议",
        "home.card_about": "关于",
        "home.about_line": "吉祥物 Calico · 内部代号 OMT",
        "home.env_line": "Python {py} · Qt {qt}",
        "home.pet.title": "Calico 的小窝",
        "home.pet.enabled": "小窝已开启，去首页看看 Calico 吧",
        "home.pet.disabled": "小窝已关闭，连点图标 7 次可再次开启",
        # 抓取面板
        "grab.range": "范围",
        "grab.mode_query": "地名",
        "grab.mode_bbox": "坐标范围",
        "grab.query_ph": "输入地名，如：北京故宫",
        "grab.layers": "图层",
        "grab.layer.road": "路网",
        "grab.layer.water": "水域",
        "grab.layer.green": "绿地",
        "grab.layer.building": "建筑",
        "grab.basemap": "瓦片底图（预览与制图）",
        "grab.basemap_none": "无底图",
        "grab.export": "导出格式",
        "grab.dpi": "PNG DPI",
        "grab.browse": "浏览…",
        "grab.start": "开始抓取",
        "grab.cancel": "取消",
        "grab.export_btn": "导出所选格式",
        # 样式
        "grab.style.preset": "样式预设",
        "grab.style.save": "存为预设…",
        "grab.style.custom": "自定义",
        "grab.preset.default": "默认",
        "grab.preset.night": "夜航（深色）",
        "grab.style.width_tip": "线宽倍率",
        "grab.style.alpha_tip": "不透明度",
        # 超大幅面
        "grab.poster": "超大幅面 PNG（分块渲染 · 仅矢量 · A0 级）",
        "grab.paper": "幅面",
        # 选区地图
        "draw.title": "选区地图（本地底图 · 离线）",
        "draw.hint": "滚轮缩放 · 右键平移 · 左键按当前工具绘制选区，点「应用选区」。",
        "draw.tool_move": "移动",
        "draw.tool_brush": "画笔",
        "draw.tool_rect": "矩形",
        "draw.tool_circle": "圆形",
        "draw.tool_poly": "多边形",
        "draw.mode": "选区模式",
        "draw.mode_new": "新建选区",
        "draw.mode_union": "叠加选区",
        "draw.mode_subtract": "从选区减去",
        "draw.hint_move": "移动：左键拖动平移，滚轮缩放。",
        "draw.hint_draw": "左键拖动绘制，松开完成。中空选区：先新建大图形，再切「从选区减去」扣掉内部。",
        "draw.hint_poly": "左键单击加点，双击或回车闭合，Esc 取消。",
        "draw.poly_points": "已取 {n} 个点",
        "draw.btn_apply": "应用选区",
        "draw.btn_clear": "清除选区",
        "draw.selected": "已选范围",
        "draw.none": "尚未框选",
        "draw.s": "南",
        "draw.w": "西",
        "draw.n": "北",
        "draw.e": "东",
        # 路径规划
        "route.title": "路径规划（OSRM · 全球）",
        "route.start_ph": "起点：经度, 纬度（如 116.397, 39.908）",
        "route.end_ph": "终点：经度, 纬度（如 116.404, 39.915）",
        "route.plan": "规划路径",
        "route.clear": "清除路线",
        "route.car": "汽车",
        "route.bike": "自行车",
        "route.foot": "步行",
        "route.bad_coords": "起终点格式应为「经度, 纬度」，如 116.397, 39.908",
        "route.planning": "正在规划路径…",
        # 设置
        "settings.section_net": "网络与抓取参数",
        "settings.interval": "请求间隔（秒）",
        "settings.http_timeout": "HTTP 超时（秒）",
        "settings.overpass_timeout": "Overpass 超时（秒）",
        "settings.max_area": "面积上限（km²）",
        "settings.cell_km": "分块边长（km）",
        "settings.cache_mb": "数据缓存上限（MB）",
        "settings.section_eps": "Overpass 端点（每行一个）",
        "settings.language": "界面语言（立即生效）",
        "settings.lang_zh": "简体中文",
        "settings.lang_en": "English",
        "settings.theme": "主题模式（立即生效）",
        "settings.theme_auto": "跟随系统",
        "settings.theme_dark": "深色",
        "settings.theme_light": "浅色",
        "settings.save": "保存设置",
        "settings.reset": "恢复默认",
        "settings.clear_data": "清除数据缓存",
        "settings.clear_tiles": "清除瓦片缓存",
        "settings.saved": "设置已保存",
        "settings.reset_hint": "已恢复默认值（需点击保存生效）",
        "settings.data_cleared": "已清除 {n} 个数据缓存条目",
        "settings.tiles_cleared": "已清除 {n} 张瓦片缓存",
        # 网络监测
        "net.title": "网络监测",
        "net.retry": "重新检测",
        "net.checking": "检测中…",
        "net.never": "尚未检测",
        "net.last": "上次检测：{t}",
        "net.online": "✓ 在线 · {ms:.0f} ms",
        "net.offline": "✗ 不可达",
        # 日志
        "logs.title": "运行日志",
        "logs.clear": "清空",
        "logs.empty": "暂无日志。开始一次抓取后，这里会显示每次请求与阶段流转。",
        "logs.hint": "记录抓取的每个分块、镜像切换、断点恢复与导出过程，排查问题用。",
        # 历史与书签
        "hist.title": "抓取历史",
        "hist.hint": "点击条目把参数（范围、图层、配色）填回抓取面板；加书签的条目不会被自动清理。",
        "hist.empty": "暂无抓取记录。完成一次抓取后自动记录。",
        "hist.refetch": "填入面板",
        "hist.bookmark": "书签",
        "hist.delete": "删除",
        "hist.clear": "清空",
        "hist.bookmarks_only": "仅显示书签",
        "hist.deleted": "已删除记录",
        "hist.cleared": "已清空 {n} 条记录",
        "hist.count_none": "无数据",
        # 关于
        "settings.about": "关于 Catlas",
        "settings.eula": "用户协议",
        "settings.copyright": "版权所有 © 2026 Wing North Studio",
        "settings.about_text": "Catlas · 猫图集 v1.0 —— 内部代号 OMT。\n"
        "吉祥物：Calico，一只好奇的黑猫。\n"
        "地图数据 © OpenStreetMap contributors，依据 ODbL 许可使用；"
        "对外发布地图成果时请注明数据来源。详见 openstreetmap.org/copyright。",
        "settings.eula_text": "Catlas 用户协议\n\n"
        "1. 许可授予\n"
        "本软件为免费软件，供个人学习、研究与合法用途使用。未经 Wing North Studio 书面许可，"
        "不得对本软件进行反向工程、出租、出售或用于任何违法用途。\n\n"
        "2. 数据来源与版权\n"
        "本软件通过 OpenStreetMap（OSM）的公开接口获取地理数据。地图数据 "
        "© OpenStreetMap contributors，依据 ODbL 许可使用；您对外发布基于该数据的"
        "地图成果时，须按照 ODbL 要求注明数据来源。\n\n"
        "3. 第三方服务条款\n"
        "本软件使用的 Overpass、瓦片、地理编码与路径规划服务均为第三方公共免费服务，"
        "请遵守各服务的使用政策（限速、User-Agent 规范、禁止批量滥用）。"
        "Esri World Imagery 卫星影像仅限软件内实时预览，禁止导出叠加该底图的成品图。\n\n"
        "4. 免责声明\n"
        "本软件按「现状」提供，不附带任何明示或默示的担保。Wing North Studio "
        "不对因使用本软件而产生的任何直接或间接损失承担责任；"
        "通过本软件获取的数据的准确性、完整性与时效性不作保证。\n\n"
        "5. 隐私\n"
        "所有数据缓存、配置与历史记录均存储在您的本地设备上；"
        "本软件不收集、不上传任何个人信息。\n\n"
        "版权所有 © 2026 Wing North Studio。保留所有权利。",
    },
    "en": {
        "app.title": "Catlas",
        "app.name": "Catlas",
        "app.tagline": "OSM geodata fetching & mapping",
        "splash.loading1": "Waking up Calico…",
        "splash.loading2": "Preparing map data…",
        "splash.loading3": "Connecting to OSM services…",
        "nav.home": "Home",
        "nav.grab": "Fetch & Map",
        "nav.draw": "Area Picker",
        "nav.history": "History",
        "nav.route": "Routing",
        "nav.network": "Network",
        "nav.logs": "Logs",
        "nav.settings": "Settings",
        "status.ready": "Ready: enter a place name or coordinates, then click \"Start Fetch\"",
        "status.wait_data": "Waiting for data",
        "exit.title": "Quit Catlas?",
        "exit.content": "Any unsaved work will be lost.",
        "exit.quit": "Quit",
        "exit.cancel": "Stay",
        "guide.title": "Welcome to Catlas",
        "guide.s1.t": "1. Fetch data",
        "guide.s1.b": "On the Fetch & Plot page, enter a place name or coordinates to grab roads, water, green areas and buildings from OpenStreetMap.",
        "guide.s2.t": "2. Select & style",
        "guide.s2.b": "Draw your area on the Selection Map page; adjust per-layer color, line width and opacity in the fetch panel, and save them as presets.",
        "guide.s3.t": "3. Export",
        "guide.s3.b": "Export SVG / PNG for visualization or further work; poster mode renders A0-size 300DPI sheets, and interrupted jobs resume from checkpoints.",
        "guide.next": "Next",
        "guide.prev": "Back",
        "guide.start": "Get started",
        "guide.skip": "Skip",
        "drop.ok": "Imported {name}: {counts}",
        "drop.unsupported": "Unsupported type {ext} (GeoJSON / Shapefile / GeoPackage only)",
        "drop.failed": "Import failed: {msg}",
        "settings.update_url": "Update check URL",
        "update.new": "New version v{v} available",
        "update.go": "Download",
        "update.check_now": "Check for updates",
        "update.checking": "Checking…",
        "update.latest": "You're up to date (v{v})",
        "update.found": "New version v{v} available",
        "update.failed": "Connection failed: {err}",
        "home.card_update": "Updates",
        "home.update_conn": "Connection",
        "home.update_conn_ok": "GitHub reachable",
        "home.update_conn_fail": "Unreachable",
        "home.update_current": "Current version",
        "home.update_latest": "Latest on GitHub",
        "home.update_btn": "Check now",
        "home.update_checking": "Checking…",
        "home.update_unknown": "Not checked",
        "update.dev.title": "Unreleased build notice",
        "update.dev.content": "You are running a version that has not been officially released. "
            "It may contain problems or errors — please use it with caution. "
            "Report issues to the GitHub repository's Issues page and include your version number. "
            "Sorry for the inconvenience.\n\nhttps://github.com/Wing-Smith/Catlas/issues",
        "update.dev.ok": "OK",
        "update.dev.go": "Go to releases page",
        "update.banner_content": "A new version is available. Click below to download. "
            "Closing this banner won't disable the reminder on next launch.",
        "update.toast": "A new Catlas release is available. Click to open the download page.\n{url}",
        "home.greet1": "Hey there!",
        "home.greet2": "Pick a corner of the world — let's map it.",
        "home.subtitle": "Fetch roads, water, green areas and buildings from OpenStreetMap, "
        "clean and convert them into GeoJSON / Shapefile, and export SVG / PNG.",
        "home.section_quick": "Quick Start",
        "home.btn_start": "Fetch data",
        "home.btn_draw": "Pick area on map",
        "home.section_info": "Runtime Info",
        "home.info_python": "Python version",
        "home.info_qt": "Qt / PySide6",
        "home.info_cache": "Data cache entries",
        "home.info_tiles": "Tile cache (files / size)",
        "home.info_endpoints": "Overpass endpoints",
        "home.info_providers": "Basemap providers",
        "home.info_profiles": "Routing profiles",
        "home.section_last": "Last Fetch",
        "home.none": "N/A",
        "home.fetch_none": "No fetch yet",
        "home.card_app": "App",
        "home.card_last": "Last Fetch",
        "home.card_env": "Runtime",
        "home.card_cache": "Data & Cache",
        "home.card_sources": "Data Sources",
        "home.card_network": "Network",
        "home.info_platform": "OS",
        "home.info_version": "App version",
        "home.net_summary": "{ok} / {total} services online",
        "home.net_checking": "Checking…",
        "home.net_waiting": "Waiting for first probe",
        "home.desc_grab": "Search a place or bbox, fetch OSM data and export maps",
        "home.desc_draw": "Draw the fetch area with a brush on the local world map",
        "home.desc_history": "Review and reload past fetches and bookmarks",
        "home.desc_route": "Car / bike / foot routing profiles",
        "home.desc_network": "Concurrent connectivity and latency probes",
        "home.desc_settings": "Theme, language, cache folders and user agreement",
        "home.open_history": "Open history",
        "home.open_network": "Open network monitor",
        "home.view_eula": "View user agreement",
        "home.card_about": "About",
        "home.about_line": "Mascot Calico · codename OMT",
        "home.env_line": "Python {py} · Qt {qt}",
        "home.pet.title": "Calico's Corner",
        "home.pet.enabled": "Corner unlocked — visit the home page for Calico",
        "home.pet.disabled": "Corner hidden — tap the icon 7 times to bring it back",
        "grab.range": "Extent",
        "grab.mode_query": "Place",
        "grab.mode_bbox": "Coordinates",
        "grab.query_ph": "Enter a place, e.g. Forbidden City, Beijing",
        "grab.layers": "Layers",
        "grab.layer.road": "Roads",
        "grab.layer.water": "Water",
        "grab.layer.green": "Green areas",
        "grab.layer.building": "Buildings",
        "grab.basemap": "Basemap (preview & export)",
        "grab.basemap_none": "No basemap",
        "grab.export": "Export formats",
        "grab.dpi": "PNG DPI",
        "grab.browse": "Browse…",
        "grab.start": "Start Fetch",
        "grab.cancel": "Cancel",
        "grab.export_btn": "Export Selected",
        # 样式
        "grab.style.preset": "Style preset",
        "grab.style.save": "Save as preset…",
        "grab.style.custom": "Custom",
        "grab.preset.default": "Default",
        "grab.preset.night": "Night (dark)",
        "grab.style.width_tip": "Line width scale",
        "grab.style.alpha_tip": "Opacity",
        # 超大幅面
        "grab.poster": "Poster PNG (tiled render · vector only · A0-class)",
        "grab.paper": "Paper size",
        "draw.title": "Area Picker (local basemap · offline)",
        "draw.hint": "Wheel: zoom · Right: pan · Left: draw with the current tool, then click \"Apply\".",
        "draw.tool_move": "Pan",
        "draw.tool_brush": "Brush",
        "draw.tool_rect": "Rect",
        "draw.tool_circle": "Circle",
        "draw.tool_poly": "Polygon",
        "draw.mode": "Mode",
        "draw.mode_new": "New selection",
        "draw.mode_union": "Add to selection",
        "draw.mode_subtract": "Subtract from selection",
        "draw.hint_move": "Pan: left-drag to move, wheel to zoom.",
        "draw.hint_draw": "Left-drag to draw; release to finish. For a hollow area: draw the big shape, then switch to \"Subtract from selection\".",
        "draw.hint_poly": "Left-click to add points; double-click or Enter to close, Esc cancels.",
        "draw.poly_points": "{n} points placed",
        "draw.btn_apply": "Apply",
        "draw.btn_clear": "Clear",
        "draw.selected": "Selected extent",
        "draw.none": "Nothing selected",
        "draw.s": "S",
        "draw.w": "W",
        "draw.n": "N",
        "draw.e": "E",
        "route.title": "Routing (OSRM · worldwide)",
        "route.start_ph": "Start: lon, lat (e.g. 116.397, 39.908)",
        "route.end_ph": "End: lon, lat (e.g. 116.404, 39.915)",
        "route.plan": "Route",
        "route.clear": "Clear",
        "route.car": "Car",
        "route.bike": "Bike",
        "route.foot": "Foot",
        "route.bad_coords": "Start/end must be \"lon, lat\", e.g. 116.397, 39.908",
        "route.planning": "Routing…",
        "settings.section_net": "Network & Fetch",
        "settings.interval": "Request interval (s)",
        "settings.http_timeout": "HTTP timeout (s)",
        "settings.overpass_timeout": "Overpass timeout (s)",
        "settings.max_area": "Max area (km²)",
        "settings.cell_km": "Cell size (km)",
        "settings.cache_mb": "Data cache limit (MB)",
        "settings.section_eps": "Overpass endpoints (one per line)",
        "settings.language": "Language (applies instantly)",
        "settings.lang_zh": "简体中文",
        "settings.lang_en": "English",
        "settings.theme": "Theme (applies instantly)",
        "settings.theme_auto": "Follow system",
        "settings.theme_dark": "Dark",
        "settings.theme_light": "Light",
        "settings.save": "Save",
        "settings.reset": "Reset Defaults",
        "settings.clear_data": "Clear Data Cache",
        "settings.clear_tiles": "Clear Tile Cache",
        "settings.saved": "Settings saved",
        "settings.reset_hint": "Defaults restored (click Save to apply)",
        "settings.data_cleared": "Cleared {n} data cache entries",
        "settings.tiles_cleared": "Cleared {n} cached tiles",
        "net.title": "Network Monitor",
        "net.retry": "Re-check",
        "net.checking": "Checking…",
        "net.never": "Not checked yet",
        "net.last": "Last check: {t}",
        "net.online": "✓ online · {ms:.0f} ms",
        "net.offline": "✗ unreachable",
        # 日志
        "logs.title": "Runtime Logs",
        "logs.clear": "Clear",
        "logs.empty": "No logs yet. Start a fetch and each request will show up here.",
        "logs.hint": "Records every fetch cell, mirror switch, checkpoint resume and export step for troubleshooting.",
        # 历史与书签
        "hist.title": "Fetch History",
        "hist.hint": "Click an entry to restore its parameters (extent, layers, styles) to the fetch panel. Bookmarked entries survive auto-cleanup.",
        "hist.empty": "No records yet. Finish a fetch to create one.",
        "hist.refetch": "Load",
        "hist.bookmark": "Bookmark",
        "hist.delete": "Delete",
        "hist.clear": "Clear",
        "hist.bookmarks_only": "Bookmarks only",
        "hist.deleted": "Record deleted",
        "hist.cleared": "Cleared {n} records",
        "hist.count_none": "no data",
        # 关于
        "settings.about": "About Catlas",
        "settings.eula": "User Agreement",
        "settings.copyright": "Copyright © 2026 Wing North Studio",
        "settings.about_text": "Catlas v1.0 — internal codename OMT.\n"
        "Mascot: Calico, a curious black cat.\n"
        "Map data © OpenStreetMap contributors, used under the ODbL license; "
        "please credit the source when publishing map outputs. See openstreetmap.org/copyright.",
        "settings.eula_text": "Catlas User Agreement\n\n"
        "1. License Grant\n"
        "This software is free of charge and intended for personal learning, research and lawful "
        "use only. Without prior written permission from Wing North Studio, you may not reverse "
        "engineer, rent, sell, or use this software for any unlawful purpose.\n\n"
        "2. Data Sources and Copyright\n"
        "This software retrieves geodata via the public APIs of OpenStreetMap (OSM). "
        "Map data © OpenStreetMap contributors, used under the ODbL license; any map output you "
        "publish must credit the data source as required by ODbL.\n\n"
        "3. Third-Party Service Terms\n"
        "Overpass, tile, geocoding and routing services used by this software are public, "
        "free third-party services. Please respect their usage policies (rate limits, "
        "User-Agent requirements, no bulk abuse). Esri World Imagery is for on-screen preview "
        "only; exporting rendered output overlaid on this basemap is prohibited.\n\n"
        "4. Disclaimer\n"
        "This software is provided \"as is\" without warranty of any kind. Wing North Studio "
        "shall not be liable for any direct or indirect damages arising from the use of this "
        "software. No guarantee is made regarding the accuracy, completeness or timeliness of "
        "data obtained through this software.\n\n"
        "5. Privacy\n"
        "All data caches, settings and history records are stored locally on your device. "
        "This software collects and uploads no personal information.\n\n"
        "Copyright © 2026 Wing North Studio. All rights reserved.",
    },
}

_current = "zh"


def language() -> str:
    return _current


def set_language(lang: str) -> None:
    global _current
    if lang in _STRINGS:
        _current = lang
    else:
        logger.warning("未知语言：%s，保持 %s", lang, _current)


def tr(key: str, **fmt) -> str:
    text = _STRINGS.get(_current, {}).get(key) or _STRINGS["zh"].get(key) or key
    return text.format(**fmt) if fmt else text
