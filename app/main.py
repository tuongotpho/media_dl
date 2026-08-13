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
BOT_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "bot_config.json"
)


def _get_admin_chat_id():
    """Doc admin chat_id tu bot_config.json."""
    if os.path.isfile(BOT_CONFIG_FILE):
        try:
            with open(BOT_CONFIG_FILE, "r") as f:
                return json.load(f).get("admin_chat_id")
        except Exception:
            pass
    return None


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


@app.post("/api/license/reset")
async def reset_license_endpoint():
    """Xoa file license.dat va approved_keys.json de quay ve trang thai Chua Kich Hoat (dung de test)."""
    lic_file = os.path.join(base_dir(), "license.dat")
    app_file = os.path.join(base_dir(), "approved_keys.json")
    if os.path.exists(lic_file):
        os.remove(lic_file)
    if os.path.exists(app_file):
        os.remove(app_file)
    return {"success": True, "message": "Đã reset trạng thái bản quyền về Chưa Kích Hoạt!"}


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
                return {
                    "success": True,
                    "message": "Đã gửi yêu cầu đến admin. Vui lòng chờ phê duyệt."
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không gửi được: {e}")

    raise HTTPException(status_code=500, detail="Không gửi được yêu cầu")


# ---- License Middleware ----

def _is_licensed() -> bool:
    """Kiem tra nhanh license co hop le khong."""
    status = get_license_status()
    return status.get("activated", False)


# ---- Video API (co kiem tra license) ----

@app.post("/api/info")
async def get_video_info(req: VideoInfoRequest):
    if not _is_licensed():
        raise HTTPException(status_code=403,
                            detail="Vui lòng kích hoạt bản quyền để sử dụng.")
    try:
        info = await asyncio.to_thread(YTDLPManager.get_info, req.url)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/download")
async def start_download(req: DownloadRequest):
    if not _is_licensed():
        raise HTTPException(status_code=403,
                            detail="Vui lòng kích hoạt bản quyền để sử dụng.")
    try:
        task_id = YTDLPManager.start_download(req.url, req.format_id, req.is_audio)
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
    return YTDLPManager.get_history()

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
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
