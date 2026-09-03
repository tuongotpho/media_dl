import os
import json
import asyncio
import subprocess
import urllib.request
import urllib.error
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .downloader import YTDLPManager, download_tasks, DOWNLOAD_DIR
from .paths import static_dir, base_dir
from .license import get_license_status, validate_license_key, save_license, get_machine_id, claim_trial_license
from .license import FULL_LIMITS
from . import engine
from . import history as history_store
from . import remote_activation

app = FastAPI(title="Media Download Studio", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Telegram Bot Config ----
BOT_TOKEN = "8870394330:AAGzPWicK_EMBygfF0xRpNJQP9bNCP_IlOI"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DEFAULT_ADMIN_CHAT_ID = 5056715300


def _get_admin_chat_id():
    """Doc admin chat_id tu bot_config.json voi fallback."""
    config_paths = [
        os.path.join(base_dir(), "bot_config.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot_config.json"),
    ]
    for path in config_paths:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    chat_id = json.load(f).get("admin_chat_id")
                    if chat_id:
                        return chat_id
            except Exception:
                pass
    return DEFAULT_ADMIN_CHAT_ID


# ---- Pydantic Models ----

class VideoInfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    is_audio: bool = False

class ActivateRequest(BaseModel):
    key: str

class LicenseRequestPayload(BaseModel):
    plan: str = "1year"


# ---- License API ----

@app.get("/api/license")
async def license_status():
    """Tra ve trang thai license hien tai."""
    return get_license_status()


@app.post("/api/license/trial")
async def claim_trial():
    """Kich hoat dung thu 7 ngay mien phi."""
    machine_id = get_machine_id()
    res = claim_trial_license(machine_id)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/license/activate")
async def activate_license(req: ActivateRequest):
    """Kich hoat license bang key."""
    machine_id = get_machine_id()
    result = validate_license_key(req.key, machine_id)

    if result["valid"]:
        save_license(req.key)
        return {
            "success": True,
            "message": "Kích hoạt thành công!",
            "expiry": result["expiry"],
            "days_left": result["days_left"],
        }
    else:
        raise HTTPException(status_code=400, detail=result["message"])


@app.post("/api/license/request")
async def request_activation(payload: LicenseRequestPayload = LicenseRequestPayload()):
    """Gui yeu cau kich hoat den admin qua Telegram."""
    machine_id = get_machine_id()
    admin_id = _get_admin_chat_id()

    if not admin_id:
        raise HTTPException(
            status_code=503,
            detail="Chưa cấu hình bot Telegram. Liên hệ admin trực tiếp."
        )

    plan_names = {
        "6months": "🥉 Gói 6 Tháng (19.000 VNĐ)",
        "1year": "🥈 Gói 1 Năm (29.000 VNĐ)",
        "lifetime": "👑 Gói Vĩnh Viễn (99.000 VNĐ)",
    }
    selected_plan_title = plan_names.get(payload.plan, "🥈 Gói 1 Năm (29.000 VNĐ)")

    from datetime import datetime
    text = (
        "🔔 *YÊU CẦU KÍCH HOẠT MỚI*\n\n"
        f"🖥 Mã máy: `{machine_id}`\n"
        f"📦 Đăng ký: *{selected_plan_title}*\n"
        f"📅 Thời gian: {datetime.now().strftime('%H:%M %d/%m/%Y')}\n\n"
        "Chọn nút tương ứng để duyệt:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🥉 Duyệt 6 Tháng (19k)", "callback_data": f"approve:{machine_id}:180"},
                {"text": "🥈 Duyệt 1 Năm (29k)", "callback_data": f"approve:{machine_id}:365"},
            ],
            [
                {"text": "👑 Duyệt Vĩnh Viễn (99k)", "callback_data": f"approve:{machine_id}:36500"},
                {"text": "❌ Từ Chối", "callback_data": f"reject:{machine_id}"},
            ]
        ]
    }

    req_payload = json.dumps({
        "chat_id": admin_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
    }).encode()

    req = urllib.request.Request(
        f"{TELEGRAM_API}/sendMessage",
        data=req_payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                # Bat dau hoi server cho key duyet. Chi hoi khi da gui yeu cau,
                # de may chi dung ban mien phi khong goi mang vo ich.
                remote_activation.mark_pending(machine_id, payload.plan)
                return {
                    "success": True,
                    "message": "Đã gửi yêu cầu đến admin. App sẽ tự mở khoá ngay khi được duyệt."
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không gửi được: {e}")

    raise HTTPException(status_code=500, detail="Không gửi được yêu cầu")


# ---- Engine yt-dlp ----

@app.get("/api/engine")
async def engine_status():
    """Phien ban engine hien tai va co ban moi hon khong."""
    return engine.status()


@app.post("/api/engine/update")
async def engine_update():
    """Tai ban yt-dlp moi nhat vao thu muc engine/ canh file .exe."""
    try:
        return await asyncio.to_thread(engine.update)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.on_event("startup")
async def _check_engine_on_startup():
    """Hoi PyPI o luong nen, khong lam cham luc mo app."""
    engine.check_in_background()


# ---- License Middleware ----

def _is_licensed() -> bool:
    """Kiem tra nhanh license co hop le khong."""
    status = get_license_status()
    return status.get("activated", False)


def _current_limits() -> dict:
    """Bang gioi han cua goi dang dung.

    Ban mien phi khong bi chan truy cap, chi bi ha tran tinh nang. Gioi han
    lay tu day chu khong lay tu request, nen sua giao dien hay goi thang API
    deu khong vuot qua duoc.
    """
    return get_license_status().get("limits", {})


# ---- Video API (co kiem tra license) ----

@app.post("/api/info")
async def get_video_info(req: VideoInfoRequest):
    limits = _current_limits()
    try:
        info = await asyncio.to_thread(
            YTDLPManager.get_info, req.url, limits.get("max_height"))
        info["limits"] = limits
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/download")
async def start_download(req: DownloadRequest):
    limits = _current_limits()

    max_concurrent = limits.get("max_concurrent", 1)
    if YTDLPManager.active_task_count() >= max_concurrent:
        raise HTTPException(
            status_code=429,
            detail=(f"Bản miễn phí tải từng file một. Đợi file hiện tại xong, "
                    f"hoặc nâng cấp để tải {FULL_LIMITS['max_concurrent']} file cùng lúc.")
            if max_concurrent == 1 else
            f"Đang tải tối đa {max_concurrent} file cùng lúc. Vui lòng đợi.")

    try:
        task_id = YTDLPManager.start_download(
            req.url, req.format_id, req.is_audio, limits)
        return {"task_id": task_id, "message": "Download task started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress/{task_id}")
async def stream_progress(task_id: str):
    """Server-Sent Events (SSE) endpoint to stream real-time progress to client."""
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        while True:
            task = download_tasks.get(task_id, {})
            status = task.get('status', 'unknown')
            
            yield f"data: {json.dumps(task)}\n\n"
            
            if status in ['finished', 'error']:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/history")
async def get_history():
    """Lich su tai xuong that su, khong phai liet ke thu muc."""
    return history_store.list_entries(DOWNLOAD_DIR)


@app.delete("/api/history/{entry_id}")
async def delete_history_entry(entry_id: str):
    history_store.remove(entry_id)
    return {"success": True}


@app.post("/api/history/clear")
async def clear_history():
    history_store.clear()
    return {"success": True}

@app.post("/api/open-folder")
async def open_download_folder(request: Request):
    """Open Windows Explorer to the downloads directory. Local requests only."""
    client_host = request.client.host if request.client else None
    if client_host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="Chi mo duoc thu muc tu may chu")
    try:
        if os.name == 'nt':
            os.startfile(DOWNLOAD_DIR)
        else:
            subprocess.Popen(['open' if os.sys.platform == 'darwin' else 'xdg-open', DOWNLOAD_DIR])
        return {"status": "ok", "message": "Opened downloads folder"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/{filename}")
async def get_file(filename: str):
    # Chi lay ten file, chan moi kieu path traversal (..\..\.., o dia tuyet doi, ...)
    safe_name = os.path.basename(filename.replace("\\", "/"))
    if not safe_name or safe_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = os.path.join(DOWNLOAD_DIR, safe_name)
    # Kiem tra lan 2: duong dan that su phai nam trong DOWNLOAD_DIR
    if os.path.commonpath([os.path.realpath(file_path), os.path.realpath(DOWNLOAD_DIR)]) != os.path.realpath(DOWNLOAD_DIR):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if os.path.isfile(file_path):
        return FileResponse(
            path=file_path,
            filename=safe_name,
            media_type='application/octet-stream'
        )
    raise HTTPException(status_code=404, detail="File not found")

# Serve Frontend static files
STATIC_DIR = static_dir()
os.makedirs(STATIC_DIR, exist_ok=True)
class NoCacheStaticFiles(StaticFiles):
    """Khong cho trinh duyet cache giao dien.

    Sau khi cap nhat app, webview van giu ban HTML/JS cu trong cache va nguoi
    dung thay giao dien cu du da cai ban moi. App chay o localhost nen tat
    cache khong ton bang thong dang ke.
    """

    def is_not_modified(self, response_headers, request_headers) -> bool:
        return False

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response


app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
