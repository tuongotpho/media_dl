import os
import asyncio
import subprocess
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .downloader import YTDLPManager, download_tasks, DOWNLOAD_DIR

app = FastAPI(title="YTDLP Studio Desktop App", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoInfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    is_audio: bool = False

@app.post("/api/info")
async def get_video_info(req: VideoInfoRequest):
    try:
        info = await asyncio.to_thread(YTDLPManager.get_info, req.url)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/download")
async def start_download(req: DownloadRequest):
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
            
            import json
            yield f"data: {json.dumps(task)}\n\n"
            
            if status in ['finished', 'error']:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/history")
async def get_history():
    return YTDLPManager.get_history()

@app.post("/api/open-folder")
async def open_download_folder():
    """Open Windows Explorer to the downloads directory."""
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
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

# Serve Frontend static files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
