@echo off
cd /d "%~dp0"
set "LOG=%~dp0error_log.txt"
echo [%date% %time%] Start > "%LOG%"

echo.
echo  ================================================
echo   Video Cutter - Starting...
echo  ================================================
echo.

:: -- Check Python --
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo.
    echo  Download Python 3.11 from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: check "Add Python to PATH"
    echo  Then run this file again.
    echo.
    start "" "https://www.python.org/downloads/"
    echo [ERROR] Python not found >> "%LOG%"
    pause
    exit /b 1
)
echo  [OK] Python found
echo [OK] Python >> "%LOG%"

:: -- Create venv if needed --
if exist "venv\Scripts\python.exe" goto :install_ok

echo.
echo  [SETUP] First run - installing packages...
echo  This will take 2-5 minutes. Please wait.
echo.

python -m venv venv >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to create venv.
    echo  Try running as Administrator.
    echo  See error_log.txt for details.
    echo [ERROR] venv failed >> "%LOG%"
    pause
    exit /b 1
)
echo  [OK] Virtual environment created
echo [OK] venv created >> "%LOG%"

echo  [SETUP] Installing: faster-whisper, ffmpeg, uvicorn...
venv\Scripts\pip install --upgrade pip -q >> "%LOG%" 2>&1
venv\Scripts\pip install -r requirements.txt -q >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Package installation failed!
    echo.
    echo  Possible reasons:
    echo  - No internet connection
    echo  - Antivirus blocking pip
    echo  - Not enough disk space, need about 2 GB
    echo.
    echo  See error_log.txt for details.
    echo.
    echo [ERROR] pip install failed >> "%LOG%"
    rmdir /s /q venv >nul 2>&1
    pause
    exit /b 1
)
echo  [OK] All packages installed
echo [OK] packages installed >> "%LOG%"

:install_ok

:: -- Check .env --
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul 2>&1
    ) else (
        echo GEN_API_KEY=> ".env"
    )
)

findstr "GEN_API_KEY=sk-" ".env" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ================================================
    echo   API key required from gen-api.ru
    echo  ================================================
    echo.
    echo  1. Register at https://gen-api.ru
    echo  2. Copy your key, which starts with sk-...
    echo  3. Paste into .env file: GEN_API_KEY=sk-...
    echo  4. Save .env using Ctrl-S and close Notepad
    echo  5. Press any key here to continue
    echo.
    start "" "https://gen-api.ru"
    timeout /t 2 >nul
    notepad ".env"
    echo.
    pause
)

:: -- Start server --
echo.
echo  ================================================
echo   Server starting at http://127.0.0.1:8000
echo   Opening browser in 3 seconds...
echo   Close this window to stop the server.
echo  ================================================
echo.
echo  NOTE: First transcription will download
echo  Whisper model (~1.5 GB) automatically.
echo.
echo [OK] Starting server >> "%LOG%"

powershell -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process 'http://127.0.0.1:8000'"

venv\Scripts\python launcher.py
if errorlevel 1 (
    echo.
    echo  [ERROR] Server crashed. See error_log.txt
    echo.
    type "%LOG%"
    echo.
)

echo.
echo  Server stopped. Press any key to exit...
pause >nul
