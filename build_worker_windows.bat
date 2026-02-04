@echo off
REM Build script for Windows standalone worker executable

echo === Building ChaarFM Remote Worker for Windows ===

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.9 or later.
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv_worker" (
    echo Creating virtual environment...
    python -m venv venv_worker
)

REM Activate virtual environment
call venv_worker\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install PyInstaller
pip install pyinstaller

REM Install worker dependencies
echo Installing dependencies...
pip install -r requirements-worker.txt

REM Check for FFmpeg
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo Warning: FFmpeg not found in PATH.
    echo FFmpeg is required for yt-dlp to work properly.
    echo Please download from: https://ffmpeg.org/download.html
    echo Or install via: winget install ffmpeg
    echo.
    pause
)

REM Create build directory
set BUILD_DIR=build_worker_windows
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%BUILD_DIR%"

REM Build with PyInstaller
echo Building executable...
pyinstaller build_worker.spec ^
    --distpath "%BUILD_DIR%\dist" ^
    --workpath "%BUILD_DIR%\build" ^
    --clean

REM Copy FFmpeg if available
where ffmpeg >nul 2>&1
if not errorlevel 1 (
    echo Copying FFmpeg to bundle...
    for %%F in (ffmpeg.exe) do (
        copy "%%~$PATH:F" "%BUILD_DIR%\dist\ffmpeg.exe" >nul 2>&1
    )
)

REM Copy README if exists, otherwise create simple one
if exist "WORKER_README.md" (
    copy "WORKER_README.md" "%BUILD_DIR%\dist\README.md" >nul
) else (
    (
    echo ChaarFM Remote Worker - Windows
    echo.
    echo INSTRUCTIONS:
    echo 1. Open Command Prompt or PowerShell
    echo 2. Navigate to this folder: cd "%BUILD_DIR%\dist"
    echo 3. Run: chaarfm_worker.exe --url https://chaarfm.onrender.com --code YOUR_CODE
    echo.
    echo MULTIPLE WORKERS:
    echo Run multiple instances with the same pairing code to speed up processing!
    echo Each worker automatically shares the workload.
    echo.
    echo For detailed instructions, see README.md
    ) > "%BUILD_DIR%\dist\README.txt"
)

echo.
echo === Build Complete ===
echo Executable location: %BUILD_DIR%\dist\chaarfm_worker.exe
echo.
echo To test:
echo   %BUILD_DIR%\dist\chaarfm_worker.exe --url https://chaarfm.onrender.com --code YOUR_CODE
echo.
pause
