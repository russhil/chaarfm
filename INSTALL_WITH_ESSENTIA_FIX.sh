#!/bin/bash
# Installation script that handles essentia compatibility issues

set -e

echo "=== Installing ChaarFM Remote Worker Dependencies ==="

# Install most packages normally
echo "Installing standard dependencies..."
pip3 install websockets requests certifi yt-dlp tensorflow tf-keras mutagen numpy librosa python-dotenv psycopg2-binary

# Install essentia with --no-compile to avoid Python 2 syntax errors
echo "Installing essentia (with compatibility fix)..."
pip3 install essentia --no-compile || {
    echo "Warning: essentia installation failed with --no-compile"
    echo "Trying alternative: pip install essentia --no-deps"
    pip3 install essentia --no-deps || {
        echo "Essentia installation failed. You may need to:"
        echo "1. Install via conda: conda install -c conda-forge essentia"
        echo "2. Or use Python 3.8 instead of 3.9"
        echo "3. Or skip essentia if not using vectorization"
    }
}

echo ""
echo "=== Installation Complete ==="
echo "To run worker:"
echo "  python3 remote_worker.py --url https://chaarfm.onrender.com --code YOUR_CODE"
