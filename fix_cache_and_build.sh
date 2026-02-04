#!/bin/bash
# Fix PyInstaller cache permissions and build

set -e

echo "=== Fixing PyInstaller Cache ==="

# Clear cache with sudo
sudo rm -rf "/Users/russhil/Library/Application Support/pyinstaller"
sudo mkdir -p "/Users/russhil/Library/Application Support/pyinstaller"
sudo chown -R $(whoami) "/Users/russhil/Library/Application Support/pyinstaller"
chmod -R 755 "/Users/russhil/Library/Application Support/pyinstaller"

echo "Cache fixed. Starting build..."

# Activate venv and build
source venv_worker/bin/activate
pyinstaller build_worker.spec \
    --distpath build_worker_macos/dist \
    --workpath build_worker_macos/build \
    --clean \
    --noconfirm

echo ""
echo "=== Build Complete ==="
if [ -f "build_worker_macos/dist/chaarfm_worker" ]; then
    echo "✅ Executable created: build_worker_macos/dist/chaarfm_worker"
    ls -lh build_worker_macos/dist/chaarfm_worker
fi
