# -*- mode: python ; coding: utf-8 -*-
"""Cau hinh dong goi YTDLP Studio thanh file .exe portable.

Build:  pyinstaller ytdlp-studio.spec --noconfirm
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

# yt-dlp nap extractor bang importlib luc chay -> PyInstaller khong tu thay duoc.
# collect_all keo toan bo submodule + data di theo.
ytdlp_datas, ytdlp_binaries, ytdlp_hidden = collect_all('yt_dlp')

# imageio_ffmpeg chua san binary ffmpeg (~88MB) trong package.
ff_datas, ff_binaries, ff_hidden = collect_all('imageio_ffmpeg')

# pywebview + pythonnet: backend Edge Chromium duoc nap dong luc chay.
wv_datas, wv_binaries, wv_hidden = collect_all('webview')
clr_datas, clr_binaries, clr_hidden = collect_all('clr_loader')

# pystray cho icon khay he thong
tray_datas, tray_binaries, tray_hidden = collect_all('pystray')

hiddenimports = (
    ytdlp_hidden
    + ff_hidden
    + wv_hidden
    + clr_hidden
    + tray_hidden
    # uvicorn chon protocol/loop bang chuoi luc chay, cung khong tu thay duoc
    + collect_submodules('uvicorn')
    + [
        'app.main',
        'app.downloader',
        'app.paths',
        'app.license',
        'clr',
    ]
)

datas = (
    [('app/static', 'static'), ('assets/icon.png', 'assets')]
    + ytdlp_datas + ff_datas + wv_datas + clr_datas + tray_datas
)
binaries = ytdlp_binaries + ff_binaries + wv_binaries + clr_binaries + tray_binaries

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Cac package nang khong dung den, loai bot cho nhe file.
        # KHONG loai PIL: pystray can PIL de nap icon khay he thong.
        'tkinter',
        'matplotlib',
        'numpy',
        'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Dang thu muc (onedir) thay vi mot file duy nhat: khong phai giai nen
# ~88MB ffmpeg ra thu muc tam moi lan chay, nen mo gan nhu tuc thi.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YTDLP-Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # console=False: khong hien cua so den. Moi thu in ra deu di vao
    # ytdlp-studio.log canh file exe (xem ensure_stdio trong gui.py).
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='YTDLP-Studio',
)
