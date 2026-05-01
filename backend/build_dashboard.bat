@echo off
cd /d "c:\Users\LENOVO\Desktop\kingin-master"
echo Building React application...
call npm run build
echo Building Tauri application...
call npm run tauri:build
echo Build complete!