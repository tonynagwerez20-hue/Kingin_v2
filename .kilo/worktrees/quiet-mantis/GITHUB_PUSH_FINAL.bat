@echo off
echo ==========================================================
echo    GITHUB PUSH: v6.1 RESTORED (Institutional Core)
echo ==========================================================
git init
git add .
git commit -m "Update: v6.1 Restored - Fixed Killzone Timezone & Enhanced Alpha Docs"
git branch -M master
git remote add origin https://github.com/tonynagwerez-hue/kingin.git
echo.
echo Attempting to push to master...
git push -u origin master
echo ==========================================================
pause
