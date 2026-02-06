#!/bin/bash
# Unified setup script for ChaarFM
# Usage: ./setup.sh [option]
# Options: server, worker, dev, essentia-fix

set -e

show_help() {
    cat << EOF
ChaarFM Setup Script

Usage: ./setup.sh [option]

Options:
  server        - Setup for running the server
  worker        - Setup for building workers
  dev           - Setup for development (both server and worker)
  essentia-fix  - Setup with Essentia compatibility fixes
  clean         - Remove virtual environments
  help          - Show this help message

Examples:
  ./setup.sh server
  ./setup.sh dev
  ./setup.sh essentia-fix

For detailed setup documentation, see: README.md
EOF
}

check_python() {
    echo "Checking Python version..."
    
    # Try different Python commands
    if command -v python3.10 &> /dev/null; then
        PYTHON_CMD="python3.10"
    elif command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3.9 &> /dev/null; then
        PYTHON_CMD="python3.9"
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    else
        echo "Error: Python 3 not found"
        echo "Please install Python 3.9-3.11"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version | cut -d' ' -f2)
    echo "Using $PYTHON_CMD ($PYTHON_VERSION)"
    
    # Check if version is in recommended range
    MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
    
    if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 9 ] && [ "$MINOR" -le 11 ]; then
        echo "✓ Python version is compatible"
    else
        echo "⚠ Warning: Python 3.9-3.11 recommended. You have $PYTHON_VERSION"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

setup_server() {
    echo "=== Setting up ChaarFM Server ==="
    
    check_python
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        $PYTHON_CMD -m venv venv
    else
        echo "Virtual environment already exists"
    fi
    
    # Activate and install
    source venv/bin/activate
    
    echo "Upgrading pip..."
    pip install --upgrade pip
    
    echo "Installing server dependencies..."
    pip install -r requirements.txt
    
    # Check for .env file
    if [ ! -f ".env" ]; then
        echo ""
        echo "⚠ Warning: .env file not found"
        echo "Please create .env with your configuration:"
        echo "  - DATABASE_URL"
        echo "  - LASTFM_API_KEY"
        echo "  - LASTFM_API_SECRET"
        echo "  - S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY"
        echo ""
        read -p "Continue without .env? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    echo ""
    echo "=== Server Setup Complete ==="
    echo ""
    echo "Next steps:"
    echo "  1. Configure .env file if not done"
    echo "  2. Initialize database: python user_db.py"
    echo "  3. Start server: python server_user.py"
    echo ""
    echo "Or use control panel: python control_panel.py"
}

setup_worker() {
    echo "=== Setting up ChaarFM Worker Build Environment ==="
    
    check_python
    
    # Create virtual environment
    if [ ! -d "venv_worker" ]; then
        echo "Creating virtual environment..."
        $PYTHON_CMD -m venv venv_worker
    else
        echo "Virtual environment already exists"
    fi
    
    # Activate and install
    source venv_worker/bin/activate
    
    echo "Upgrading pip..."
    pip install --upgrade pip
    
    echo "Installing PyInstaller..."
    pip install pyinstaller
    
    echo "Installing worker dependencies..."
    pip install -r requirements-worker.txt
    
    # Check for FFmpeg
    if ! command -v ffmpeg &> /dev/null; then
        echo ""
        echo "⚠ Warning: FFmpeg not found"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Install with: brew install ffmpeg"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "Install with: sudo apt-get install ffmpeg"
        else
            echo "Download from: https://ffmpeg.org/download.html"
        fi
    else
        echo "✓ FFmpeg found: $(ffmpeg -version | head -1)"
    fi
    
    echo ""
    echo "=== Worker Setup Complete ==="
    echo ""
    echo "Next steps:"
    echo "  1. Build worker: ./build.sh macos"
    echo "  2. Or test locally: python remote_worker.py --url http://localhost:5000 --code TEST"
    echo ""
    echo "See docs/BUILD_GUIDE.md for detailed build instructions"
}

setup_dev() {
    echo "=== Setting up ChaarFM Development Environment ==="
    
    # Setup both server and worker
    setup_server
    echo ""
    setup_worker
    
    echo ""
    echo "=== Development Setup Complete ==="
    echo ""
    echo "Available commands:"
    echo "  Server:  source venv/bin/activate && python server_user.py"
    echo "  Worker:  source venv_worker/bin/activate && python remote_worker.py"
    echo "  Tests:   source venv/bin/activate && python scripts/debug_tools.py all"
    echo "  Build:   ./build.sh macos"
}

setup_essentia_fix() {
    echo "=== Setting up with Essentia Compatibility Fix ==="
    
    check_python
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        $PYTHON_CMD -m venv venv
    fi
    
    source venv/bin/activate
    
    echo "Upgrading pip..."
    pip install --upgrade pip
    
    echo "Installing with Essentia fixes..."
    
    # Force legacy Keras
    export TF_USE_LEGACY_KERAS=1
    
    # Install TensorFlow first
    pip install "tensorflow<2.16" "tensorflow-io-gcs-filesystem<0.32"
    
    # Install Essentia
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        pip install essentia-tensorflow
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        pip install essentia-tensorflow
    else
        echo "Note: Essentia may require manual installation on Windows"
        pip install essentia-tensorflow || echo "Essentia installation failed - you may need to build from source"
    fi
    
    # Install remaining dependencies
    echo "Installing remaining dependencies..."
    pip install -r requirements.txt
    
    echo ""
    echo "=== Essentia Setup Complete ==="
    echo ""
    echo "Test Essentia: python scripts/debug_tools.py essentia"
}

clean_setup() {
    echo "=== Cleaning Virtual Environments ==="
    
    read -p "Remove venv and venv_worker? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        rm -rf venv_worker
        echo "Virtual environments removed"
    else
        echo "Cancelled"
    fi
}

# Main script
case "${1:-help}" in
    server)
        setup_server
        ;;
    worker)
        setup_worker
        ;;
    dev)
        setup_dev
        ;;
    essentia-fix)
        setup_essentia_fix
        ;;
    clean)
        clean_setup
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
