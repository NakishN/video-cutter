@echo off
chcp 65001 >nul 2>&1
title Нарезчик видео

:: Размер окна
mode con cols=65 lines=35 >nul 2>&1

set "DIR=%~dp0"
cd /d "%DIR%"

goto :main

:: ══════════════════════════════════════════
:print_header
cls
echo.
echo  ┌─────────────────────────────────────────────┐
echo  │          🎬  Нарезчик видео                 │
echo  │     Twitch / YouTube → транскрипция         │
echo  └─────────────────────────────────────────────┘
echo.
goto :eof

:: ══════════════════════════════════════════
:main
call :print_header

:: ── 1. Проверяем Python ─────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ❌  Python не найден!
    echo.
    echo  Нужен Python 3.11 или новее.
    echo  Открываем страницу загрузки...
    echo.
    start "" "https://www.python.org/downloads/"
    echo  После установки Python:
    echo   • Поставьте галочку "Add Python to PATH"
    echo   • Закройте это окно
    echo   • Запустите Запустить.bat снова
    echo.
    pause
    exit /b
)

:: ── 2. Первый запуск: создаём окружение ─
if not exist "venv\Scripts\python.exe" (
    call :print_header
    echo  ⏳  Первый запуск — установка компонентов...
    echo      (займёт 2-5 минут, интернет нужен)
    echo.

    echo  [1/2] Создание окружения Python...
    python -m venv venv >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  ❌  Не удалось создать виртуальное окружение.
        echo.
        echo  Попробуйте:
        echo   • Запустить от имени Администратора
        echo   • Переустановить Python с сайта python.org
        echo.
        pause
        exit /b
    )

    echo  [2/2] Загрузка и установка пакетов...
    echo      (faster-whisper, ffmpeg, uvicorn...)
    echo.
    call venv\Scripts\pip install --upgrade pip -q --no-warn-script-location
    call venv\Scripts\pip install -r requirements.txt -q --no-warn-script-location
    if errorlevel 1 (
        echo.
        echo  ❌  Ошибка установки пакетов.
        echo.
        echo  Возможные причины:
        echo   • Нет подключения к интернету
        echo   • Антивирус блокирует pip
        echo   • Мало места на диске (нужно ~2 ГБ)
        echo.
        echo  Попробуйте запустить снова или
        echo  отключите антивирус на время установки.
        echo.
        :: Удаляем неполное окружение, чтобы при след. запуске повторить
        rmdir /s /q venv >nul 2>&1
        pause
        exit /b
    )

    call :print_header
    echo  ✅  Компоненты установлены!
    echo.
)

:: ── 3. Проверяем .env и GEN_API_KEY ─────
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul 2>&1
    ) else (
        echo GEN_API_KEY=> .env
    )
)

:: Ищем рабочий ключ (начинается с sk-)
findstr /r /c:"GEN_API_KEY=sk-" ".env" >nul 2>&1
if errorlevel 1 (
    call :print_header
    echo  🔑  Нужен API-ключ для анализа видео.
    echo.
    echo  Получите бесплатный ключ на сайте:
    echo  https://gen-api.ru
    echo.
    echo  1. Зарегистрируйтесь (есть пробный баланс)
    echo  2. Скопируйте ключ (начинается с sk-...)
    echo  3. Вставьте в файл .env который откроется
    echo.
    echo  Открываем сайт и файл настроек...
    echo.
    start "" "https://gen-api.ru"
    timeout /t 2 >nul
    notepad ".env"
    echo.
    echo  Сохраните .env (Ctrl+S в блокноте),
    echo  затем нажмите любую клавишу...
    echo.
    pause >nul

    :: Повторная проверка
    findstr /r /c:"GEN_API_KEY=sk-" ".env" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  ⚠️   Ключ не найден в .env.
        echo  Транскрипция будет работать,
        echo  но анализ моментов — нет.
        echo.
        timeout /t 3 >nul
    )
)

:: ── 4. Запускаем! ────────────────────────
call :print_header
echo  🚀  Запуск сервера...
echo.
echo  ┌─────────────────────────────────────────────┐
echo  │  Адрес:  http://127.0.0.1:8000             │
echo  │                                             │
echo  │  Браузер откроется автоматически.           │
echo  │  Закройте это окно — сервер остановится.   │
echo  └─────────────────────────────────────────────┘
echo.
echo  (При первой транскрипции скачается модель
echo   Whisper ~1.5 ГБ — это нормально, один раз)
echo.

:: Открываем браузер через 3 секунды
start "" /b powershell -WindowStyle Hidden -Command ^
    "Start-Sleep 3; Start-Process 'http://127.0.0.1:8000'" >nul 2>&1

:: Запускаем сервер
call venv\Scripts\python launcher.py

:: Сервер остановлен
echo.
echo  Сервер остановлен.
echo  Нажмите любую клавишу для выхода...
pause >nul
