# Build Permission Issue - Solution

## Problem
PyInstaller is trying to write to `/Users/russhil/Library/Application Support/pyinstaller` but doesn't have permission.

## Solution Options

### Option 1: Create the cache directory manually (Recommended)
Run this command first, then build:

```bash
sudo mkdir -p "/Users/russhil/Library/Application Support/pyinstaller"
sudo chown -R $(whoami) "/Users/russhil/Library/Application Support/pyinstaller"
```

Then run:
```bash
./build_worker_macos.sh
```

### Option 2: Use sudo for the build (Not recommended but works)
```bash
sudo ./build_worker_macos.sh
```

### Option 3: Build in a directory you own
```bash
cd ~/Desktop
mkdir chaarfm_build
cp -r /Users/russhil/cursor/chaarfm/* chaarfm_build/
cd chaarfm_build
./build_worker_macos.sh
```

### Option 4: Fix project directory permissions
```bash
sudo chown -R $(whoami) /Users/russhil/cursor/chaarfm
chmod -R u+w /Users/russhil/cursor/chaarfm
```

Then run:
```bash
./build_worker_macos.sh
```

## Quick Fix Command

Run this single command to fix permissions and build:

```bash
sudo mkdir -p "/Users/russhil/Library/Application Support/pyinstaller" && sudo chown -R $(whoami) "/Users/russhil/Library/Application Support/pyinstaller" && ./build_worker_macos.sh
```
