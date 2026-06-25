import re
from typing import List, Dict, Optional
from time_utils import parse_time_to_seconds, parse_srt_time, format_srt_time


# ---------------------------------------------------------------------------
# SRT → список (start_sec, end_sec) для умной привязки границ
# ---------------------------------------------------------------------------

def _parse_srt_entries(srt_text: str) -> List[tuple]:
    """Парсит SRT и возвращает список (start_sec, end_sec, text)."""
    if not srt_text.strip():
        return []
    block_re = re.compile(
        r'\d+\s*\n'
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'
        r'((?:.*(?:\n(?!\d+\s*\n|\Z).*)*))'
    )
    entries = []
    for m in block_re.finditer(srt_text):
        try:
            s = parse_srt_time(m.group(1))
            e = parse_srt_time(m.group(2))
            entries.append((s, e, m.group(3).strip()))
        except Exception:
            pass
    return entries


def smart_clip_boundaries(
    raw_start: float,
    raw_end: float,
    srt_entries: List[tuple],
    *,
    pre_padding: float = 0.4,      # тишина перед первой репликой
    post_padding: float = 0.6,     # тишина после последней реплики
    max_snap_before: float = 3.0,  # макс. насколько двинуть старт назад
    max_snap_after: float = 3.0,   # макс. насколько двинуть конец вперёд
    max_duration: float = 30.0,    # жёсткий потолок длины клипа
    min_duration: float = 10.0,    # минимальная длина клипа
) -> Optional[tuple]:
    """
    Умная привязка границ клипа к репликам из SRT.

    Алгоритм:
      1. Ищет реплику SRT, начало которой ближайшее к raw_start
         (в диапазоне [raw_start - max_snap_before, raw_start + max_snap_before]).
         Если нашли — сдвигаем старт к ней (минус pre_padding).
      2. Ищет реплику SRT, конец которой ближайший к raw_end
         (в диапазоне [raw_end - max_snap_after, raw_end + max_snap_after]).
         Если нашли — сдвигаем конец к ней (плюс post_padding).
      3. Применяет ограничения длины.
      4. Возвращает None если клип слишком короткий.
    """
    if not srt_entries:
        # Нет SRT — используем старые паддинги
        start = max(0.0, raw_start - 1.5)
        end = raw_end + 2.0
        if end - start > max_duration:
            end = start + max_duration
        if end - start < min_duration:
            return None
        return start, end

    # --- Привязка старта ---
    best_start = raw_start
    best_start_dist = float("inf")
    for s, e, _ in srt_entries:
        if raw_start - max_snap_before <= s <= raw_start + max_snap_before:
            dist = abs(s - raw_start)
            if dist < best_start_dist:
                best_start_dist = dist
                best_start = s

    # --- Привязка конца ---
    best_end = raw_end
    best_end_dist = float("inf")
    for s, e, _ in srt_entries:
        if raw_end - max_snap_after <= e <= raw_end + max_snap_after:
            dist = abs(e - raw_end)
            if dist < best_end_dist:
                best_end_dist = dist
                best_end = e

    final_start = max(0.0, best_start - pre_padding)
    final_end = best_end + post_padding

    # Если привязка дала слишком длинный клип — ищем хорошую паузу для обрезки
    if final_end - final_start > max_duration:
        target = final_start + max_duration
        # Ищем конец реплики непосредственно до target
        last_good_end = final_start + max_duration
        for s, e, _ in srt_entries:
            if e <= target and e > final_start:
                last_good_end = e
        final_end = last_good_end + post_padding
        # Окончательный жёсткий потолок
        if final_end - final_start > max_duration:
            final_end = final_start + max_duration

    if final_end - final_start < min_duration:
        return None

    return final_start, final_end


# ---------------------------------------------------------------------------
# Дедупликация перекрывающихся клипов
# ---------------------------------------------------------------------------

def deduplicate_clips(clips: List[Dict], min_gap: float = 3.0) -> List[Dict]:
    """
    Убирает перекрывающиеся клипы (с запасом min_gap секунд).
    При конфликте оставляет клип с бо́льшим score.
    Возвращает список, отсортированный по времени.
    """
    # Сортируем по score убывающему, чтобы первый greedy-выбор = лучший
    ranked = sorted(clips, key=lambda x: x.get("score", 0), reverse=True)
    accepted: List[Dict] = []
    for clip in ranked:
        cs = clip["start_sec"]
        ce = clip["end_sec"]
        overlap = False
        for kept in accepted:
            ks = kept["start_sec"]
            ke = kept["end_sec"]
            # Клипы пересекаются если не (ce + gap <= ks или cs >= ke + gap)
            if not (ce + min_gap <= ks or cs >= ke + min_gap):
                overlap = True
                break
        if not overlap:
            accepted.append(clip)
    # Возвращаем в хронологическом порядке
    return sorted(accepted, key=lambda x: x["start_sec"])


# ---------------------------------------------------------------------------
# Основной парсер ответа LLM
# ---------------------------------------------------------------------------

def parse_summary_to_clips(
    summary_text: str,
    transcript_srt: str = "",
    max_clip_sec: float = 30.0,
    min_clip_sec: float = 10.0,
) -> List[Dict]:
    """
    Парсит ответ LLM вида:
    [00:01:20 - 00:01:45] Заголовок | Оценка: 95 | Описание момента
    Также поддерживает старый двухсекционный формат:
    [00:01:20 - 00:01:45] Заголовок | Описание момента

    Если передан transcript_srt — применяет умную привязку границ
    к ближайшим репликам (smart_clip_boundaries).
    После парсинга устраняет перекрытия (deduplicate_clips).
    """
    # Один раз парсим SRT-записи для умной привязки
    srt_entries = _parse_srt_entries(transcript_srt) if transcript_srt else []

    clips = []
    for line in summary_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Поддерживаем опциональную нумерацию "1: [...]" и форматы ЧЧ:ММ:СС / ММ:СС
        time_match = re.match(
            r'^(?:\d+[\.:\)]\s*)?\[\s*((?:\d{1,2}:)?\d{2}:\d{2})\s*-\s*((?:\d{1,2}:)?\d{2}:\d{2})\s*\]\s*(.+)$',
            line
        )
        if not time_match:
            continue

        start_str, end_str, rest = time_match.groups()

        parts = [p.strip() for p in rest.split('|')]
        title = parts[0]
        score = 80
        description = ""

        if len(parts) == 2:
            description = parts[1]
        elif len(parts) >= 3:
            score_part = parts[1]
            description = parts[2]
            score_match = re.search(r'(\d+)', score_part)
            if score_match:
                score = int(score_match.group(1))
        else:
            description = rest

        raw_start = parse_time_to_seconds(start_str)
        raw_end = parse_time_to_seconds(end_str)

        # Умная привязка к субтитрам (или фоллбек на фиксированные паддинги)
        result = smart_clip_boundaries(
            raw_start, raw_end, srt_entries,
            max_duration=max_clip_sec,
            min_duration=min_clip_sec,
        )
        if result is None:
            continue  # клип слишком короткий — пропускаем
        start_sec, end_sec = result

        clips.append({
            "start_str": start_str,
            "end_str": end_str,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "title": title,
            "score": score,
            "description": description,
        })

    # Убираем перекрывающиеся клипы
    clips = deduplicate_clips(clips)
    return clips


# ---------------------------------------------------------------------------
# Извлечение субтитров для клипа
# ---------------------------------------------------------------------------

def extract_subtitles_for_clip(full_srt_text: str, start_sec: float, end_sec: float) -> str:
    """
    Находит все блоки субтитров, которые попадают в интервал [start_sec, end_sec],
    и смещает их тайминги так, чтобы они начинались с 0.
    """
    if not full_srt_text.strip():
        return ""

    # Регулярка для блоков SRT
    block_re = re.compile(
        r'(\d+)\s*\n'
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'
        r'((?:.*(?:\n(?!\d+\s*\n|\Z).*)*))'
    )

    new_blocks = []
    idx = 1
    for match in block_re.finditer(full_srt_text):
        s_str, e_str, text = match.group(2), match.group(3), match.group(4)
        try:
            s_sec = parse_srt_time(s_str)
            e_sec = parse_srt_time(e_str)
        except Exception:
            continue

        # Пересекаются ли интервалы?
        if s_sec < end_sec and e_sec > start_sec:
            new_s = max(0.0, s_sec - start_sec)
            new_e = max(0.0, e_sec - start_sec)
            if new_e > new_s:
                new_blocks.append(
                    f"{idx}\n"
                    f"{format_srt_time(new_s)} --> {format_srt_time(new_e)}\n"
                    f"{text.strip()}\n"
                )
                idx += 1

    return "\n".join(new_blocks)
