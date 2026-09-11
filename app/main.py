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

app = FastAPI(title="Media Download Studio", version="1.1.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- May chu ban quyen ----
#
# App KHONG con giu bot token. Truoc day app tu goi Telegram nen token nam
# trong moi file .exe phat hanh; ai giai nen cung lay duoc va tu duyet ban
# quyen cho minh. Gio app goi may chu tren Render, may chu moi goi Telegram.
# Xem server/webhook.py.
LICENSE_SERVER = os.environ.get(
    "MDS_LICENSE_SERVER", "https://mds-license-server.onrender.com").strip().rstrip("/")

# Goi mien phi cua Render ngu sau 15 phut khong ai goi, lan goi dau mat
# ~50 giay de day. Timeout phai du rong va thu lai mot lan, khong thi nguoi
# vua chuyen khoan xong bam nut se thay "khong gui duoc".
LICENSE_SERVER_TIMEOUT = 75
LICENSE_SERVER_RETRIES = 2


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

class ErrorReportPayload(BaseModel):
    task_id: str = ""      # tai dang hien tren man hinh
    entry_id: str = ""     # hoac mot muc trong lich su
    note: str = ""         # khach ghi them, tuy chon


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
    """Gui yeu cau kich hoat len may chu; may chu se nhan cho admin qua Telegram."""
    machine_id = get_machine_id()
    # Ma rieng cho lan yeu cau nay: server gan vao nut Duyet/Tu Choi, app
    # doi chieu khi nhan ket qua de khong nham voi lan truoc.
    import uuid
    request_id = uuid.uuid4().hex[:12]
    body = json.dumps({"machine_id": machine_id, "plan": payload.plan,
                       "request_id": request_id}).encode()

    def call_server():
        req = urllib.request.Request(
            f"{LICENSE_SERVER}/api/request-activation",
            data=body,
            headers={"Content-Type": "application/json",
                     "User-Agent": "MediaDownloadStudio"},
        )
        with urllib.request.urlopen(req, timeout=LICENSE_SERVER_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    last_error = None
    for attempt in range(LICENSE_SERVER_RETRIES):
        try:
            result = await asyncio.to_thread(call_server)
            if result.get("success"):
                # Bat dau hoi server cho key duyet. Chi hoi khi da gui yeu cau,
                # de may chi dung ban mien phi khong goi mang vo ich.
                remote_activation.mark_pending(machine_id, payload.plan, request_id)
                return result
            last_error = result.get("message") or result.get("detail") or "Máy chủ từ chối"
            break
        except urllib.error.HTTPError as e:
            try:
                last_error = json.loads(e.read().decode("utf-8")).get("detail", str(e))
            except Exception:
                last_error = f"HTTP {e.code}"
            if e.code < 500:
                break           # loi phia minh (400...) thi thu lai vo ich
        except Exception as e:
            last_error = str(e)  # timeout, mat mang: thu lai

    raise HTTPException(
        status_code=502,
        detail=("Không gửi được yêu cầu đến máy chủ (%s). "
                "Kiểm tra kết nối mạng rồi thử lại, hoặc liên hệ admin qua Telegram "
                "@august8787 kèm mã máy %s." % (last_error, machine_id)),
    )


# ---- Bao loi cho admin ----

def _log_tail(max_chars: int = 900) -> str:
    """Duoi file log cua ban .exe (gui.py ghi stderr vao day). Dev mode: rong."""
    path = os.path.join(base_dir(), "ytdlp-studio.log")
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 4000))
            tail = f.read().decode("utf-8", "replace")
        lines = [l for l in tail.splitlines() if l.strip()][-25:]
        return "\n".join(lines)[-max_chars:]
    except Exception:
        return ""


@app.post("/api/report-error")
async def report_error(payload: ErrorReportPayload):
    """Gui bao cao loi tai file len may chu; may chu chuyen cho admin qua Telegram.

    Chi chay khi nguoi dung bam nut, khong tu dong: link video la du lieu
    rieng cua ho, va admin khong can nhan moi loi vat (video rieng tu, mat
    mang...). Nut bam la su dong y, va nguoi dung thay ro minh gui gi.
    """
    import platform

    url = quality = error = ""
    engine_hint = False
    if payload.task_id and payload.task_id in download_tasks:
        t = download_tasks[payload.task_id]
        url, error = t.get("url", ""), t.get("error", "")
        engine_hint = bool(t.get("engine_hint"))
        entry = next((e for e in history_store.list_entries(DOWNLOAD_DIR)
                      if e.get("id") == t.get("entry_id")), None)
        quality = (entry or {}).get("quality", "")
    elif payload.entry_id:
        entry = next((e for e in history_store.list_entries(DOWNLOAD_DIR)
                      if e.get("id") == payload.entry_id), None)
        if entry:
            url, error, quality = entry.get("url", ""), entry.get("error", ""), entry.get("quality", "")
            engine_hint = engine.looks_like_engine_failure(error)
    if not error:
        raise HTTPException(status_code=400, detail="Không tìm thấy lỗi để báo cáo.")

    lic = get_license_status()
    eng = engine.status()
    body = json.dumps({
        "machine_id": get_machine_id(),
        "app_version": app.version,
        "tier_name": lic.get("tier_name", ""),
        "days_left": lic.get("days_left"),
        "engine_version": eng.get("current", ""),
        "engine_source": "tự cập nhật" if eng.get("using_updated_engine") else "đóng gói sẵn",
        "os_info": "%s %s" % (platform.system(), platform.release()),
        "url": url,
        "quality": quality,
        "error": error,
        "engine_hint": engine_hint,
        "log_tail": _log_tail(),
        "note": payload.note[:300],
    }).encode()

    def call_server():
        req = urllib.request.Request(
            f"{LICENSE_SERVER}/api/report-error", data=body,
            headers={"Content-Type": "application/json", "User-Agent": "MediaDownloadStudio"})
        with urllib.request.urlopen(req, timeout=LICENSE_SERVER_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        return await asyncio.to_thread(call_server)
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail", str(e))
        except Exception:
            detail = f"HTTP {e.code}"
        raise HTTPException(status_code=502, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502,
                            detail=f"Không gửi được báo cáo ({e}). Kiểm tra mạng rồi thử lại.")


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
