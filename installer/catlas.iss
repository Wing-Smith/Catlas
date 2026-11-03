; ============================================================
; Catlas 1.3.2 安装脚本（Inno Setup 7 适配）
; 依赖的 7 代特性：
;   - WizardStyle=modern dynamic   向导跟随 Windows 明暗模式（6.6+）
;   - WizardImageFile 支持 PNG     向导图无需转 BMP（6.5.2+）
;   - WizardBackImageFile          整页背景图预留位（6.7+）
;   - RedirectionGuard             Windows 重定向防护（6.7+）
; 编译前请确认 ..\Release\Catlas 目录存在（Nuitka standalone 产物）
; ============================================================

#define MyAppName      "Catlas"
#define MyAppVersion   "1.3.2"
#define MyAppPublisher "Wing North Studio"
#define MyAppURL       "https://github.com/Wing-Smith/Catlas"
#define MyAppExe       "Catlas.exe"
#define MyAppId        "{3ACA8653-2F01-11E9-B04B-FAD5F7370A27}"

[Setup]
; 固定 AppId：升级安装时覆盖旧版本而不是并存
AppId={{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 目标系统：Windows 10 1809+（Mica 毛玻璃的最低要求）
MinVersion=10.0.17763
; 仅 64 位 Windows
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 重定向防护（DLL 劫持缓解，Inno 6.7+）
RedirectionGuard=yes

; 用户级安装，不需要管理员权限（写入 %LOCALAPPDATA%\Programs）
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 注意：不使用 SourceDir，否则 LicenseFile/OutputDir/SetupIconFile 等
; 所有相对路径都会改为相对 ..\Release\Catlas 解析（Inno 行为）。
; 保持脚本所在目录为基准，[Files] 段直接指向 ..\Release\Catlas。
OutputDir=..\Release\installer
OutputBaseFilename=Catlas-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; 向导风格：modern + 跟随系统明暗模式；暗色下 RTF 协议文字自动反色
WizardStyle=modern dynamic

; 向导图片（预留位——豆包素材到位后直接放 PNG，取消注释即可）
; 主图：modern 风格建议 120x460 及以上、PNG（旧版要求 BMP，7 代已支持 PNG）
; 小图：55x58 及以上、PNG
;WizardImageFile=setup_banner.png
;WizardSmallImageFile=setup_small.png
; 整页背景图（6.7+，可选；设置后自动启用 windows11 风格）
;WizardBackImageFile=setup_bg.png
;WizardBackImageFileDynamicDark=setup_bg_dark.png

; 图标与版本信息（写入安装程序属性）
SetupIconFile=..\app\assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExe}
VersionInfoVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Catlas Setup
VersionInfoCopyright=Copyright (c) 2026 Wing North Studio
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoOriginalFileName=Catlas-Setup-{#MyAppVersion}.exe

; 用户协议（中英双语，暗色模式自动适配）
LicenseFile=EULA.rtf

; 关闭运行中的实例再装
CloseApplications=yes
CloseApplicationsFilter={#MyAppExe}

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

[Languages]
; 安装界面语言由用户在向导第一步选择（官方中文语言包随 Inno 自带）
Name: "chs"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "en";  MessagesFile: "compiler:Default.isl"

[Messages]
; 向导底部提示语（两种语言都显示，版本号随 #define 自动更新）
chs.BeveledLabel=Catlas v{#MyAppVersion} ©{#MyAppPublisher} 2026
en.BeveledLabel=Catlas v{#MyAppVersion} ©{#MyAppPublisher} 2026

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; standalone 模式整个文件夹原样安装
Source: "..\Release\Catlas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; AppUserModelID 必须与应用内 WindowsToaster("Catlas") 完全一致，
; 系统通知才能显示应用图标与名称
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; AppUserModelID: "Catlas"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon; AppUserModelID: "Catlas"

[Run]
; 装完可选直接启动
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 可选：卸载时清理用户数据（取消注释生效；便携模式的 CatlasData 在安装目录，会被自动移除）
;Type: filesandordirs; Name: "{localappdata}\osm-map-tool"
