@echo off
setlocal

echo ============================================================
echo   Video Cutter - Compile Standalone Windows EXE
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: -- Check venv --
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo         Please run setup_windows.bat first.
    pause & exit /b 1
)
call venv\Scripts\activate.bat

:: -- Check PyInstaller --
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install -q pyinstaller
)

echo [1/2] Compiling EXE (takes 1-3 minutes)...
pyinstaller video_cutter.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Compilation failed. See output above.
    pause & exit /b 1
)

:: -- Copy binaries and models to dist/ --
set "DIST=dist\VideoCutter"

echo [2/2] Copying assets to %DIST%...

if exist "whisper.exe"  copy /Y "whisper.exe"  "%DIST%\whisper.exe"  >nul
if exist "ffmpeg.exe"   copy /Y "ffmpeg.exe"   "%DIST%\ffmpeg.exe"   >nul
if exist "ffprobe.exe"  copy /Y "ffprobe.exe"  "%DIST%\ffprobe.exe"  >nul

if exist "models" (
    if not exist "%DIST%\models" mkdir "%DIST%\models"
    xcopy /Y /Q "models\*" "%DIST%\models" >nul
)

if exist ".env" (
    copy /Y ".env" "%DIST%\.env" >nul
) else if exist ".env.example" (
    copy /Y ".env.example" "%DIST%\.env" >nul
    echo [!] Copied .env.example -> %DIST%\.env
    echo     Please edit it and insert your GEN_API_KEY!
)

echo.
echo ============================================================
echo   Success! Distribution created at:  %DIST%\
echo   Run:                               %DIST%\VideoCutter.exe
echo ============================================================
pause
