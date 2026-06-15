import os
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Импорт локальных модулей
from config import ROOT, VIDEO_DIR, OUTPUT_DIR, TMP_DIR, USE_GPU, WHISPER_LANGUAGE, GEN_API_KEY, _find_ffmpeg, _find_ffprobe
from jobs import _create_job, _get_job
from time_utils import parse_time_to_seconds
from clip_utils import extract_subtitles_for_clip
from video_editor import cut_and_crop_video
from downloader import download_twitch_video
from transcriber import list_whisper_models
from summarizer import list_summary_backends, _default_summary_backend
from processor import process_media, _run_job

app = FastAPI()

# Монтируем статические ресурсы
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = Path(__file__).parent / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/options")
async def api_options():
    gpu_bin = ROOT / "whisper-cuda"
    return {
        "whisper_models": list_whisper_models(),
        "summary_backends": list_summary_backends(),
        "default_whisper": "medium" if any(m["id"] == "medium" for m in list_whisper_models()) else None,
        "default_summary": _default_summary_backend(),
        "genapi_configured": bool(GEN_API_KEY),
        "whisper_language": WHISPER_LANGUAGE,
        "whisper_gpu": USE_GPU and gpu_bin.is_file(),
    }

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    return _get_job(job_id).to_dict()

@app.post("/process")
async def process_video(
    file: UploadFile = File(...),
    whisper_model: Optional[str] = Form(None),
    summary_backend: str = Form("genapi-gpt-4-1"),
    with_timestamps: bool = Form(True),
    layout: str = Form("vertical_reels"),
):
    dest_path = VIDEO_DIR / Path(file.filename).name
    with dest_path.open("wb") as out_f:
        shutil.copyfileobj(file.file, out_f)

    job = _create_job()
    threading.Thread(
        target=_run_job,
        args=(
            job,
            lambda: process_media(
                dest_path,
                whisper_model_id=whisper_model,
                summary_backend=summary_backend,
                with_timestamps=with_timestamps,
                layout=layout,
                job=job,
            ),
        ),
        daemon=True,
    ).start()
    return {"job_id": job.id}

@app.post("/process/sync")
async def process_video_sync(
    file: UploadFile = File(...),
    whisper_model: Optional[str] = Form(None),
    summary_backend: str = Form("genapi-gpt-4-1"),
    with_timestamps: bool = Form(True),
    layout: str = Form("vertical_reels"),
):
    dest_path = VIDEO_DIR / Path(file.filename).name
    with dest_path.open("wb") as out_f:
        shutil.copyfileobj(file.file, out_f)
    try:
        return process_media(
            dest_path,
            whisper_model_id=whisper_model,
            summary_backend=summary_backend,
            with_timestamps=with_timestamps,
            layout=layout,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

class TwitchDownloadRequest(BaseModel):
    url: str
    whisper_model: Optional[str] = None
    summary_backend: str = "genapi-gpt-4-1"
    with_timestamps: bool = True
    layout: str = "vertical_reels"
    download_mode: str = "audio"

@app.post("/twitch")
async def download_twitch(request: TwitchDownloadRequest):
    if not request.url:
        raise HTTPException(status_code=400, detail="Missing 'url' field")
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="yt_dlp Python package not installed. Install with 'pip install yt-dlp'.",
        )

    job = _create_job()

    def work() -> dict:
        video_id = int(time.time())
        video_path = VIDEO_DIR / f"download_{video_id}.mp4"
        job.log("Скачивание медиа...", progress=0, status="downloading")
        try:
            title = download_twitch_video(request.url, video_path, request.download_mode, job=job)
            # Санитизируем название видео
            safe_title = re.sub(r'[\\/*?:"<>| ]', "_", title)
            safe_title = re.sub(r'_+', '_', safe_title).strip('_')[:80]
            if not safe_title:
                safe_title = f"downloaded_video_{video_id}"
            
            pretty_path = VIDEO_DIR / f"{safe_title}_{video_id}.mp4"
            try:
                # Переименовываем скачанный файл в красивое имя
                video_path.rename(pretty_path)
                video_path = pretty_path
            except Exception:
                pass
        except Exception as e:
            raise RuntimeError(f"Скачивание yt_dlp завершилось с ошибкой: {e}") from e
        
        job.log("Скачивание завершено", progress=1)
        return process_media(
            video_path,
            whisper_model_id=request.whisper_model,
            summary_backend=request.summary_backend,
            with_timestamps=request.with_timestamps,
            layout=request.layout,
            job=job,
        )

    threading.Thread(target=_run_job, args=(job, work), daemon=True).start()
    return {"job_id": job.id}

class ManualCutRequest(BaseModel):
    video_name: str
    start_str: str
    end_str: str
    title: str
    layout: str = "vertical_reels"
    with_timestamps: bool = True

@app.post("/api/cut-manual")
async def cut_manual(request: ManualCutRequest):
    # Предотвращение directory traversal
    video_name = os.path.basename(request.video_name)
    video_path = VIDEO_DIR / video_name
    if not video_path.is_file():
        # Попробуем найти без расширения или поискать по названию
        stem = Path(video_name).stem
        candidates = list(VIDEO_DIR.glob(f"{stem}*"))
        if candidates:
            video_path = candidates[0]
        else:
            raise HTTPException(status_code=404, detail=f"Оригинальное видео не найдено в кэше: {video_name}")

    try:
        start_sec = parse_time_to_seconds(request.start_str)
        end_sec = parse_time_to_seconds(request.end_str)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат времени (используйте ЧЧ:ММ:СС или ММ:СС): {e}"
        )

    if end_sec <= start_sec:
        raise HTTPException(
            status_code=400,
            detail="Время окончания должно быть больше времени начала"
        )

    # Ищем SRT в output
    srt_name = f"{video_path.stem}_transcript.srt"
    srt_path = OUTPUT_DIR / srt_name
    clip_srt_path = None
    if request.with_timestamps and srt_path.is_file():
        full_srt_text = srt_path.read_text(encoding="utf-8")
        clip_subtitles = extract_subtitles_for_clip(full_srt_text, start_sec, end_sec)
        clip_srt_path = TMP_DIR / f"{video_path.stem}_manual_{int(time.time())}.srt"
        clip_srt_path.write_text(clip_subtitles, encoding="utf-8")

    clip_id = int(time.time())
    output_clip_path = OUTPUT_DIR / f"{video_path.stem}_manual_{clip_id}.mp4"

    try:
        cut_and_crop_video(
            video_path=video_path,
            start_sec=start_sec,
            end_sec=end_sec,
            clip_srt_path=clip_srt_path,
            output_clip_path=output_clip_path,
            ffmpeg_bin=_find_ffmpeg(),
            ffprobe_bin=_find_ffprobe(),
            layout=request.layout,
            use_gpu=USE_GPU
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при нарезке видео: {e}")

    return {
        "status": "ok",
        "clip": {
            "title": request.title or f"Ручной клип ({request.start_str} - {request.end_str})",
            "start_str": request.start_str,
            "end_str": request.end_str,
            "score": 100,
            "description": "Создан вручную пользователем",
            "filename": output_clip_path.name
        }
    }

@app.get("/download/{video_name}")
async def download_results(video_name: str):
    # Предотвращение directory traversal
    video_name = os.path.basename(video_name)
    
    files = [
        OUTPUT_DIR / f"{video_name}_transcript.txt",
        OUTPUT_DIR / f"{video_name}_transcript.srt",
        OUTPUT_DIR / f"{video_name}_summary.txt",
    ]
    # Добавляем все сгенерированные клипы
    for clip_path in OUTPUT_DIR.glob(f"{video_name}_clip_*.mp4"):
        files.append(clip_path)

    existing = [p for p in files if p.is_file()]
    if not existing:
        raise HTTPException(status_code=404, detail="Results not found.")

    zip_path = OUTPUT_DIR / f"{video_name}_results.zip"
    
    # Кроссплатформенная генерация архива на чистом Python
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for p in existing:
            zip_file.write(p, arcname=p.name)
            
    return FileResponse(zip_path, filename=zip_path.name)

@app.post("/api/clear-cache")
async def clear_cache():
    try:
        cleaned_size = 0
        # Очищаем папки videos/ и tmp/
        for directory in [VIDEO_DIR, TMP_DIR]:
            for item in directory.glob("*"):
                if item.is_file():
                    cleaned_size += item.stat().st_size
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                    
        # Очищаем сгенерированные файлы результатов в output/
        for item in OUTPUT_DIR.glob("*"):
            if item.is_file():
                cleaned_size += item.stat().st_size
                item.unlink()
                
        return {"status": "ok", "cleaned_mb": round(cleaned_size / 1_048_576, 2)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
