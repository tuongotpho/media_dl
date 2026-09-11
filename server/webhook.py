# -*- coding: utf-8 -*-
"""May chu duyet ban quyen — chay tren Render (goi Web Service mien phi).

VI SAO CAN
----------
license_bot.py dung long polling nen phai co tien trinh song 24/7. Tren
Render loai do la Background Worker, khong co goi mien phi. Ban nay doi
sang webhook: Telegram tu goi vao day moi khi admin bam nut, nen chay duoc
tren Web Service mien phi (ngu khi khong ai goi, Telegram gui lai neu
lan dau timeout).

Loi ich lon hon: BOT_TOKEN khong con nam trong file .exe. Truoc day app
cua khach tu goi Telegram nen token di theo moi ban phat hanh, ai giai nen
cung lay duoc. Gio app goi may chu nay, may chu moi goi Telegram.

BIEN MOI TRUONG CAN DAT TREN RENDER
-----------------------------------
  BOT_TOKEN                     token bot Telegram
  ADMIN_CHAT_ID                 chat id cua admin (bot tra ve khi gui /start)
  WEBHOOK_SECRET                chuoi ngau nhien, dung de xac thuc Telegram
  FIREBASE_DB_URL               https://...firebasedatabase.app
  FIREBASE_SERVICE_ACCOUNT_JSON toan bo noi dung file JSON service account
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.license import generate_license_key          # noqa: E402
import admin_publish                                  # noqa: E402

# .strip() vi dan gia tri vao o cua Render rat de dinh khoang trang hoac
# xuong dong o cuoi, va khi do phep so sanh chat id se sai ma khong bao gi.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").strip()
TELEGRAM_API = "https://api.telegram.org/bot%s" % BOT_TOKEN

PLAN_LABELS = {
    "6months": ("🥉 Gói 6 Tháng (19.000 VNĐ)", 180),
    "1year": ("🥈 Gói 1 Năm (29.000 VNĐ)", 365),
    "lifetime": ("👑 Gói Vĩnh Viễn (99.000 VNĐ)", 36500),
}

app = FastAPI(title="Media Download Studio — License Server")


# ===================== TELEGRAM =====================

def tg(method: str, payload: dict) -> dict:
    req = urllib.request.Request(
        "%s/%s" % (TELEGRAM_API, method),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print("[tg] %s that bai: %s" % (method, e), flush=True)
        return {"ok": False}


def tg_get(method: str) -> dict:
    """Goi Telegram bang GET, dung cho cac lenh khong can tham so."""
    try:
        with urllib.request.urlopen(
                "%s/%s" % (TELEGRAM_API, method), timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print("[tg] %s that bai: %s" % (method, e), flush=True)
        return {"ok": False}


def approval_keyboard(machine_id: str, request_id: str = "") -> dict:
    """Nut bam mang theo request_id de app phan biet lan nay voi lan truoc."""
    rid = ":" + request_id if request_id else ""
    return {"inline_keyboard": [
        [
            {"text": "🥉 Duyệt 6 Tháng (19k)", "callback_data": "approve:%s:180%s" % (machine_id, rid)},
            {"text": "🥈 Duyệt 1 Năm (29k)", "callback_data": "approve:%s:365%s" % (machine_id, rid)},
        ],
        [
            {"text": "👑 Duyệt Vĩnh Viễn (99k)", "callback_data": "approve:%s:36500%s" % (machine_id, rid)},
            {"text": "❌ Từ Chối", "callback_data": "reject:%s%s" % (machine_id, rid)},
        ],
    ]}


# ===================== APP CUA KHACH GOI VAO =====================

class ActivationRequest(BaseModel):
    machine_id: str
    plan: str = "1year"
    request_id: str = ""


@app.post("/api/request-activation")
async def request_activation(req: ActivationRequest):
    """App cua khach goi vao day thay vi goi thang Telegram.

    Nho vay BOT_TOKEN khong con phai di kem file .exe.
    """
    if not ADMIN_CHAT_ID:
        raise HTTPException(503, "Máy chủ chưa cấu hình ADMIN_CHAT_ID.")

    machine_id = req.machine_id.upper().strip()
    if not machine_id or len(machine_id) > 32 or not machine_id.isalnum():
        raise HTTPException(400, "Mã máy không hợp lệ.")
    request_id = req.request_id.strip()[:16]
    if request_id and not request_id.isalnum():
        raise HTTPException(400, "Mã yêu cầu không hợp lệ.")

    label = PLAN_LABELS.get(req.plan, PLAN_LABELS["1year"])[0]
    text = ("🔔 *YÊU CẦU KÍCH HOẠT MỚI*\n\n"
            "🖥 Mã máy: `%s`\n"
            "📦 Đăng ký: *%s*\n"
            "📅 Thời gian: %s\n\n"
            "Chọn nút tương ứng để duyệt:"
            % (machine_id, label, datetime.now().strftime("%H:%M %d/%m/%Y")))

    res = tg("sendMessage", {
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": approval_keyboard(machine_id, request_id),
    })
    if not res.get("ok"):
        raise HTTPException(502, "Không gửi được yêu cầu đến admin. Thử lại sau.")
    return {"success": True,
            "message": "Đã gửi yêu cầu đến admin. App sẽ tự mở khoá ngay khi được duyệt."}


# ===================== TELEGRAM GOI VAO =====================

@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    """Telegram goi vao moi khi admin bam nut."""
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(403, "Sai secret token")

    update = await request.json()
    cq = update.get("callback_query")
    if cq:
        handle_callback(cq)
    elif "message" in update:
        handle_message(update["message"])
    return {"ok": True}


def handle_message(msg: dict) -> None:
    text = (msg.get("text") or "").strip()
    chat_id = msg["chat"]["id"]

    if text.startswith("/start"):
        tg("sendMessage", {
            "chat_id": chat_id, "parse_mode": "Markdown",
            "text": "✅ *Máy chủ bản quyền đã sẵn sàng.*\n\n"
                    "📌 Chat ID của bạn: `%s`\n\n"
                    "Đặt giá trị này vào biến môi trường `ADMIN_CHAT_ID` trên Render."
                    % chat_id})
    elif text.startswith("/status"):
        tg("sendMessage", {
            "chat_id": chat_id, "parse_mode": "Markdown",
            "text": "📊 *Trạng thái*\n\nMáy chủ: đang chạy\nAdmin đã cấu hình: `%s`"
                    % (ADMIN_CHAT_ID or "chưa đặt")})
    elif text.startswith("/genkey"):
        parts = text.split()
        if str(chat_id) != str(ADMIN_CHAT_ID):
            return
        if len(parts) < 2:
            tg("sendMessage", {"chat_id": chat_id, "text": "Dùng: /genkey <mã máy> [số ngày]"})
            return
        mid = parts[1].upper().strip()
        days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 365
        deliver(chat_id, None, mid, days)


def handle_callback(cq: dict) -> None:
    cb_id = cq["id"]
    data = cq.get("data", "")
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]

    if str(chat_id) != str(ADMIN_CHAT_ID):
        tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": "⛔ Không có quyền"})
        return

    parts = data.split(":")
    if parts[0] == "approve" and len(parts) >= 3:
        rid = parts[3] if len(parts) > 3 else ""
        deliver(chat_id, message_id, parts[1], int(parts[2]), cb_id, rid)
    elif parts[0] == "reject" and len(parts) >= 2:
        mid = parts[1].upper()
        rid = parts[2] if len(parts) > 2 else ""
        # Ghi quyet dinh len Firebase: khong ghi thi app cua khach cu doi mai.
        try:
            admin_publish.publish_rejection(mid, rid)
            note = "App của khách đã được báo."
        except Exception as e:
            note = "⚠️ Không báo được cho app: `%s`" % e
            print("[reject] publish_rejection that bai: %s" % e, flush=True)
        tg("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "parse_mode": "Markdown",
            "text": "❌ *ĐÃ TỪ CHỐI*\n\n🖥 Mã máy: `%s`\n%s" % (mid, note)})
        tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": "❌ Đã từ chối"})
    else:
        tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": "⚠️ Không hiểu lệnh"})


def deliver(chat_id, message_id, machine_id: str, days: int,
            cb_id: str = None, request_id: str = "") -> None:
    """Sinh key, dua len Realtime Database, bao lai cho admin."""
    machine_id = machine_id.upper().strip()
    key, expiry = generate_license_key(machine_id, days)

    try:
        admin_publish.publish_key(machine_id, key, expiry, days, request_id)
        delivery = "⚡ Key đã lên server — app của khách tự mở khoá trong vài giây."
        toast = "✅ Đã duyệt & đẩy key lên server"
    except Exception as e:
        delivery = ("⚠️ *KHÔNG đưa được key lên server:* `%s`\n"
                    "Hãy gửi key trên cho khách dán tay vào app." % e)
        toast = "⚠️ Duyệt xong nhưng chưa đẩy được key"
        print("[deliver] publish_key that bai: %s" % e, flush=True)

    text = ("✅ *ĐÃ DUYỆT*\n\n"
            "🖥 Mã máy: `%s`\n"
            "🔐 Key: `%s`\n"
            "📅 Hết hạn: *%s*\n\n%s"
            % (machine_id, key, expiry.strftime("%d/%m/%Y"), delivery))

    if message_id:
        tg("editMessageText", {"chat_id": chat_id, "message_id": message_id,
                               "text": text, "parse_mode": "Markdown"})
    else:
        tg("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

    if cb_id:
        tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": toast})
    print("[deliver] %s -> %s (%d ngay)" % (machine_id, key, days), flush=True)


# ===================== KIEM TRA SUC KHOE =====================

@app.get("/")
async def health():
    """Render goi vao day de biet dich vu con song."""
    return {
        "service": "Media Download Studio — License Server",
        "bot_token": "đã đặt" if BOT_TOKEN else "CHƯA ĐẶT",
        "admin_chat_id": "đã đặt" if ADMIN_CHAT_ID else "CHƯA ĐẶT",
        "webhook_secret": "đã đặt" if WEBHOOK_SECRET else "CHƯA ĐẶT",
        "firebase_db": "đã đặt" if os.environ.get("FIREBASE_DB_URL") else "CHƯA ĐẶT",
        "service_account": "đã đặt" if os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") else "CHƯA ĐẶT",
    }


@app.get("/diag")
async def diag():
    """Tu kiem tra tung manh cau hinh.

    "Da dat" chua co nghia la "dat dung": token co the la ban da bi huy,
    chat id co the go nham, JSON service account co the dan thieu. Cho may
    chu tu thu tung thu roi bao ket qua, khoi phai doan.

    Khong lo bi mat: chi in ten bot, ma chat id (von chi la mot so), va
    dia chi email cua service account.
    """
    out = {}

    # 1. Token co goi duoc Telegram khong
    me = tg_get("getMe")
    if me.get("ok"):
        out["bot_token"] = "OK — @%s" % me["result"].get("username")
    else:
        out["bot_token"] = "HỎNG — Telegram từ chối token này (đã bị huỷ, hoặc dán sai)"

    # 2. Chat id
    out["admin_chat_id"] = ADMIN_CHAT_ID or "CHƯA ĐẶT"
    out["admin_chat_id_hop_le"] = ADMIN_CHAT_ID.lstrip("-").isdigit()

    # 3. Service account
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        out["service_account"] = "CHƯA ĐẶT"
    else:
        try:
            sa = json.loads(raw)
            out["service_account"] = "OK — %s" % sa.get("client_email", "?")
        except Exception as e:
            out["service_account"] = "HỎNG — JSON không đọc được (dán thiếu?): %s" % e

    # 4. Ghi thu vao Realtime Database
    try:
        admin_publish.publish_key("DIAGSELFTEST", "MDS-DIAG-ONLY", "2000-01-01", 0)
        admin_publish.revoke_key("DIAGSELFTEST")
        out["firebase_ghi_duoc"] = "OK"
    except Exception as e:
        out["firebase_ghi_duoc"] = "HỎNG — %s" % e

    return out
