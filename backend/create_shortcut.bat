@echo off
echo Creating desktop shortcut for Institutional Trading System...

set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%src-tauri\target\release\institutional-trading-system.exe"
set "ICON=%SCRIPT_DIR%src-tauri\icons\icon.ico"
set "USER_DESKTOP=%USERPROFILE%\Desktop"
set "PUBLIC_DESKTOP=%PUBLIC%\Desktop"
set "SHORTCUT_NAME=Institutional Trading System.lnk"

if not exist "%PUBLIC_DESKTOP%" (
    set "PUBLIC_DESKTOP=%USER_DESKTOP%"
)

if not exist "%ICON%" (
    REM Fallback to tauri build icon if repo icon missing
    if exist "%SCRIPT_DIR%src-tauri\icons\icon.ico" (
        set "ICON=%SCRIPT_DIR%src-tauri\icons\icon.ico"
    ) else (
        set "ICON=%TARGET%"
    )
)

echo Checking if executable exists...
if not exist "%TARGET%" (
    echo WARNING: Executable not found at %TARGET%
    echo Please make sure the build completed successfully.
)

echo Creating shortcut(s)...
powershell -NoProfile -Command ^
    "$desktops = @('%USER_DESKTOP%', '%PUBLIC_DESKTOP%') | Select-Object -Unique;" ^
    "$oldPaths = @();" ^
    "foreach ($desktop in $desktops) {" ^
    "  $oldPaths += ($desktop + '\kingin.lnk');" ^
    "  $oldPaths += ($desktop + '\%SHORTCUT_NAME%');" ^
    "};" ^
    "foreach ($path in $oldPaths) { if (Test-Path $path) { Remove-Item $path -Force -ErrorAction SilentlyContinue } }" ^
    "$WshShell = New-Object -ComObject WScript.Shell;" ^
    "foreach ($desktop in $desktops) {" ^
    "  if (-not (Test-Path $desktop)) { continue }" ^
    "  $path = Join-Path $desktop '%SHORTCUT_NAME%';" ^
    "  try {" ^
    "    $Shortcut = $WshShell.CreateShortcut($path);" ^
    "    $Shortcut.TargetPath = '%TARGET%';" ^
    "    $Shortcut.WorkingDirectory = '%SCRIPT_DIR%';" ^
    "    $Shortcut.Description = 'Launch Institutional Trading System Dashboard';" ^
    "    $Shortcut.IconLocation = '%ICON%';" ^
    "    $Shortcut.Save();" ^
    "    Write-Output (\"OK: \" + $path);" ^
    "  } catch {" ^
    "    Write-Warning (\"Unable to save shortcut \" + $path + \": \" + $_.Exception.Message)" ^
    "  }" ^
    "}"

if exist "%USER_DESKTOP%\%SHORTCUT_NAME%" (
    echo SUCCESS: User desktop shortcut created at %USER_DESKTOP%\%SHORTCUT_NAME%
)
if exist "%PUBLIC_DESKTOP%\%SHORTCUT_NAME%" (
    echo SUCCESS: Public desktop shortcut created at %PUBLIC_DESKTOP%\%SHORTCUT_NAME%
)

echo Done.
pause