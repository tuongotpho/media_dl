# -*- coding: utf-8 -*-
"""Lich su tai xuong.

Truoc day tab Thu Vien chi liet ke file co trong thu muc downloads, nen no
hien ca .gitkeep lan file nguoi dung tu chep vao, va mat sach dau vet cua
nhung lan tai that bai. Day la lich su that: moi lan bam tai deu duoc ghi,
ke ca khi hong, kem link goc de tai lai.
"""
import json
import os
import threading
import time
import uuid

MAX_ENTRIES = 300
_lock = threading.Lock()


def _path() -> str:
    from .paths import base_dir
    return os.path.join(base_dir(), "history.json")


def _load() -> list:
    p = _path()
    if not os.path.isfile(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(entries: list) -> None:
    tmp = _path() + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries[:MAX_ENTRIES], f, ensure_ascii=False, indent=1)
        os.replace(tmp, _path())
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def add(url: str, title: str, quality: str, is_audio: bool) -> str:
    """Ghi mot muc dang tai. Tra ve id de cap nhat ve sau."""
    entry_id = str(uuid.uuid4())
    with _lock:
        entries = _load()
        entries.insert(0, {
            "id": entry_id,
            "url": url,
            "title": title or "",   # rong -> giao dien hien link goc
            "quality": quality,
            "is_audio": is_audio,
            "status": "downloading",
            "filename": "",
            "size_bytes": 0,
            "error": "",
            "ts": int(time.time()),
        })
        _save(entries)
    return entry_id


def update(entry_id: str, **fields) -> None:
    if not entry_id:
        return
    with _lock:
        entries = _load()
        for e in entries:
            if e.get("id") == entry_id:
                e.update(fields)
                break
        _save(entries)


def finish(entry_id: str, filename: str, download_dir: str) -> None:
    size = 0
    if filename:
        p = os.path.join(download_dir, filename)
        if os.path.isfile(p):
            size = os.path.getsize(p)
    update(entry_id, status="finished", filename=filename, size_bytes=size, error="")


def fail(entry_id: str, error: str) -> None:
    update(entry_id, status="error", error=str(error)[:500])


def list_entries(download_dir: str) -> list:
    """Lich su kem co con file tren dia khong."""
    out = []
    for e in _load():
        e = dict(e)
        fname = e.get("filename") or ""
        e["exists"] = bool(fname) and os.path.isfile(os.path.join(download_dir, fname))
        # Muc dang tai do lan chay truoc bo do -> danh dau la loi
        if e.get("status") == "downloading" and time.time() - e.get("ts", 0) > 86400:
            e["status"] = "error"
            e["error"] = e.get("error") or "Bị gián đoạn"
        out.append(e)
    return out


def remove(entry_id: str) -> None:
    with _lock:
        _save([e for e in _load() if e.get("id") != entry_id])


def clear() -> None:
    with _lock:
        _save([])
