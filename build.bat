@echo off
chcp 65001 >nul
title Build Media Download Studio .exe
cd /d "%~dp0"

echo ============================================================
echo    Dong goi Media Download Studio thanh file .exe portable
echo ============================================================
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [1/2] Dang cai PyInstaller...
    python -m pip install pyinstaller
) else (
    echo [1/2] PyInstaller da co.
)

echo.
echo [2/2] Dang build... mat khoang 1-3 phut, dung tat cua so.
echo.

python -m PyInstaller MediaDownloadStudio.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [LOI] Build that bai. Xem log ben tren.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   XONG! App nam tai:  dist\MediaDownloadStudio\MediaDownloadStudio.exe
echo.
echo   Chep ca thu muc dist\MediaDownloadStudio di dau cung chay duoc,
echo   khong can cai Python.
echo   Video tai ve nam trong thu muc "downloads" canh file exe.
echo ============================================================
echo.
pause
