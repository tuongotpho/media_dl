import os
import re
import time
import uuid
import threading
import yt_dlp
from typing import Dict, Any, Optional

from .paths import downloads_dir

DOWNLOAD_DIR = downloads_dir()

# Global task storage for progress tracking
download_tasks: Dict[str, Dict[str, Any]] = {}


def _clamp_format_height(format_id: str, max_height: int) -> str:
    """Ha tran do phan giai trong chuoi format cua yt-dlp.

    'bestvideo[height<=2160]+bestaudio/best' voi max_height=1080
    -> 'bestvideo[height<=1080]+bestaudio/best'

    Chuoi khong theo mau tren (vi du 'best') se duoc thay bang mot chuoi
    co rang buoc chieu cao, de khong con duong nao vuot tran.
    """
    def repl(m):
        return "height<=%d" % min(int(m.group(1)), max_height)

    clamped, n = re.subn(r'height<=(\d+)', repl, format_id)
    if n:
        return clamped
    return "bestvideo[height<=%d]+bestaudio/best[height<=%d]/best[height<=%d]" % (
        max_height, max_height, max_height)

def get_ffmpeg_path() -> Optional[str]:
    """Locate FFmpeg executable path via imageio_ffmpeg or system PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which('ffmpeg')

JS_RUNTIMES_OPT = {'node': {}}


def js_runtime_opts() -> Dict[str, Any]:
    """Chi ep dung Node khi may that su co Node.

    Ban .exe portable co the chay tren may khong cai Node. Neu van ep
    js_runtimes={'node': {}} thi yt-dlp khong con runtime nao de giai ma
    signature. Bo han key nay thi yt-dlp tu do cac runtime khac.
    """
    import shutil
    if shutil.which('node'):
        return {'js_runtimes': JS_RUNTIMES_OPT}
    return {}

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
    def get_info(url: str, max_height: Optional[int] = None) -> Dict[str, Any]:
        """Fetch video metadata and available download formats."""
        ffmpeg_path = get_ffmpeg_path()
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            **js_runtime_opts(),
        }
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

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
            'note': 'Audio MP3 128kbps' if max_height else 'Audio MP3 320kbps',
            'resolution': 'Âm thanh duy nhất',
            'is_audio': True,
            'locked': False
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
                    locked = max_height is not None and height > max_height
                    formats_list.append({
                        'format_id': f"bestvideo[height<={height}]+bestaudio/best",
                        'ext': 'mp4',
                        'note': f"Video {res_str} — cần nâng cấp" if locked
                                else f"Video {res_str} (Siêu nét)",
                        'resolution': res_str,
                        'is_audio': False,
                        'locked': locked
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
    def active_task_count() -> int:
        """So task dang chay (chua ket thuc, chua loi)."""
        return sum(1 for t in download_tasks.values()
                   if t.get('status') not in ('finished', 'error'))

    @staticmethod
    def start_download(url: str, format_id: str, is_audio: bool = False,
                       limits: Optional[Dict[str, Any]] = None) -> str:
        """Start a background download task and return task_id.

        `limits` la bang gioi han cua goi hien tai (xem license.get_limits).
        Gioi han duoc ap o day chu khong chi o giao dien, nen sua HTML hay
        goi thang API cung khong vuot qua duoc.
        """
        limits = limits or {}
        max_height = limits.get('max_height')
        audio_quality = limits.get('audio_quality', '320')

        if not is_audio and max_height:
            format_id = _clamp_format_height(format_id, max_height)

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
                    'speed': f"{format_bytes(speed)}/s" if speed else "Đang xử lý...",
                    'eta': format_seconds(eta) if eta else "---",
                    'filename': os.path.basename(d.get('filename', ''))
                })
            elif d['status'] == 'finished':
                # Stream component completed; wait for full process completion
                download_tasks[task_id].update({
                    'percentage': 99.0,
                    'speed': 'Đang xử lý ghép file...',
                    'eta': 'Đang ghép...'
                })

        def postprocessor_hook(d: Dict[str, Any]):
            pp = d.get('postprocessor')
            status = d.get('status')
            if pp == 'Merger' and status == 'started':
                download_tasks[task_id].update({
                    'status': 'merging',
                    'percentage': 99.5,
                    'speed': 'Đang ghép Video & Audio (FFmpeg)...',
                    'eta': 'Sắp xong...'
                })

        def run_download():
            outtmpl = os.path.join(DOWNLOAD_DIR, '%(title)s [%(id)s].%(ext)s')
            ffmpeg_path = get_ffmpeg_path()
            
            ydl_opts = {
                'outtmpl': outtmpl,
                'progress_hooks': [progress_hook],
                'postprocessor_hooks': [postprocessor_hook],
                'quiet': True,
                'no_warnings': True,
                'overwrites': True,
                **js_runtime_opts(),
            }

            # Immediately update status to downloading so UI responds instantly
            download_tasks[task_id].update({
                'status': 'downloading',
                'percentage': 0.1,
                'speed': 'Đang kết nối...',
                'eta': 'Đang xử lý...'
            })

            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = ffmpeg_path

            if is_audio:
                if ffmpeg_path:
                    ydl_opts.update({
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': audio_quality,
                        }],
                    })
                else:
                    ydl_opts['format'] = 'bestaudio/best'
            else:
                if ffmpeg_path:
                    ydl_opts['format'] = format_id if '+' in format_id or 'best' in format_id else f"{format_id}+bestaudio/best"
                    ydl_opts['merge_output_format'] = 'mp4'
                else:
                    ydl_opts['format'] = 'best'

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'Video') if info else 'Video'
                    download_tasks[task_id]['title'] = title
                    
                    final_filename = ""
                    if info:
                        final_filepath = ydl.prepare_filename(info)
                        if not is_audio and ffmpeg_path:
                            base, _ = os.path.splitext(final_filepath)
                            final_filepath = base + '.mp4'
                        final_filename = os.path.basename(final_filepath)

                    download_tasks[task_id].update({
                        'status': 'finished',
                        'percentage': 100.0,
                        'filename': final_filename,
                        'speed': '0 B/s',
                        'eta': 'Hoàn thành'
                    })
            except Exception as e:
                # Retry fallback to best single stream if multi-stream setup fails
                try:
                    ydl_opts['format'] = 'best'
                    ydl_opts.pop('merge_output_format', None)
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        final_filename = os.path.basename(ydl.prepare_filename(info)) if info else ''
                        download_tasks[task_id].update({
                            'status': 'finished',
                            'percentage': 100.0,
                            'filename': final_filename,
                            'speed': '0 B/s',
                            'eta': 'Hoàn thành'
                        })
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

