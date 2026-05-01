@echo off
git --version > git_out.txt 2>&1
echo Exit Code: %errorlevel% >> git_out.txt
