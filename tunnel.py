"""Khoi dong YTDLP Studio + Cloudflare Tunnel, tu dong lay URL public.

Chay:  python tunnel.py     (hoac double-click start-tunnel.bat)
"""
import os
import re
import sys
import time
import shutil
import socket
import subprocess
import threading
import urllib.error
import urllib.request
import webbrowser

# line_buffering de URL hien ra ngay ca khi output bi pipe (khong phai console)
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))
URL_RE = re.compile(r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com")

# winget cai cloudflared nhung PATH cua session hien tai co the chua cap nhat,
# nen dò them cac vi tri cai dat quen thuoc.
CANDIDATES = [
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"),
]


def find_cloudflared():
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    for path in CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def port_is_open(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_for_server(port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_is_open(port):
            return True
        time.sleep(0.5)
    return False


def origin_healthy(port, timeout=3):
    """Kiem tra that su co app tra loi HTTP, khong chi la port dang mo."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError:
        return True  # co app tra loi, chi la route / bi loi -> van coi la song
    except Exception:
        return False


def start_server(port):
    env = dict(os.environ, NO_BROWSER="1", HOST="0.0.0.0", PORT=str(port))
    return subprocess.Popen([sys.executable, "run.py"], cwd=ROOT, env=env)


def watchdog(port, state, stop_event):
    """Server chet => tunnel tra 502. Tu bat lai server va bao cho nguoi dung."""
    while not stop_event.wait(5):
        if origin_healthy(port):
            continue
        print(f"\n[CANH BAO] Server o port {port} da ngung -> tunnel se tra loi 502.")
        proc = state.get("server")
        if proc is not None and proc.poll() is None:
            proc.terminate()
        print("[WATCHDOG] Dang khoi dong lai server...")
        state["server"] = start_server(port)
        if wait_for_server(port, timeout=30) and origin_healthy(port):
            print("[WATCHDOG] Server da song lai. Tai lai trang tren trinh duyet.\n")
        else:
            print("[WATCHDOG] Khoi dong lai that bai. Kiem tra log cua server.\n")


def main():
    cloudflared = find_cloudflared()
    if not cloudflared:
        print("[LOI] Khong tim thay cloudflared.")
        print("      Cai bang lenh:  winget install --id Cloudflare.cloudflared")
        return 1

    print("=" * 60)
    print("   YTDLP Studio  +  Cloudflare Tunnel")
    print("=" * 60)
    print(f"cloudflared: {cloudflared}")

    state = {"server": None}
    if port_is_open(PORT):
        if not origin_healthy(PORT):
            print(f"[LOI] Port {PORT} dang bi chiem boi thu gi do khong phai app nay.")
            print(f"      Dong tien trinh do, hoac chay lai voi port khac: set PORT=8010")
            return 1
        print(f"[1/2] Server da chay san o port {PORT}, dung luon.")
        print("      Luu y: day la server o cua so khac. Neu cua so do dong,")
        print("      watchdog se tu bat lai server moi.")
    else:
        print(f"[1/2] Dang khoi dong server FastAPI (port {PORT})...")
        state["server"] = start_server(PORT)
        if not wait_for_server(PORT):
            print("[LOI] Server khong khoi dong duoc trong 30 giay.")
            state["server"].terminate()
            return 1
        print("      Server san sang.")

    print("[2/2] Dang mo Cloudflare Tunnel...\n")
    tunnel = subprocess.Popen(
        [cloudflared, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    stop_event = threading.Event()
    threading.Thread(
        target=watchdog, args=(PORT, state, stop_event), daemon=True
    ).start()

    public_url = None
    try:
        for line in tunnel.stdout:
            if public_url is None:
                match = URL_RE.search(line)
                if match:
                    public_url = match.group(0)
                    print("\n" + "=" * 60)
                    print("  DIA CHI PUBLIC (mo duoc tren dien thoai / may khac):")
                    print(f"\n     {public_url}\n")
                    print("  Nhan Ctrl+C de dong tunnel.")
                    print("=" * 60 + "\n")
                    webbrowser.open(public_url)
                    continue
            # Sau khi co URL thi chi hien loi, bo qua log rac
            if public_url is None or "ERR" in line or "error" in line.lower():
                print(line.rstrip())
    except KeyboardInterrupt:
        print("\nDang dong...")
    finally:
        stop_event.set()
        tunnel.terminate()
        if state["server"] is not None:
            state["server"].terminate()

    return 0


if __name__ == "__main__":
    sys.exit(main())
