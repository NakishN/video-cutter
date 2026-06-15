def parse_time_to_seconds(time_str: str) -> float:
    """Конвертирует ЧЧ:ММ:СС или ММ:СС в секунды."""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60 + float(s)
    return float(parts[0])

def parse_srt_time(srt_time_str: str) -> float:
    """Конвертирует ЧЧ:ММ:СС,МММ в секунды."""
    time_part, ms_part = srt_time_str.strip().split(',')
    return parse_time_to_seconds(time_part) + float(ms_part) / 1000.0

def format_srt_time(seconds: float) -> str:
    """Конвертирует секунды в формат ЧЧ:ММ:СС,МММ."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms -= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _fmt_srt_time(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _fmt_timestamp(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
