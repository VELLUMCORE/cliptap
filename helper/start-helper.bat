@echo off
setlocal
cd /d "%~dp0"
echo Starting ClipTap helper...
python server.py
pause
