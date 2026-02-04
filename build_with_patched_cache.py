#!/usr/bin/env python3
"""Build script that patches PyInstaller to use local cache"""
import os
import sys

# Set local cache BEFORE importing PyInstaller
local_cache = os.path.join(os.path.dirname(__file__), '.pyinstaller_cache_local')
os.makedirs(local_cache, exist_ok=True)

# Patch environment before PyInstaller loads
os.environ['PYINSTALLER_CACHE_DIR'] = local_cache

# Import and patch PyInstaller's cache location
import PyInstaller.building.utils

# Monkey-patch the cache directory function
original_makedirs = os.makedirs
def patched_makedirs(name, mode=0o777, exist_ok=False):
    # If it's trying to create the system cache, redirect to local cache
    if '/Library/Application Support/pyinstaller' in name:
        # Replace with local cache path
        new_path = name.replace('/Users/russhil/Library/Application Support/pyinstaller', local_cache)
        return original_makedirs(new_path, mode, exist_ok)
    return original_makedirs(name, mode, exist_ok)

# Patch os.makedirs in the utils module
PyInstaller.building.utils.os.makedirs = patched_makedirs

# Also patch the cachedir
if hasattr(PyInstaller.building.utils, '_CACHEDIR'):
    PyInstaller.building.utils._CACHEDIR = local_cache

# Now run PyInstaller
from PyInstaller import __main__

# Build command
sys.argv = [
    'pyinstaller',
    'remote_worker.py',
    '--name', 'chaarfm_worker',
    '--onefile',
    '--distpath', 'build_worker_macos/dist',
    '--workpath', 'build_worker_macos/build',
    '--noconfirm',
    '--hidden-import', 'websockets',
    '--hidden-import', 'websockets.client',
    '--hidden-import', 'yt_dlp',
    '--hidden-import', 'tensorflow',
    '--hidden-import', 'essentia',
    '--hidden-import', 'essentia.standard',
    '--hidden-import', 'mutagen',
    '--hidden-import', 'librosa',
    '--hidden-import', 'certifi',
    '--add-data', 'populate_youtube_universe.py:.',
    '--add-data', 'music_pipeline/vectorizer.py:music_pipeline',
    '--add-data', 'music_pipeline/config.py:music_pipeline',
    '--console'
]

__main__.run()
