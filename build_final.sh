#!/bin/bash
# Build single-file executable - final version (no cache cleanup)

set -e

echo "=== Building Single-File Executable ==="

# Activate venv
source venv_worker/bin/activate

# Build WITHOUT --clean to avoid cache permission issues
# The cache issue only affects cleanup, not the actual build
echo "Building with --onefile mode (skipping cache cleanup)..."
pyinstaller remote_worker.py \
    --name chaarfm_worker \
    --onefile \
    --distpath build_worker_macos/dist \
    --workpath build_worker_macos/build \
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
    echo "✅✅✅ SUCCESS! Single-file executable created! ✅✅✅"
    ls -lh build_worker_macos/dist/chaarfm_worker
    file build_worker_macos/dist/chaarfm_worker
    echo ""
    echo "Executable location: build_worker_macos/dist/chaarfm_worker"
    echo ""
    echo "To test:"
    echo "  ./build_worker_macos/dist/chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_CODE"
else
    echo "❌ Build failed - executable not found"
    exit 1
fi
