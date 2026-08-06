# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Stinger Studio.

Bundles:
  - app.py / engine.py  (the program)
  - ui.html             (the interface, loaded at runtime)
  - bin/ffmpeg.exe      (the render backend, so users install nothing)

Produces a single-file windowed exe: dist/StingerStudio.exe
"""
import os

block_cipher = None

datas = [
    ('ui.html', '.'),
]
# bundle ffmpeg if present in ./bin (build.bat downloads it there)
if os.path.isfile(os.path.join('bin', 'ffmpeg.exe')):
    datas.append(('bin/ffmpeg.exe', 'bin'))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['PIL', 'PIL.Image', 'PIL.ImageFilter', 'PIL.ImageSequence',
                   'numpy'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pytest'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='StingerStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,           # windowed app, no console box
    disable_windowed_traceback=False,
    icon=None,
)
