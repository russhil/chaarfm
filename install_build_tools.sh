#!/bin/bash
# Install PyInstaller and build dependencies for ChaarFM Worker

set -e

echo "=== Installing Build Tools ==="

# Create virtual environment if it doesn't exist
if [ ! -d "venv_worker" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv_worker
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv_worker/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install PyInstaller
echo "Installing PyInstaller..."
pip install pyinstaller

# Install worker dependencies
echo "Installing worker dependencies..."
pip install -r requirements-worker.txt

echo ""
echo "=== Installation Complete ==="
echo ""
echo "PyInstaller version:"
pyinstaller --version
echo ""
echo "You can now run: ./build_worker_macos.sh"
