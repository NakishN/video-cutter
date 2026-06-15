"""
launcher.py — точка входа для Windows .exe (PyInstaller).
Устанавливает APP_ROOT, запускает uvicorn и открывает браузер.
"""
import os
import sys
import threading
import time
import webbrowser


def _get_base_dir() -> str:
    """Папка рядом с .exe (или папка скрипта при запуске из исходников)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()

# Меняем CWD — server.py открывает файлы по относительным путям
os.chdir(BASE_DIR)

# Сообщаем серверу, где лежат данные (videos/, models/, output/ и т.д.)
os.environ.setdefault("APP_ROOT", BASE_DIR)

# При сборке PyInstaller добавляет распакованные модули в sys._MEIPASS
if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)


def _open_browser() -> None:
    """Открываем браузер после небольшой паузы (пока стартует uvicorn)."""
    time.sleep(2.5)
    webbrowser.open("http://127.0.0.1:8000")


def main() -> None:
    import traceback
    import platform
    import sys

    try:
        import uvicorn
        from server import app  # noqa: импорт после смены CWD/PATH

        threading.Thread(target=_open_browser, daemon=True).start()

        print("=" * 55)
        print("  Video Cutter is running: http://127.0.0.1:8000")
        print("  Close this window to stop the server.")
        print("=" * 55)

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",
        )
    except Exception as e:
        crash_id = int(time.time())
        report_file = os.path.join(BASE_DIR, f"crash_report_{crash_id}.txt")
        
        # Gather file status
        files_to_check = ["ffmpeg.exe", "ffprobe.exe", "whisper.exe", "models/ggml-medium.bin"]
        files_status = {}
        for f in files_to_check:
            p = os.path.join(BASE_DIR, f)
            exists = os.path.exists(p)
            size = os.path.getsize(p) if exists else 0
            files_status[f] = f"EXISTS ({size} bytes)" if exists else "MISSING"

        # Check CUDA
        has_cuda = False
        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except Exception:
            pass

        # Mask API key
        api_key = os.environ.get("GEN_API_KEY", "")
        masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else ("SET" if api_key else "NOT_SET")

        try:
            with open(report_file, "w", encoding="utf-8") as rf:
                rf.write("============================================================\n")
                rf.write("                  VIDEO CUTTER CRASH REPORT                 \n")
                rf.write("============================================================\n")
                rf.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                rf.write(f"Crash ID: {crash_id}\n\n")
                
                rf.write("--- SYSTEM INFO ---\n")
                rf.write(f"OS: {platform.system()} {platform.release()} ({platform.version()})\n")
                rf.write(f"Python: {sys.version}\n")
                rf.write(f"Executable: {sys.executable}\n")
                rf.write(f"App Root: {BASE_DIR}\n")
                rf.write(f"CUDA Available: {has_cuda}\n\n")
                
                rf.write("--- ENVIRONMENT ---\n")
                rf.write(f"GEN_API_KEY: {masked_key}\n")
                rf.write(f"APP_ROOT: {os.environ.get('APP_ROOT', 'NOT_SET')}\n\n")
                
                rf.write("--- CRITICAL FILES ---\n")
                for filename, status in files_status.items():
                    rf.write(f"{filename}: {status}\n")
                rf.write("\n")
                
                rf.write("--- TRACEBACK ---\n")
                rf.write(traceback.format_exc())
                rf.write("\n============================================================\n")
        except Exception as log_err:
            print(f"Failed to write crash report to file: {log_err}")

        print("\n" + "!" * 55)
        print("  CRITICAL ERROR: The application has crashed!")
        print(f"  A crash report has been saved to:")
        print(f"  {report_file}")
        print("!" * 55)
        print("\nTraceback summary:")
        print(traceback.format_exc())
        
        print("\nPress Enter to exit...")
        input()
        sys.exit(1)


if __name__ == "__main__":
    main()
