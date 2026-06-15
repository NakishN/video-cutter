import os
import sys
import subprocess
from pathlib import Path
from typing import Optional
import cv2
import numpy as np

def find_optimal_crop_center_x(video_path: Path, start_sec: float, end_sec: float, ffmpeg_bin: str) -> Optional[int]:
    """Анализирует кадры и находит медианную X-координату лица (для Рилсов/Mootion)."""
    try:
        duration = end_sec - start_sec
        if duration <= 0:
            return None
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
            if not proc.stdout:
                continue
            
            np_arr = np.frombuffer(proc.stdout, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            
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
