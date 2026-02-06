# ChaarFM Build Guide

Complete guide for building and deploying ChaarFM components.

## Table of Contents
1. [Worker Executables](#worker-executables)
2. [Build Scripts](#build-scripts)
3. [Troubleshooting](#troubleshooting)
4. [Distribution](#distribution)

---

## Worker Executables

Build standalone executables for the ChaarFM Remote Worker that can run without Python or dependencies installed.

### Features

- **Standalone**: No Python installation required
- **Multi-worker support**: Multiple workers share workload automatically
- **Cross-platform**: Builds for Windows (.exe) and macOS (.app/.dmg)
- **Bundled dependencies**: Includes Essentia, TensorFlow, yt-dlp, etc.

### Prerequisites

#### macOS
- Python 3.9-3.11 (3.12+ may have compatibility issues)
- Xcode Command Line Tools: `xcode-select --install`
- Homebrew (optional, for FFmpeg): `brew install ffmpeg`

#### Windows
- Python 3.9-3.11
- Visual C++ Redistributable
- FFmpeg: `winget install ffmpeg` or download from https://ffmpeg.org/

---

## Build Scripts

### macOS Build

**Quick Build:**
```bash
./build_worker_macos.sh
```

**What it does:**
1. Creates virtual environment
2. Installs PyInstaller and dependencies
3. Builds executable with PyInstaller
4. Creates DMG file for distribution

**Output:** `chaarfm_worker_macos.dmg`

**Alternative: Offline Build (if PyInstaller already installed):**
```bash
./build_worker_offline.sh
```

### Windows Build

**Quick Build:**
```batch
build_worker_windows.bat
```

**What it does:**
1. Creates virtual environment
2. Installs PyInstaller and dependencies
3. Builds executable
4. Creates distributable folder

**Output:** `build_worker_windows/dist/chaarfm_worker.exe`

### Build with Existing Environment

If you already have a Python environment set up:
```bash
./build_with_existing_env.sh
```

### One-File Build (No Sudo)

For single-file executable without admin privileges:
```bash
./build_onefile_nosudo.sh
```

Or using the spec file:
```bash
source venv_worker/bin/activate
pyinstaller chaarfm_worker_onefile.spec \
    --distpath build_worker_macos/dist \
    --workpath build_worker_macos/build \
    --noconfirm
```

---

## Usage

### Running the Worker

**macOS:**
```bash
./chaarfm_worker --url https://chaarfm.onrender.com --code YOUR_PAIRING_CODE
```

**Windows:**
```cmd
chaarfm_worker.exe --url https://chaarfm.onrender.com --code YOUR_PAIRING_CODE
```

### Getting a Pairing Code

1. Navigate to `/ingest` on your ChaarFM server
2. Generate a pairing code
3. Use that code when starting workers

### Multiple Workers

Run multiple instances for parallel processing:

**Same machine:**
```bash
# Terminal 1
./chaarfm_worker --url https://chaarfm.onrender.com --code ABC123

# Terminal 2
./chaarfm_worker --url https://chaarfm.onrender.com --code ABC123

# Terminal 3
./chaarfm_worker --url https://chaarfm.onrender.com --code ABC123
```

**Different machines:**
Install the executable on different machines and use the same pairing code.

Tasks are automatically distributed across all connected workers. With 3 workers, processing time is reduced by ~3x.

---

## Troubleshooting

### PyInstaller Cache Permission Issue

If you encounter cache permission errors:

**Option 1: Use the onefile spec**
```bash
rm -f chaarfm_worker.spec
source venv_worker/bin/activate
pyinstaller chaarfm_worker_onefile.spec \
    --distpath build_worker_macos/dist \
    --workpath build_worker_macos/build \
    --noconfirm
```

**Option 2: Fix cache permissions**
```bash
sudo chmod -R 755 ~/Library/Application\ Support/pyinstaller
```

**Option 3: Use local cache**
```bash
python build_with_fixed_cache.py build_worker.spec
```

### SSL Certificate Errors

**macOS:**
```bash
# Update system certificates
sudo update-ca-certificates
# Or update macOS via System Preferences
```

**Windows:**
Update Windows to get latest root certificates via Windows Update.

### FFmpeg Not Found

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
```cmd
winget install ffmpeg
```
Or download from https://ffmpeg.org/ and add to PATH.

### Essentia Library Errors

- Use Python 3.9-3.11 (3.12+ may have issues)
- Ensure system libraries are available
- On Linux: `sudo apt-get install libessentia-dev`

### Large Executable Size

The executable is 500MB-1GB because it includes:
- TensorFlow/Keras models
- Essentia audio processing libraries
- All Python dependencies
- FFmpeg (if bundled)

This is normal for standalone executables.

### Network Connectivity Issues

If build fails due to network issues:
1. Check internet connection
2. Try again (PyPI might be temporarily down)
3. Use a VPN if PyPI is blocked
4. Pre-download packages: `pip download -r requirements-worker.txt`

---

## Distribution

### macOS DMG

**Creating DMG:**
```bash
# Already done by build_worker_macos.sh
# Manual creation:
hdiutil create -volname "ChaarFM Worker" \
    -srcfolder build_worker_macos/dist \
    -ov -format UDZO chaarfm_worker_macos.dmg
```

**Distribution:**
Users can:
1. Mount the DMG
2. Drag the app to Applications
3. Run from Applications or double-click

### Windows Installer

**Options for creating installer:**

**Inno Setup:**
```iss
[Setup]
AppName=ChaarFM Worker
AppVersion=1.0
DefaultDirName={pf}\ChaarFM Worker
OutputDir=output
OutputBaseFilename=ChaarFM_Worker_Setup

[Files]
Source: "build_worker_windows\dist\*"; DestDir: "{app}"; Flags: recursesubdirs
```

**Alternative:** NSIS, WiX Toolset, or distribute the `dist` folder as ZIP.

---

## Architecture

### Worker Connection Flow
1. Worker connects to server via WebSocket
2. Server authenticates using pairing code
3. Worker receives tasks from queue
4. Tasks are distributed across all connected workers
5. Completed tasks are sent back to server

### Task Distribution
- Tasks queued when ingestion starts
- Available workers receive tasks immediately
- Finished workers automatically get next task
- Disconnected workers' tasks are reassigned
- All workers share same queue for efficient parallel processing

---

## Build Specifications

### PyInstaller Spec Files

**`build_worker.spec`**: Standard build with all options
**`chaarfm_worker_onefile.spec`**: Single-file executable build

### Hidden Imports

Required for proper bundling:
```python
--hidden-import websockets
--hidden-import websockets.client
--hidden-import yt_dlp
--hidden-import tensorflow
--hidden-import essentia
--hidden-import essentia.standard
--hidden-import mutagen
--hidden-import librosa
--hidden-import certifi
```

### Data Files

```python
--add-data "populate_youtube_universe.py:."
--add-data "music_pipeline/vectorizer.py:music_pipeline"
--add-data "music_pipeline/config.py:music_pipeline"
```

---

## Development

### Testing Changes

1. Edit `remote_worker.py`
2. Test locally: `python remote_worker.py --url http://localhost:5000 --code TEST`
3. Rebuild: `./build_worker_macos.sh`
4. Test executable
5. Distribute

### Debugging Build Issues

**Enable verbose output:**
```bash
pyinstaller --log-level DEBUG build_worker.spec
```

**Check built executable:**
```bash
# macOS
otool -L build_worker_macos/dist/chaarfm_worker

# Windows
dumpbin /dependents build_worker_windows\dist\chaarfm_worker.exe
```

---

## Notes

- First run is slower as Essentia downloads MusicNN model (~50MB)
- Model is cached locally after first download
- Network connectivity required for audio download and server connection
- Workers process tasks sequentially, but multiple workers process in parallel
- Build time: 10-30 minutes depending on download speeds

---

## Quick Reference

### One-Command Setup (with Python 3.10)

```bash
# Install Python 3.10
brew install python@3.10

# Setup and build
python3.10 -m venv venv_worker && \
source venv_worker/bin/activate && \
pip install --upgrade pip && \
pip install -r requirements-worker.txt && \
pyinstaller build_worker.spec --noconfirm
```

### Clean Build

```bash
# Remove old builds
rm -rf build_worker_macos build_worker_windows dist build *.spec

# Force clear cache
./force_clear_cache.sh

# Fresh build
./build_worker_macos.sh
```

---

## Resources

- **PyInstaller Documentation**: https://pyinstaller.org/
- **Essentia**: https://essentia.upf.edu/
- **TensorFlow**: https://www.tensorflow.org/
- **yt-dlp**: https://github.com/yt-dlp/yt-dlp
