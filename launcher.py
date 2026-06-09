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
    import uvicorn
    from server import app  # noqa: импорт после смены CWD/PATH

    threading.Thread(target=_open_browser, daemon=True).start()

    print("=" * 55)
    print("  Нарезчик видео запущен: http://127.0.0.1:8000")
    print("  Закройте это окно, чтобы остановить сервер.")
    print("=" * 55)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
