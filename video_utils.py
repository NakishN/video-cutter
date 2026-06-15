"""
video_utils.py — Совместимый слой обратной совместимости.
Все функции перенесены в соответствующие специализированные модули.
"""

from time_utils import parse_time_to_seconds, parse_srt_time, format_srt_time
from clip_utils import parse_summary_to_clips, extract_subtitles_for_clip
from face_tracker import find_optimal_crop_center_x
from video_editor import (
    escape_ffmpeg_subtitles_path,
    check_nvenc_supported,
    has_video_stream,
    extract_screenshot,
    cut_and_crop_video
)
