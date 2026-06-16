import os
import json
import platform
import shutil
from pathlib import Path
from contextlib import contextmanager, nullcontext
from dotenv import load_dotenv

# Добавляем пути к CUDA DLL на Windows для корректной работы faster-whisper/ctranslate2 на GPU
if platform.system() == "Windows":
    import sys
    import site
    
    site_folders = [Path(sys.prefix) / "Lib" / "site-packages"]
    try:
        for p in site.getsitepackages():
            site_folders.append(Path(p))
    except Exception:
        pass
    try:
        site_folders.append(Path(site.getusersitepackages()))
    except Exception:
        pass
        
    for sf in site_folders:
        nvidia_dir = sf / "nvidia"
        if nvidia_dir.is_dir():
            for p in nvidia_dir.glob("**/bin"):
                if p.is_dir():
                    dll_dir_str = str(p.resolve())
                    try:
                        os.add_dll_directory(dll_dir_str)
                    except Exception:
                        pass
                    os.environ["PATH"] = dll_dir_str + os.pathsep + os.environ.get("PATH", "")
                    
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        cuda_bin = Path(cuda_path) / "bin"
        if cuda_bin.is_dir():
            cuda_bin_str = str(cuda_bin.resolve())
            try:
                os.add_dll_directory(cuda_bin_str)
            except Exception:
                pass
            os.environ["PATH"] = cuda_bin_str + os.pathsep + os.environ.get("PATH", "")
            
    default_cuda_root = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
    if default_cuda_root.is_dir():
        for version_dir in default_cuda_root.glob("v*"):
            cuda_bin = version_dir / "bin"
            if cuda_bin.is_dir():
                cuda_bin_str = str(cuda_bin.resolve())
                try:
                    os.add_dll_directory(cuda_bin_str)
                except Exception:
                    pass
                os.environ["PATH"] = cuda_bin_str + os.pathsep + os.environ.get("PATH", "")

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

import tempfile
tempfile.tempdir = str(TMP_DIR.resolve())


# Проверяем доступность GPU (CUDA) и наличие необходимых библиотек (DLL/.so)
USE_GPU = False
if cfg.get("use_gpu", False):
    try:
        import ctranslate2
        # get_cuda_device_count() вернет > 0, если CUDA доступна и все необходимые библиотеки (cublas, cudnn) успешно загружены.
        if ctranslate2.get_cuda_device_count() > 0:
            USE_GPU = True
        else:
            print("[INFO] CUDA-совместимые устройства не обнаружены. GPU-режим отключен, используется CPU.")
    except Exception as e:
        print(f"[WARNING] Не удалось инициализировать CUDA: {e}. GPU-режим отключен, используется автоматический откат на CPU.")
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
