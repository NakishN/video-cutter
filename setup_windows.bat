@echo off
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "LOG=%SCRIPT_DIR%setup_log.txt"
echo [%date% %time%] Setup started > "%LOG%"

echo ============================================================
echo   Video Cutter - Installer for Windows
echo ============================================================
echo.
echo   Logging details to: setup_log.txt
echo.

:: -- 1. Check Python --
python --version >> "%LOG%" 2>&1
if not errorlevel 1 goto python_ok
echo [ERROR] Python not found.
echo Please download Python 3.11+ from https://python.org and check "Add to PATH" during installation.
echo [ERROR] Python not found >> "%LOG%"
pause & exit /b 1

:python_ok
echo [OK] Python found.
echo [OK] Python found >> "%LOG%"

:: -- 2. Virtual Environment & Dependencies --
if exist "venv" goto venv_ok
echo [1/4] Creating virtual environment...
echo [1/4] Creating virtual environment >> "%LOG%"
python -m venv venv >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment. See setup_log.txt
    echo [ERROR] Failed to create venv >> "%LOG%"
    pause & exit /b 1
)

:venv_ok
echo [1/4] Installing Python packages (this may take a minute)...
echo [1/4] Installing Python packages >> "%LOG%"
call venv\Scripts\activate.bat >> "%LOG%" 2>&1
pip install -q -r requirements.txt pyinstaller >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. See setup_log.txt
    echo [ERROR] Failed to install dependencies >> "%LOG%"
    pause & exit /b 1
)
echo     OK
echo     OK >> "%LOG%"

:: -- 3. Download FFmpeg --
if exist "ffmpeg.exe" goto ffmpeg_exists
echo [2/4] Downloading FFmpeg (about 100 MB)...
echo [2/4] Downloading FFmpeg >> "%LOG%"
powershell -NoProfile -Command ^
    "$url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';" ^
    "Invoke-WebRequest $url -OutFile ffmpeg_tmp.zip -UseBasicParsing" >> "%LOG%" 2>&1
if errorlevel 1 goto ffmpeg_download_fail

echo [2/4] Extracting FFmpeg...
echo [2/4] Extracting FFmpeg >> "%LOG%"
powershell -NoProfile -Command ^
    "Expand-Archive ffmpeg_tmp.zip ffmpeg_tmp -Force;" ^
    "$exe = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1;" ^
    "Copy-Item $exe.FullName ffmpeg.exe;" ^
    "$ffprobe = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffprobe.exe | Select-Object -First 1;" ^
    "if ($ffprobe) { Copy-Item $ffprobe.FullName ffprobe.exe }" ^
    "Remove-Item ffmpeg_tmp,ffmpeg_tmp.zip -Recurse -Force" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to extract FFmpeg. See setup_log.txt
    echo [ERROR] Failed to extract FFmpeg >> "%LOG%"
    pause & exit /b 1
)
echo     ffmpeg.exe - OK
echo     ffmpeg.exe - OK >> "%LOG%"
goto ffmpeg_done

:ffmpeg_download_fail
echo [ERROR] Failed to download FFmpeg. See setup_log.txt
echo [ERROR] Failed to download FFmpeg >> "%LOG%"
echo Please download manually from https://ffmpeg.org/download.html and place ffmpeg.exe in the project folder.
goto ffmpeg_done

:ffmpeg_exists
echo [2/4] ffmpeg.exe already exists - skipping.
echo [2/4] ffmpeg.exe already exists >> "%LOG%"

:ffmpeg_done


:: -- 4. Download Whisper.exe --
if exist "whisper.exe" goto whisper_exists
echo [3/4] Downloading whisper.exe (about 5 MB)...
echo [3/4] Downloading whisper.exe >> "%LOG%"
powershell -NoProfile -Command ^
    "$url = 'https://github.com/ggml-org/whisper.cpp/releases/download/v1.7.5/whisper-blas-bin-x64.zip';" ^
    "Invoke-WebRequest $url -OutFile whisper_tmp.zip -UseBasicParsing" >> "%LOG%" 2>&1
if errorlevel 1 goto whisper_download_fail

echo [3/4] Extracting whisper.exe...
echo [3/4] Extracting whisper.exe >> "%LOG%"
powershell -NoProfile -Command ^
    "Expand-Archive whisper_tmp.zip whisper_tmp -Force;" ^
    "$exe = Get-ChildItem whisper_tmp -Recurse -Filter 'main.exe' | Select-Object -First 1;" ^
    "if (!$exe) { $exe = Get-ChildItem whisper_tmp -Recurse -Filter 'whisper*.exe' | Select-Object -First 1 };" ^
    "Copy-Item $exe.FullName whisper.exe;" ^
    "Remove-Item whisper_tmp,whisper_tmp.zip -Recurse -Force" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to extract whisper.exe. See setup_log.txt
    echo [ERROR] Failed to extract whisper.exe >> "%LOG%"
    pause & exit /b 1
)
echo     whisper.exe - OK
echo     whisper.exe - OK >> "%LOG%"
goto whisper_done

:whisper_download_fail
echo [ERROR] Failed to download whisper.exe. See setup_log.txt
echo [ERROR] Failed to download whisper.exe >> "%LOG%"
echo Please download manually from https://github.com/ggml-org/whisper.cpp/releases and place whisper.exe in the project folder.
goto whisper_done

:whisper_exists
echo [3/4] whisper.exe already exists - skipping.
echo [3/4] whisper.exe already exists >> "%LOG%"

:whisper_done


:: -- 5. Download Whisper Model --
if exist "models\ggml-medium.bin" goto model_exists
echo [4/4] Downloading Whisper medium model (~1.5 GB, this may take a few minutes)...
echo [4/4] Downloading Whisper model >> "%LOG%"
if not exist "models" mkdir models
powershell -NoProfile -Command ^
    "$url = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin';" ^
    "Invoke-WebRequest $url -OutFile models\ggml-medium.bin -UseBasicParsing" >> "%LOG%" 2>&1
if errorlevel 1 goto model_download_fail
echo     ggml-medium.bin - OK
echo     ggml-medium.bin - OK >> "%LOG%"
goto model_done

:model_download_fail
echo [ERROR] Failed to download model. See setup_log.txt
echo [ERROR] Failed to download model >> "%LOG%"
echo Please download manually from:
echo https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
echo and place it in models/ directory.
goto model_done

:model_exists
echo [4/4] models\ggml-medium.bin already exists - skipping.
echo [4/4] models\ggml-medium.bin already exists >> "%LOG%"

:model_done


:: -- 6. Setup .env --
if exist ".env" goto env_done
echo.
echo [!] Please configure .env file:
echo     GEN_API_KEY=sk-your-key-from-gen-api.ru
copy .env.example .env >nul 2>&1
echo     Created .env from template - open it and paste your key.
echo [!] Created .env from template >> "%LOG%"

:env_done

echo.
echo ============================================================
echo   Done! Now run build_windows.bat to compile the app,
echo   or simply run: python launcher.py
echo ============================================================
echo [%date% %time%] Setup finished successfully >> "%LOG%"
pause
