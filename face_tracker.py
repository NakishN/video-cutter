import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
import cv2
import numpy as np

# Проверяем доступность MediaPipe
try:
    import mediapipe as mp
    _MP_FACE_DETECTION = mp.solutions.face_detection
    HAS_MEDIAPIPE = True
except Exception:
    HAS_MEDIAPIPE = False


def _detect_face_center_mediapipe(img: np.ndarray) -> Optional[int]:
    """Детектирует лицо через MediaPipe Face Detection (устойчив к поворотам головы)."""
    if not HAS_MEDIAPIPE:
        return None
    try:
        h, w, _ = img.shape
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        with _MP_FACE_DETECTION.FaceDetection(model_selection=1, min_detection_confidence=0.45) as detector:
            results = detector.process(rgb)
            if results and results.detections:
                # Берём самое уверенно детекченное лицо
                best_detection = max(
                    results.detections,
                    key=lambda d: d.score[0] if d.score else 0.0
                )
                bbox = best_detection.location_data.relative_bounding_box
                center_x_px = int((bbox.xmin + bbox.width / 2.0) * w)
                return max(0, min(w, center_x_px))
    except Exception as e:
        print(f"MediaPipe detection fallback: {e}")
    return None


def _detect_face_center_haar(img: np.ndarray, face_cascade: cv2.CascadeClassifier) -> Optional[int]:
    """Фоллбек: Детектирует лицо через OpenCV Haar Cascade."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) > 0:
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, w, h = faces[0]
            return x + w // 2
    except Exception:
        pass
    return None


def find_optimal_crop_center_x(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    ffmpeg_bin: str
) -> Optional[int]:
    """
    Анализирует кадры из фрагмента видео и находит медианную X-координату лица.
    Сначала пробоует MediaPipe (высокая точность под углом/при повороте),
    затем откатывается на Haar Cascade.
    """
    try:
        duration = end_sec - start_sec
        if duration <= 0:
            return None
        samples = 7
        interval = duration / (samples + 1)
        timestamps = [start_sec + i * interval for i in range(1, samples + 1)]

        def _extract_frame(t: float) -> Optional[bytes]:
            cmd = [
                ffmpeg_bin, "-y", "-ss", f"{t:.3f}", "-i", str(video_path),
                "-vframes", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"
            ]
            proc = subprocess.run(cmd, capture_output=True)
            return proc.stdout if proc.stdout else None

        with ThreadPoolExecutor(max_workers=samples) as pool:
            raw_frames = list(pool.map(_extract_frame, timestamps))

        # Загружаем каскад Haar на случай фоллбека
        xml_path = None
        if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
            xml_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        if not xml_path or not os.path.exists(xml_path):
            if getattr(sys, "frozen", False):
                xml_path = os.path.join(getattr(sys, "_MEIPASS", ""), 'haarcascade_frontalface_default.xml')
        if not xml_path or not os.path.exists(xml_path):
            xml_path = 'haarcascade_frontalface_default.xml'

        face_cascade = cv2.CascadeClassifier(xml_path) if os.path.exists(xml_path) else None

        face_centers_x = []
        for raw in raw_frames:
            if not raw:
                continue
            np_arr = np.frombuffer(raw, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is None:
                continue

            cx = _detect_face_center_mediapipe(img)
            if cx is None and face_cascade and not face_cascade.empty():
                cx = _detect_face_center_haar(img, face_cascade)

            if cx is not None:
                face_centers_x.append(cx)

        if face_centers_x:
            return int(np.median(face_centers_x))
    except Exception as e:
        print(f"Ошибка во время поиска центра лица: {e}")
    return None

