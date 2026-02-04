#!/bin/bash
# Build single-file executable without sudo (uses local cache)

set -e

echo "=== Building Single-File Executable (No Sudo) ==="

# Use local cache directory instead of system cache
export PYINSTALLER_CACHE_DIR="$PWD/.pyinstaller_cache_local"
mkdir -p "$PYINSTALLER_CACHE_DIR"

# Activate venv
source venv_worker/bin/activate

# Build with --onefile flag and skip cache cleanup
echo "Building with --onefile mode (using local cache)..."
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
    --console \
    --log-level=WARN 2>&1 | grep -v "WARNING: Hidden import" | grep -v "INFO: Processing" | tail -100

echo ""
echo "=== Build Complete ==="
if [ -f "build_worker_macos/dist/chaarfm_worker" ]; then
    echo "✅✅✅ Single-file executable created! ✅✅✅"
    ls -lh build_worker_macos/dist/chaarfm_worker
    file build_worker_macos/dist/chaarfm_worker
    echo ""
    echo "To test: ./build_worker_macos/dist/chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_CODE"
else
    echo "❌ Build failed - checking logs..."
    tail -50 build_onefile_output.log 2>/dev/null || echo "No log file found"
    exit 1
fi
