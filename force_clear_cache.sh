#!/bin/bash
# Force clear PyInstaller cache - more aggressive approach

echo "=== Force Clearing PyInstaller Cache ==="

CACHE_DIR="/Users/russhil/Library/Application Support/pyinstaller"

# Try multiple methods to clear the cache
echo "Method 1: Using sudo rm -rf..."
sudo rm -rf "$CACHE_DIR" 2>/dev/null || true

echo "Method 2: Clearing subdirectories individually..."
if [ -d "$CACHE_DIR" ]; then
    sudo find "$CACHE_DIR" -type d -exec sudo rm -rf {} + 2>/dev/null || true
    sudo find "$CACHE_DIR" -type f -exec sudo rm -f {} + 2>/dev/null || true
fi

echo "Method 3: Recreating directory..."
sudo rm -rf "$CACHE_DIR"
sudo mkdir -p "$CACHE_DIR"
sudo chown -R $(whoami):staff "$CACHE_DIR"
chmod -R 755 "$CACHE_DIR"

echo "✅ Cache cleared and recreated with proper permissions"
echo ""
echo "Cache directory: $CACHE_DIR"
ls -la "$CACHE_DIR" 2>/dev/null || echo "Directory is empty (good!)"
