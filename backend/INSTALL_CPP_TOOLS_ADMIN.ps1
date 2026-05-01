# INSTALL_CPP_TOOLS_ADMIN.ps1
# -------------------------------------------------------------------
# Institutional Trading System - Prerequisites Installer
# -------------------------------------------------------------------
# Run this script As Administrator BEFORE running SETUP_TAURI.bat 
# on a completely brand new machine. It silently installs the 
# Windows MSVC C++ Linker and Windows SDK required for the Desktop App.
# -------------------------------------------------------------------

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " INSTALLING PREREQUISITES FOR NEW MACHINE (C++ BUILD TOOLS)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Ensure Administrator Privileges
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[ERROR] This script MUST be run as an Administrator!" -ForegroundColor Red
    Write-Host "Please close this window, right-click PowerShell -> 'Run as Administrator', and try again." -ForegroundColor Yellow
    Pause
    exit
}

Write-Host "`n[1/1] Requesting Winget to silently download and install Microsoft Desktop C++ Workloads (~2GB+)..." -ForegroundColor Yellow
Write-Host "Depending on your internet connection, this could take 5-15 minutes. Please be patient.`n"

# Run Winget installation silently.
winget install Microsoft.VisualStudio.2022.BuildTools --override "--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" --accept-package-agreements --accept-source-agreements

if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 3010) {
    Write-Host "`n[SUCCESS] The C++ Native Linker and Windows SDK were successfully installed!" -ForegroundColor Green
    Write-Host "You are now fully ready to run SETUP_TAURI.bat." -ForegroundColor Green
} else {
    Write-Host "`n[WARNING] Winget exited with code: $LASTEXITCODE" -ForegroundColor DarkYellow
    Write-Host "If the code is 1603, ensure nothing else is installing. If the installer was already installed via another method, you can proceed." -ForegroundColor DarkYellow
}

Write-Host "`nPress any key to close..."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
