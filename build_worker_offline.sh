#!/bin/bash
# Build script that checks for existing dependencies first
# Use this if you have network issues but PyInstaller is already installed

set -e

echo "=== Building ChaarFM Remote Worker for macOS (Offline Mode) ==="

# Check if PyInstaller is available
if ! command -v pyinstaller &> /dev/null && ! python3 -m PyInstaller --version &> /dev/null; then
    echo "ERROR: PyInstaller not found."
    echo "Please install it first:"
    echo "  pip install pyinstaller"
    echo ""
    echo "Or use the online build script: ./build_worker_macos.sh"
    exit 1
fi

# Use system Python or existing venv
if [ -d "venv_worker" ]; then
    echo "Using existing virtual environment..."
    source venv_worker/bin/activate
else
    echo "WARNING: No virtual environment found."
    echo "Using system Python. This may work if dependencies are installed globally."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for required Python packages
echo "Checking dependencies..."
python3 -c "import websockets, requests, yt_dlp, tensorflow, essentia" 2>/dev/null || {
    echo "ERROR: Missing required dependencies."
    echo "Please install: pip install -r requirements-worker.txt"
    exit 1
}

# Check for FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: FFmpeg not found in PATH."
    echo "yt-dlp may not work properly without FFmpeg."
    echo "Install with: brew install ffmpeg"
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
echo "Building executable..."
if command -v pyinstaller &> /dev/null; then
    pyinstaller build_worker.spec \
        --distpath "$BUILD_DIR/dist" \
        --workpath "$BUILD_DIR/build" \
        --clean
else
    python3 -m PyInstaller build_worker.spec \
        --distpath "$BUILD_DIR/dist" \
        --workpath "$BUILD_DIR/build" \
        --clean
fi

# Copy FFmpeg binary if available
if command -v ffmpeg &> /dev/null; then
    FFMPEG_PATH=$(which ffmpeg)
    echo "Copying FFmpeg to bundle..."
    mkdir -p "$BUILD_DIR/dist/chaarfm_worker.app/Contents/MacOS" 2>/dev/null || true
    cp "$FFMPEG_PATH" "$BUILD_DIR/dist/chaarfm_worker.app/Contents/MacOS/ffmpeg" 2>/dev/null || \
    cp "$FFMPEG_PATH" "$BUILD_DIR/dist/ffmpeg" 2>/dev/null || true
fi

# Create DMG
echo "Creating DMG..."
DMG_NAME="chaarfm_worker_macos.dmg"
DMG_TEMP="temp_dmg"

# Remove old DMG if exists
rm -f "$DMG_NAME"

# Create temporary directory for DMG contents
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

# Copy app to DMG
if [ -d "$BUILD_DIR/dist/chaarfm_worker.app" ]; then
    cp -R "$BUILD_DIR/dist/chaarfm_worker.app" "$DMG_TEMP/"
elif [ -f "$BUILD_DIR/dist/chaarfm_worker" ]; then
    cp "$BUILD_DIR/dist/chaarfm_worker" "$DMG_TEMP/"
else
    echo "ERROR: Built executable not found!"
    exit 1
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
echo "DMG created: $DMG_NAME"
echo "Executable location: $BUILD_DIR/dist/chaarfm_worker"
echo ""
echo "To test:"
echo "  ./$BUILD_DIR/dist/chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_CODE"
