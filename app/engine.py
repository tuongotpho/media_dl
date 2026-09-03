# -*- coding: utf-8 -*-
"""Tu cap nhat engine yt-dlp ma khong can phat hanh lai file .exe.

VAN DE
------
PyInstaller dong bang phien ban yt-dlp tai thoi diem build. YouTube doi co
che vai thang mot lan, ban cu bat dau tra HTTP 403 giua chung khi tai. Nguoi
mua goi vinh vien khong the tu nang cap, va tac gia phai phat hanh lai app.

CACH LAM
--------
Khong ghi de duoc vao thu muc goi san (sys._MEIPASS bi xoa moi lan thoat),
nen ban moi duoc dat canh file .exe:

    <thu muc chua .exe>/engine/yt_dlp/...

`bootstrap()` chen thu muc do len DAU sys.path truoc khi bat ky cho nao
import yt_dlp, nen ban moi thang ban dong goi san. Xoa thu muc engine/ la
quay ve ban goc.

Tai wheel truc tiep tu PyPI roi giai nen bang zipfile, khong can pip - ban
.exe khong co pip.
"""
import json
import os
import shutil
import ssl
import sys
import tempfile
import threading
import urllib.request
import zipfile

PYPI_JSON = "https://pypi.org/pypi/yt-dlp/json"
PACKAGE = "yt_dlp"

# Ban toi thieu chay duoc. Ban 2026.7.4 tra 403 giua chung khi tai YouTube.
MIN_VERSION = (2026, 8, 19)

_update_state = {
    "checking": False,
    "latest": None,
    "error": None,
    "updated_to": None,
}


# ===================== DUONG DAN =====================

def engine_dir() -> str:
    """Thu muc chua engine cap nhat, nam canh file .exe."""
    from .paths import base_dir
    return os.path.join(base_dir(), "engine")


def bootstrap() -> None:
    """Nap engine da cap nhat neu co.

    PHAI goi truoc khi bat ky module nao import yt_dlp.
    """
    d = engine_dir()
    if os.path.isdir(os.path.join(d, PACKAGE)) and d not in sys.path:
        sys.path.insert(0, d)


# ===================== PHIEN BAN =====================

def _parse(v: str) -> tuple:
    parts = []
    for chunk in str(v).split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def installed_version() -> str:
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:
        return "khong xac dinh"


def is_outdated() -> bool:
    """True khi ban dang chay cu hon nguong toi thieu chay duoc."""
    try:
        return _parse(installed_version()) < MIN_VERSION
    except Exception:
        return False


def running_from_engine_dir() -> bool:
    """True khi yt-dlp dang chay la ban da tu cap nhat."""
    try:
        import yt_dlp
        return os.path.abspath(engine_dir()) in os.path.abspath(yt_dlp.__file__)
    except Exception:
        return False


# ===================== MANG =====================

def _opener():
    """urlopen co xac thuc chung chi, dung ca khi chay tu .exe."""
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def fetch_latest() -> dict:
    """Hoi PyPI ban moi nhat. Tra ve {'version': ..., 'wheel_url': ...}."""
    req = urllib.request.Request(PYPI_JSON, headers={"User-Agent": "MediaDownloadStudio"})
    with _opener().open(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))

    version = data["info"]["version"]
    wheel = None
    for f in data["urls"]:
        if f["filename"].endswith("-py3-none-any.whl"):
            wheel = f["url"]
            break
    if not wheel:
        raise RuntimeError("PyPI khong co wheel py3-none-any cho ban %s" % version)
    return {"version": version, "wheel_url": wheel}


# ===================== CAP NHAT =====================

def update(force: bool = False) -> dict:
    """Tai ban moi nhat va dat vao engine/.

    Tra ve dict co 'updated' (bool) va 'message'. Phai khoi dong lai app thi
    ban moi co hieu luc, vi yt_dlp cu da nam trong bo nho.
    """
    current = installed_version()
    latest = fetch_latest()

    if not force and _parse(current) >= _parse(latest["version"]):
        return {
            "updated": False,
            "current": current,
            "latest": latest["version"],
            "message": "Đang dùng bản mới nhất (%s)." % current,
        }

    target = engine_dir()
    staging = target + ".new"
    backup = target + ".old"

    for path in (staging, backup):
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(staging, exist_ok=True)

    # Tai wheel ve file tam
    with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as tmp:
        wheel_path = tmp.name
    try:
        req = urllib.request.Request(latest["wheel_url"],
                                     headers={"User-Agent": "MediaDownloadStudio"})
        with _opener().open(req, timeout=120) as r, open(wheel_path, "wb") as out:
            shutil.copyfileobj(r, out)

        # Chi lay thu muc yt_dlp/ trong wheel, bo qua metadata
        with zipfile.ZipFile(wheel_path) as z:
            members = [n for n in z.namelist() if n.startswith(PACKAGE + "/")]
            if not members:
                raise RuntimeError("Wheel khong chua thu muc %s/" % PACKAGE)
            z.extractall(staging, members)

        if not os.path.isdir(os.path.join(staging, PACKAGE)):
            raise RuntimeError("Giai nen xong nhung khong thay %s/" % PACKAGE)

        # Doi cho: giu ban cu lam du phong roi mieu doi ten
        if os.path.isdir(target):
            os.rename(target, backup)
        os.rename(staging, target)
        shutil.rmtree(backup, ignore_errors=True)

        _update_state["updated_to"] = latest["version"]
        return {
            "updated": True,
            "current": current,
            "latest": latest["version"],
            "message": "Đã cập nhật engine lên %s. Khởi động lại ứng dụng để áp dụng."
                       % latest["version"],
        }
    except Exception as e:
        # Khoi phuc ban cu neu doi cho dang do
        if not os.path.isdir(target) and os.path.isdir(backup):
            os.rename(backup, target)
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("Cập nhật thất bại: %s" % e)
    finally:
        try:
            os.unlink(wheel_path)
        except Exception:
            pass


def check_in_background() -> None:
    """Hoi PyPI o luong nen luc khoi dong. Khong bao gio nem loi ra ngoai."""
    def run():
        _update_state["checking"] = True
        try:
            _update_state["latest"] = fetch_latest()["version"]
            _update_state["error"] = None
        except Exception as e:
            _update_state["error"] = str(e)
        finally:
            _update_state["checking"] = False

    threading.Thread(target=run, daemon=True).start()


def status() -> dict:
    """Trang thai engine de hien trong giao dien."""
    current = installed_version()
    latest = _update_state.get("latest")
    has_update = bool(latest) and _parse(latest) > _parse(current)
    return {
        "current": current,
        "latest": latest,
        "checking": _update_state["checking"],
        "check_error": _update_state["error"],
        "has_update": has_update,
        "outdated": is_outdated(),
        "using_updated_engine": running_from_engine_dir(),
        "engine_dir": engine_dir(),
        "pending_restart": bool(_update_state.get("updated_to")),
    }
