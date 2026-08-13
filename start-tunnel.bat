@echo off
chcp 65001 >nul
title YTDLP Studio - Cloudflare Tunnel
cd /d "%~dp0"

python tunnel.py

echo.
echo Tunnel da dong.
pause
