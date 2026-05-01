
Write-Host "=========================================="
Write-Host "   IGOF SYSTEM STARTUP  "
Write-Host "=========================================="
Write-Host ""
Write-Host "[1/3] Checks..."
$currentDir = $PSScriptRoot
Set-Location $currentDir
Write-Host "Project Root: $currentDir"

Write-Host "[1/3] Checks..."
$pythonPath = "python"
if (Test-Path "$currentDir\.venv_v2\Scripts\python.exe") {
    $pythonPath = "$currentDir\.venv_v2\Scripts\python.exe"
    Write-Host "Using Virtual Environment: $pythonPath"
}
else {
    Write-Host "Using Global Python"
}

Write-Host "[2/3] Launching Data Feed Server (server.py)..."
# Start-Process -FilePath $pythonPath -ArgumentList "data_feed/server.py" -NoNewWindow
# Better: Start in new window so we can see logs
Start-Process "cmd.exe" -ArgumentList "/k $pythonPath data_feed/server.py"
Write-Host "Waiting 5 seconds for Server to initialize..."
Start-Sleep -Seconds 5

Write-Host "[3/3] Launching Modular Strategy Pipeline (modular_bootstrapper.py)..."
$env:PYTHONPATH = $currentDir
& $pythonPath Engine/modular_bootstrapper.py

Write-Host "System Shutdown."
Read-Host "Press Enter to exit..."
