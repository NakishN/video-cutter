#!/usr/bin/env bash
# deploy.sh — Пошаговый деплой «Нарезчика видео» на Ubuntu 22.04 LTS
# Запуск: bash deploy.sh
set -euo pipefail

###############################################################################
# Конфигурация — измените перед запуском
###############################################################################
GEN_API_KEY="${GEN_API_KEY:-}"          # или вставьте ключ прямо сюда
APP_DIR="/opt/video-cutter"             # куда установить приложение
WHISPER_MODEL="ggml-medium.bin"         # tiny / base / small / medium / large
###############################################################################

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }
section() { echo -e "\n${YELLOW}══ $* ══${NC}"; }

# ── 0. Проверки ──────────────────────────────────────────────────────────────
section "Проверка окружения"
[[ "$(id -u)" -eq 0 ]] || error "Запустите скрипт с правами root: sudo bash deploy.sh"
grep -qi "ubuntu" /etc/os-release || warn "Скрипт тестировался на Ubuntu 22.04"

# ── 1. Docker ────────────────────────────────────────────────────────────────
section "Установка Docker"
if command -v docker &>/dev/null; then
    info "Docker уже установлен: $(docker --version)"
else
    apt-get update -q
    apt-get install -y -q ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    info "Docker установлен"
fi

# ── 2. Копирование файлов проекта ────────────────────────────────────────────
section "Копирование файлов проекта"
mkdir -p "$APP_DIR"
# Если скрипт запущен из папки проекта — копируем оттуда
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/server.py" ]]; then
    rsync -a --exclude=venv --exclude=__pycache__ --exclude='*.pyc' \
          --exclude=videos --exclude=output --exclude=tmp \
          --exclude='models/*.bin' \
          --exclude=gemma-4-12B-it-qat-q4_0-unquantized \
          "$SCRIPT_DIR/" "$APP_DIR/"
    info "Файлы скопированы в $APP_DIR"
else
    warn "server.py не найден рядом со скриптом — пропускаем копирование."
    warn "Убедитесь, что файлы проекта уже в $APP_DIR"
fi
cd "$APP_DIR"

# ── 3. .env ──────────────────────────────────────────────────────────────────
section "Настройка .env"
if [[ ! -f "$APP_DIR/.env" ]]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env" 2>/dev/null || touch "$APP_DIR/.env"
fi
if [[ -n "$GEN_API_KEY" ]]; then
    grep -q "^GEN_API_KEY=" "$APP_DIR/.env" \
        && sed -i "s|^GEN_API_KEY=.*|GEN_API_KEY=$GEN_API_KEY|" "$APP_DIR/.env" \
        || echo "GEN_API_KEY=$GEN_API_KEY" >> "$APP_DIR/.env"
    info "GEN_API_KEY записан в .env"
else
    warn "GEN_API_KEY не задан. Отредактируйте $APP_DIR/.env вручную:"
    warn "  nano $APP_DIR/.env"
fi

# ── 4. Модель Whisper ─────────────────────────────────────────────────────────
section "Загрузка модели Whisper ($WHISPER_MODEL)"
mkdir -p "$APP_DIR/models"
MODEL_PATH="$APP_DIR/models/$WHISPER_MODEL"
if [[ -f "$MODEL_PATH" ]] && [[ "$(stat -c%s "$MODEL_PATH")" -gt 1000000 ]]; then
    info "Модель уже скачана — пропускаем."
else
    info "Скачиваем $WHISPER_MODEL (~1.5 GB для medium)..."
    wget -q --show-progress \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WHISPER_MODEL" \
        -O "$MODEL_PATH"
    info "Модель загружена: $MODEL_PATH"
fi

# ── 5. Сборка и запуск ──────────────────────────────────────────────────────
section "Сборка Docker-образа (первый раз ~5–10 мин)"
docker compose build

section "Запуск контейнера"
docker compose up -d
info "Контейнер запущен"

# ── 6. Healthcheck ───────────────────────────────────────────────────────────
section "Проверка работоспособности"
for i in $(seq 1 12); do
    sleep 5
    if curl -sf http://localhost:8000/health | grep -q ok; then
        info "Сервер отвечает на http://localhost:8000"
        SERVER_IP=$(curl -sf https://ipinfo.io/ip 2>/dev/null || echo "<IP сервера>")
        echo -e "\n${GREEN}═══════════════════════════════════════════${NC}"
        echo -e "${GREEN}  Приложение доступно по адресу:${NC}"
        echo -e "${GREEN}  http://$SERVER_IP:8000${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════${NC}\n"
        exit 0
    fi
    echo "  Ожидание запуска... ($i/12)"
done
error "Сервер не ответил за 60 секунд. Проверьте: docker compose logs"
