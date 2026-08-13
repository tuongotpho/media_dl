"""He thong ban quyen Media Download Studio (Bao mat nang cao).

- HMAC-SHA256 Signed License Keys
- Hardware Fingerprinting (MAC + Hostname + OS)
- XOR Secret Key Masking (Chong reverse-engineering string extraction)
- System Clock Rollback Protection (Chong lui dong ho Windows)
- Dual Registry & File Trial Anti-Cheat (Chong xoa file 7 ngay dung thu)

Khong phu thuoc thu vien ngoai – chi dung stdlib Python.
"""
import base64
import hashlib
import hmac
import json
import os
import struct
import uuid
import platform
from datetime import date, datetime, timedelta

from .paths import base_dir

# ---- BAO MAT: XOR Secret Key Masking (Chong soi text plain trong binary) ----
_XOR_KEY = b"Aug87SecretKey2026"
_XOR_MASK = bytes([a ^ b for a, b in zip(
    b"MDS_Aug87_LicEngine_v1_2026_xK9pQ",
    (_XOR_KEY * 3)[:33]
)])
_EPOCH = date(2024, 1, 1)
_LICENSE_FILE = "license.dat"


def _get_secret() -> bytes:
    """Giai ma Secret Key dong trong RAM."""
    return bytes([a ^ b for a, b in zip(_XOR_MASK, (_XOR_KEY * 3)[:len(_XOR_MASK)])])


# ===================== MACHINE ID =====================

def get_machine_id() -> str:
    """Tao ma dinh danh duy nhat cho may tinh hien tai (12 ky tu HEX)."""
    raw = f"{uuid.getnode()}-{platform.node()}-{os.name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def _machine_hash(machine_id: str) -> bytes:
    """4 bytes hash cua machine_id, nhung vao trong key."""
    return hashlib.sha256(machine_id.upper().encode()).digest()[:4]


# ===================== TIME GUARD (Chong lui gio he thong) =====================

def _check_and_update_time_guard() -> tuple[bool, str]:
    """Kiem tra xem thoi gian he thong co bi lui quay ve qua khu khong.

    Luu last_seen timestamp. Neu current_time < last_seen_time -> Block!
    """
    path = os.path.join(base_dir(), "time_guard.dat")
    now_ts = int(datetime.now().timestamp())
    last_ts = 0

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_ts = int(data.get("last_seen", 0))
        except Exception:
            last_ts = 0

    # Cho phep sai so toi da 10 phut (600s) phong truong hop dong ho lech nhe
    if last_ts > 0 and now_ts < (last_ts - 600):
        last_date_str = datetime.fromtimestamp(last_ts).strftime('%H:%M %d/%m/%Y')
        return False, f"Phát hiện đồng hồ bị lùi! (Mốc thời gian trước đây: {last_date_str}). Vui lòng chỉnh lại ngày giờ trên máy tính."

    # Cap nhat timestamp moi nhat
    if now_ts > last_ts:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"last_seen": now_ts, "updated_at": datetime.now().isoformat()}, f, indent=2)
        except Exception:
            pass

    return True, ""


# ===================== WINDOWS REGISTRY TRIAL GUARD =====================

def _is_trial_in_registry(machine_id: str) -> bool:
    """Kiem tra xem trial da duoc dang ky trong Windows Registry chưa."""
    if os.name != 'nt':
        return False
    try:
        import winreg
        key_path = r"SOFTWARE\MediaDownloadStudio\Trial"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, machine_id.upper())
            return val == 1
    except Exception:
        return False


def _record_trial_in_registry(machine_id: str):
    """Ghi vet trial vao Windows Registry."""
    if os.name != 'nt':
        return
    try:
        import winreg
        key_path = r"SOFTWARE\MediaDownloadStudio\Trial"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, machine_id.upper(), 0, winreg.REG_DWORD, 1)
    except Exception:
        pass


# ===================== KEY GENERATION =====================

def generate_license_key(machine_id: str, days: int = 365) -> tuple:
    """Tao license key cho mot machine_id cu the.

    Returns:
        (key_string, expiry_date)
        Key format: MDS-XXXX-XXXX-XXXX-XXXX-XXXX  (20 ky tu base32, 5 nhom)
    """
    machine_id = machine_id.upper().strip()
    expiry = date.today() + timedelta(days=days)
    expiry_days = (expiry - _EPOCH).days  # uint16, toi da ~179 nam

    mid_hash = _machine_hash(machine_id)
    payload = struct.pack(">H", expiry_days) + mid_hash  # 6 bytes
    sig = hmac.new(_get_secret(), payload, hashlib.sha256).digest()[:6]  # 6 bytes

    raw = payload + sig  # 12 bytes
    b32 = base64.b32encode(raw).decode().rstrip("=")  # 20 chars

    parts = [b32[i:i + 4] for i in range(0, len(b32), 4)]
    key = "MDS-" + "-".join(parts)
    return key, expiry


# ===================== KEY VALIDATION =====================

def validate_license_key(key: str, machine_id: str = None) -> dict:
    """Xac minh license key (Kiem tra ca HMAC signature, Hardware binding va Time Guard)."""
    if machine_id is None:
        machine_id = get_machine_id()
    machine_id = machine_id.upper().strip()

    # 1. Kiem tra Time Guard (lui dong ho)
    time_ok, time_err = _check_and_update_time_guard()
    if not time_ok:
        return {"valid": False, "message": time_err, "expired": False}

    try:
        clean = key.strip().upper().replace("MDS-", "").replace("-", "").replace(" ", "")
        padding = (8 - len(clean) % 8) % 8
        raw = base64.b32decode(clean + "=" * padding)

        if len(raw) < 12:
            return {"valid": False, "message": "Key không hợp lệ", "expired": False}

        payload, sig = raw[:6], raw[6:12]

        # 2. Kiem tra chu ky HMAC
        expected_sig = hmac.new(_get_secret(), payload, hashlib.sha256).digest()[:6]
        if not hmac.compare_digest(sig, expected_sig):
            return {"valid": False, "message": "License key không hợp lệ", "expired": False}

        # 3. Kiem tra Hardware Binding
        expiry_days = struct.unpack(">H", payload[:2])[0]
        mid_hash = payload[2:6]
        expected_hash = _machine_hash(machine_id)

        if mid_hash != expected_hash:
            return {"valid": False, "message": "License key không dùng cho máy này", "expired": False}

        # 4. Kiem tra het han
        expiry = _EPOCH + timedelta(days=expiry_days)
        today = date.today()

        if today > expiry:
            return {
                "valid": False,
                "message": f"License đã hết hạn từ {expiry.strftime('%d/%m/%Y')}",
                "expiry": expiry.isoformat(),
                "days_left": 0,
                "expired": True,
            }

        days_left = (expiry - today).days
        return {
            "valid": True,
            "message": "License hợp lệ",
            "expiry": expiry.isoformat(),
            "days_left": days_left,
            "expired": False,
        }
    except Exception:
        return {"valid": False, "message": "Key không đúng định dạng", "expired": False}


# ===================== FILE I/O =====================

def _license_path() -> str:
    return os.path.join(base_dir(), _LICENSE_FILE)


def _approved_keys_path() -> str:
    return os.path.join(base_dir(), "approved_keys.json")


def save_license(key: str):
    """Luu license key vao file license.dat canh exe / project root."""
    data = {"key": key.strip(), "activated_at": datetime.now().isoformat()}
    with open(_license_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_license() -> str | None:
    """Doc license key tu file. Tra ve None neu chua co hoac file loi."""
    path = _license_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("key")
    except Exception:
        return None


# ===================== AUTO ACTIVATION VIA TELEGRAM =====================

def record_approved_key(machine_id: str, key: str):
    """Ghi nhan key da duoc Admin duyet qua Telegram vao approved_keys.json."""
    machine_id = machine_id.upper().strip()
    path = _approved_keys_path()
    store = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                store = json.load(f)
        except Exception:
            store = {}
    store[machine_id] = {
        "key": key,
        "approved_at": datetime.now().isoformat()
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def check_and_apply_approved_key(machine_id: str = None) -> dict:
    """Kiem tra xem may da duoc Admin duyet chua."""
    if machine_id is None:
        machine_id = get_machine_id()
    machine_id = machine_id.upper().strip()

    path = _approved_keys_path()
    if not os.path.isfile(path):
        return {"approved": False}

    try:
        with open(path, "r", encoding="utf-8") as f:
            store = json.load(f)
    except Exception:
        return {"approved": False}

    if machine_id in store:
        key = store[machine_id]["key"]
        val_res = validate_license_key(key, machine_id)
        if val_res["valid"]:
            save_license(key)
            del store[machine_id]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(store, f, indent=2)
            return {
                "approved": True,
                "key": key,
                "expiry": val_res["expiry"],
                "days_left": val_res["days_left"]
            }

    return {"approved": False}


# ===================== TRIAL GUARD (DUAL FILE & REGISTRY) =====================

def _trial_path() -> str:
    return os.path.join(base_dir(), "trial_used.dat")


def claim_trial_license(machine_id: str = None) -> dict:
    """Kich hoat dung thu 7 ngay mien phi cho machine_id (Kiem tra ca File & Registry)."""
    if machine_id is None:
        machine_id = get_machine_id()
    machine_id = machine_id.upper().strip()

    # Kiem tra ca File va Registry
    file_claimed = False
    trial_file = _trial_path()
    used_machines = set()

    if os.path.exists(trial_file):
        try:
            with open(trial_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                used_machines = set(data.get("machines", []))
                file_claimed = machine_id in used_machines
        except Exception:
            file_claimed = False

    reg_claimed = _is_trial_in_registry(machine_id)

    if file_claimed or reg_claimed:
        return {
            "success": False,
            "message": "Máy này đã hết lượt sử dụng gói Dùng Thử 7 ngày. Vui lòng chọn gói bản quyền."
        }

    key, expiry = generate_license_key(machine_id, days=7)
    save_license(key)

    # Ghi vet vao ca 2 noi: File & Registry
    used_machines.add(machine_id)
    with open(trial_file, "w", encoding="utf-8") as f:
        json.dump({"machines": list(used_machines)}, f, indent=2)

    _record_trial_in_registry(machine_id)

    return {
        "success": True,
        "message": "Kích hoạt dùng thử 7 ngày miễn phí thành công!",
        "days_left": 7,
        "expiry": expiry.isoformat()
    }


# ===================== STATUS =====================

def get_license_status() -> dict:
    """Tra ve trang thai license hien tai."""
    machine_id = get_machine_id()

    # Kiem tra xem co key vua duoc duyet tu Telegram khong
    check_and_apply_approved_key(machine_id)

    key = load_license()

    if key is None:
        return {
            "activated": False,
            "machine_id": machine_id,
            "message": "Chưa kích hoạt",
            "expiry": None,
            "days_left": None,
            "is_lifetime": False,
            "plan_name": "Chưa Kích Hoạt",
        }

    result = validate_license_key(key, machine_id)
    if not result["valid"]:
        return {
            "activated": False,
            "machine_id": machine_id,
            "message": result["message"],
            "expiry": result.get("expiry"),
            "days_left": 0,
            "is_lifetime": False,
            "plan_name": "Hết Hạn",
        }

    days_left = result.get("days_left", 0)
    is_lifetime = days_left > 10000

    plan_name = "Chính Thức"
    if is_lifetime:
        plan_name = "Gói Vĩnh Viễn"
    elif days_left > 300:
        plan_name = "Gói 1 Năm"
    elif days_left > 100:
        plan_name = "Gói 6 Tháng"
    elif days_left <= 7:
        plan_name = "Dùng Thử 7 Ngày"

    return {
        "activated": True,
        "machine_id": machine_id,
        "message": result["message"],
        "expiry": result.get("expiry"),
        "days_left": days_left,
        "is_lifetime": is_lifetime,
        "plan_name": plan_name,
    }
