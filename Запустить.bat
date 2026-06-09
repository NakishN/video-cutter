@echo off
chcp 65001 >nul 2>&1
title Нарезчик видео
cd /d "%~dp0"

echo ================================================
echo   Нарезчик видео - запуск
echo ================================================
echo.

:: Пишем лог чтобы видеть ошибки
set "LOG=%~dp0error_log.txt"
echo [%date% %time%] Запуск > "%LOG%"

:: ── 1. Python ────────────────────────────────────
echo [1] Проверка Python...
python --version >> "%LOG%" 2>&1
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ОШИБКА: Python не найден!
    echo.
    echo  Скачайте Python 3.11 с https://www.python.org/downloads/
    echo  При установке обязательно поставьте галочку:
    echo  "Add Python to PATH"
    echo.
    echo  После установки запустите этот файл снова.
    echo.
    start "" "https://www.python.org/downloads/"
    echo [ERROR] Python not found >> "%LOG%"
    pause
    exit /b 1
)
echo  Python найден - OK
echo [OK] Python found >> "%LOG%"

:: ── 2. Виртуальное окружение ─────────────────────
if exist "venv\Scripts\python.exe" goto :deps_ok

echo.
echo [2] Первый запуск - создание окружения...
echo     (займёт 2-5 минут)
echo.

python -m venv venv >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  ОШИБКА: не удалось создать venv.
    echo  Попробуйте запустить от имени Администратора.
    echo  Подробности в файле: error_log.txt
    echo.
    echo [ERROR] venv creation failed >> "%LOG%"
    pause
    exit /b 1
)
echo  Окружение создано - OK
echo [OK] venv created >> "%LOG%"

echo.
echo [3] Установка пакетов (faster-whisper, ffmpeg, uvicorn...)
echo     Это займёт несколько минут, ждите...
echo.

venv\Scripts\pip install --upgrade pip >> "%LOG%" 2>&1
venv\Scripts\pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  ОШИБКА: не удалось установить пакеты.
    echo.
    echo  Возможные причины:
    echo  - Нет интернета
    echo  - Антивирус блокирует pip
    echo  - Мало места на диске (нужно ~2 ГБ)
    echo.
    echo  Подробности в файле: error_log.txt
    echo.
    echo [ERROR] pip install failed >> "%LOG%"
    rmdir /s /q venv >nul 2>&1
    pause
    exit /b 1
)
echo  Пакеты установлены - OK
echo [OK] packages installed >> "%LOG%"

:deps_ok

:: ── 3. Файл .env ─────────────────────────────────
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
    echo ================================================
    echo   Нужен API-ключ с сайта gen-api.ru
    echo ================================================
    echo.
    echo  1. Зарегистрируйтесь на https://gen-api.ru
    echo  2. Скопируйте ключ (начинается с sk-...)
    echo  3. Вставьте в файл .env который сейчас откроется
    echo     Строка: GEN_API_KEY=sk-ваш-ключ
    echo  4. Сохраните файл (Ctrl+S) и закройте блокнот
    echo  5. Нажмите любую клавишу здесь
    echo.
    start "" "https://gen-api.ru"
    timeout /t 2 >nul
    notepad ".env"
    echo.
    echo  Нажмите любую клавишу для продолжения...
    pause >nul
)

:: ── 4. Запуск ─────────────────────────────────────
echo.
echo ================================================
echo   Запуск сервера...
echo   Адрес: http://127.0.0.1:8000
echo   Закройте это окно чтобы остановить.
echo ================================================
echo.
echo   ВАЖНО: при первой транскрипции автоматически
echo   скачается модель Whisper (~1.5 ГБ) - это нормально!
echo.
echo [OK] Starting server >> "%LOG%"

:: Открываем браузер через 3 сек
powershell -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process 'http://127.0.0.1:8000'" >nul 2>&1

venv\Scripts\python launcher.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  Сервер завершился с ошибкой.
    echo  Подробности в файле: error_log.txt
    echo.
    echo  Содержимое лога:
    echo  ----------------
    type "%LOG%"
    echo.
)

echo.
echo  Сервер остановлен. Нажмите любую клавишу...
pause >nul
