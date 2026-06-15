import re
import platform
import subprocess
from pathlib import Path
from typing import Optional, Union
from config import ROOT, USE_GPU, WHISPER_LANGUAGE, TMP_DIR, MODELS_DIR, cfg, _find_ffmpeg, _find_ffprobe
from jobs import Job
from time_utils import _fmt_srt_time, _fmt_timestamp

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}

def _probe_duration(media_path: Path) -> Optional[float]:
    cmd = [
        _find_ffprobe(), "-v", "error",
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
        _find_ffmpeg(), "-y", "-i", str(media_path),
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
    stderr_log = []
    for line in proc.stderr:
        stderr_log.append(line)
        if not job or not duration:
            continue
        match = time_re.search(line)
        if not match:
            continue
        h, m, s = match.groups()
        seconds = int(h) * 3600 + int(m) * 60 + float(s)
        pct = min(99, int(seconds / duration * 100))
        job.log(f"Извлечение аудио: {pct}%", progress=1 + int(pct * 0.04))

    rc = proc.wait()
    if rc != 0:
        err_msg = "".join(stderr_log[-30:])
        raise RuntimeError(f"ffmpeg audio extraction failed with exit code {rc}. Stderr:\n{err_msg}")
    if job:
        job.log("Аудио готово", progress=5)
    return audio_path

def run_whisper_faster(
    video_path: Path,
    model_name: str = "medium",
    *,
    with_timestamps: bool = True,
    job: Optional[Job] = None,
) -> tuple[str, str]:
    """Транскрипция через faster-whisper (pip-пакет, без бинарника)."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        raise RuntimeError(
            "Установите faster-whisper: pip install faster-whisper"
        )

    if job:
        job.log(
            f"Загрузка модели Whisper '{model_name}' "
            "(первый раз: авто-загрузка ~1.5 ГБ)…",
            progress=2, status="transcribing",
        )

    if USE_GPU:
        try:
            fw_model = WhisperModel(model_name, device="cuda", compute_type="float16")
            if job:
                job.log("Whisper инициализирован на GPU (CUDA).")
        except Exception as e:
            if job:
                job.log(f"Не удалось запустить Whisper на GPU: {e}. Переключаемся на CPU.")
            fw_model = WhisperModel(model_name, device="cpu", compute_type="int8")
    else:
        fw_model = WhisperModel(model_name, device="cpu", compute_type="int8")

    audio_path = extract_audio(video_path, job=job)
    duration = _probe_duration(audio_path)

    if job:
        job.log("Транскрипция (faster-whisper)…", progress=10, status="transcribing")

    lang = WHISPER_LANGUAGE if WHISPER_LANGUAGE.lower() != "auto" else None
    segments_gen, _info = fw_model.transcribe(
        str(audio_path), language=lang, beam_size=1, vad_filter=True,
    )

    transcript_parts: list[str] = []
    srt_parts: list[str] = []
    idx = 0
    for segment in segments_gen:
        text = segment.text.strip()
        if not text:
            continue
        idx += 1
        transcript_parts.append(text)
        if with_timestamps:
            srt_parts.append(
                f"{idx}\n"
                f"{_fmt_srt_time(segment.start)} --> {_fmt_srt_time(segment.end)}\n"
                f"{text}\n"
            )
        if job and idx % 10 == 0:
            if duration and duration > 0:
                pct = min(89, 10 + int((segment.start / duration) * 80))
            else:
                pct = min(89, 10 + idx // 3)
            job.log(f"[{_fmt_timestamp(segment.start)}] {text[:80]}", progress=pct)

    if job:
        job.log("Транскрипция завершена", progress=90)
    return "\n".join(transcript_parts), "\n".join(srt_parts)

def run_whisper(
    video_path: Path,
    whisper_model: Union[Path, str],
    *,
    with_timestamps: bool = True,
    job: Optional[Job] = None,
) -> tuple[str, str]:
    if isinstance(whisper_model, str):
        return run_whisper_faster(video_path, whisper_model, with_timestamps=with_timestamps, job=job)

    _ext = ".exe" if platform.system() == "Windows" else ""
    _cuda_name = f"whisper-cuda{_ext}"
    _plain_name = f"whisper{_ext}"
    
    use_cuda = USE_GPU and (ROOT / _cuda_name).is_file()
    whisper_bin = ROOT / (_cuda_name if use_cuda else _plain_name)
    
    if not whisper_bin.is_file():
        # Бинарник не найден — используем faster-whisper (pip-пакет)
        model_name = whisper_model.stem.removeprefix("ggml-") if whisper_model else "medium"
        return run_whisper_faster(
            video_path, model_name,
            with_timestamps=with_timestamps, job=job,
        )

    if not whisper_model.is_file() or whisper_model.stat().st_size < 1_000_000:
        raise RuntimeError(f"Модель Whisper не найдена или повреждена: {whisper_model}")

    audio_path = extract_audio(video_path, job=job)
    
    def _execute_bin(bin_path: Path, gpu_enabled: bool) -> tuple[str, str]:
        cmd = [
            str(bin_path), "-m", str(whisper_model), "-f", str(audio_path),
            "-otxt", "-pp", "-l", WHISPER_LANGUAGE,
        ]
        if with_timestamps:
            cmd.append("-osrt")
        if not gpu_enabled:
            cmd.append("-ng")

        gpu_label = "GPU" if gpu_enabled else "CPU"
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
            raise RuntimeError(f"Бинарник Whisper ({gpu_label}) завершился с ошибкой")

        txt_path = Path(f"{audio_path}.txt")
        if not txt_path.is_file():
            raise RuntimeError("Файл транскрипции не был создан бинарником.")
        transcript = txt_path.read_text(encoding="utf-8")

        srt_path = Path(f"{audio_path}.srt")
        transcript_srt = srt_path.read_text(encoding="utf-8") if srt_path.is_file() else ""
        return transcript, transcript_srt

    try:
        return _execute_bin(whisper_bin, use_cuda)
    except Exception as e:
        if use_cuda:
            plain_bin = ROOT / _plain_name
            if plain_bin.is_file():
                if job:
                    job.log(f"Ошибка GPU транскрипции: {e}. Пробуем CPU версию…")
                try:
                    return _execute_bin(plain_bin, False)
                except Exception as cpu_err:
                    raise RuntimeError(f"Транскрипция не удалась на GPU и CPU: {cpu_err}") from cpu_err
        raise e

def list_whisper_models() -> list[dict]:
    models = []
    for fw in ["tiny", "base", "small", "medium", "large-v2", "large-v3"]:
        models.append({"id": fw, "label": f"faster-whisper: {fw}", "size_mb": 0})
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

def resolve_whisper_model(model_id: Optional[str]) -> Union[Path, str]:
    fw_models = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
    if model_id in fw_models:
        return model_id

    models = {path.stem.removeprefix("ggml-"): path for path in MODELS_DIR.glob("ggml-*.bin") if path.stat().st_size > 1_000_000}
    
    if model_id and model_id in models:
        return models[model_id]
        
    fallback = ROOT / cfg.get("whisper_model_path", "models/ggml-medium.bin")
    if fallback.is_file() and fallback.stat().st_size > 1_000_000:
        return fallback
        
    if "medium" in models:
        return models["medium"]
    if models:
        return next(iter(models.values()))
    
    # Fallback default
    return "medium"
