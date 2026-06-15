@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================
echo   Нарезчик видео — Установка зависимостей для Windows
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: ── 1. Проверка Python ───────────────────────────────────────
python --version >nul 2>&1
if not errorlevel 1 goto python_ok
echo [ОШИБКА] Python не найден.
echo Скачайте Python 3.11+ с https://python.org и установите с галочкой "Add to PATH".
pause & exit /b 1

:python_ok
echo [OK] Python найден.

:: ── 2. Виртуальное окружение и Python-зависимости ───────────
if exist "venv" goto venv_ok
echo [1/4] Создание виртуального окружения...
python -m venv venv

:venv_ok
echo [1/4] Установка Python-зависимостей...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt pyinstaller
echo     OK

:: ── 3. ffmpeg ────────────────────────────────────────────────
if exist "ffmpeg.exe" goto ffmpeg_exists
echo [2/4] Загрузка ffmpeg...
powershell -NoProfile -Command ^
    "$url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';" ^
    "Invoke-WebRequest $url -OutFile ffmpeg_tmp.zip -UseBasicParsing"
if errorlevel 1 goto ffmpeg_download_fail

powershell -NoProfile -Command ^
    "Expand-Archive ffmpeg_tmp.zip ffmpeg_tmp -Force;" ^
    "$exe = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1;" ^
    "Copy-Item $exe.FullName ffmpeg.exe;" ^
    "$ffprobe = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffprobe.exe | Select-Object -First 1;" ^
    "if ($ffprobe) { Copy-Item $ffprobe.FullName ffprobe.exe }" ^
    "Remove-Item ffmpeg_tmp,ffmpeg_tmp.zip -Recurse -Force"
echo     ffmpeg.exe — OK
goto ffmpeg_done

:ffmpeg_download_fail
echo [ОШИБКА] Не удалось скачать ffmpeg. Скачайте вручную с https://ffmpeg.org/download.html
echo          и положите ffmpeg.exe в папку проекта.
goto ffmpeg_done

:ffmpeg_exists
echo [2/4] ffmpeg.exe уже есть — пропускаем.

:ffmpeg_done


:: ── 4. Whisper.cpp (CPU, Windows x64) ───────────────────────
if exist "whisper.exe" goto whisper_exists
echo [3/4] Загрузка whisper.exe (whisper.cpp, CPU-версия)...
powershell -NoProfile -Command ^
    "$url = 'https://github.com/ggml-org/whisper.cpp/releases/download/v1.7.5/whisper-blas-bin-x64.zip';" ^
    "Invoke-WebRequest $url -OutFile whisper_tmp.zip -UseBasicParsing"
if errorlevel 1 goto whisper_download_fail

powershell -NoProfile -Command ^
    "Expand-Archive whisper_tmp.zip whisper_tmp -Force;" ^
    "$exe = Get-ChildItem whisper_tmp -Recurse -Filter 'main.exe' | Select-Object -First 1;" ^
    "if (!$exe) { $exe = Get-ChildItem whisper_tmp -Recurse -Filter 'whisper*.exe' | Select-Object -First 1 };" ^
    "Copy-Item $exe.FullName whisper.exe;" ^
    "Remove-Item whisper_tmp,whisper_tmp.zip -Recurse -Force"
echo     whisper.exe — OK
goto whisper_done

:whisper_download_fail
echo [ОШИБКА] Не удалось скачать whisper.exe.
echo          Скачайте вручную с https://github.com/ggml-org/whisper.cpp/releases
echo          и положите whisper.exe в папку проекта.
goto whisper_done

:whisper_exists
echo [3/4] whisper.exe уже есть — пропускаем.

:whisper_done


:: ── 5. Модель Whisper medium ─────────────────────────────────
if exist "models\ggml-medium.bin" goto model_exists
echo [4/4] Загрузка модели Whisper medium (~1.5 GB)...
if not exist "models" mkdir models
powershell -NoProfile -Command ^
    "$url = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin';" ^
    "Invoke-WebRequest $url -OutFile models\ggml-medium.bin -UseBasicParsing"
if errorlevel 1 goto model_download_fail
echo     ggml-medium.bin — OK
goto model_done

:model_download_fail
echo [ОШИБКА] Не удалось скачать модель. Скачайте вручную:
echo          https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
echo          и положите в папку models\
goto model_done

:model_exists
echo [4/4] models\ggml-medium.bin уже есть — пропускаем.

:model_done


:: ── 6. .env ──────────────────────────────────────────────────
if exist ".env" goto env_done
echo.
echo [!] Создайте файл .env рядом с программой:
echo     GEN_API_KEY=sk-ваш-ключ-с-gen-api.ru
copy .env.example .env >nul 2>&1
echo     Файл .env создан из шаблона — откройте его и вставьте ключ.

:env_done

echo.
echo ============================================================
echo   Готово! Теперь запустите: build_windows.bat
echo   (чтобы собрать .exe) или просто: python launcher.py
echo ============================================================
pause
