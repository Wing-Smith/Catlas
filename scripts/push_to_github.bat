@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0\.."

REM ========== Catlas 首次推送到 GitHub ==========
REM 用法：
REM   1. 先在 https://github.com/new 建一个【空仓库】
REM      （名字建议 Catlas，不要勾 README/.gitignore/License）
REM   2. 双击本脚本，按提示粘贴仓库地址（如 https://github.com/你的用户名/Catlas.git）
REM   3. 首次推送会弹出浏览器让你登录 GitHub 授权（Git Credential Manager）

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 找不到 git，请先安装 Git for Windows 或用 GitHub Desktop 自带的 git。
    pause
    exit /b 1
)

if not exist .git (
    echo [1/4] 初始化仓库...
    git init -b main
) else (
    echo [1/4] 仓库已初始化，跳过。
)

echo [2/4] 添加文件并提交...
git add .
git commit -m "Catlas v1.2.7: OSM 地理数据抓取与制图工具初始提交" >nul 2>nul
if errorlevel 1 echo     （没有新的改动需要提交，跳过。）

set /p REPO=请输入 GitHub 仓库地址（https 或 git@ 均可，回车确认）:
if "%REPO%"=="" (
    echo [ERROR] 仓库地址不能为空。
    pause
    exit /b 1
)

echo [3/4] 设置远程仓库: %REPO%
git remote remove origin >nul 2>nul
git remote add origin "%REPO%"

echo [4/4] 推送到 GitHub（首次会弹出浏览器授权）...
git push -u origin main
if errorlevel 1 (
    echo.
    echo [ERROR] 推送失败。常见原因：
    echo   - 仓库地址写错，或远程仓库不是空的（新建时必须不勾任何初始化文件）
    echo   - 没完成浏览器授权
    pause
    exit /b 1
)

echo.
echo [OK] 推送完成！仓库地址: %REPO%
pause
