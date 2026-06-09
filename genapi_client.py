"""Клиент GenAPI (https://gen-api.ru/docs) для облачных LLM."""

from __future__ import annotations

import time
from typing import Any

import httpx

GENAPI_BASE = "https://api.gen-api.ru/api/v1"


def _extract_text(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, str) and output.strip():
        return output.strip()

    result = payload.get("result")
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, str):
            return first.strip()
        if isinstance(first, dict):
            for key in ("text", "content", "message"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    full = payload.get("full_response")
    if isinstance(full, list):
        parts: list[str] = []
        for item in full:
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    parts.append(content)
            for key in ("text", "content"):
                value = item.get(key)
                if isinstance(value, str):
                    parts.append(value)
        joined = "\n".join(p.strip() for p in parts if p.strip())
        if joined:
            return joined

    raise RuntimeError(f"GenAPI: не удалось извлечь текст из ответа: {payload}")


SUMMARY_PROMPT = """\
Ты — редактор видеоконтента. Проанализируй транскрипт видео с таймкодами и найди самые интересные моменты для нарезки клипов.

Задача:
1. Выбери 5–15 самых интересных, эмоциональных, смешных или ключевых фрагментов
2. Для каждого укажи таймкод начала момента (формат ЧЧ:ММ:СС)
3. Кратко опиши, что происходит и почему это стоит вырезать в клип

Формат ответа (строго, каждый момент с новой строки):
[ЧЧ:ММ:СС] Описание момента (1–2 предложения)

Правила:
- Используй только таймкоды из транскрипта ниже, не выдумывай время
- Игнорируй технические повторы, титры, музыку без речи
- Пиши на русском языке
- Сортируй моменты по времени (от начала к концу)
- Не добавляй вступлений и заключений — только список моментов

Транскрипт с таймкодами:
{transcript}"""


def summarize(
    transcript: str,
    api_key: str,
    network_id: str = "gemini-2-5-flash-lite",
    *,
    transcript_srt: str = "",
    poll_interval: float = 3.0,
    max_wait: float = 600.0,
) -> str:
    """Интересные моменты с таймкодами через GenAPI (GPT, Gemini и др.)."""
    from transcript_utils import prepare_transcript_for_summary

    if not api_key:
        raise RuntimeError("GEN_API_KEY не задан. Добавьте ключ в файл .env")

    prepared = prepare_transcript_for_summary(transcript, transcript_srt)
    if not prepared.strip():
        raise RuntimeError("Транскрипт пуст после очистки")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    prompt = SUMMARY_PROMPT.format(transcript=prepared)
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "is_sync": True,
    }

    # Не используем системный SOCKS/HTTP-прокси (Clash/V2Ray и т.п.):
    # без пакета socksio httpx падает с «Unknown scheme for proxy URL socks://…»
    with httpx.Client(
        timeout=httpx.Timeout(300.0, connect=30.0),
        trust_env=False,
    ) as client:
        create = client.post(f"{GENAPI_BASE}/networks/{network_id}", json=body, headers=headers)
        if create.status_code == 401:
            raise RuntimeError("GenAPI: неверный API-ключ")
        create.raise_for_status()
        data = create.json()

        if data.get("status") == "success":
            return _extract_text(data)

        request_id = data.get("request_id")
        if not request_id:
            raise RuntimeError(f"GenAPI: неожиданный ответ: {data}")

        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            poll = client.get(f"{GENAPI_BASE}/request/get/{request_id}", headers=headers)
            poll.raise_for_status()
            result = poll.json()
            status = result.get("status")
            if status == "success":
                return _extract_text(result)
            if status == "failed":
                raise RuntimeError(f"GenAPI: задача не выполнена — {result}")

        raise RuntimeError("GenAPI: превышено время ожидания результата")
