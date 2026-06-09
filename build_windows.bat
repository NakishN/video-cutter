@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   Нарезчик видео — Сборка Windows .exe
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Активируем venv (setup_windows.bat должен быть запущен раньше)
if not exist "venv\Scripts\activate.bat" (
    echo [ОШИБКА] Виртуальное окружение не найдено.
    echo          Сначала запустите setup_windows.bat
    pause & exit /b 1
)
call venv\Scripts\activate.bat

:: Проверяем PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Установка PyInstaller...
    pip install -q pyinstaller
)

echo [1/2] Сборка .exe (это займёт 1–3 минуты)...
pyinstaller video_cutter.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Сборка завершилась с ошибкой. Смотрите вывод выше.
    pause & exit /b 1
)

:: Копируем бинарники и модели в dist/НарезчикВидео/
set "DIST=dist\НарезчикВидео"

echo [2/2] Копирование внешних файлов в %DIST%...

if exist "whisper.exe"  copy /Y "whisper.exe"  "%DIST%\whisper.exe"  >nul
if exist "ffmpeg.exe"   copy /Y "ffmpeg.exe"   "%DIST%\ffmpeg.exe"   >nul
if exist "ffprobe.exe"  copy /Y "ffprobe.exe"  "%DIST%\ffprobe.exe"  >nul

if exist "models\" (
    if not exist "%DIST%\models\" mkdir "%DIST%\models"
    xcopy /Y /Q "models\*" "%DIST%\models\" >nul
)

if exist ".env" (
    copy /Y ".env" "%DIST%\.env" >nul
) else if exist ".env.example" (
    copy /Y ".env.example" "%DIST%\.env" >nul
    echo [!] Скопирован .env.example → %DIST%\.env
    echo     Откройте его и вставьте GEN_API_KEY!
)

echo.
echo ============================================================
echo   Готово! Дистрибутив:  %DIST%\
echo   Запустите:            %DIST%\НарезчикВидео.exe
echo ============================================================
pause
