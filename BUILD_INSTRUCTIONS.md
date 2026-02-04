# Build Instructions for Standalone Worker Executables

## Current Status

Due to network connectivity issues, the executables cannot be built automatically at this time. However, all build scripts and configurations are ready.

## Prerequisites

### macOS Build
- Python 3.9+ installed
- Xcode Command Line Tools: `xcode-select --install`
- Internet connection (for downloading dependencies)
- FFmpeg (optional, can be installed via Homebrew: `brew install ffmpeg`)

### Windows Build
- Python 3.9+ installed
- Internet connection (for downloading dependencies)
- FFmpeg (download from https://ffmpeg.org/download.html)

## Building When Network is Available

### macOS

**Option 1: Online Build (Recommended)**
```bash
./build_worker_macos.sh
```

**Option 2: Offline Build (if PyInstaller already installed)**
```bash
./build_worker_offline.sh
```

**Option 3: Manual Build**
```bash
# Create virtual environment
python3 -m venv venv_worker
source venv_worker/bin/activate

# Install dependencies
pip install --upgrade pip
pip install pyinstaller
pip install -r requirements-worker.txt

# Build
pyinstaller build_worker.spec \
    --distpath build_worker_macos/dist \
    --workpath build_worker_macos/build \
    --clean

# Create DMG (optional)
hdiutil create -volname "ChaarFM Worker" \
    -srcfolder build_worker_macos/dist \
    -ov -format UDZO chaarfm_worker_macos.dmg
```

### Windows

**Option 1: Batch Script**
```batch
build_worker_windows.bat
```

**Option 2: Manual Build**
```batch
REM Create virtual environment
python -m venv venv_worker
venv_worker\Scripts\activate

REM Install dependencies
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r requirements-worker.txt

REM Build
pyinstaller build_worker.spec ^
    --distpath build_worker_windows\dist ^
    --workpath build_worker_windows\build ^
    --clean
```

## Build Output

### macOS
- **DMG**: `chaarfm_worker_macos.dmg` (if DMG creation succeeds)
- **Executable**: `build_worker_macos/dist/chaarfm_worker`
- **App Bundle**: `build_worker_macos/dist/chaarfm_worker.app` (if created)

### Windows
- **Executable**: `build_worker_windows/dist/chaarfm_worker.exe`
- **Support Files**: `build_worker_windows/dist/` (all required DLLs and data files)

## Troubleshooting

### Network Issues
If you encounter network connectivity issues:
1. Check your internet connection
2. Verify DNS is working: `ping pypi.org`
3. Try using a different network/VPN
4. Use offline build script if PyInstaller is already installed

### Missing Dependencies
If build fails due to missing packages:
```bash
# macOS/Linux
pip install -r requirements-worker.txt

# Windows
pip install -r requirements-worker.txt
```

### PyInstaller Issues
If PyInstaller fails:
- Ensure you're using Python 3.9-3.11 (Python 3.12+ may have compatibility issues)
- Try: `pip install --upgrade pyinstaller`
- Check PyInstaller version: `pyinstaller --version`

### Essentia Issues
Essentia can be tricky to bundle:
- Ensure Essentia is properly installed: `python3 -c "import essentia; print(essentia.__file__)"`
- Check that Essentia shared libraries are accessible
- On macOS, you may need to set library paths

### Large Executable Size
The executable will be large (500MB-1GB) because it includes:
- TensorFlow/Keras (~300-400MB)
- Essentia libraries
- All Python dependencies
- MusicNN model (downloaded on first run)

This is normal and expected.

## Testing the Build

After building, test the executable:

**macOS:**
```bash
./build_worker_macos/dist/chaarfm_worker \
    --url https://chaarfm.onrender.com \
    --code YOUR_PAIRING_CODE
```

**Windows:**
```cmd
build_worker_windows\dist\chaarfm_worker.exe ^
    --url https://chaarfm.onrender.com ^
    --code YOUR_PAIRING_CODE
```

## Distribution

### macOS DMG
The DMG file can be distributed directly. Users can:
1. Download and mount the DMG
2. Drag the app to Applications (or run directly)
3. Run from Terminal

### Windows
Distribute the entire `dist` folder or create an installer using:
- Inno Setup (free)
- NSIS (free)
- WiX Toolset (free, Microsoft)

## Files Created

All build files are ready:
- ✅ `build_worker.spec` - PyInstaller configuration
- ✅ `build_worker_macos.sh` - macOS build script
- ✅ `build_worker_windows.bat` - Windows build script
- ✅ `build_worker_offline.sh` - Offline macOS build script
- ✅ `requirements-worker.txt` - Worker dependencies
- ✅ `WORKER_README.md` - User documentation
- ✅ `BUILD_WORKER.md` - Detailed build guide

## Next Steps

1. **When network is available**: Run the appropriate build script
2. **Test the executable**: Verify it works with your server
3. **Distribute**: Share the DMG/EXE with users
4. **Document**: Update any deployment docs with the new executables

## Support

If you encounter issues:
1. Check the build output for specific errors
2. Verify all prerequisites are met
3. Ensure Python version is compatible (3.9-3.11 recommended)
4. Check PyInstaller documentation: https://pyinstaller.org/
