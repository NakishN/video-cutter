@echo off
color 0B
cd /d "%~dp0"
echo ============================================================
echo   Video Cutter - Настройка CUDA ускорения для Windows
echo ============================================================
echo.
echo   Этот скрипт установит необходимые библиотеки NVIDIA (cuBLAS, cuDNN)
echo   прямо в виртуальное окружение Python для включения GPU ускорения Whisper.
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ОШИБКА] Виртуальное окружение (venv) не обнаружено.
    echo Сначала запустите run_windows.bat для установки базовых зависимостей!
    echo.
    pause
    exit /b 1
)

echo [1/2] Активация виртуального окружения...
call venv\Scripts\activate.bat

echo [2/2] Установка пакетов nvidia-cublas-cu12 и nvidia-cudnn-cu12...
echo Пожалуйста, подождите, скачивание может занять некоторое время (~300-500 МБ)...
echo.
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить CUDA библиотеки. 
    echo Проверьте интернет-соединение или версию pip.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [УСПЕШНО] CUDA библиотеки установлены!
echo ============================================================
echo.
echo   Теперь программа автоматически сможет использовать вашу видеокарту
echo   NVIDIA для ускорения Whisper (транскрипции) и FFmpeg (нарезки).
echo.
echo   Убедитесь, что в файле config.json включен GPU режим ("use_gpu": true).
echo.
pause
