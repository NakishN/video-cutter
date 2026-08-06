# Video Cutter

Автоматическая локальная транскрипция аудио и видео контента, интеллектуальный поиск вирусных фрагментов с помощью ИИ и автоматический рендеринг клипов для Twitch, YouTube, Shorts, Reels и TikTok.

---

## Архитектура системы

Приложение построено по модульной структуре с асинхронной обработкой фоновых задач и поддержкой аппаратного ускорения NVIDIA CUDA / NVENC.

```
+-------------------------------------------------------------------------+
|                        Web Interface (Frontend)                         |
|         HTML5 / Vanilla JS (ES6+) / SSE Stream / CSS Glassmorphism      |
+------------------------------------+------------------------------------+
                                     | HTTP / SSE
+------------------------------------v------------------------------------+
|                         Backend Server (FastAPI)                        |
|       server.py — REST API, SSE Status Stream, Job Semaphore Queue       |
+---------+--------------------------+--------------------------+---------+
          |                          |                          |
+---------v----------+     +---------v----------+     +---------v----------+
| Media Downloader   |     |    STT Engine      |     |    LLM Engine      |
| downloader.py      |     | transcriber.py     |     | summarizer.py      |
| yt-dlp + FFmpeg    |     | faster-whisper/cuda|     | GenAPI (GPT /      |
+--------------------+     +--------------------+     | Gemini Flash)      |
                                                      +---------+----------+
                                                                |
                                                      +---------v----------+
                                                      |   Video Editing    |
                                                      | video_editor.py    |
                                                      | FFmpeg + NVENC +   |
                                                      | MediaPipe FaceTrack|
                                                      +--------------------+
```

---

## Ключевые возможности

* **Автоматическая ИИ-нарезка клипов**: Локальная транскрипция речи и семантический анализ текста через ИИ (GPT-4.1, Gemini 2.5 Flash Lite) с ранжированием фрагментов по шкале интересности.
* **Кадрово-точная синхронизация субтитров**: Алгоритм поиска FFmpeg привязан к временным меткам `.srt`, что полностью исключает рассинхрон речи, видео и субтитров.
* **Интеллектуальный Face-Tracking**: Автоматическое удерживание лица говорящего в центре кадра 9:16 с использованием нейросетевого детектора **MediaPipe** (с фоллбеком на OpenCV Haar Cascade).
* **Специализированные режимы кадрирования (Layouts)**:
  * `widescreen`: Горизонтальный оригинал (16:9).
  * `vertical_reels`: Вертикальное видео 9:16 со слежением за лицом.
  * `vertical_split`: Разделенный экран для стримеров и Втуберов (верх 60% геймплей, низ 40% веб-камера).
  * `vertical_vtuber`: Вертикальное кадрирование со смещением аватара (15% слева).
* **Вирусные стили субтитров (Subtitles Presets)**: Поддержка контрастных стилей субтитров (`viral_yellow`, `viral_white`, `box_black`, `neon_cyan`) с увеличенным нижним отступом (`MarginV=45`), предотвращающим перекрытие элементами интерфейса соцсетей.
* **Оптимизация загрузки (Twitch / YouTube)**: Загрузка только аудиодорожки (`bestaudio`), что ускоряет обработку VOD в 10-50 раз.
* **Аппаратное ускорение**: Поддержка NVIDIA CUDA для транскрипции Whisper и NVENC (`h264_nvenc`) для рендеринга видео.

---

## Установка и запуск

### Windows (Автоматический запуск)

1. Установите Python 3.9+ с сайта [python.org](https://www.python.org/downloads/).
   > [!IMPORTANT]
   > Во время установки обязательно отметьте галочку **"Add python.exe to PATH"**.

2. Запустите скрипт `run_windows.bat` в корневой папке.
3. Откройте созданный файл `.env` и укажите ваш ключ GenAPI:
   ```env
   GEN_API_KEY=sk-ваш_ключ_gen_api
   ```
4. Приложение будет доступно по адресу `http://127.0.0.1:8000`.

#### Включение ускорения CUDA на Windows

1. Запустите скрипт `setup_cuda_windows.bat`.
2. В файле `config.json` установите:
   ```json
   "use_gpu": true
   ```

---

### Linux (Локальный запуск)

#### 1. Системные зависимости

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg zip wget git cmake make g++ libopenblas-dev
```

#### 2. Окружение и запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Отредактируйте .env и вставьте GEN_API_KEY=sk-...

bash start.sh
```

---

### Linux (Деплой через Docker)

```bash
GEN_API_KEY=sk-ваш-ключ sudo -E bash deploy.sh
```

Контейнер разворачивается с помощью `docker-compose.yml` и доступен на порту `8000`.

---

## Сборка автономных релизов (Releases)

Приложение поддерживает сборку в полностью автономные бинарные пакеты, не требующие установленного Python на целевой системе.

### 1. Сборка для Windows (.exe)

Сборка осуществляется через PyInstaller на базе спецификации `video_cutter.spec`.

```cmd
build_windows.bat
```

После завершения компиляции готовый дистрибутив будет расположен в директории:
`dist\VideoCutter\VideoCutter.exe`

### 2. Сборка для Linux (.AppImage)

Для сборки портативного пакета Linux AppImage выполните исполняемый скрипт `build_appimage.sh`:

```bash
chmod +x build_appimage.sh
./build_appimage.sh
```

Скрипт автоматически создаст AppDir структуру, свяжет зависимости и сформирует файл:
`dist/VideoCutter-x86_64.AppImage`

Запуск готового AppImage пакета на любой системе Linux:
```bash
chmod +x dist/VideoCutter-x86_64.AppImage
./dist/VideoCutter-x86_64.AppImage
```

---

## Конфигурация (config.json)

```json
{
  "whisper_model_path": "models/ggml-medium.bin",
  "genapi_network_id": "gpt-4-1",
  "models_dir": "models",
  "use_gpu": true,
  "whisper_language": "ru",
  "video_dir": "videos",
  "output_dir": "output",
  "temp_dir": "tmp"
}
```

| Параметр | Описание | Значения по умолчанию |
|---|---|---|
| `whisper_model_path` | Путь к локальной модели Whisper | `"models/ggml-medium.bin"` |
| `genapi_network_id` | Идентификатор LLM сети в GenAPI | `"gpt-4-1"` / `"gemini-2-5-flash-lite"` |
| `use_gpu` | Использование NVIDIA CUDA / NVENC | `true` / `false` |
| `whisper_language` | Язык распознавания речи | `"ru"`, `"en"`, `"auto"` |
| `video_dir` | Директория загрузки исходных медиа | `"videos"` |
| `output_dir` | Директория сгенерированных результатов | `"output"` |
| `temp_dir` | Директория временных файлов | `"tmp"` |

---

## API Эндпоинты

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/` | Главная страница веб-интерфейса |
| `GET` | `/api/options` | Список доступных моделей Whisper, LLM и статус CUDA |
| `POST` | `/process` | Асинхронная загрузка и обработка локального файла |
| `POST` | `/twitch` | Обработка видео/аудио по URL (YouTube / Twitch) |
| `GET` | `/api/jobs/{job_id}/stream` | SSE-поток статуса и консольных логов задачи |
| `POST` | `/api/cut-manual` | Ручная нарезка фрагмента по точным таймкодам |
| `GET` | `/download/{video_name}` | Скачивание ZIP-архива с результатами |
| `POST` | `/api/clear-cache` | Очистка временных файлов и кэша |

---

## Лицензия

Проект распространяется под лицензией MIT.
