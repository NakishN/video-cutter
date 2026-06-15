import os
import json
import platform
import shutil
from pathlib import Path
from contextlib import contextmanager, nullcontext
from dotenv import load_dotenv

load_dotenv()

# APP_ROOT задаётся launcher.py при запуске как .exe (PyInstaller)
ROOT = Path(os.environ.get("APP_ROOT", Path(__file__).parent))

# Загружаем config.json: сначала ищем рядом с .exe, затем в ресурсах сборки
CONFIG_PATH = ROOT / "config.json"
if not CONFIG_PATH.is_file():
    CONFIG_PATH = Path(__file__).parent / "config.json"
if not CONFIG_PATH.is_file():
    raise RuntimeError("config.json not found. Please create it first.")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

# Монтируем папки на диске
VIDEO_DIR = ROOT / cfg.get("video_dir", "videos")
OUTPUT_DIR = ROOT / cfg.get("output_dir", "output")
TMP_DIR = ROOT / cfg.get("temp_dir", "tmp")
MODELS_DIR = ROOT / cfg.get("models_dir", "models")

# Создаем директории на диске, если их еще нет, чтобы избежать ошибок при монтировании StaticFiles
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

USE_GPU = cfg.get("use_gpu", False)
WHISPER_LANGUAGE = cfg.get("whisper_language", "ru")
GEN_API_KEY = os.getenv("GEN_API_KEY", "")
GENAPI_NETWORK_ID = cfg.get("genapi_network_id", "gemini-2-5-flash-lite")
SUMMARY_MODEL_PATH = ROOT / cfg.get(
    "summary_model_path", "gemma-4-12B-it-qat-q4_0-unquantized"
)

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

YTDLP_PROXY = os.getenv("YTDLP_PROXY")

@contextmanager
def _without_system_proxy():
    saved = {key: os.environ.pop(key) for key in _PROXY_ENV_KEYS if key in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)

def _find_ffmpeg() -> str:
    """ffmpeg: рядом с приложением → PATH → imageio-ffmpeg (Windows-бандл)."""
    ext = ".exe" if platform.system() == "Windows" else ""
    local = ROOT / f"ffmpeg{ext}"
    if local.is_file():
        return str(local)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return "ffmpeg"  # упадёт с понятной ошибкой

def _find_ffprobe() -> str:
    """ffprobe: рядом с приложением → PATH → рядом с imageio-ffmpeg."""
    ext = ".exe" if platform.system() == "Windows" else ""
    local = ROOT / f"ffprobe{ext}"
    if local.is_file():
        return str(local)
    found = shutil.which("ffprobe")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe_path = Path(ffmpeg_path).with_name(f"ffprobe{ext}")
        if ffprobe_path.is_file():
            return str(ffprobe_path)
    except Exception:
        pass
    return "ffprobe"
