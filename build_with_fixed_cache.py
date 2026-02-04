#!/usr/bin/env python3
"""Wrapper script to fix PyInstaller cache directory permissions"""
import os
import sys

# Set cache directory to project-local directory before importing PyInstaller
cache_dir = os.path.join(os.path.dirname(__file__), '.pyinstaller_cache')
os.makedirs(cache_dir, exist_ok=True)

# Import and patch BEFORE any PyInstaller modules are loaded
import PyInstaller.building.utils

# Monkey-patch the cache directory function
original_get_cache_dir = PyInstaller.building.utils.get_cache_dir

def patched_get_cache_dir():
    return cache_dir

PyInstaller.building.utils.get_cache_dir = patched_get_cache_dir
PyInstaller.building.utils._CACHEDIR = cache_dir

# Also patch process_collected_binary to use our cache
original_process = PyInstaller.building.utils.process_collected_binary

def patched_process_collected_binary(*args, **kwargs):
    # Force use of our cache directory
    import PyInstaller.building.utils as utils
    old_cache = getattr(utils, '_CACHEDIR', None)
    utils._CACHEDIR = cache_dir
    try:
        return original_process(*args, **kwargs)
    finally:
        if old_cache:
            utils._CACHEDIR = old_cache

PyInstaller.building.utils.process_collected_binary = patched_process_collected_binary

# Set environment variable
os.environ['PYINSTALLER_CACHE_DIR'] = cache_dir

# Now run PyInstaller
from PyInstaller import __main__
if len(sys.argv) > 1 and sys.argv[1] == 'build_worker.spec':
    sys.argv = ['pyinstaller'] + sys.argv[1:]
else:
    sys.argv = ['pyinstaller'] + sys.argv[1:]
__main__.run()
