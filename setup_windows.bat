@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo   Video Cutter - Installer for Windows
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: -- 1. Check Python --
python --version >nul 2>&1
if not errorlevel 1 goto python_ok
echo [ERROR] Python not found.
echo Please download Python 3.11+ from https://python.org and check "Add to PATH" during installation.
pause & exit /b 1

:python_ok
echo [OK] Python found.

:: -- 2. Virtual Environment & Dependencies --
if exist "venv" goto venv_ok
echo [1/4] Creating virtual environment...
python -m venv venv

:venv_ok
echo [1/4] Installing Python packages...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt pyinstaller
echo     OK

:: -- 3. Download FFmpeg --
if exist "ffmpeg.exe" goto ffmpeg_exists
echo [2/4] Downloading FFmpeg...
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
echo     ffmpeg.exe - OK
goto ffmpeg_done

:ffmpeg_download_fail
echo [ERROR] Failed to download FFmpeg. Please download manually from https://ffmpeg.org/download.html
echo         and place ffmpeg.exe and ffprobe.exe in the project folder.
goto ffmpeg_done

:ffmpeg_exists
echo [2/4] ffmpeg.exe already exists - skipping.

:ffmpeg_done


:: -- 4. Download Whisper.exe --
if exist "whisper.exe" goto whisper_exists
echo [3/4] Downloading whisper.exe (whisper.cpp CPU)...
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
echo     whisper.exe - OK
goto whisper_done

:whisper_download_fail
echo [ERROR] Failed to download whisper.exe.
echo         Please download manually from https://github.com/ggml-org/whisper.cpp/releases
echo         and place whisper.exe in the project folder.
goto whisper_done

:whisper_exists
echo [3/4] whisper.exe already exists - skipping.

:whisper_done


:: -- 5. Download Whisper Model --
if exist "models\ggml-medium.bin" goto model_exists
echo [4/4] Downloading Whisper medium model (~1.5 GB)...
if not exist "models" mkdir models
powershell -NoProfile -Command ^
    "$url = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin';" ^
    "Invoke-WebRequest $url -OutFile models\ggml-medium.bin -UseBasicParsing"
if errorlevel 1 goto model_download_fail
echo     ggml-medium.bin - OK
goto model_done

:model_download_fail
echo [ERROR] Failed to download model. Please download manually from:
echo         https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
echo         and place it in models/ directory.
goto model_done

:model_exists
echo [4/4] models\ggml-medium.bin already exists - skipping.

:model_done


:: -- 6. Setup .env --
if exist ".env" goto env_done
echo.
echo [!] Please configure .env file:
echo     GEN_API_KEY=sk-your-key-from-gen-api.ru
copy .env.example .env >nul 2>&1
echo     Created .env from template - open it and paste your key.

:env_done

echo.
echo ============================================================
echo   Done! Now run build_windows.bat to compile the app,
echo   or simply run: python launcher.py
echo ============================================================
pause
