# -*- mode: python ; coding: utf-8 -*-
# video_cutter.spec — PyInstaller spec для сборки Windows .exe
#
# Запуск сборки:
#   pip install pyinstaller
#   pyinstaller video_cutter.spec --clean

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Собираем скрытые подмодули uvicorn и fastapi
hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + collect_submodules("starlette")
    + collect_submodules("anyio")
    + collect_submodules("httpx")
    + collect_submodules("yt_dlp")
    + collect_submodules("faster_whisper")
    + collect_submodules("ctranslate2")
    + [
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "dotenv",
        "email.mime.text",
        "email.mime.multipart",
        "traceback",
        "platform",
        "multipart",
        "typing_extensions",
        "onnxruntime",
        "tokenizers",
        "huggingface_hub",
    ]
)

collected_datas = (
    collect_data_files("faster_whisper")
    + collect_data_files("ctranslate2")
    + collect_data_files("tokenizers")
    + collect_data_files("huggingface_hub")
    + collect_data_files("cv2")
)

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[
        # UI
        ("index.html", "."),
        ("styles.css", "."),
        ("config.json", "."),
        ("static", "static"),
        # Python-модули проекта (нужны uvicorn при поиске 'server:app')
        ("server.py", "."),
        ("genapi_client.py", "."),
        ("transcript_utils.py", "."),
        ("video_utils.py", "."),
        # .env.example — подсказка пользователю
        (".env.example", "."),
    ] + collected_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "transformers", "tensorflow", "PIL"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # файлы данных — в папке рядом с .exe
    name="VideoCutter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,                   # консоль видна — пользователь видит прогресс
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,                      # можно заменить на путь к .ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VideoCutter",           # имя папки с dist/
)
