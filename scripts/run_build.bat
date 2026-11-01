@echo off
rem Catlas Nuitka build launcher (background use, log goes to project root)
set PROCESSOR_ARCHITECTURE=AMD64
set PROCESSOR_ARCHITEW6432=AMD64
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build_nuitka.ps1" > "nuitka_build.log" 2>&1
echo DONE_%ERRORLEVEL% >> "nuitka_build.log"
