#!/bin/bash
# One-command setup and run script for remote worker

set -e

GIT_REPO="${1:-https://github.com/YOUR_USERNAME/chaarfm.git}"
PAIRING_CODE="${2}"
SERVER_URL="${3:-https://chaarfm.onrender.com}"

if [ -z "$PAIRING_CODE" ]; then
    echo "Usage: $0 <GIT_REPO_URL> <PAIRING_CODE> [SERVER_URL]"
    echo ""
    echo "Example:"
    echo "  $0 https://github.com/username/chaarfm.git ABC123"
    echo ""
    echo "Or set environment variables:"
    echo "  export CHAARFM_REPO=https://github.com/username/chaarfm.git"
    echo "  export CHAARFM_CODE=ABC123"
    echo "  $0"
    exit 1
fi

echo "=== ChaarFM Remote Worker Setup ==="
echo "Repository: $GIT_REPO"
echo "Pairing Code: $PAIRING_CODE"
echo "Server: $SERVER_URL"
echo ""

# Clone if directory doesn't exist
if [ ! -d "chaarfm_worker" ]; then
    echo "Cloning repository..."
    git clone "$GIT_REPO" chaarfm_worker
else
    echo "Directory exists, updating..."
    cd chaarfm_worker
    git pull || true
    cd ..
fi

cd chaarfm_worker

# Install dependencies
echo "Installing dependencies..."
pip3 install -q websockets requests certifi yt-dlp tensorflow tf-keras mutagen numpy librosa python-dotenv psycopg2-binary essentia 2>/dev/null || \
pip3 install websockets requests certifi yt-dlp tensorflow tf-keras mutagen numpy librosa python-dotenv psycopg2-binary essentia

# Run worker
echo ""
echo "Starting worker..."
echo ""
python3 remote_worker.py --url "$SERVER_URL" --code "$PAIRING_CODE"
