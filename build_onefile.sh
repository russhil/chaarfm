#!/bin/bash
# Build single-file executable (onefile mode)

set -e

echo "=== Building Single-File Executable ==="

# Completely clear the corrupted cache
echo "Clearing PyInstaller cache..."
sudo rm -rf "/Users/russhil/Library/Application Support/pyinstaller" 2>/dev/null || true
sudo mkdir -p "/Users/russhil/Library/Application Support/pyinstaller"
sudo chown -R $(whoami):staff "/Users/russhil/Library/Application Support/pyinstaller"
chmod -R 755 "/Users/russhil/Library/Application Support/pyinstaller"
echo "Cache cleared."

# Activate venv
source venv_worker/bin/activate

# Build with --onefile flag (simpler, avoids PKG step)
echo "Building with --onefile mode..."
pyinstaller remote_worker.py \
    --name chaarfm_worker \
    --onefile \
    --distpath build_worker_macos/dist \
    --workpath build_worker_macos/build \
    --clean \
    --noconfirm \
    --hidden-import websockets \
    --hidden-import websockets.client \
    --hidden-import yt_dlp \
    --hidden-import tensorflow \
    --hidden-import essentia \
    --hidden-import essentia.standard \
    --hidden-import mutagen \
    --hidden-import librosa \
    --hidden-import certifi \
    --add-data "populate_youtube_universe.py:." \
    --add-data "music_pipeline/vectorizer.py:music_pipeline" \
    --add-data "music_pipeline/config.py:music_pipeline" \
    --console

echo ""
echo "=== Build Complete ==="
if [ -f "build_worker_macos/dist/chaarfm_worker" ]; then
    echo "✅ Single-file executable created!"
    ls -lh build_worker_macos/dist/chaarfm_worker
    file build_worker_macos/dist/chaarfm_worker
else
    echo "❌ Build failed - executable not found"
    exit 1
fi
