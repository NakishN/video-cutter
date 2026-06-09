# ── Нарезчик видео — Dockerfile (CPU, GenAPI-only) ──────────────────────────
# Образ: python 3.11 slim + ffmpeg + whisper.cpp (CPU)
# Запуск: docker-compose up -d

FROM python:3.11-slim AS builder

# Системные зависимости для сборки whisper.cpp
RUN apt-get update && apt-get install -y --no-install-recommends \
        git cmake make g++ libopenblas-dev wget zip \
    && rm -rf /var/lib/apt/lists/*

# ── Сборка whisper.cpp (CPU + OpenBLAS) ─────────────────────────────────────
WORKDIR /build/whisper.cpp
RUN git clone --depth 1 https://github.com/ggerganov/whisper.cpp . \
    && cmake -B build -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS \
    && cmake --build build --config Release -j"$(nproc)" \
    && cp build/bin/whisper-cli /whisper

# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Системные зависимости runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg zip libopenblas-base \
    && rm -rf /var/lib/apt/lists/*

# Whisper binary из builder-стадии
COPY --from=builder /whisper /app/whisper
RUN chmod +x /app/whisper

WORKDIR /app

# Python-зависимости (кэшируются отдельным слоем)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Исходный код приложения
COPY server.py genapi_client.py transcript_utils.py ./
COPY config.json .env.example ./
COPY index.html styles.css app.js ./
COPY static/ ./static/

# Папки для данных (монтируются как volumes)
RUN mkdir -p videos output tmp models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
