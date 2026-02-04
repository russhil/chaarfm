# -*- mode: python ; coding: utf-8 -*-
# Onefile spec for chaarfm_worker - single executable file

block_cipher = None

a = Analysis(
    ['remote_worker.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('populate_youtube_universe.py', '.'),
        ('music_pipeline/vectorizer.py', 'music_pipeline'),
        ('music_pipeline/config.py', 'music_pipeline'),
    ],
    hiddenimports=[
        'websockets', 'websockets.client', 'yt_dlp', 'tensorflow',
        'essentia', 'essentia.standard', 'mutagen', 'librosa', 'certifi'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='chaarfm_worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
