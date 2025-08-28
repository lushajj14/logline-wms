# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app', 'app'), ('fonts', 'fonts'), ('sounds', 'sounds')],
    hiddenimports=['PyQt5.sip', 'app.ui.pages.picklist_page', 'app.ui.pages.scanner_page', 'app.ui.pages.backorders_page', 'app.ui.pages.report_page', 'app.ui.pages.label_page', 'app.ui.pages.loader_page', 'app.ui.pages.shipment_page', 'app.ui.pages.settings_page', 'app.ui.pages.taskboard_page', 'app.ui.pages.user_page', 'app.ui.pages.help_page', 'app.ui.pages.barcode_page'],
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
    name='LOGLine_WMS',
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
