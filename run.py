import os
import sys
import time
import webbrowser
import threading
import uvicorn

# Ensure UTF-8 stdout encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def open_browser():
    time.sleep(1.5)
    print("\n[YTDLP Studio] Dang mo giao dien tren trinh duyet tai http://127.0.0.1:8000 ...")
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("=" * 60)
    print("      YTDLP Studio Desktop WebApp Engine (FastAPI)     ")
    print("=" * 60)
    print("Server: http://127.0.0.1:8000")
    print("Thu muc chua file tai: app/downloads")
    print("=" * 60)

    # Thread to open browser automatically
    threading.Thread(target=open_browser, daemon=True).start()

    # Start FastAPI Server
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

