import subprocess
from pathlib import Path
from typing import Optional
from face_tracker import find_optimal_crop_center_x

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
