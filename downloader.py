import re
import time
from pathlib import Path
from typing import Optional
from contextlib import nullcontext
from config import YTDLP_PROXY, _without_system_proxy, _find_ffmpeg
from jobs import Job

def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)

def _build_yt_dlp_opts(outtmpl: str, download_mode: str = "audio") -> dict:
    fmt = "bestaudio/best" if download_mode == "audio" else "bestvideo+bestaudio/best"
    opts: dict = {
        "outtmpl": outtmpl,
        "format": fmt,
        "ffmpeg_location": _find_ffmpeg(),
        "merge_output_format": "mp4" if download_mode == "video" else None
    }
    if YTDLP_PROXY is not None:
        proxy = YTDLP_PROXY.strip()
        if proxy.lower() in ("", "direct", "none", "false", "0"):
            opts["proxy"] = ""
        else:
            opts["proxy"] = proxy
    return opts

def _is_proxy_connection_error(exc: BaseException) -> bool:
    msg = _strip_ansi(str(exc)).lower()
    return "connection refused" in msg or "errno 111" in msg

def download_twitch_video(url: str, video_path: Path, download_mode: str = "audio", job: Optional[Job] = None) -> str:
    """Скачивает VOD с Twitch/YouTube; при мёртвом прокси в окружении пробует без него. Возвращает название видео."""
    from yt_dlp import YoutubeDL

    outtmpl = str(video_path)
    opts = _build_yt_dlp_opts(outtmpl, download_mode)
    force_direct = YTDLP_PROXY is not None and opts.get("proxy") == ""

    platform_name = "видео"
    if "twitch" in url.lower():
        platform_name = "Twitch"
    elif "youtube" in url.lower() or "youtu.be" in url.lower():
        platform_name = "YouTube"

    def make_progress_hook(job_obj):
        last_update = [0.0]
        last_pct = [-1]
        
        def hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                
                pct_val = 0
                percent_str = ""
                if total:
                    pct_val = int(downloaded / total * 100)
                    percent_str = f"{pct_val}%"
                else:
                    raw_pct = d.get('_percent_str')
                    if raw_pct:
                        percent_str = re.sub(r"\x1b\[[0-9;]*m", "", raw_pct).strip()
                        match = re.search(r'([0-9.]+)%', percent_str)
                        if match:
                            try:
                                pct_val = int(float(match.group(1)))
                            except ValueError:
                                pass
                
                now = time.time()
                # Обновляем не чаще раза в секунду или при изменении процента
                if now - last_update[0] >= 1.0 or pct_val != last_pct[0]:
                    last_update[0] = now
                    last_pct[0] = pct_val
                    
                    speed = re.sub(r"\x1b\[[0-9;]*m", "", d.get('_speed_str', '')).strip()
                    eta = re.sub(r"\x1b\[[0-9;]*m", "", d.get('_eta_str', '')).strip()
                    
                    msg = f"Скачивание: {percent_str}" if percent_str else "Скачивание..."
                    if speed:
                        msg += f" ({speed})"
                    if eta:
                        msg += f" ETA: {eta}"
                    
                    job_obj.log(msg, progress=pct_val, status="downloading")
        return hook

    def _run(use_direct: bool) -> str:
        run_opts = dict(opts)
        if use_direct:
            run_opts["proxy"] = ""
        if job:
            run_opts["progress_hooks"] = [make_progress_hook(job)]
        ctx = _without_system_proxy() if use_direct else nullcontext()
        with ctx:
            with YoutubeDL(run_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info.get("title") or f"downloaded_video_{int(time.time())}"

    try:
        if force_direct:
            if job:
                job.log(f"Скачивание с {platform_name} (без прокси)…", progress=0, status="downloading")
            return _run(use_direct=True)
        if job:
            job.log(f"Скачивание с {platform_name}…", progress=0, status="downloading")
        return _run(use_direct=False)
    except Exception as first_error:
        if not _is_proxy_connection_error(first_error):
            raise RuntimeError(_strip_ansi(str(first_error))) from first_error
        if job:
            job.log("Прокси недоступен, повтор без прокси…")
        try:
            return _run(use_direct=True)
        except Exception as second_error:
            raise RuntimeError(
                f"Не удалось скачать с {platform_name}. Прокси в системе недоступен "
                f"(127.0.0.1: Connection refused). Запустите VPN/Clash или добавьте в .env:\n"
                "YTDLP_PROXY=direct — скачивать без прокси\n"
                "YTDLP_PROXY=socks5://127.0.0.1:10808 — явный адрес прокси\n\n"
                f"Ошибка: {_strip_ansi(str(second_error))}"
            ) from second_error
