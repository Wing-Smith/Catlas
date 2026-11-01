# ==========================================
# Catlas: add Windows Defender exclusions
# Run ONCE as Administrator (right-click -> Run with PowerShell)
# Encoding: UTF-8 with BOM
# ==========================================
$projectDir = "C:\Users\ytmpw\Documents\kimi\tasks\2026-10-30\13-56-04-a2accd3e\osm-map-tool"
$paths = @(
    "$projectDir\dist_nuitka",
    "$projectDir\Release",
    "C:\Users\ytmpw\AppData\Local\Nuitka"
)

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Please run this script as Administrator." -ForegroundColor Red
    pause
    exit 1
}

foreach ($p in $paths) {
    try {
        Add-MpPreference -ExclusionPath $p -ErrorAction Stop
        Write-Host "[OK] Exclusion added: $p" -ForegroundColor Green
    } catch {
        Write-Host "[FAIL] $p -- $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Current exclusions:" -ForegroundColor Cyan
(Get-MpPreference).ExclusionPath
pause
