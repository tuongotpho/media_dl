# -*- coding: utf-8 -*-
"""Nhan key da duoc admin duyet, qua Firebase Realtime Database.

VAN DE CU
---------
Bot ghi approved_keys.json vao thu muc cua MAY ADMIN, con app doc
approved_keys.json tu thu muc cua MAY KHACH. Hai file nam tren hai may khac
nhau va khong co duong truyen nao giua chung, nen "tu dong kich hoat" chua
bao gio chay duoc voi khach that - no chi chay khi admin va app cung mot may.

CACH LAM
--------
Admin bam Duyet -> bot ghi vao Realtime Database:

    approved/<MA_MAY> = { key, expiry, days, approved_at }

App hoi dung document cua chinh no bang mot lenh GET khong can dang nhap.
Quy tac bao mat chi cho doc khi biet chinh xac ma may, va cam ghi - chi
service account cua bot moi ghi duoc.

Key von da khoa theo may (HMAC co nhung ma may vao), nen doc duoc key cua
may khac cung khong dung duoc o dau.

Chi hoi khi nguoi dung DA bam gui yeu cau kich hoat, de app khong goi mang
lien tuc suot doi voi nguoi chi dung ban mien phi.
"""
import json
import os
import ssl
import time
import urllib.error
import urllib.request

# Doi thanh URL that sau khi tao Realtime Database.
# Xem trong Firebase Console > Realtime Database, dang:
#   https://<ten>-default-rtdb.<vung>.firebasedatabase.app
DB_URL = os.environ.get(
    "FIREBASE_DB_URL",
    "https://media-download-free-default-rtdb.asia-southeast1.firebasedatabase.app",
)

REQUEST_TIMEOUT = 8
POLL_INTERVAL = 3          # giay, tranh hoi don dap
PENDING_MAX_AGE = 7 * 86400   # ngung hoi sau 7 ngay khong duoc duyet

_last_poll = 0.0


def _pending_path() -> str:
    from .paths import base_dir
    return os.path.join(base_dir(), "pending_activation.json")


def mark_pending(machine_id: str, plan: str = "") -> None:
    """Danh dau da gui yeu cau kich hoat, de bat dau hoi server."""
    try:
        with open(_pending_path(), "w", encoding="utf-8") as f:
            json.dump({"machine_id": machine_id, "plan": plan,
                       "ts": int(time.time())}, f)
    except Exception:
        pass


def clear_pending() -> None:
    try:
        os.unlink(_pending_path())
    except Exception:
        pass


def _pending() -> dict:
    p = _pending_path()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if time.time() - data.get("ts", 0) > PENDING_MAX_AGE:
        clear_pending()
        return {}
    return data


def fetch_approved_key(machine_id: str) -> str:
    """Doc key da duyet cua may nay. Tra ve chuoi rong neu chua co.

    Khong bao gio nem loi ra ngoai: mat mang hay server loi thi coi nhu
    chua duyet, app van chay binh thuong o ban mien phi.
    """
    url = "%s/approved/%s.json" % (DB_URL.rstrip("/"), machine_id.upper().strip())
    try:
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
        req = urllib.request.Request(url, headers={"User-Agent": "MediaDownloadStudio"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict):
            return str(data.get("key") or "")
    except Exception:
        pass
    return ""


def poll_if_pending(machine_id: str) -> str:
    """Hoi server neu dang cho duyet va da qua khoang cach toi thieu."""
    global _last_poll
    if not _pending():
        return ""
    now = time.time()
    if now - _last_poll < POLL_INTERVAL:
        return ""
    _last_poll = now
    return fetch_approved_key(machine_id)
