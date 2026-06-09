import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from genapi_client import summarize as genapi_summarize

load_dotenv()

_PROXY_ENV_KEYS = (
    "ALL_PROXY", "all_proxy",
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "SOCKS_PROXY", "socks_proxy",
    "SOCKS5_PROXY", "socks5_proxy",
)


def _normalize_proxy_env() -> None:
    """socks:// без версии ломает pip, httpx и yt-dlp — заменяем на socks5://."""
    for key in _PROXY_ENV_KEYS:
        value = os.environ.get(key)
        if value and value.lower().startswith("socks://"):
            os.environ[key] = "socks5://" + value[8:]


_normalize_proxy_env()

YTDLP_PROXY = os.getenv("YTDLP_PROXY")  # direct / none = без прокси; URL = явный прокси; не задан = из окружения


@contextmanager
def _without_system_proxy():
    saved = {key: os.environ.pop(key) for key in _PROXY_ENV_KEYS if key in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _build_yt_dlp_opts(outtmpl: str) -> dict:
    opts: dict = {"outtmpl": outtmpl, "format": "best"}
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


def download_twitch_video(url: str, video_path: Path, job: Optional["Job"] = None) -> None:
    """Скачивает VOD с Twitch; при мёртвом прокси в окружении пробует без него."""
    from yt_dlp import YoutubeDL

    outtmpl = str(video_path)
    opts = _build_yt_dlp_opts(outtmpl)
    force_direct = YTDLP_PROXY is not None and opts.get("proxy") == ""

    def _run(use_direct: bool) -> None:
        run_opts = dict(opts)
        if use_direct:
            run_opts["proxy"] = ""
        ctx = _without_system_proxy() if use_direct else nullcontext()
        with ctx:
            with YoutubeDL(run_opts) as ydl:
                ydl.download([url])

    try:
        if force_direct:
            if job:
                job.log("Скачивание с Twitch (без прокси)…")
            _run(use_direct=True)
            return
        _run(use_direct=False)
    except Exception as first_error:
        if not _is_proxy_connection_error(first_error):
            raise RuntimeError(_strip_ansi(str(first_error))) from first_error
        if job:
            job.log("Прокси недоступен, повтор без прокси…")
        try:
            _run(use_direct=True)
        except Exception as second_error:
            raise RuntimeError(
                "Не удалось скачать с Twitch. Прокси в системе недоступен "
                f"(127.0.0.1: Connection refused). Запустите VPN/Clash или добавьте в .env:\n"
                "YTDLP_PROXY=direct — скачивать без прокси\n"
                "YTDLP_PROXY=socks5://127.0.0.1:10808 — явный адрес прокси\n\n"
                f"Ошибка: {_strip_ansi(str(second_error))}"
            ) from second_error


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

CONFIG_PATH = Path(__file__).parent / "config.json"
if not CONFIG_PATH.is_file():
    raise RuntimeError("config.json not found. Please create it first.")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

# APP_ROOT задаётся launcher.py при запуске как .exe (PyInstaller)
ROOT = Path(os.environ.get("APP_ROOT", Path(__file__).parent))
VIDEO_DIR = ROOT / cfg.get("video_dir", "videos")
OUTPUT_DIR = ROOT / cfg.get("output_dir", "output")
TMP_DIR = ROOT / cfg.get("temp_dir", "tmp")
MODELS_DIR = ROOT / cfg.get("models_dir", "models")
USE_GPU = cfg.get("use_gpu", False)
WHISPER_LANGUAGE = cfg.get("whisper_language", "ru")
GEN_API_KEY = os.getenv("GEN_API_KEY", "")
GENAPI_NETWORK_ID = cfg.get("genapi_network_id", "gemini-2-5-flash-lite")
SUMMARY_MODEL_PATH = ROOT / cfg.get(
    "summary_model_path", "gemma-4-12B-it-qat-q4_0-unquantized"
)
AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}

_gemma_tokenizer = None
_gemma_model = None

_jobs: dict[str, "Job"] = {}
_jobs_lock = threading.Lock()


@dataclass
class Job:
    id: str
    status: str = "queued"
    progress: int = 0
    message: str = "В очереди…"
    log_lines: list[str] = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None

    def log(self, line: str, *, progress: Optional[int] = None, status: Optional[str] = None) -> None:
        line = line.strip()
        if not line:
            return
        with _jobs_lock:
            self.log_lines.append(line)
            if len(self.log_lines) > 120:
                self.log_lines = self.log_lines[-120:]
            self.message = line if len(line) < 200 else line[:197] + "…"
            if progress is not None:
                self.progress = max(0, min(100, progress))
            if status is not None:
                self.status = status

    def to_dict(self) -> dict:
        with _jobs_lock:
            return {
                "id": self.id,
                "status": self.status,
                "progress": self.progress,
                "message": self.message,
                "log_lines": list(self.log_lines[-30:]),
                "result": self.result,
                "error": self.error,
            }


def _create_job() -> Job:
    job = Job(id=uuid.uuid4().hex[:12])
    with _jobs_lock:
        _jobs[job.id] = job
    return job


def _get_job(job_id: str) -> Job:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return job


VIDEO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)


def list_whisper_models() -> list[dict]:
    models = []
    for path in sorted(MODELS_DIR.glob("ggml-*.bin")):
        if path.stat().st_size < 1_000_000:
            continue
        model_id = path.stem.removeprefix("ggml-")
        models.append(
            {
                "id": model_id,
                "label": model_id,
                "size_mb": round(path.stat().st_size / 1_048_576),
            }
        )
    return models


def resolve_whisper_model(model_id: Optional[str]) -> Path:
    models = {m["id"]: MODELS_DIR / f"ggml-{m['id']}.bin" for m in list_whisper_models()}
    if not models:
        fallback = ROOT / cfg.get("whisper_model_path", "models/ggml-medium.bin")
        if fallback.is_file() and fallback.stat().st_size > 1_000_000:
            return fallback
        raise RuntimeError("Нет доступных моделей Whisper в папке models/")
    if model_id and model_id in models:
        return models[model_id]
    if "medium" in models:
        return models["medium"]
    return next(iter(models.values()))


GENAPI_MODELS: dict[str, tuple[str, str]] = {
    "genapi-gpt-4-1": ("GPT-4.1", "gpt-4-1"),
    "genapi-gemini": ("Gemini Flash-Lite", "gemini-2-5-flash-lite"),
}
# обратная совместимость: старый id «genapi» → модель из config
GENAPI_LEGACY_ID = "genapi"


def _resolve_genapi_network(backend: str) -> str | None:
    if backend in GENAPI_MODELS:
        return GENAPI_MODELS[backend][1]
    if backend == GENAPI_LEGACY_ID:
        return GENAPI_NETWORK_ID
    return None


def list_summary_backends() -> list[dict]:
    backends = [
        {"id": "none", "label": "Только транскрипция (без резюме)"},
    ]
    if GEN_API_KEY:
        for backend_id, (label, _network) in GENAPI_MODELS.items():
            backends.append({"id": backend_id, "label": f"Облако: {label} (GenAPI)"})
    # Локальная Gemma убрана — используем только облачный GenAPI
    return backends


def _default_summary_backend() -> str:
    if not GEN_API_KEY:
        return "none"
    for backend_id, (_label, network) in GENAPI_MODELS.items():
        if network == GENAPI_NETWORK_ID:
            return backend_id
    return next(iter(GENAPI_MODELS))


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTMLResponse((ROOT / "index.html").read_text(encoding="utf-8"))


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


def _probe_duration(media_path: Path) -> Optional[float]:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def extract_audio(media_path: Path, job: Optional[Job] = None) -> Path:
    if media_path.suffix.lower() in AUDIO_EXTENSIONS:
        return media_path

    audio_path = TMP_DIR / f"{media_path.stem}.wav"
    duration = _probe_duration(media_path)
    cmd = [
        "ffmpeg", "-y", "-i", str(media_path),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(audio_path),
    ]
    if job:
        job.log("Извлечение аудио из видео…", progress=1, status="extracting_audio")

    proc = subprocess.Popen(
        cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, bufsize=1,
    )
    time_re = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
    assert proc.stderr is not None
    for line in proc.stderr:
        if not job or not duration:
            continue
        match = time_re.search(line)
        if not match:
            continue
        h, m, s = match.groups()
        seconds = int(h) * 3600 + int(m) * 60 + float(s)
        pct = min(99, int(seconds / duration * 100))
        job.log(f"Извлечение аудио: {pct}%", progress=1 + int(pct * 0.04))

    if proc.wait() != 0:
        raise RuntimeError("ffmpeg audio extraction failed")
    if job:
        job.log("Аудио готово", progress=5)
    return audio_path


def run_whisper(
    video_path: Path,
    whisper_model: Path,
    *,
    with_timestamps: bool = True,
    job: Optional[Job] = None,
) -> tuple[str, str]:
    import platform as _platform
    _ext = ".exe" if _platform.system() == "Windows" else ""
    _cuda_name = f"whisper-cuda{_ext}"
    _plain_name = f"whisper{_ext}"
    whisper_bin = ROOT / (_cuda_name if USE_GPU and (ROOT / _cuda_name).is_file() else _plain_name)
    if not whisper_bin.is_file():
        text = "[Whisper binary missing – transcription unavailable]"
        return text, ""

    if not whisper_model.is_file() or whisper_model.stat().st_size < 1_000_000:
        raise RuntimeError(f"Модель Whisper не найдена или повреждена: {whisper_model}")

    audio_path = extract_audio(video_path, job=job)
    cmd = [
        str(whisper_bin), "-m", str(whisper_model), "-f", str(audio_path),
        "-otxt", "-pp", "-l", WHISPER_LANGUAGE,
    ]
    if with_timestamps:
        cmd.append("-osrt")
    if not USE_GPU:
        cmd.append("-ng")

    gpu_label = "GPU" if USE_GPU else "CPU"
    if job:
        job.log(
            f"Транскрипция Whisper ({whisper_model.stem.removeprefix('ggml-')}, "
            f"{WHISPER_LANGUAGE}, {gpu_label})…",
            progress=6,
            status="transcribing",
        )

    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    progress_re = re.compile(r"progress\s*=\s*(\d+)%")
    assert proc.stderr is not None
    for line in proc.stderr:
        line = line.rstrip()
        if not line:
            continue
        pct_match = progress_re.search(line)
        if pct_match and job:
            pct = int(pct_match.group(1))
            job.log(f"Транскрипция: {pct}%", progress=5 + int(pct * 0.84))
        elif line.startswith("[") and job:
            job.log(line)
        elif "processing" in line.lower() and job:
            job.log(line, progress=7)

    if proc.wait() != 0:
        raise RuntimeError("Whisper failed")

    txt_path = Path(f"{audio_path}.txt")
    if not txt_path.is_file():
        raise RuntimeError("Transcription file not generated.")
    transcript = txt_path.read_text(encoding="utf-8")

    srt_path = Path(f"{audio_path}.srt")
    transcript_srt = srt_path.read_text(encoding="utf-8") if srt_path.is_file() else ""
    return transcript, transcript_srt


def _load_local_gemma():
    global _gemma_tokenizer, _gemma_model
    if _gemma_model is not None and _gemma_tokenizer is not None:
        return
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    repo = SUMMARY_MODEL_PATH if SUMMARY_MODEL_PATH.is_dir() else SUMMARY_MODEL_PATH.parent
    _gemma_tokenizer = AutoTokenizer.from_pretrained(
        str(repo), trust_remote_code=True, use_fast=True,
    )
    _gemma_model = AutoModelForCausalLM.from_pretrained(
        str(repo),
        device_map="auto",
        dtype=torch.float16,
        trust_remote_code=True,
    )


def run_summary(
    transcript: str,
    backend: str,
    *,
    transcript_srt: str = "",
    job: Optional[Job] = None,
) -> str:
    if backend == "none":
        return ""

    network_id = _resolve_genapi_network(backend)
    if network_id:
        if not GEN_API_KEY:
            raise RuntimeError("GenAPI не настроен. Добавьте GEN_API_KEY в файл .env")
        model_label = GENAPI_MODELS.get(backend, (network_id, network_id))[0]
        if job:
            job.log(
                f"Анализ интересных моментов через {model_label} (GenAPI)…",
                progress=92,
                status="summarizing",
            )
        text = genapi_summarize(
            transcript, GEN_API_KEY, network_id, transcript_srt=transcript_srt,
        )
        if job:
            job.log("Резюме готово", progress=99)
        return text

    if backend == "local":
        if job:
            job.log("Загрузка локальной Gemma…", progress=92, status="summarizing")
        _load_local_gemma()
        if job:
            job.log("Генерация резюме…", progress=95)
        inputs = _gemma_tokenizer(transcript, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(_gemma_model.device) for k, v in inputs.items()}
        output_ids = _gemma_model.generate(**inputs, max_new_tokens=200, do_sample=False)
        return _gemma_tokenizer.decode(output_ids[0], skip_special_tokens=True)

    raise RuntimeError(f"Неизвестный режим резюме: {backend}")


def save_results(stem: str, transcript: str, transcript_srt: str, summary: str) -> None:
    (OUTPUT_DIR / f"{stem}_transcript.txt").write_text(transcript, encoding="utf-8")
    if transcript_srt:
        (OUTPUT_DIR / f"{stem}_transcript.srt").write_text(transcript_srt, encoding="utf-8")
    if summary:
        (OUTPUT_DIR / f"{stem}_summary.txt").write_text(summary, encoding="utf-8")


def process_media(
    media_path: Path,
    *,
    whisper_model_id: Optional[str],
    summary_backend: str,
    with_timestamps: bool,
    job: Optional[Job] = None,
) -> dict:
    if _resolve_genapi_network(summary_backend) and not GEN_API_KEY:
        raise RuntimeError("GenAPI не настроен. Добавьте GEN_API_KEY в файл .env")

    whisper_model = resolve_whisper_model(whisper_model_id)
    transcript, transcript_srt = run_whisper(
        media_path, whisper_model, with_timestamps=with_timestamps, job=job,
    )
    if job:
        job.log("Транскрипция завершена", progress=90)
    summary = run_summary(
        transcript, summary_backend, transcript_srt=transcript_srt, job=job,
    )
    save_results(media_path.stem, transcript, transcript_srt, summary)

    return {
        "filename": media_path.name,
        "transcript": transcript,
        "transcript_srt": transcript_srt,
        "summary": summary,
        "whisper_model": whisper_model.stem.removeprefix("ggml-"),
        "summary_backend": summary_backend,
    }


def _run_job(
    job: Job,
    work: Callable[[], dict],
) -> None:
    try:
        result = work()
        with _jobs_lock:
            job.result = result
            job.status = "done"
            job.progress = 100
            job.message = "Готово"
    except Exception as e:
        with _jobs_lock:
            job.status = "error"
            job.error = str(e)
            job.message = f"Ошибка: {e}"


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    return _get_job(job_id).to_dict()


@app.post("/process")
async def process_video(
    file: UploadFile = File(...),
    whisper_model: Optional[str] = Form(None),
    summary_backend: str = Form("genapi-gpt-4-1"),
    with_timestamps: bool = Form(True),
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
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class TwitchDownloadRequest(BaseModel):
    url: str
    whisper_model: Optional[str] = None
    summary_backend: str = "genapi-gpt-4-1"
    with_timestamps: bool = True


@app.post("/twitch")
async def download_twitch(request: TwitchDownloadRequest):
    if not request.url:
        raise HTTPException(status_code=400, detail="Missing 'url' field")
    try:
        import yt_dlp  # noqa: F401 — проверка, что пакет установлен
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="yt_dlp Python package not installed. Install with 'pip install yt-dlp'.",
        )

    job = _create_job()

    def work() -> dict:
        video_path = VIDEO_DIR / f"twitch_video_{int(time.time())}.mp4"
        job.log("Скачивание с Twitch…", progress=0, status="downloading")
        try:
            download_twitch_video(request.url, video_path, job=job)
        except Exception as e:
            raise RuntimeError(f"yt_dlp download failed: {e}") from e
        job.log("Скачивание завершено", progress=1)
        return process_media(
            video_path,
            whisper_model_id=request.whisper_model,
            summary_backend=request.summary_backend,
            with_timestamps=request.with_timestamps,
            job=job,
        )

    threading.Thread(target=_run_job, args=(job, work), daemon=True).start()
    return {"job_id": job.id}


@app.get("/download/{video_name}")
async def download_results(video_name: str):
    files = [
        OUTPUT_DIR / f"{video_name}_transcript.txt",
        OUTPUT_DIR / f"{video_name}_transcript.srt",
        OUTPUT_DIR / f"{video_name}_summary.txt",
    ]
    existing = [p for p in files if p.is_file()]
    if not existing:
        raise HTTPException(status_code=404, detail="Results not found.")

    zip_path = OUTPUT_DIR / f"{video_name}_results.zip"
    subprocess.run(["zip", "-j", str(zip_path), *[str(p) for p in existing]], check=True)
    return FileResponse(zip_path, filename=zip_path.name)
