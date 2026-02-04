# Building Standalone Remote Worker Executables

This guide explains how to build standalone executables for the ChaarFM Remote Worker that can run on Windows and macOS without requiring Python or any dependencies to be installed.

## Features

- **Standalone**: No Python installation required
- **Multi-worker support**: Multiple workers can connect to the same pairing code and automatically share workload
- **Cross-platform**: Builds for both Windows (.exe) and macOS (.app/.dmg)
- **Bundled dependencies**: Includes all required libraries including Essentia, TensorFlow, yt-dlp, etc.

## Prerequisites

### macOS
- Python 3.9 or later
- Xcode Command Line Tools: `xcode-select --install`
- Homebrew (optional, for FFmpeg): `brew install ffmpeg`

### Windows
- Python 3.9 or later
- Visual C++ Redistributable (usually already installed)
- FFmpeg (download from https://ffmpeg.org/download.html or install via `winget install ffmpeg`)

## Building

### macOS

```bash
./build_worker_macos.sh
```

This will:
1. Create a virtual environment
2. Install all dependencies
3. Build the executable using PyInstaller
4. Create a DMG file for easy distribution

Output: `chaarfm_worker_macos.dmg`

### Windows

```batch
build_worker_windows.bat
```

This will:
1. Create a virtual environment
2. Install all dependencies
3. Build the executable using PyInstaller
4. Create a distributable folder

Output: `build_worker_windows/dist/chaarfm_worker.exe`

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
3. Use that code when starting the worker

### Multiple Workers

You can run multiple instances of the worker:

1. **Same machine**: Just run the executable multiple times with the same pairing code
2. **Different machines**: Install the executable on different machines and use the same pairing code

Tasks will be automatically distributed across all connected workers. If you have 3 workers connected, tasks will be split 3 ways, reducing processing time proportionally.

## Troubleshooting

### SSL Certificate Errors

If you see SSL certificate errors:
- **macOS**: Update your system certificates: `sudo update-ca-certificates` or update macOS
- **Windows**: Update Windows to get latest root certificates

### FFmpeg Not Found

The worker needs FFmpeg for audio processing:
- **macOS**: `brew install ffmpeg`
- **Windows**: Download from https://ffmpeg.org/download.html and add to PATH, or the build script will attempt to bundle it

### Essentia Library Errors

If you see errors about Essentia:
- Ensure you're using a compatible Python version (3.9-3.11 recommended)
- Essentia requires specific system libraries that should be bundled automatically
- On Linux, you may need: `sudo apt-get install libessentia-dev` (not applicable for Windows/macOS standalone builds)

### Large Executable Size

The executable is large (~500MB-1GB) because it includes:
- TensorFlow/Keras models
- Essentia audio processing libraries
- All Python dependencies
- FFmpeg (if bundled)

This is normal for a standalone executable.

## Distribution

### macOS DMG

The DMG file can be distributed directly. Users can:
1. Mount the DMG
2. Drag the app to Applications
3. Run from Applications or double-click the executable

### Windows

Distribute the entire `dist` folder or create an installer using tools like:
- Inno Setup
- NSIS
- WiX Toolset

## Architecture

The worker connects via WebSocket to the coordinator running on your server. The coordinator automatically distributes tasks across all connected workers for the same pairing code.

### Task Distribution

- Tasks are queued when ingestion starts
- Available workers receive tasks immediately
- When a worker finishes, it automatically receives the next task
- If a worker disconnects, its current task is reassigned (if possible)
- All workers share the same queue, ensuring efficient parallel processing

## Development

To modify the worker:

1. Edit `remote_worker.py`
2. Rebuild using the appropriate build script
3. Test with a local server

## Notes

- The first run may be slower as Essentia downloads the MusicNN model
- The model is cached locally after first download
- Network connectivity is required for downloading audio and connecting to the server
- The worker processes tasks sequentially but multiple workers process in parallel
