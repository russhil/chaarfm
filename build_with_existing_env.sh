#!/bin/bash
# Build script that uses existing Python environment
# Tries to use system packages if available

set -e

echo "=== Building ChaarFM Remote Worker (Using Existing Environment) ==="

# Check for PyInstaller
PYINSTALLER_CMD=""
if command -v pyinstaller &> /dev/null; then
    PYINSTALLER_CMD="pyinstaller"
    echo "Found pyinstaller in PATH"
elif python3 -m PyInstaller --version &> /dev/null 2>&1; then
    PYINSTALLER_CMD="python3 -m PyInstaller"
    echo "Found PyInstaller as Python module"
else
    echo "ERROR: PyInstaller not found!"
    echo ""
    echo "Please install PyInstaller first:"
    echo "  pip3 install pyinstaller"
    echo ""
    echo "Or if you have network issues, try:"
    echo "  pip3 install --index-url https://pypi.org/simple pyinstaller"
    exit 1
fi

# Check for required packages
echo "Checking for required packages..."
MISSING_PACKAGES=()
python3 -c "import websockets" 2>/dev/null || MISSING_PACKAGES+=("websockets")
python3 -c "import requests" 2>/dev/null || MISSING_PACKAGES+=("requests")
python3 -c "import yt_dlp" 2>/dev/null || MISSING_PACKAGES+=("yt-dlp")
python3 -c "import tensorflow" 2>/dev/null || MISSING_PACKAGES+=("tensorflow")
python3 -c "import essentia" 2>/dev/null || MISSING_PACKAGES+=("essentia")

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "WARNING: Missing packages: ${MISSING_PACKAGES[*]}"
    echo "The build may fail if these are not available."
    echo ""
    echo "Install with:"
    echo "  pip3 install ${MISSING_PACKAGES[*]}"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create build directory
BUILD_DIR="build_worker_macos"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Build with PyInstaller
echo "Building executable with $PYINSTALLER_CMD..."
$PYINSTALLER_CMD build_worker.spec \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/build" \
    --clean \
    --noconfirm

# Check if build succeeded
if [ ! -f "$BUILD_DIR/dist/chaarfm_worker" ] && [ ! -d "$BUILD_DIR/dist/chaarfm_worker.app" ]; then
    echo "ERROR: Build failed - executable not found!"
    echo "Check build output above for errors."
    exit 1
fi

# Copy FFmpeg if available
if command -v ffmpeg &> /dev/null; then
    FFMPEG_PATH=$(which ffmpeg)
    echo "Copying FFmpeg to bundle..."
    if [ -d "$BUILD_DIR/dist/chaarfm_worker.app" ]; then
        mkdir -p "$BUILD_DIR/dist/chaarfm_worker.app/Contents/MacOS"
        cp "$FFMPEG_PATH" "$BUILD_DIR/dist/chaarfm_worker.app/Contents/MacOS/ffmpeg" 2>/dev/null || true
    else
        cp "$FFMPEG_PATH" "$BUILD_DIR/dist/ffmpeg" 2>/dev/null || true
    fi
fi

# Create DMG
echo "Creating DMG..."
DMG_NAME="chaarfm_worker_macos.dmg"
DMG_TEMP="temp_dmg"

rm -f "$DMG_NAME"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

# Copy executable
if [ -d "$BUILD_DIR/dist/chaarfm_worker.app" ]; then
    cp -R "$BUILD_DIR/dist/chaarfm_worker.app" "$DMG_TEMP/"
elif [ -f "$BUILD_DIR/dist/chaarfm_worker" ]; then
    cp "$BUILD_DIR/dist/chaarfm_worker" "$DMG_TEMP/"
fi

# Copy README
if [ -f "WORKER_README.md" ]; then
    cp "WORKER_README.md" "$DMG_TEMP/README.md"
fi

# Create DMG
hdiutil create -volname "ChaarFM Worker" -srcfolder "$DMG_TEMP" -ov -format UDZO "$DMG_NAME"

# Cleanup
rm -rf "$DMG_TEMP"

echo ""
echo "=== Build Complete ==="
echo "✅ DMG created: $DMG_NAME"
echo "✅ Executable: $BUILD_DIR/dist/chaarfm_worker"
echo ""
echo "To test:"
echo "  ./$BUILD_DIR/dist/chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_CODE"
