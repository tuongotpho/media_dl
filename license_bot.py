"""Telegram Bot cho admin Media Download Studio.

Chay tren may admin de:
  1. Nhan thong bao khi nguoi dung yeu cau kich hoat
  2. Duyet bang nut bam -> tu dong tao license key va gui lai
  3. Admin chi can bam 1 nut tren dien thoai

Cach dung:
  1. Gui /start cho bot tren Telegram (lan dau)
  2. Chay: python license_bot.py
  3. De chay ngam, khong tat

Khong can thu vien ngoai – chi dung stdlib (urllib).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

# Them project root vao path de import app.license
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.license import generate_license_key, record_approved_key
import admin_publish

# ---- Cau hinh ----
BOT_TOKEN = "8870394330:AAGzPWicK_EMBygfF0xRpNJQP9bNCP_IlOI"
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")

# Admin chat_id – tu dong luu khi admin gui /start
ADMIN_CHAT_ID = None


def api_call(method: str, data: dict = None) -> dict:
    """Goi Telegram Bot API."""
    url = f"{API_BASE}/{method}"
    if data:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"[API Error] {method}: {e.code} {body[:200]}")
        return {"ok": False}
    except Exception as e:
        print(f"[Network Error] {method}: {e}")
        return {"ok": False}


def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Gui tin nhan Telegram."""
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = reply_markup
    return api_call("sendMessage", data)


def answer_callback(callback_id, text=""):
    """Tra loi callback query (tat loading tren nut)."""
    return api_call("answerCallbackQuery",
                    {"callback_query_id": callback_id, "text": text})


def edit_message(chat_id, message_id, text, parse_mode="Markdown"):
    """Sua tin nhan da gui."""
    return api_call("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    })


def load_config():
    """Doc admin chat_id tu file config."""
    global ADMIN_CHAT_ID
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        ADMIN_CHAT_ID = cfg.get("admin_chat_id")
    return ADMIN_CHAT_ID


def save_config():
    """Luu admin chat_id."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"admin_chat_id": ADMIN_CHAT_ID}, f, indent=2)


def handle_start(message):
    """Xu ly lenh /start – luu admin chat_id."""
    global ADMIN_CHAT_ID
    chat_id = message["chat"]["id"]
    username = message["from"].get("username", "")
    first_name = message["from"].get("first_name", "")

    ADMIN_CHAT_ID = chat_id
    save_config()

    send_message(chat_id,
        f"✅ *Xin chào {first_name}!*\n\n"
        f"Bot quản lý bản quyền Media Download Studio đã sẵn sàng.\n\n"
        f"📌 Chat ID của bạn: `{chat_id}`\n"
        f"📌 Username: @{username}\n\n"
        f"Khi người dùng yêu cầu kích hoạt, bot sẽ gửi thông báo cho bạn "
        f"kèm nút *Duyệt* để tạo key tự động.\n\n"
        f"💡 Lệnh hỗ trợ:\n"
        f"/genkey `<mã máy>` – Tạo key thủ công\n"
        f"/status – Trạng thái bot"
    )
    print(f"[Bot] Admin registered: {first_name} (@{username}), chat_id={chat_id}")


def handle_genkey(message):
    """Xu ly lenh /genkey <machine_id> – tao key thu cong."""
    chat_id = message["chat"]["id"]
    if chat_id != ADMIN_CHAT_ID:
        send_message(chat_id, "⛔ Bạn không có quyền sử dụng bot này.")
        return

    text = message.get("text", "")
    parts = text.strip().split()
    if len(parts) < 2:
        send_message(chat_id,
            "⚠️ Cú pháp: `/genkey <mã máy>`\n"
            "Ví dụ: `/genkey ABC123DEF456`")
        return

    machine_id = parts[1].upper().strip()
    if len(machine_id) != 12:
        send_message(chat_id, f"⚠️ Mã máy phải đúng 12 ký tự. Bạn nhập: `{machine_id}` ({len(machine_id)} ký tự)")
        return

    key, expiry = generate_license_key(machine_id, days=365)
    record_approved_key(machine_id, key)
    send_message(chat_id,
        f"🔑 *LICENSE KEY ĐÃ TẠO & TỰ ĐỘNG GỬI VỀ APP*\n\n"
        f"🖥 Mã máy: `{machine_id}`\n"
        f"🔐 Key: `{key}`\n"
        f"📅 Hết hạn: *{expiry.strftime('%d/%m/%Y')}*\n\n"
        f"⚡ Phần mềm của người dùng sẽ tự động mở khóa!")


def handle_callback(callback_query):
    """Xu ly khi admin bam nut Duyet/Tu choi."""
    cb_id = callback_query["id"]
    data = callback_query.get("data", "")
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]

    if chat_id != ADMIN_CHAT_ID:
        answer_callback(cb_id, "⛔ Không có quyền")
        return

    parts = data.split(":")
    action = parts[0]

    if action == "approve" and len(parts) >= 3:
        machine_id = parts[1]
        days = int(parts[2]) if len(parts) > 2 else 365

        key, expiry = generate_license_key(machine_id, days)
        record_approved_key(machine_id, key)   # ban sao cuc bo, chi dung khi cung may

        # Duong that su den may khach: dua key len Realtime Database.
        try:
            admin_publish.publish_key(machine_id, key, expiry, days)
            delivery = "⚡ Key đã lên server — app của khách tự mở khoá trong vài giây."
        except Exception as pub_err:
            delivery = ("⚠️ *KHÔNG đưa được key lên server:* `%s`\n"
                        "Hãy gửi key trên cho khách dán tay vào app." % pub_err)
            print("[Bot] publish_key that bai: %s" % pub_err)

        # Sua tin nhan cu thanh da duyet
        edit_message(chat_id, message_id,
            f"✅ *ĐÃ DUYỆT*\n\n"
            f"🖥 Mã máy: `{machine_id}`\n"
            f"🔐 Key: `{key}`\n"
            f"📅 Hết hạn: *{expiry.strftime('%d/%m/%Y')}*\n\n"
            f"{delivery}")

        answer_callback(cb_id, "✅ Đã duyệt — gửi key cho khách")
        print(f"[Bot] Approved: {machine_id} -> {key} (expires {expiry})")

    elif action == "reject" and len(parts) >= 2:
        machine_id = parts[1]
        edit_message(chat_id, message_id,
            f"❌ *ĐÃ TỪ CHỐI*\n\n"
            f"🖥 Mã máy: `{machine_id}`")
        answer_callback(cb_id, "❌ Đã từ chối")
        print(f"[Bot] Rejected: {machine_id}")

    else:
        answer_callback(cb_id, "⚠️ Không hiểu lệnh")


def handle_status(message):
    """Xu ly lenh /status."""
    chat_id = message["chat"]["id"]
    if chat_id != ADMIN_CHAT_ID:
        return
    send_message(chat_id,
        f"📊 *Trạng thái Bot*\n\n"
        f"✅ Bot đang hoạt động\n"
        f"👤 Admin Chat ID: `{ADMIN_CHAT_ID}`\n"
        f"🤖 Bot đang lắng nghe yêu cầu kích hoạt...")


def polling_loop():
    """Vong lap chinh – long polling Telegram updates."""
    print("=" * 50)
    print("  Media Download Studio - License Bot")
    print("=" * 50)

    load_config()

    if ADMIN_CHAT_ID:
        print(f"[Bot] Admin chat_id: {ADMIN_CHAT_ID}")
    else:
        print("[Bot] Chua co admin. Gui /start cho bot tren Telegram.")

    # Kiem tra bot token
    me = api_call("getMe")
    if me.get("ok"):
        bot_name = me["result"].get("username", "?")
        print(f"[Bot] Bot: @{bot_name}")
        print(f"[Bot] Dang lang nghe... (Ctrl+C de dung)")
    else:
        print("[Bot] LOI: Khong ket noi duoc Telegram. Kiem tra BOT_TOKEN.")
        return

    offset = 0
    while True:
        try:
            result = api_call("getUpdates", {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message", "callback_query"]
            })

            if not result.get("ok"):
                time.sleep(5)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                # Xu ly tin nhan text
                if "message" in update:
                    msg = update["message"]
                    text = msg.get("text", "")

                    if text.startswith("/start"):
                        handle_start(msg)
                    elif text.startswith("/genkey"):
                        handle_genkey(msg)
                    elif text.startswith("/status"):
                        handle_status(msg)

                # Xu ly callback (nut bam inline)
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])

        except KeyboardInterrupt:
            print("\n[Bot] Dang dung bot...")
            break
        except Exception as e:
            print(f"[Bot] Loi: {e}")
            time.sleep(5)


if __name__ == "__main__":
    polling_loop()
