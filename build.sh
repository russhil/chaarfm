#!/bin/bash
# Unified build script for ChaarFM Worker
# Usage: ./build.sh [option]
# Options: macos, windows, onefile, offline, clean

set -e

show_help() {
    cat << EOF
ChaarFM Worker Build Script

Usage: ./build.sh [option]

Options:
  macos      - Build worker for macOS (creates DMG)
  windows    - Build worker for Windows (creates EXE)
  onefile    - Build single-file executable (no folders)
  offline    - Build using existing PyInstaller installation
  clean      - Clean all build artifacts
  help       - Show this help message

Examples:
  ./build.sh macos
  ./build.sh onefile
  ./build.sh clean

For detailed build documentation, see: docs/BUILD_GUIDE.md
EOF
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo "Using Python $PYTHON_VERSION"
    
    # Warn if using Python 3.12+
    if [[ $(echo "$PYTHON_VERSION >= 3.12" | bc -l 2>/dev/null || echo "0") == "1" ]]; then
        echo "Warning: Python 3.12+ may have compatibility issues. Python 3.9-3.11 recommended."
    fi
}

setup_venv() {
    local venv_name=${1:-venv_worker}
    
    if [ ! -d "$venv_name" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "$venv_name"
    fi
    
    source "$venv_name/bin/activate"
    pip install --upgrade pip
}

install_dependencies() {
    echo "Installing dependencies..."
    pip install pyinstaller
    pip install -r requirements-worker.txt
}

check_ffmpeg() {
    if ! command -v ffmpeg &> /dev/null; then
        echo "Warning: FFmpeg not found"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Install with: brew install ffmpeg"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "Install with: sudo apt-get install ffmpeg"
        else
            echo "Download from: https://ffmpeg.org/download.html"
        fi
        return 1
    fi
    return 0
}

build_macos() {
    echo "=== Building ChaarFM Worker for macOS ==="
    
    if [[ "$OSTYPE" != "darwin"* ]]; then
        echo "Error: macOS build must be run on macOS"
        exit 1
    fi
    
    check_python
    setup_venv
    install_dependencies
    check_ffmpeg
    
    BUILD_DIR="build_worker_macos"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    
    echo "Building executable..."
    pyinstaller build_worker.spec \
        --distpath "$BUILD_DIR/dist" \
        --workpath "$BUILD_DIR/build" \
        --clean
    
    # Copy FFmpeg if available
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
    
    rm -f "$DMG_NAME"
    rm -rf "$DMG_TEMP"
    mkdir -p "$DMG_TEMP"
    
    # Copy to DMG
    if [ -d "$BUILD_DIR/dist/chaarfm_worker.app" ]; then
        cp -R "$BUILD_DIR/dist/chaarfm_worker.app" "$DMG_TEMP/"
    else
        cp "$BUILD_DIR/dist/chaarfm_worker" "$DMG_TEMP/"
    fi
    
    # Create README
    cat > "$DMG_TEMP/README.txt" << 'EOF'
ChaarFM Remote Worker - macOS

USAGE:
  ./chaarfm_worker --url https://your-server.com --code YOUR_CODE

MULTIPLE WORKERS:
  Run multiple instances with the same code for parallel processing!

For full documentation, see docs/BUILD_GUIDE.md
EOF
    
    hdiutil create -volname "ChaarFM Worker" -srcfolder "$DMG_TEMP" -ov -format UDZO "$DMG_NAME"
    rm -rf "$DMG_TEMP"
    
    echo ""
    echo "=== Build Complete ==="
    echo "DMG: $DMG_NAME"
    echo "Executable: $BUILD_DIR/dist/chaarfm_worker"
    echo ""
    echo "Test with:"
    echo "  ./$BUILD_DIR/dist/chaarfm_worker --url http://localhost:5000 --code TEST"
}

build_windows() {
    echo "=== Building ChaarFM Worker for Windows ==="
    
    if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Note: Cross-compiling for Windows from $OSTYPE"
        echo "For best results, build on Windows directly"
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    check_python
    setup_venv
    install_dependencies
    
    BUILD_DIR="build_worker_windows"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    
    echo "Building executable..."
    pyinstaller build_worker.spec \
        --distpath "$BUILD_DIR/dist" \
        --workpath "$BUILD_DIR/build" \
        --clean
    
    echo ""
    echo "=== Build Complete ==="
    echo "Executable: $BUILD_DIR/dist/chaarfm_worker.exe"
    echo ""
    echo "Distribute the entire dist/ folder or create an installer"
}

build_onefile() {
    echo "=== Building One-File Executable ==="
    
    check_python
    setup_venv
    install_dependencies
    
    BUILD_DIR="build_onefile"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    
    echo "Building single-file executable..."
    
    if [ -f "chaarfm_worker_onefile.spec" ]; then
        pyinstaller chaarfm_worker_onefile.spec \
            --distpath "$BUILD_DIR/dist" \
            --workpath "$BUILD_DIR/build" \
            --noconfirm
    else
        pyinstaller remote_worker.py \
            --name chaarfm_worker \
            --onefile \
            --distpath "$BUILD_DIR/dist" \
            --workpath "$BUILD_DIR/build" \
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
    fi
    
    echo ""
    echo "=== Build Complete ==="
    echo "Single-file executable: $BUILD_DIR/dist/chaarfm_worker"
}

build_offline() {
    echo "=== Building (Offline Mode) ==="
    echo "Using existing PyInstaller installation..."
    
    if [ ! -d "venv_worker" ]; then
        echo "Error: venv_worker not found. Run 'build.sh macos' first to set up environment."
        exit 1
    fi
    
    source venv_worker/bin/activate
    
    if ! command -v pyinstaller &> /dev/null; then
        echo "Error: PyInstaller not installed in venv_worker"
        echo "Run 'build.sh macos' first to install dependencies"
        exit 1
    fi
    
    BUILD_DIR="build_worker_offline"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    
    echo "Building executable..."
    pyinstaller build_worker.spec \
        --distpath "$BUILD_DIR/dist" \
        --workpath "$BUILD_DIR/build" \
        --clean
    
    echo ""
    echo "=== Build Complete ==="
    echo "Executable: $BUILD_DIR/dist/chaarfm_worker"
}

clean_build() {
    echo "=== Cleaning Build Artifacts ==="
    
    rm -rf build_worker_macos
    rm -rf build_worker_windows
    rm -rf build_onefile
    rm -rf build_worker_offline
    rm -rf build
    rm -rf dist
    rm -rf temp_dmg
    rm -f *.dmg
    rm -f *.spec 2>/dev/null || true
    rm -rf __pycache__
    rm -rf *.egg-info
    
    # Clear PyInstaller cache
    if [ -d ~/.pyinstaller ]; then
        rm -rf ~/.pyinstaller
    fi
    if [ -d ~/Library/Application\ Support/pyinstaller ]; then
        rm -rf ~/Library/Application\ Support/pyinstaller
    fi
    
    echo "Build artifacts cleaned!"
}

# Main script
case "${1:-help}" in
    macos)
        build_macos
        ;;
    windows)
        build_windows
        ;;
    onefile)
        build_onefile
        ;;
    offline)
        build_offline
        ;;
    clean)
        clean_build
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown option: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
