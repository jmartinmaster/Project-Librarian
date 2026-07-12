# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\jamie\\OneDrive\\Personel\\Documents\\GitHub\\Project-Librarian\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\jamie\\OneDrive\\Personel\\Documents\\GitHub\\Project-Librarian\\app\\views\\forms', 'app\\views\\forms'), ('C:\\Users\\jamie\\OneDrive\\Personel\\Documents\\GitHub\\Project-Librarian\\app\\views\\assets', 'app\\views\\assets'), ('C:\\Users\\jamie\\OneDrive\\Personel\\Documents\\GitHub\\Project-Librarian\\LICENSE', '.'), ('C:\\Users\\jamie\\OneDrive\\Personel\\Documents\\GitHub\\Project-Librarian\\LICENSE-MIT', '.')],
    hiddenimports=[],
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
    name='ProjectLibrarian',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
