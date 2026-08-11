import os
import time
import uuid
import threading
import yt_dlp
from typing import Dict, Any, Optional

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Global task storage for progress tracking
download_tasks: Dict[str, Dict[str, Any]] = {}

def format_bytes(bytes_num: Optional[float]) -> str:
    if not bytes_num:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} TB"

def format_seconds(seconds: Optional[float]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

class YTDLPManager:
    @staticmethod
    def get_info(url: str) -> Dict[str, Any]:
        """Fetch video metadata and available download formats."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        if not info:
            raise ValueError("Không thể lấy thông tin video từ URL này.")

        # Extract available formats
        formats_list = []
        seen_resolutions = set()
        
        # Audio option
        formats_list.append({
            'format_id': 'bestaudio/best',
            'ext': 'mp3',
            'note': 'Audio MP3 (Chất lượng cao nhất)',
            'resolution': 'Âm thanh duy nhất',
            'is_audio': True
        })
        
        raw_formats = info.get('formats', [])
        for f in raw_formats:
            vcodec = f.get('vcodec', 'none')
            height = f.get('height')
            ext = f.get('ext', 'mp4')
            
            if vcodec != 'none' and height and height >= 360:
                res_str = f"{height}p"
                if res_str not in seen_resolutions:
                    seen_resolutions.add(res_str)
                    formats_list.append({
                        'format_id': f['format_id'],
                        'ext': ext,
                        'note': f"Video {res_str} ({ext})",
                        'resolution': res_str,
                        'is_audio': False
                    })
                    
        # Sort video formats by height descending
        video_formats = sorted(
            [f for f in formats_list if not f['is_audio']],
            key=lambda x: int(x['resolution'].replace('p', '')) if x['resolution'].endswith('p') else 0,
            reverse=True
        )
        audio_formats = [f for f in formats_list if f['is_audio']]

        return {
            'title': info.get('title', 'Untitled Video'),
            'uploader': info.get('uploader', 'Unknown Uploader'),
            'duration': format_seconds(info.get('duration')),
            'duration_raw': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'view_count': info.get('view_count', 0),
            'formats': audio_formats + video_formats,
            'webpage_url': info.get('webpage_url', url)
        }

    @staticmethod
    def start_download(url: str, format_id: str, is_audio: bool = False) -> str:
        """Start a background download task and return task_id."""
        task_id = str(uuid.uuid4())
        
        download_tasks[task_id] = {
            'task_id': task_id,
            'status': 'starting',
            'percentage': 0.0,
            'speed': '0 MB/s',
            'eta': 'Đang tính...',
            'filename': '',
            'error': None,
            'url': url,
            'title': 'Đang chuẩn bị...'
        }
        
        def progress_hook(d: Dict[str, Any]):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                percentage = (downloaded / total * 100) if total > 0 else 0.0
                speed = d.get('speed')
                eta = d.get('eta')
                
                download_tasks[task_id].update({
                    'status': 'downloading',
                    'percentage': round(percentage, 1),
                    'downloaded_str': format_bytes(downloaded),
                    'total_str': format_bytes(total),
                    'speed': f"{format_bytes(speed)}/s" if speed else "Đang cập nhật...",
                    'eta': format_seconds(eta) if eta else "---",
                    'filename': os.path.basename(d.get('filename', ''))
                })
            elif d['status'] == 'finished':
                final_filename = os.path.basename(d.get('filename', ''))
                download_tasks[task_id].update({
                    'status': 'finished',
                    'percentage': 100.0,
                    'filename': final_filename,
                    'speed': '0 B/s',
                    'eta': 'Hoàn thành'
                })

        def run_download():
            outtmpl = os.path.join(DOWNLOAD_DIR, '%(title)s [%(id)s].%(ext)s')
            
            ydl_opts = {
                'outtmpl': outtmpl,
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
            }

            # Check for ffmpeg via imageio_ffmpeg or system PATH
            ffmpeg_path = None
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                import shutil
                ffmpeg_path = shutil.which('ffmpeg')

            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = ffmpeg_path

            if is_audio:
                if ffmpeg_path:
                    ydl_opts.update({
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                    })
                else:
                    # Download native audio stream if ffmpeg is missing
                    ydl_opts['format'] = 'bestaudio/best'
            else:
                if ffmpeg_path:
                    ydl_opts['format'] = f"{format_id}+bestaudio/best" if format_id != 'best' else 'bestvideo+bestaudio/best'
                    ydl_opts['merge_output_format'] = 'mp4'
                else:
                    # Fallback to single stream (video + audio combined in one file) if ffmpeg missing
                    ydl_opts['format'] = 'best'

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info:
                        download_tasks[task_id]['title'] = info.get('title', 'Video')
            except Exception as e:
                # Retry with simplest single stream format
                try:
                    ydl_opts['format'] = 'best'
                    ydl_opts.pop('merge_output_format', None)
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return
                except Exception as err:
                    e = err
                download_tasks[task_id].update({
                    'status': 'error',
                    'error': str(e)
                })

        thread = threading.Thread(target=run_download, daemon=True)
        thread.start()
        return task_id

    @staticmethod
    def get_history() -> list:
        """List files in the downloads folder."""
        files = []
        if not os.path.exists(DOWNLOAD_DIR):
            return files
            
        for fname in os.listdir(DOWNLOAD_DIR):
            fpath = os.path.join(DOWNLOAD_DIR, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                files.append({
                    'name': fname,
                    'size': format_bytes(stat.st_size),
                    'size_bytes': stat.st_size,
                    'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                    'path': fpath
                })
        # Sort newest first
        return sorted(files, key=lambda x: x['mtime'], reverse=True)
