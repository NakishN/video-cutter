import re
from typing import List, Dict
from time_utils import parse_time_to_seconds, parse_srt_time, format_srt_time

def parse_summary_to_clips(summary_text: str) -> List[Dict]:
    """
    Парсит ответ LLM вида:
    [00:01:20 - 00:01:45] Заголовок | Оценка: 95 | Описание момента
    Также поддерживает старый двухсекционный формат:
    [00:01:20 - 00:01:45] Заголовок | Описание момента
    """
    clips = []
    for line in summary_text.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Регулярное выражение с поддержкой опциональной нумерации строк (например, "1: ")
        # и поддержкой форматов как ЧЧ:ММ:СС, так и ММ:СС
        time_match = re.match(r'^(?:\d+[\.:]\s*)?\[\s*((?:\d{1,2}:)?\d{2}:\d{2})\s*-\s*((?:\d{1,2}:)?\d{2}:\d{2})\s*\]\s*(.+)$', line)
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
            
        clips.append({
            "start_str": start_str,
            "end_str": end_str,
            "start_sec": max(0.0, parse_time_to_seconds(start_str) - 1.5), # padding
            "end_sec": parse_time_to_seconds(end_str) + 2.0,               # padding
            "title": title,
            "score": score,
            "description": description
        })
    return clips

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
