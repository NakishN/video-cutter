# 📹 Твич‑нарезка: автоматическая транскрипция, ключевые фрагменты и резюме

## 📦 О проекте
Это автономное локальное веб‑приложение, которое позволяет:
1. **Скачивать** Twitch‑VOD (или работать с уже скачанными файлами).
2. **Транскрибировать** речь полностью с помощью **Whisper‑GGML** (GPU‑ускорение).
3. **Извлекать ключевые фрагменты** и **генерировать краткое резюме** при помощи локальной LLM (Llama 2 13 B GGML).
4. **Отображать** результаты в стильном тёмном UI с анимациями и spinner‑индикатором.

Все зависимости ставятся без внешних API‑ключей, работа происходит полностью офлайн.

---

## 📋 Требования
| Требование | Минимум | Рекомендация |
|------------|--------|--------------|
| ОС | Linux (Ubuntu/Debian) | — |
| Python | 3.9+ | — |
| ОЗУ | 8 GB | 16 GB+ для `whisper‑medium` + LLM |
| GPU | CUDA‑совместимая видеокарта (не менее 4 GB VRAM) – **опционально**, но сильно ускоряет Whisper и LLM |
| Дисковое пространство | ~10 GB для моделей | — |

## 📦 Установка системных зависимостей
```bash
# Обновляем пакеты
sudo apt-get update

# Устанавливаем ffmpeg (для извлечения аудио) и yt-dlp (скачивает Twitch/VOD)
sudo apt-get install -y ffmpeg yt-dlp
```

## 🐍 Настройка Python‑окружения
```bash
# Создаём и активируем venv
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости (uvicorn с optional‑зависимостями)
pip install fastapi "uvicorn[standard]" pydantic tqdm
```
> **Ошибка *Missing dependencies for SOCKS support*** обычно появляется, если `uvicorn` установлен без optional‑зависимостей. Установка `uvicorn[standard]` решит проблему.

## 🤖 Установка моделей
1. **Whisper‑GGML** (для GPU):
   ```bash
   mkdir -p models
   cd models
   wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin -O ggml-medium.bin
   ```
   (Можно выбрать `tiny`, `base`, `small` – меняйте `ggml-medium.bin` в `config.json`.)
2. **LLM (Llama‑2 13 B GGML Q4_0)**:
   ```bash
   wget https://huggingface.co/TheBloke/Llama-2-13B-GGML/resolve/main/llama-2-13b.ggmlv3.q4_0.bin -O llama-2-13b-ggml-q4_0.bin
   ```
   Положите файл в `models/`.

## ⚙️ Конфигурация (`config.json`)
```json
{
  "whisper_model_path": "models/ggml-medium.bin",
  "llm_model_path": "models/llama-2-13b-ggml-q4_0.bin",
  "use_gpu": true,
  "videos_dir": "videos",
  "temp_dir": "tmp"
}
```
*Если GPU нет – поставьте `false`.*

## 🚀 Запуск сервера
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```
Откройте в браузере: `http://localhost:8000`

## 📺 Как пользоваться UI
1. **Выберите файлы** через кнопку *Выбор видео* **или** введите URL Twitch‑VOD и нажмите *Скачать с Twitch*.
2. После появления файла в списке нажмите на название – он станет текущим.
3. Нажмите **Запустить транскрипцию** – появится spinner‑индикатор и прогресс‑бар.
4. Когда транскрипция завершится, автоматически выполнится запрос к LLM и отобразятся **ключевые фрагменты** и **резюме**.
5. Результаты можно копировать или скачать в виде `*.txt`/`*.json`.

## 🎨 UI‑детали (spinner)
* В `static/styles.css` добавлен стиль `.spinner` – вращающийся круг.
* В `static/app.js` реализована функция `showSpinner()` / `hideSpinner()` для отображения индикатора во время длительных запросов (`/api/download`, `/api/transcribe`, `/api/summary`).

## 📚 Тестирование
Для быстрой проверки возьмите любой короткий Twitch‑VOD (≈30 сек). Пример URL:
```
https://www.twitch.tv/videos/123456789
```
Нажмите *Скачать с Twitch*, затем *Транскрибировать*. После завершения вы увидите массив ключевых пунктов и резюме.

## 🛠️ Возможные проблемы
| Проблема | Решение |
|----------|--------|
| `uvicorn` не устанавливается (SOCKS error) | Установите `pip install "uvicorn[standard]"` как показано выше. |
| Ошибка `whisper: CUDA not found` | Проверьте, что драйвер NVIDIA и CUDA‑toolkit установлены; `nvidia-smi` должна показывать вашу видеокарту. |
| LLM «out of memory» | Снизьте размер модели (например, `ggml-q5_0`‑версию) или запустите с `--cpu` (уберите `use_gpu`). |
| Нет доступа к папке `videos/` | Убедитесь, что пользователь имеет права записи в каталоге проекта. |

## 📄 Лицензия
MIT – свободно использовать, модифицировать и распространять.

---

*Happy hacking! 🚀*
