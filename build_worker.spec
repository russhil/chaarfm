# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for remote_worker standalone executable

import os
import sys

block_cipher = None

# Collect all necessary data files
datas = []

# Include music_pipeline modules
datas += [
    ('music_pipeline/vectorizer.py', 'music_pipeline'),
    ('music_pipeline/config.py', 'music_pipeline'),
]

# Include populate_youtube_universe.py
datas += [
    ('populate_youtube_universe.py', '.'),
]

# Include TensorFlow/Keras models if they exist
model_paths = [
    'music_pipeline/models',
    'models',
]
for path in model_paths:
    if os.path.exists(path):
        datas += [(path, os.path.basename(path))]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'websockets',
    'websockets.client',
    'websockets.server',
    'yt_dlp',
    'yt_dlp.extractor',
    'tensorflow',
    'tensorflow.python',
    'tensorflow.python.keras',
    'keras',
    'librosa',
    'librosa.core',
    'librosa.feature',
    'mutagen',
    'mutagen.mp3',
    'mutagen.id3',
    'certifi',
    'requests',
    'numpy',
    'psycopg2',
    'psycopg2.extensions',
    'dotenv',
    'essentia',
    'essentia.standard',
    'essentia.streaming',
    'ssl',
    'asyncio',
    'json',
    'logging',
    'traceback',
]

# Collect Essentia binaries and shared libraries
binaries = []
try:
    import essentia
    import os
    essentia_path = os.path.dirname(essentia.__file__)
    # Essentia typically has .so/.dylib/.dll files in its package
    for root, dirs, files in os.walk(essentia_path):
        for file in files:
            if file.endswith(('.so', '.dylib', '.dll')):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, essentia_path)
                binaries.append((full_path, f'essentia/{rel_path}'))
except ImportError:
    pass

a = Analysis(
    ['remote_worker.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='chaarfm_worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Keep console for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='chaarfm_worker',
)
