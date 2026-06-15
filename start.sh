#!/usr/bin/env bash
# Запуск сервера без проблем с socks:// в переменных окружения VPN.
set -euo pipefail
cd "$(dirname "$0")"

# socks:// без версии ломает pip/requests; для Clash/V2Ray обычно нужен socks5://
for var in ALL_PROXY all_proxy HTTP_PROXY http_proxy HTTPS_PROXY https_proxy \
           SOCKS_PROXY socks_proxy SOCKS5_PROXY socks5_proxy; do
  val="${!var:-}"
  if [[ "$val" == socks://* ]]; then
    export "$var=socks5://${val#socks://}"
  fi
done

source venv/bin/activate
exec uvicorn server:app --host 0.0.0.0 --port 8000 --loop asyncio
