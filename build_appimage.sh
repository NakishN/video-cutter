#!/usr/bin/env bash
# ==============================================================================
# build_appimage.sh — Скрипт сборки видео-нарезчика в автономный .AppImage (Linux)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "  Сборка автономного Linux AppImage для AI Нарезчик видео "
echo "=========================================================="

# 1. Активация/проверка виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 2. Установка PyInstaller при необходимости
if ! command -v pyinstaller &> /dev/null; then
    echo "[BUILD] Установка PyInstaller..."
    pip install pyinstaller
fi

# 3. Сборка PyInstaller дистрибутива
echo "[BUILD] Компиляция проекта через PyInstaller..."
pyinstaller --noconfirm video_cutter.spec --clean

# 4. Проверка и загрузка appimagetool
APPIMAGETOOL="$SCRIPT_DIR/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "[BUILD] Загрузка appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage" -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

# 5. Создание структуры AppDir
APPDIR="$SCRIPT_DIR/dist/VideoCutter.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Копируем результаты сборки PyInstaller в AppDir
cp -r "$SCRIPT_DIR/dist/VideoCutter/"* "$APPDIR/usr/bin/"

# Создаем Desktop файл
cat << 'EOF' > "$APPDIR/VideoCutter.desktop"
[Desktop Entry]
Name=VideoCutter
Comment=AI Video Cutter & Transcriber for VTubers and Content Creators
Exec=VideoCutter
Icon=video_cutter
Type=Application
Categories=Video;AudioVideo;AudioVideoEditing;
Terminal=true
EOF

# Иконка-заглушка для AppImage
if [ ! -f "$APPDIR/video_cutter.png" ]; then
    # Простой SVG/PNGплейсхолдер для десктопа
    cat << 'EOF' > "$APPDIR/video_cutter.svg"
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 24 24" fill="#6366f1">
  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9 13v-2.5L7.5 15l-1.42-1.42L8.5 11 6.08 8.58 7.5 7.16 10 9.66V7h2v2.66l2.5-2.5 1.42 1.42L13.5 11l2.42 2.42-1.42 1.42L12 12.5V16h-2z"/>
</svg>
EOF
    cp "$APPDIR/video_cutter.svg" "$APPDIR/video_cutter.svg"
    cp "$APPDIR/video_cutter.svg" "$APPDIR/.DirIcon"
fi

# Создаем AppRun скрипт входа
cat << 'EOF' > "$APPDIR/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "${ZERO:-$0}")")"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/bin:$LD_LIBRARY_PATH"
exec "$HERE/usr/bin/VideoCutter" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# 6. Упаковка в AppImage
echo "[BUILD] Генерация файла VideoCutter-x86_64.AppImage..."
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$SCRIPT_DIR/dist/VideoCutter-x86_64.AppImage"

echo ""
echo "=========================================================="
echo "  СБОРКА УСПЕШНО ЗАВЕРШЕНА!                               "
echo "  Готовый AppImage пакет сохранен в:                      "
echo "  dist/VideoCutter-x86_64.AppImage                        "
echo "=========================================================="
