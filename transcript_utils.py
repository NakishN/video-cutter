"""Подготовка транскрипта для резюме с таймкодами."""

from __future__ import annotations

import re
from collections import Counter

# Типичный мусор из вшитых субтитров YouTube/TV
_GARBAGE_PATTERNS = re.compile(
    r"(?i)"
    r"(редактор\s+субтитров|корректор|субтитр|перевод|озвуч|"
    r"©|copyright|all\s+rights\s+reserved|"
    r"^\s*[\.\…]+\s*$|^\s*[\-–—]+\s*$)"
)

_SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"((?:.*(?:\n(?!\d+\s*\n|\Z).*)*))",
    re.MULTILINE,
)


def _srt_time_to_hms(srt_time: str) -> str:
    """00:01:23,456 -> 00:01:23"""
    return srt_time.split(",")[0]


def _is_garbage_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) < 2:
        return True
    return bool(_GARBAGE_PATTERNS.search(stripped))


def _detect_repeated_garbage(lines: list[str], *, min_count: int = 5) -> set[str]:
    """Строки, которые повторяются слишком часто — скорее всего артефакт субтитров."""
    normalized = [ln.strip().lower() for ln in lines if ln.strip()]
    counts = Counter(normalized)
    return {text for text, count in counts.items() if count >= min_count and len(text) < 80}


def parse_srt(srt_text: str) -> list[tuple[str, str, str]]:
    """Парсит SRT в список (start_hms, end_hms, text)."""
    entries: list[tuple[str, str, str]] = []
    for match in _SRT_BLOCK_RE.finditer(srt_text):
        start = _srt_time_to_hms(match.group(2))
        end = _srt_time_to_hms(match.group(3))
        text = match.group(4).strip().replace("\n", " ")
        entries.append((start, end, text))
    return entries


def clean_transcript_lines(lines: list[str]) -> list[str]:
    """Убирает мусор и частые повторы из списка строк."""
    repeated = _detect_repeated_garbage(lines)
    cleaned: list[str] = []
    prev = ""
    for line in lines:
        text = line.strip()
        if not text or _is_garbage_line(text):
            continue
        if text.lower() in repeated:
            continue
        if text == prev:
            continue
        cleaned.append(text)
        prev = text
    return cleaned


def srt_to_timestamped_text(srt_text: str, *, max_chars: int = 80000) -> str:
    """Конвертирует SRT в компактный текст вида [ЧЧ:ММ:СС] реплика."""
    entries = parse_srt(srt_text)
    if not entries:
        return ""

    all_texts = [text for _, _, text in entries]
    repeated = _detect_repeated_garbage(all_texts)

    lines: list[str] = []
    prev_text = ""
    for start, _end, text in entries:
        text = text.strip()
        if not text or _is_garbage_line(text):
            continue
        if text.lower() in repeated:
            continue
        if text == prev_text:
            continue
        lines.append(f"[{start}] {text}")
        prev_text = text

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n… (транскрипт обрезан)"
    return result


def prepare_transcript_for_summary(transcript: str, transcript_srt: str = "") -> str:
    """
    Готовит текст для LLM: предпочитает SRT с таймкодами,
    иначе очищает plain-текст.
    """
    if transcript_srt.strip():
        timestamped = srt_to_timestamped_text(transcript_srt)
        if timestamped.strip():
            return timestamped

    lines = clean_transcript_lines(transcript.splitlines())
    result = "\n".join(lines)
    if len(result) > 80000:
        result = result[:80000] + "\n… (транскрипт обрезан)"
    return result
