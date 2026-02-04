#!/bin/bash
# Build script for macOS standalone worker executable

set -e

echo "=== Building ChaarFM Remote Worker for macOS ==="

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This script is for macOS only"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv_worker" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv_worker
fi

# Activate virtual environment
source venv_worker/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install PyInstaller
pip install pyinstaller

# Install worker dependencies
echo "Installing dependencies..."
pip install -r requirements-worker.txt

# Install FFmpeg if not available (needed for yt-dlp)
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg not found. Installing via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "Warning: Homebrew not found. Please install FFmpeg manually."
        echo "Download from: https://ffmpeg.org/download.html"
    fi
fi

# Create build directory
BUILD_DIR="build_worker_macos"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Build with PyInstaller
echo "Building executable..."
pyinstaller build_worker.spec \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/build" \
    --clean

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
else
    cp "$BUILD_DIR/dist/chaarfm_worker" "$DMG_TEMP/"
fi

# Copy README
if [ -f "WORKER_README.md" ]; then
    cp "WORKER_README.md" "$DMG_TEMP/README.md"
else
    # Create simple README if main one doesn't exist
    cat > "$DMG_TEMP/README.txt" << 'EOF'
ChaarFM Remote Worker - macOS

INSTRUCTIONS:
1. Open Terminal
2. Navigate to this folder: cd /Volumes/ChaarFM\ Worker
3. Run: ./chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_CODE

MULTIPLE WORKERS:
Run multiple instances with the same pairing code to speed up processing!
Each worker automatically shares the workload.

For detailed instructions, see WORKER_README.md
EOF
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
