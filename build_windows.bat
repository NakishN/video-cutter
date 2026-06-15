@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "LOG=%SCRIPT_DIR%build_log.txt"
echo [%date% %time%] Build started > "%LOG%"

echo ============================================================
echo   Video Cutter - Compile Standalone Windows EXE
echo ============================================================
echo.
echo   Logging details to: build_log.txt
echo.

:: -- Check venv --
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo         Please run setup_windows.bat first.
    echo [ERROR] Virtual environment not found >> "%LOG%"
    pause & exit /b 1
)
call venv\Scripts\activate.bat >> "%LOG%" 2>&1

:: -- Check PyInstaller --
pyinstaller --version >> "%LOG%" 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    echo Installing PyInstaller >> "%LOG%"
    pip install -q pyinstaller >> "%LOG%" 2>&1
)

echo [1/2] Compiling EXE (takes 1-3 minutes)...
echo [1/2] Compiling EXE >> "%LOG%"
pyinstaller video_cutter.spec --clean --noconfirm >> "%LOG%" 2>&1

if errorlevel 1 (
    echo.
    echo [ERROR] Compilation failed. See build_log.txt
    echo [ERROR] Compilation failed >> "%LOG%"
    pause & exit /b 1
)

:: -- Copy binaries and models to dist/ --
set "DIST=dist\VideoCutter"

echo [2/2] Copying assets to %DIST%...
echo [2/2] Copying assets to %DIST% >> "%LOG%"

if exist "whisper.exe"  copy /Y "whisper.exe"  "%DIST%\whisper.exe"  >> "%LOG%" 2>&1
if exist "ffmpeg.exe"   copy /Y "ffmpeg.exe"   "%DIST%\ffmpeg.exe"   >> "%LOG%" 2>&1
if exist "ffprobe.exe"  copy /Y "ffprobe.exe"  "%DIST%\ffprobe.exe"  >> "%LOG%" 2>&1

if exist "models" (
    if not exist "%DIST%\models" mkdir "%DIST%\models"
    xcopy /Y /Q "models\*" "%DIST%\models" >> "%LOG%" 2>&1
)

if exist ".env" (
    copy /Y ".env" "%DIST%\.env" >> "%LOG%" 2>&1
) else if exist ".env.example" (
    copy /Y ".env.example" "%DIST%\.env" >> "%LOG%" 2>&1
    echo [!] Copied .env.example -> %DIST%\.env
    echo [!] Copied .env.example -> %DIST%\.env >> "%LOG%"
    echo     Please edit it and insert your GEN_API_KEY!
)

echo.
echo ============================================================
echo   Success! Distribution created at:  %DIST%\
echo   Run:                               %DIST%\VideoCutter.exe
echo ============================================================
echo [%date% %time%] Build finished successfully >> "%LOG%"
pause
