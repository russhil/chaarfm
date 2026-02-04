# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['remote_worker.py'],
    pathex=[],
    binaries=[],
    datas=[('populate_youtube_universe.py', '.'), ('music_pipeline/vectorizer.py', 'music_pipeline'), ('music_pipeline/config.py', 'music_pipeline')],
    hiddenimports=['websockets', 'websockets.client', 'yt_dlp', 'tensorflow', 'essentia', 'essentia.standard', 'mutagen', 'librosa', 'certifi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='chaarfm_worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
