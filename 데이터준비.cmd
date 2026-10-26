@echo off
cd /d "%~dp0"
python -m pip install --target .deps --upgrade yt-dlp
python prepare.py
pause
