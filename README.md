# 🎬 Нарезчик видео

Автоматическая транскрипция Twitch-VOD и YouTube-видео с выделением ключевых моментов.

**Как работает:**
1. Загружаете видео или вставляете ссылку на Twitch/YouTube
2. [Whisper](https://github.com/ggerganov/whisper.cpp) транскрибирует речь локально (без интернета)
3. [GenAPI](https://gen-api.ru) (GPT-4.1 или Gemini) находит самые интересные моменты и выдаёт список с таймкодами
4. Скачиваете готовый текст

---

## 🪟 Windows — запуск одним файлом

### Шаг 1 — Установите Python (один раз)

Скачайте Python 3.11+ с [python.org](https://www.python.org/downloads/).

> ⚠️ При установке **обязательно** поставьте галочку **«Add Python to PATH»**

### Шаг 2 — Скачайте проект

Нажмите зелёную кнопку **Code → Download ZIP**, распакуйте в любую папку.

### Шаг 3 — Запустите

Откройте папку и дважды кликните:

```
Запустить.bat
```

**При первом запуске** скрипт сам:
- Создаст виртуальное окружение Python
- Установит все зависимости (faster-whisper, ffmpeg и т.д.)
- Откроет файл `.env` для вставки API-ключа

**При каждом следующем запуске** — просто запускает сервер и открывает браузер.

> 🔑 **API-ключ** нужен для анализа интересных моментов.
> Получите бесплатно на [gen-api.ru](https://gen-api.ru) (есть пробный баланс).
> Скрипт сам откроет сайт и файл `.env` при первом запуске.

> ⚠️ При **первой транскрипции** автоматически скачается модель Whisper (~1.5 ГБ).
> Это происходит один раз, потом модель кешируется.

### Если что-то пошло не так

| Проблема | Решение |
|---|---|
| Окно сразу закрылось | Нажмите ПКМ на `Запустить.bat` → «Запуск от имени администратора» |
| «Python не найден» | Переустановите Python с сайта python.org с галочкой «Add to PATH» |
| Ошибка установки пакетов | Проверьте интернет, отключите антивирус на время установки |
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
