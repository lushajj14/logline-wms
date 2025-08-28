# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Temel modülleri topla
app_modules = collect_submodules('app')

# Reportlab için veri dosyalarını topla
reportlab_datas = collect_data_files('reportlab')

# PIL/Pillow için veri dosyalarını topla
try:
    pil_datas = collect_data_files('PIL')
except:
    pil_datas = []

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Temel proje dosyaları
        ('app', 'app'),
        ('fonts', 'fonts'),
        ('sounds', 'sounds'),
        ('labels', 'labels'),
        # Config dosyaları
        ('*.json', '.'),
        ('*.txt', '.'),
        ('requirements.txt', '.'),
        ('settings.json', '.'),
        # Reportlab ve PIL veri dosyaları
        *reportlab_datas,
        *pil_datas,
    ],
    hiddenimports=[
        # App modülleri
        *app_modules,
        # PyQt5 temel modülleri
        'PyQt5.sip',
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtMultimedia',
        'PyQt5.QtNetwork',
        'PyQt5.QtSql',
        # Reportlab modülleri
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.lib.styles',
        'reportlab.lib.enums',
        'reportlab.lib.utils',
        'reportlab.platypus',
        'reportlab.platypus.paragraph',
        'reportlab.platypus.frames',
        'reportlab.platypus.doctemplate',
        'reportlab.platypus.tables',
        'reportlab.platypus.flowables',
        'reportlab.graphics',
        'reportlab.graphics.shapes',
        'reportlab.graphics.charts',
        'reportlab.graphics.barcode',
        'reportlab.graphics.barcode.common',
        'reportlab.graphics.barcode.code128',
        'reportlab.graphics.barcode.code39',
        'reportlab.graphics.barcode.eanbc',
        'reportlab.graphics.barcode.qr',
        'reportlab.pdfbase',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.pdfbase._fontdata',
        'reportlab.pdfbase.ttfonts',
        'reportlab.rl_config',
        # PIL modülleri
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageFilter',
        'PIL.ImageEnhance',
        'PIL.ImageOps',
        # Database modülleri
        'pyodbc',
        'sqlite3',
        # Temel sistem modülleri
        'logging',
        'json',
        'pathlib',
        'importlib',
        'threading',
        'queue',
        'datetime',
        'decimal',
        'base64',
        'io',
        'sys',
        'os',
        'platform',
        'subprocess',
        'shutil',
        'tempfile',
        'csv',
        'xml',
        'xml.etree',
        'xml.etree.ElementTree',
        'collections',
        'itertools',
        'functools',
        'operator',
        'contextlib',
        'typing',
        'string',
        're',
        'math',
        'random',
        'uuid',
        'hashlib',
        'copy',
    ],
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
    a.binaries,
    a.zipfiles,
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
