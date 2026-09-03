import os
import sys
import time
import webbrowser
import threading
import multiprocessing

import uvicorn

# Ensure UTF-8 stdout encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        # Ban .exe che do windowed khong co stdout that
        pass

IS_FROZEN = getattr(sys, "frozen", False)

# Ban .exe mac dinh chi mo tren may nay cho an toan.
# Ban chay bang python giu 0.0.0.0 de tunnel / LAN dung duoc.
DEFAULT_HOST = "127.0.0.1" if IS_FROZEN else "0.0.0.0"
HOST = os.environ.get("HOST", DEFAULT_HOST)
PORT = int(os.environ.get("PORT", "8000"))
RELOAD = os.environ.get("RELOAD", "0") == "1" and not IS_FROZEN


def open_browser():
    time.sleep(1.5)
    print(f"\n[YTDLP Studio] Dang mo giao dien tren trinh duyet tai http://127.0.0.1:{PORT} ...")
    webbrowser.open(f"http://127.0.0.1:{PORT}")


def main():
    # PHAI chay truoc moi import yt_dlp (xem app/engine.py)
    from app.engine import bootstrap
    bootstrap()

    from app.paths import downloads_dir

    print("=" * 60)
    print("      YTDLP Studio Desktop WebApp Engine (FastAPI)     ")
    print("=" * 60)
    print(f"Server: http://127.0.0.1:{PORT}  (bind {HOST})")
    print(f"Thu muc chua file tai: {downloads_dir()}")
    if HOST == "0.0.0.0":
        print("Che do mo: may khac trong mang LAN va Cloudflare Tunnel deu vao duoc.")
    print("=" * 60)

    if os.environ.get("NO_BROWSER") != "1":
        threading.Thread(target=open_browser, daemon=True).start()

    if RELOAD:
        # reload can import string de nap lai module
        uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
    else:
        # Trong .exe phai truyen thang doi tuong app: PyInstaller khong co
        # cay thu muc de uvicorn resolve chuoi "app.main:app".
        from app.main import app as fastapi_app
        uvicorn.run(fastapi_app, host=HOST, port=PORT)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
