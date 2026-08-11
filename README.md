# 🎬 YTDLP Studio - Ultra Video Downloader WebApp

![YTDLP Studio](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.7.4-red.svg)

Một ứng dụng Desktop WebApp hiện đại được xây dựng bằng **Python (FastAPI)** và **yt-dlp Engine**, hỗ trợ tải video và âm thanh từ YouTube, TikTok, Facebook và 1.000+ nền tảng khác với giao diện Glassmorphism Dark Mode sang trọng.

---

## 🌟 Tính Năng Nổi Bật

- 🚀 **Tốc độ tải cực nhanh**: Trích xuất stream trực tiếp, loại bỏ giới hạn băng thông.
- 🎨 **Giao diện Glassmorphism**: Hiệu ứng kính mờ sang trọng, responsive trên mọi kích thước màn hình.
- 📊 **Tiến trình Realtime (SSE)**: Cập nhật phần trăm %, tốc độ tải (MB/s), thời gian còn lại (ETA) theo thời gian thực.
- 🎵 **Chuyển đổi MP3**: Hỗ trợ tách nhạc chất lượng cao (320kbps MP3 / M4A).
- 📁 **Quản lý Thư viện**: Xem lại các file đã tải và mở nhanh thư mục trong Windows Explorer.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy

### 1. Yêu cầu hệ thống
- Python 3.9 trở lên
- FFmpeg (dành cho tính năng gộp video 1080p+ và convert MP3)

### 2. Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```

### 3. Khởi chạy ứng dụng (1-Click)
```bash
python run.py
```
Ứng dụng sẽ tự động mở tại địa chỉ: **http://127.0.0.1:8000**

---

## 🛠️ Công Nghệ Sử Dụng

- **Backend**: Python 3, FastAPI, Uvicorn, yt-dlp, Server-Sent Events (SSE).
- **Frontend**: HTML5, Vanilla CSS3 (Glassmorphism), JavaScript (ES6+), FontAwesome 6.
