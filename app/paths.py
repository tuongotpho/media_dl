"""Xu ly duong dan cho ca 2 che do: chay bang python va chay tu file .exe.

PyInstaller giai nen tai nguyen vao mot thu muc tam (sys._MEIPASS) moi lan chay,
nen __file__ khong con dung de tim file tinh, va cang khong dung de luu video tai ve.
"""
import os
import sys


def is_frozen() -> bool:
    """True khi dang chay tu file .exe do PyInstaller dong goi."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def static_dir() -> str:
    """Thu muc chua giao dien web (chi doc)."""
    if is_frozen():
        return os.path.join(sys._MEIPASS, "static")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def asset_path(name: str) -> str:
    """Duong dan toi file trong assets/ (icon...), dung ca 2 che do."""
    if is_frozen():
        return os.path.join(sys._MEIPASS, "assets", name)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "assets", name)


def base_dir() -> str:
    """Thu muc goc de ghi du lieu.

    Che do exe: thu muc chua file .exe -> portable that su, chep di dau
    cung mang theo video da tai. Khong dung _MEIPASS vi no bi xoa khi thoat.
    """
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def downloads_dir() -> str:
    """Thu muc luu video, tu tao neu chua co.

    Che do exe: nam canh file .exe (portable).
    Che do python: giu nguyen app/downloads nhu truoc de khong mat lich su
    va khong phai di chuyen cac file da tai.
    """
    if is_frozen():
        path = os.path.join(base_dir(), "downloads")
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    os.makedirs(path, exist_ok=True)
    return path
