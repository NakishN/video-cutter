import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict
import cv2
import numpy as np

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
            "start_sec": parse_time_to_seconds(start_str),
            "end_sec": parse_time_to_seconds(end_str),
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

def escape_ffmpeg_subtitles_path(p: Path) -> str:
    """Экранирует путь к файлу субтитров для фильтра FFmpeg subtitles."""
    s = str(p.absolute())
    s = s.replace("\\", "/")  # Для кроссплатформенности
    s = s.replace(":", "\\:")
    s = s.replace("'", "'\\\\''")
    return s

def _probe_resolution(media_path: Path, ffprobe_bin: str) -> tuple[int, int]:
    """Возвращает кортеж (ширина, высота) видео."""
    cmd = [
        ffprobe_bin, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(media_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        w_str, h_str = result.stdout.strip().split('x')
        return int(w_str), int(h_str)
    except Exception:
        return 1920, 1080  # fallback в Full HD

def find_optimal_crop_center_x(video_path: Path, start_sec: float, end_sec: float, ffmpeg_bin: str) -> Optional[int]:
    """Анализирует кадры и находит медианную X-координату лица (для Рилсов/Mootion)."""
    try:
        import os
        import sys
        duration = end_sec - start_sec
        if duration <= 0: return None
        samples = 5
        interval = duration / (samples + 1)
        
        xml_path = None
        # Сначала пробуем стандартный путь OpenCV
        if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
            xml_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        
        # Если файл не найден, пробуем найти в папке сборки PyInstaller
        if not xml_path or not os.path.exists(xml_path):
            if getattr(sys, "frozen", False):
                xml_path = os.path.join(sys._MEIPASS, 'haarcascade_frontalface_default.xml')
                
        # Если всё ещё нет, пробуем в текущей папке
        if not xml_path or not os.path.exists(xml_path):
            xml_path = 'haarcascade_frontalface_default.xml'
            
        if not os.path.exists(xml_path):
            return None
            
        face_cascade = cv2.CascadeClassifier(xml_path)
        if face_cascade.empty():
            return None
            
        face_centers_x = []
        
        for i in range(1, samples + 1):
            t = start_sec + i * interval
            cmd = [
                ffmpeg_bin, "-y", "-ss", str(t), "-i", str(video_path),
                "-vframes", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"
            ]
            proc = subprocess.run(cmd, capture_output=True)
            if not proc.stdout: continue
            
            np_arr = np.frombuffer(proc.stdout, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is None: continue
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) > 0:
                # Найти самое большое лицо
                faces = sorted(faces, key=lambda x: x[2]*x[3], reverse=True)
                x, y, w, h = faces[0]
                face_centers_x.append(x + w//2)
                
        if face_centers_x:
            return int(np.median(face_centers_x))
    except Exception as e:
        print(f"Ошибка во время поиска центра лица: {e}")
    return None


def extract_screenshot(video_path: Path, output_jpeg_path: Path, ffmpeg_bin: str) -> None:
    """Извлекает кадр из видео на 10-й (или 1-й) секунде для Vision-анализа."""
    # Пробуем взять кадр на 10-й секунде
    cmd = [
        ffmpeg_bin, "-y",
        "-ss", "00:00:10",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_jpeg_path)
    ]
    subprocess.run(cmd, capture_output=True)
    if not output_jpeg_path.is_file():
        # Если не вышло (короткое видео), берем на 1-й секунде
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", "00:00:01",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_jpeg_path)
        ]
        subprocess.run(cmd, capture_output=True)

_has_nvenc = None

def check_nvenc_supported(ffmpeg_bin: str) -> bool:
    global _has_nvenc
    if _has_nvenc is not None:
        return _has_nvenc
    try:
        result = subprocess.run([ffmpeg_bin, "-encoders"], capture_output=True, text=True, check=False)
        _has_nvenc = "h264_nvenc" in result.stdout
    except Exception:
        _has_nvenc = False
    return _has_nvenc

def has_video_stream(media_path: Path, ffprobe_bin: str) -> bool:
    """Проверяет, есть ли в медиафайле видеопоток."""
    cmd = [
        ffprobe_bin, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1",
        str(media_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip() == "video"

def cut_and_crop_video(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    clip_srt_path: Optional[Path],
    output_clip_path: Path,
    ffmpeg_bin: str,
    ffprobe_bin: str = "ffprobe",
    vtuber_center_x_percent: float = 50.0,
    layout: str = "vertical_split",
    use_gpu: bool = True
) -> None:
    """
    Вырезает фрагмент видео, кадрирует его в соответствии с выбранным layout,
    и впекает субтитры. Использует GPU (NVENC) при наличии и разрешения,
    иначе откатывается на CPU (libx264). Если видеопотока нет, то вырезается только аудио.
    """
    has_video = has_video_stream(video_path, ffprobe_bin)
    
    if not has_video:
        # Аудио-нарезка (без видео)
        approx_start = max(0.0, start_sec - 60.0)
        exact_offset = start_sec - approx_start
        duration = end_sec - start_sec
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", str(approx_start),
            "-i", str(video_path),
            "-ss", str(exact_offset),
            "-t", str(duration),
            "-vn",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_clip_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio cut failed: {result.stderr}")
        return

    video_filters = []
    filter_complex = None
    
    # Получаем исходные размеры видео
    iw, ih = _probe_resolution(video_path, ffprobe_bin)
    
    # Если видео вертикальное или квадратное, кроп 9:16 не имеет смысла
    is_vertical = iw <= ih
    
    if is_vertical or layout == "widescreen":
        if clip_srt_path and clip_srt_path.is_file():
            escaped_srt = escape_ffmpeg_subtitles_path(clip_srt_path)
            style = (
                "Fontname=Arial,Fontsize=18,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "Outline=2,Alignment=2,MarginV=25"
            )
            video_filters.append(f"subtitles='{escaped_srt}':force_style='{style}'")
        vf_arg = ",".join(video_filters) if video_filters else None
    else:
        # Вычисляем параметры кропа 9:16 (ширина cw, высота ih)
        cw = int(ih * 9 / 16)
        if cw % 2 != 0:
            cw += 1
            
        if layout == "vertical_center":
            cx = int(iw / 2)
            x_left = cx - int(cw / 2)
            x_left = max(0, min(iw - cw, x_left))
            video_filters.append(f"crop={cw}:{ih}:{x_left}:0")
            if clip_srt_path and clip_srt_path.is_file():
                escaped_srt = escape_ffmpeg_subtitles_path(clip_srt_path)
                style = (
                    "Fontname=Arial,Fontsize=18,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "Outline=2,Alignment=2,MarginV=25"
                )
                video_filters.append(f"subtitles='{escaped_srt}':force_style='{style}'")
            vf_arg = ",".join(video_filters)
            
        elif layout == "vertical_vtuber":
            cx = int(iw * vtuber_center_x_percent / 100.0)
            x_left = cx - int(cw / 2)
            x_left = max(0, min(iw - cw, x_left))
            video_filters.append(f"crop={cw}:{ih}:{x_left}:0")
            if clip_srt_path and clip_srt_path.is_file():
                escaped_srt = escape_ffmpeg_subtitles_path(clip_srt_path)
                style = (
                    "Fontname=Arial,Fontsize=18,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "Outline=2,Alignment=2,MarginV=25"
                )
                video_filters.append(f"subtitles='{escaped_srt}':force_style='{style}'")
            vf_arg = ",".join(video_filters)
            
        elif layout == "vertical_reels":
            # Используем ИИ для отслеживания лица
            cx = find_optimal_crop_center_x(video_path, start_sec, end_sec, ffmpeg_bin)
            if cx is None:
                cx = int(iw / 2) # фоллбек в центр
            
            x_left = cx - int(cw / 2)
            x_left = max(0, min(iw - cw, x_left))
            video_filters.append(f"crop={cw}:{ih}:{x_left}:0")
            if clip_srt_path and clip_srt_path.is_file():
                escaped_srt = escape_ffmpeg_subtitles_path(clip_srt_path)
                style = (
                    "Fontname=Arial,Fontsize=18,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "Outline=2,Alignment=2,MarginV=25"
                )
                video_filters.append(f"subtitles='{escaped_srt}':force_style='{style}'")
            vf_arg = ",".join(video_filters)
            
        elif layout == "vertical_split":
            # Stacked layout (gameplay top 60%, Vtuber bottom 40%)
            gh = int(ih * 0.6)
            if gh % 2 != 0:
                gh += 1
            vh = ih - gh
            if vh % 2 != 0:
                vh += 1
                ih = gh + vh # adjust total height to remain even
            
            # Центр для геймплея (сверху, чтобы избежать наложения Втубера)
            g_x = int((iw - cw) / 2)
            g_x = max(0, min(iw - cw, g_x))
            g_y = 0
            
            # Втубер (снизу экрана, где он обычно находится)
            cx = int(iw * vtuber_center_x_percent / 100.0)
            v_x = cx - int(cw / 2)
            v_x = max(0, min(iw - cw, v_x))
            v_y = ih - vh
            
            filter_complex = (
                f"[0:v]split=2[g][vt];"
                f"[g]crop={cw}:{gh}:{g_x}:{g_y}[top];"
                f"[vt]crop={cw}:{vh}:{v_x}:{v_y}[bottom];"
                f"[top][bottom]vstack=inputs=2[v_stacked]"
            )
            
            if clip_srt_path and clip_srt_path.is_file():
                escaped_srt = escape_ffmpeg_subtitles_path(clip_srt_path)
                style = (
                    "Fontname=Arial,Fontsize=18,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "Outline=2,Alignment=2,MarginV=25"
                )
                filter_complex += f";[v_stacked]subtitles='{escaped_srt}':force_style='{style}'[v]"
            else:
                filter_complex += f";[v_stacked]null[v]"
            
            vf_arg = None
        else:
            # Fallback
            cx = int(iw / 2)
            x_left = cx - int(cw / 2)
            x_left = max(0, min(iw - cw, x_left))
            video_filters.append(f"crop={cw}:{ih}:{x_left}:0")
            if clip_srt_path and clip_srt_path.is_file():
                escaped_srt = escape_ffmpeg_subtitles_path(clip_srt_path)
                style = (
                    "Fontname=Arial,Fontsize=18,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "Outline=2,Alignment=2,MarginV=25"
                )
                video_filters.append(f"subtitles='{escaped_srt}':force_style='{style}'")
            vf_arg = ",".join(video_filters)
            
    # Двойной поиск (двойной seek) для максимальной скорости и точности:
    # 1. Быстрый поиск до точки (start_sec - 60 секунд) перед -i
    # 2. Точный поиск на оставшиеся секунды после -i
    approx_start = max(0.0, start_sec - 60.0)
    exact_offset = start_sec - approx_start
    duration = end_sec - start_sec

    # Базовая часть команды для CPU
    cmd_base_cpu = [
        ffmpeg_bin, "-y",
        "-ss", str(approx_start),
        "-i", str(video_path),
        "-ss", str(exact_offset),
        "-t", str(duration),
    ]

    attempt_gpu = use_gpu and check_nvenc_supported(ffmpeg_bin)
    
    if attempt_gpu:
        # Для GPU добавляем аппаратное декодирование (-hwaccel cuda) перед -i
        cmd_gpu = [
            ffmpeg_bin, "-y",
            "-hwaccel", "cuda",
            "-ss", str(approx_start),
            "-i", str(video_path),
            "-ss", str(exact_offset),
            "-t", str(duration),
        ]
        
        if filter_complex:
            cmd_gpu.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?"])
        elif vf_arg:
            cmd_gpu.extend(["-vf", vf_arg])
            
        cmd_gpu.extend([
            "-c:v", "h264_nvenc",
            "-preset", "p3",
            "-cq", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_clip_path)
        ])
        
        result = subprocess.run(cmd_gpu, capture_output=True, text=True)
        if result.returncode == 0:
            return
        print(f"GPU encoding failed (return code {result.returncode}), falling back to CPU. Stderr: {result.stderr}")
        
    # Откат на CPU (libx264)
    cmd_cpu = list(cmd_base_cpu)
    if filter_complex:
        cmd_cpu.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?"])
    elif vf_arg:
        cmd_cpu.extend(["-vf", vf_arg])
        
    cmd_cpu.extend([
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_clip_path)
    ])
    
    result = subprocess.run(cmd_cpu, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed with return code {result.returncode}.\nStderr: {result.stderr}")
