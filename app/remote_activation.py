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
).strip()

REQUEST_TIMEOUT = 8
POLL_INTERVAL = 3          # giay, tranh hoi don dap
PENDING_MAX_AGE = 7 * 86400   # ngung hoi sau 7 ngay khong duoc duyet

_last_poll = 0.0

# Quyet dinh tu choi gan nhat, de giao dien hien thong bao. Giu cho toi khi
# nguoi dung gui yeu cau moi (khong xoa sau lan doc dau, vi nhieu endpoint
# cung doc trang thai license va se "an mat" thong bao truoc khi giao dien
# kip thay).
_last_rejection = None


def _pending_path() -> str:
    from .paths import base_dir
    return os.path.join(base_dir(), "pending_activation.json")


def mark_pending(machine_id: str, plan: str = "", request_id: str = "") -> None:
    """Danh dau da gui yeu cau kich hoat, de bat dau hoi server."""
    global _last_rejection
    _last_rejection = None          # yeu cau moi -> xoa thong bao tu choi cu
    try:
        with open(_pending_path(), "w", encoding="utf-8") as f:
            json.dump({"machine_id": machine_id, "plan": plan,
                       "request_id": request_id, "ts": int(time.time())}, f)
    except Exception:
        pass


def last_rejection():
    return _last_rejection


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


def fetch_decision(machine_id: str) -> dict:
    """Doc node cua may nay. Tra ve {} neu chua co gi.

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
            return data
    except Exception:
        pass
    return {}


def fetch_approved_key(machine_id: str) -> str:
    return str(fetch_decision(machine_id).get("key") or "")


def poll_if_pending(machine_id: str) -> str:
    """Hoi server neu dang cho duyet. Tra ve key neu duoc duyet.

    Neu bi TU CHOI dung yeu cau dang cho (khop request_id) thi ngung cho
    va luu lai de giao dien bao. Node tu choi cua lan truoc (request_id
    khac) bi bo qua, nen yeu cau moi khong bi tu choi oan.
    """
    global _last_poll, _last_rejection
    pending = _pending()
    if not pending:
        return ""
    now = time.time()
    if now - _last_poll < POLL_INTERVAL:
        return ""
    _last_poll = now

    node = fetch_decision(machine_id)
    if node.get("key"):
        return str(node["key"])

    if node.get("status") == "rejected":
        same_request = (not pending.get("request_id")
                        or node.get("request_id") == pending.get("request_id"))
        if same_request:
            _last_rejection = {
                "request_id": pending.get("request_id", ""),
                "plan": pending.get("plan", ""),
                "at": node.get("rejected_at", ""),
            }
            clear_pending()
    return ""
