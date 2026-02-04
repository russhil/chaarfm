#!/bin/bash
# Setup script that uses Python 3.10+ instead of deprecated 3.9

set -e

echo "=== ChaarFM Worker Setup with Python 3.10+ ==="

# Find available Python versions (prefer 3.10+)
PYTHON_CMD=""
for version in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v $version &> /dev/null; then
        PYTHON_VERSION=$($version --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD=$version
            echo "Found Python $PYTHON_VERSION: $PYTHON_CMD"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.10 or higher not found!"
    echo "Please install Python 3.10+ from: https://www.python.org/downloads/"
    exit 1
fi

# Create virtual environment with correct Python
echo "Creating virtual environment with $PYTHON_CMD..."
$PYTHON_CMD -m venv venv_worker

# Activate virtual environment
echo "Activating virtual environment..."
source venv_worker/bin/activate

# Verify Python version in venv
echo "Python version in venv:"
python --version

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install websockets requests certifi yt-dlp tensorflow tf-keras mutagen numpy librosa python-dotenv psycopg2-binary

# Install essentia with compatibility fix
echo "Installing essentia (with compatibility fix)..."
pip install essentia --no-compile || pip install essentia --no-deps || {
    echo "Warning: Essentia installation had issues, but continuing..."
}

echo ""
echo "=== Setup Complete ==="
echo "To run worker:"
echo "  source venv_worker/bin/activate"
echo "  python remote_worker.py --url https://chaarfm.onrender.com --code YOUR_CODE"
