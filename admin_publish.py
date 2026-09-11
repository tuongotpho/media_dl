# -*- coding: utf-8 -*-
"""Dua key da duyet len Firebase Realtime Database (chi chay tren may admin).

App cua khach doc key tu day. Xem app/remote_activation.py de biet vi sao
phai co buoc nay: file approved_keys.json cuc bo khong bao gio di duoc tu
may admin sang may khach.

Cau hinh trong .env.local (da nam trong .gitignore):

    FIREBASE_SERVICE_ACCOUNT=C:\\Users\\...\\media-download-free-firebase-adminsdk-....json
    FIREBASE_DB_URL=https://<ten>-default-rtdb.<vung>.firebasedatabase.app

File nay KHONG duoc dong goi vao .exe: no can service account, ma service
account thi khong bao gio duoc phat hanh cho nguoi dung.
"""
import json
import os
import urllib.request

SCOPES = [
    "https://www.googleapis.com/auth/firebase.database",
    "https://www.googleapis.com/auth/userinfo.email",
]

_ROOT = os.path.dirname(os.path.abspath(__file__))
_credentials = None


def load_env(path=None) -> None:
    """Nap KEY=value tu .env.local vao os.environ."""
    path = path or os.path.join(_ROOT, ".env.local")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def _db_url() -> str:
    # .strip() truoc: dan vao o cua Render rat de dinh xuong dong o cuoi,
    # va urllib tu choi thang URL co ky tu dieu khien.
    url = os.environ.get("FIREBASE_DB_URL", "").strip().rstrip("/")
    if not url:
        raise RuntimeError(
            "Thieu FIREBASE_DB_URL trong .env.local.\n"
            "Lay trong Firebase Console > Realtime Database, dang:\n"
            "  https://<ten>-default-rtdb.<vung>.firebasedatabase.app")
    if not url.startswith(("https://", "http://")):
        url = "https://" + url
    return url


def _token() -> str:
    """Lay OAuth access token tu service account, tu lam moi khi het han."""
    global _credentials
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    if _credentials is None:
        # Tren may admin: duong dan toi file JSON.
        # Tren server (Render...): dan nguyen noi dung JSON vao bien moi truong,
        # vi server khong co cho de file.
        raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        path = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()

        if raw:
            _credentials = service_account.Credentials.from_service_account_info(
                json.loads(raw), scopes=SCOPES)
        elif path and os.path.isfile(path):
            _credentials = service_account.Credentials.from_service_account_file(
                path, scopes=SCOPES)
        else:
            raise RuntimeError(
                "Thieu thong tin service account. Dat MOT trong hai:\n"
                "  FIREBASE_SERVICE_ACCOUNT_JSON = toan bo noi dung file JSON\n"
                "  FIREBASE_SERVICE_ACCOUNT      = duong dan toi file JSON")

    if not _credentials.valid:
        _credentials.refresh(Request())
    return _credentials.token


def publish_key(machine_id: str, key: str, expiry, days: int) -> None:
    """Ghi key da duyet len duong dan approved/<MA_MAY>."""
    load_env()
    machine_id = machine_id.upper().strip()
    body = json.dumps({
        "key": key,
        "expiry": expiry.isoformat() if hasattr(expiry, "isoformat") else str(expiry),
        "days": days,
        "approved_at": __import__("datetime").datetime.now().isoformat(),
    }).encode()

    url = "%s/approved/%s.json?access_token=%s" % (_db_url(), machine_id, _token())
    req = urllib.request.Request(url, data=body, method="PUT",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status not in (200, 204):
            raise RuntimeError("Realtime Database tra ve %s" % r.status)


def revoke_key(machine_id: str) -> None:
    """Xoa key cua mot may (vi du khi hoan tien)."""
    load_env()
    url = "%s/approved/%s.json?access_token=%s" % (
        _db_url(), machine_id.upper().strip(), _token())
    req = urllib.request.Request(url, method="DELETE")
    urllib.request.urlopen(req, timeout=20)


if __name__ == "__main__":
    # Kiem tra cau hinh nhanh: python admin_publish.py
    load_env()
    print("Service account :", os.environ.get("FIREBASE_SERVICE_ACCOUNT", "(chua dat)"))
    print("Database URL    :", os.environ.get("FIREBASE_DB_URL", "(chua dat)"))
    try:
        t = _token()
        print("OAuth token     : lay duoc (%d ky tu)" % len(t))
    except Exception as e:
        print("OAuth token     : LOI ->", e)
