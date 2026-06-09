# 🎬 Нарезчик видео

Автоматическая транскрипция Twitch-VOD и YouTube-видео с выделением ключевых моментов.

**Как работает:**
1. Загружаете видео или вставляете ссылку на Twitch/YouTube
2. [Whisper](https://github.com/ggerganov/whisper.cpp) транскрибирует речь локально (без интернета)
3. [GenAPI](https://gen-api.ru) (GPT-4.1 или Gemini) находит самые интересные моменты и выдаёт список с таймкодами
4. Скачиваете готовый текст

---

## 🪟 Windows — запуск .exe

### Шаг 1 — Скачайте проект

Нажмите зелёную кнопку **Code → Download ZIP** на этой странице, распакуйте архив в любую папку.

### Шаг 2 — Установите Python

Скачайте Python 3.11+ с [python.org](https://www.python.org/downloads/).

> ⚠️ При установке обязательно поставьте галочку **«Add Python to PATH»**

### Шаг 3 — Запустите установку зависимостей

Откройте папку проекта, дважды кликните на файл:

```
setup_windows.bat
```

Скрипт автоматически скачает (~1.5 ГБ, займёт несколько минут):
- `ffmpeg.exe` — обработка аудио
- `whisper.exe` — распознавание речи
- `models/ggml-medium.bin` — языковая модель Whisper

### Шаг 4 — Добавьте API-ключ

В папке проекта откройте файл `.env` (блокнотом или любым редактором) и вставьте ключ:

```
GEN_API_KEY=sk-ваш-ключ
```

Ключ получите на [gen-api.ru](https://gen-api.ru) (регистрация бесплатная, есть пробный баланс).

### Шаг 5 — Соберите .exe

Дважды кликните:

```
build_windows.bat
```

Сборка займёт 1–3 минуты. Готовый дистрибутив появится в папке:

```
dist\НарезчикВидео\
```

### Шаг 6 — Запускайте

```
dist\НарезчикВидео\НарезчикВидео.exe
```

Откроется консольное окно и автоматически браузер на `http://127.0.0.1:8000`.

> 💡 Закройте консольное окно — сервер остановится.

### Структура папки после сборки

```
dist/НарезчикВидео/
├── НарезчикВидео.exe   ← запускать это
├── whisper.exe          ← транскрипция (не удалять)
├── ffmpeg.exe           ← аудио (не удалять)
├── ffprobe.exe          ← аудио (не удалять)
├── .env                 ← ключ GenAPI (не удалять)
├── models/
│   └── ggml-medium.bin  ← модель ~1.5 ГБ (не удалять)
├── videos/              ← загруженные видео
└── output/              ← транскрипты и резюме
```

### Возможные проблемы (Windows)

| Проблема | Решение |
|---|---|
| «Python не найден» | Переустановите Python с галочкой «Add to PATH» |
| «ffmpeg не скачался» | Скачайте вручную с [ffmpeg.org](https://ffmpeg.org/download.html), положите `ffmpeg.exe` в папку проекта |
| «whisper не скачался» | Скачайте с [github.com/ggerganov/whisper.cpp/releases](https://github.com/ggerganov/whisper.cpp/releases), переименуйте в `whisper.exe` |
| Антивирус блокирует .exe | Добавьте папку `dist\НарезчикВидео\` в исключения |
| Браузер не открылся | Откройте вручную: `http://127.0.0.1:8000` |

---

## 🐧 Linux — локальный запуск

### Требования

- Ubuntu 20.04+ / Debian 11+ / любой Linux
- Python 3.9+
- ffmpeg
- CUDA (опционально, для ускорения Whisper)

### Шаг 1 — Системные зависимости

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg zip wget git cmake make g++ libopenblas-dev
```

### Шаг 2 — Скачайте проект

```bash
git clone https://github.com/NakishN/video-cutter.git
cd video-cutter
```

### Шаг 3 — Python-окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Шаг 4 — Скомпилируйте Whisper

```bash
cd whisper.cpp
cmake -B build -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS
cmake --build build --config Release -j$(nproc)
cp build/bin/whisper-cli ../whisper
cd ..
```

> Если есть NVIDIA GPU:
> ```bash
> cmake -B build -DGGML_CUDA=ON
> cmake --build build --config Release -j$(nproc)
> cp build/bin/whisper-cli ../whisper-cuda
> ```
> И поставьте `"use_gpu": true` в `config.json`.

### Шаг 5 — Скачайте модель Whisper

```bash
mkdir -p models
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin \
     -O models/ggml-medium.bin
```

Альтернативные модели (меньше = быстрее, но хуже качество):

| Модель | Размер | Качество | Скорость (CPU) |
|---|---|---|---|
| `ggml-tiny.bin` | 75 МБ | низкое | ~2 мин/час видео |
| `ggml-base.bin` | 142 МБ | среднее | ~5 мин/час видео |
| `ggml-small.bin` | 466 МБ | хорошее | ~10 мин/час видео |
| `ggml-medium.bin` | 1.5 ГБ | **отличное** | ~20 мин/час видео |

### Шаг 6 — Настройте .env

```bash
cp .env.example .env
nano .env
```

Вставьте ключ:
```
GEN_API_KEY=sk-ваш-ключ
```

### Шаг 7 — Запуск

```bash
bash start.sh
```

Откройте в браузере: `http://localhost:8000`

---

## 🌐 Linux — деплой на VPS (Docker)

Подходит если хотите использовать сервис круглосуточно из браузера с любого устройства.

### Требования к серверу

| | Минимум | Рекомендуется |
|---|---|---|
| CPU | 2 ядра | 4 ядра |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 10 ГБ | 20 ГБ |
| ОС | Ubuntu 22.04 | Ubuntu 22.04 |

**Стоимость:** ~1 000–1 500 ₽/мес (Selectel, Timeweb, Hetzner).

### Деплой одной командой

Скопируйте проект на сервер и выполните:

```bash
# С вашей локальной машины — копируем проект на сервер
scp -r /путь/к/video-cutter user@IP_СЕРВЕРА:/opt/video-cutter

# Подключаемся к серверу
ssh user@IP_СЕРВЕРА

# Запускаем деплой
cd /opt/video-cutter
GEN_API_KEY=sk-ваш-ключ sudo -E bash deploy.sh
```

Скрипт сам:
- Установит Docker
- Скачает модель Whisper (~1.5 ГБ)
- Соберёт Docker-образ (5–10 мин при первом запуске)
- Запустит контейнер
- Проверит работоспособность

После запуска приложение доступно по адресу: `http://IP_СЕРВЕРА:8000`

### Управление контейнером

```bash
# Посмотреть статус
docker compose ps

# Посмотреть логи
docker compose logs -f

# Перезапустить
docker compose restart

# Остановить
docker compose down

# Обновить после изменений в коде
docker compose up -d --build
```

### Возможные проблемы (Linux / Docker)

| Проблема | Решение |
|---|---|
| `GEN_API_KEY не задан` | Отредактируйте `/opt/video-cutter/.env`, добавьте ключ, перезапустите |
| Нет места на диске | Очистите старые видео: `rm /opt/video-cutter/videos/*` |
| Контейнер падает | Проверьте логи: `docker compose logs --tail=50` |
| Порт 8000 занят | Измените в `docker-compose.yml`: `"8080:8000"` |

---

## ⚙️ Настройки (config.json)

```json
{
  "whisper_model_path": "models/ggml-medium.bin",
  "genapi_network_id": "gpt-4-1",
  "models_dir": "models",
  "use_gpu": false,
  "whisper_language": "ru",
  "video_dir": "videos",
  "output_dir": "output",
  "temp_dir": "tmp"
}
```

| Параметр | Описание |
|---|---|
| `whisper_model_path` | Путь к модели Whisper |
| `genapi_network_id` | Модель GenAPI: `gpt-4-1` или `gemini-2-5-flash-lite` |
| `use_gpu` | `true` — Whisper на GPU (нужна NVIDIA + CUDA), `false` — CPU |
| `whisper_language` | Язык транскрипции: `ru`, `en`, `auto` |

---

## 🔑 Получение ключа GenAPI

1. Зарегистрируйтесь на [gen-api.ru](https://gen-api.ru)
2. Перейдите в раздел **API Keys**
3. Создайте ключ и скопируйте его
4. Вставьте в `.env`: `GEN_API_KEY=sk-...`

---

## 📄 Лицензия

MIT — свободно использовать, изменять, распространять.
