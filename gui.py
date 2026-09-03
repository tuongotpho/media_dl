"""Entry point che do desktop: mo giao dien trong cua so native, khong console.

Server FastAPI chay o thread nen, giao dien web duoc nhung vao mot cua so
WebView2 (Edge Chromium) nen nguoi dung thay day la mot app desktop binh thuong.

Chay:  python gui.py        (hoac double-click MediaDownloadStudio.exe sau khi build)
"""
import os
import sys
import socket
import threading
import time

ACTIVE_STATUSES = ('starting', 'downloading', 'merging')

# Dong cua so chi thu xuong khay, thoat han phai qua menu khay.
state = {'quitting': False}


def ensure_stdio():
    """Che do windowed khong co console nen sys.stdout/stderr = None.

    uvicorn va logging deu ghi vao stderr; neu de None thi loi bi nuot sach
    va app chet im lang khong dau vet. Tro chung vao file log canh exe.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return

    from app.paths import base_dir
    try:
        stream = open(os.path.join(base_dir(), "ytdlp-studio.log"),
                      "a", encoding="utf-8", buffering=1)
    except Exception:
        stream = open(os.devnull, "w", encoding="utf-8")

    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def find_free_port() -> int:
    """Xin he dieu hanh mot port trong, tranh dung do voi app khac o 8000."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def start_tray(window, count_active):
    """Tao icon khay he thong. Tra ve icon, hoac None neu khong tao duoc.

    Tra ve None la tin hieu quan trong: khong co khay thi cua so phai dong
    that su, neu khong nguoi dung se mat duong vao app.
    """
    try:
        import pystray
        from PIL import Image
        from app.paths import asset_path

        image = Image.open(asset_path("icon.png"))

        def do_show(icon=None, item=None):
            window.show()

        def do_quit(icon=None, item=None):
            active = count_active()
            if active:
                window.show()
                try:
                    ok = window.create_confirmation_dialog(
                        "Dang tai video",
                        f"Con {active} video chua tai xong. Thoat se huy.\n\nVan thoat?"
                    )
                    if not ok:
                        return
                except Exception:
                    pass
            state['quitting'] = True
            icon.stop()
            window.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Mo Media Download Studio", do_show, default=True),
            pystray.MenuItem("Thoat", do_quit),
        )
        icon = pystray.Icon("media_dl_studio", image, "Media Download Studio", menu)
        threading.Thread(target=icon.run, daemon=True).start()
        return icon
    except Exception as exc:
        print(f"[tray] Khong tao duoc icon khay: {exc}")
        return None


def main() -> int:
    ensure_stdio()

    # PHAI chay truoc moi import yt_dlp: nap engine da tu cap nhat (neu co)
    # thay cho ban dong goi san trong .exe.
    from app.engine import bootstrap
    bootstrap()

    import uvicorn
    import webview

    from app.main import app as fastapi_app
    from app.downloader import download_tasks

    port = find_free_port()
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port,
                            log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    if not wait_for_server(port):
        webview.create_window(
            "Media Download Studio - Loi",
            html="<h2 style='font-family:sans-serif;padding:24px'>"
                 "Khong khoi dong duoc server.<br>"
                 "Xem chi tiet trong file ytdlp-studio.log canh file exe.</h2>",
            width=560, height=240,
        )
        webview.start()
        return 1

    window = webview.create_window(
        "Media Download Studio",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=860,
        min_size=(900, 600),
    )

    def count_active():
        return sum(1 for t in download_tasks.values()
                   if t.get('status') in ACTIVE_STATUSES)

    tray = start_tray(window, count_active)

    def on_closing():
        if state['quitting'] or tray is None:
            # Khong co khay -> dong that, tranh app chay ngam khong loi thoat
            return True
        # Thu xuong khay, video dang tai van chay tiep
        window.hide()
        return False

    window.events.closing += on_closing
    webview.start()

    if tray is not None:
        tray.stop()
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
