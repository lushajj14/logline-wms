# -*- mode: python ; coding: utf-8 -*-
"""
LOGLine WMS - Tek Dosya EXE Build Specification
===============================================
Bu spec dosyası, mevcut Python uygulamanızı tam işlevsel
tek dosya .exe haline çevirir.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Proje kök dizini
ROOT_DIR = os.path.dirname(os.path.abspath(SPEC))

# Tüm app modüllerini otomatik topla
app_modules = collect_submodules('app')

# PyQt5 ile alakalı ek modüller
pyqt5_modules = [
    'PyQt5.sip',
    'PyQt5.QtCore',
    'PyQt5.QtGui', 
    'PyQt5.QtWidgets',
    'PyQt5.QtPrintSupport',
    'PyQt5.QtMultimedia',
    'PyQt5.QtNetwork',
    'PyQt5.QtSql',
    'PyQt5.QtSvg',
]

# Reportlab veri dosyalarını topla
try:
    reportlab_datas = collect_data_files('reportlab')
except:
    reportlab_datas = []

# PIL/Pillow veri dosyalarını topla  
try:
    pil_datas = collect_data_files('PIL')
except:
    pil_datas = []

# Numpy veri dosyalarını topla
try:
    numpy_datas = collect_data_files('numpy')
except:
    numpy_datas = []

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=[
        # App dizini (tüm uygulama kodu)
        ('app', 'app'),
        
        # Font dosyaları
        ('fonts', 'fonts'),
        ('app/fonts', 'app/fonts'),
        
        # Ses dosyaları  
        ('sounds', 'sounds'),
        ('app/sounds', 'app/sounds'),
        
        # Kaynak dosyaları
        ('app/resources', 'app/resources'),
        
        # Çıktı ve log dizinleri (boş olsa da)
        ('labels', 'labels'),
        ('output', 'output'), 
        ('logs', 'logs'),
        ('app/logs', 'app/logs'),
        
        # Konfigürasyon dosyaları
        ('settings.json', '.'),
        ('requirements.txt', '.'),
        ('run_myapp.txt', '.'),
        
        # Harici kütüphane dosyaları
        *reportlab_datas,
        *pil_datas,
        *numpy_datas,
    ],
    hiddenimports=[
        # Uygulama modülleri
        *app_modules,
        
        # PyQt5 modülleri
        *pyqt5_modules,
        
        # Ana uygulama sayfaları (explicit)
        'app.ui.pages.picklist_page',
        'app.ui.pages.scanner_page', 
        'app.ui.pages.backorders_page',
        'app.ui.pages.report_page',
        'app.ui.pages.label_page',
        'app.ui.pages.loader_page',
        'app.ui.pages.shipment_page',
        'app.ui.pages.settings_page',
        'app.ui.pages.taskboard_page',
        'app.ui.pages.barcode_page',
        
        # Servis modülleri
        'app.services.label_service',
        'app.services.picklist',
        'app.services.backorder_label_service',
        'app.services.import_barcodes',
        'app.services.backorder_picklist',
        'app.services.backorder_reporter',
        'app.services.backorder_worker',
        
        # DAO ve model modülleri
        'app.dao.logo',
        'app.ui.models.schemas',
        'app.ui.dialogs.activity_viewer',
        
        # Ana modüller
        'app.backorder',
        'app.shipment', 
        'app.settings',
        'app.sound',
        'app.config',
        'app.ddl',
        
        # Utils modülleri
        'app.utils.fonts',
        'app.utils.pdf_utils',
        'app.utils.zpl_utils',
        
        # Scanner modülleri
        'app.scanner.scanner_ui',
        'app.scanner.services',
        
        # Reportlab modülleri (PDF oluşturma için)
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
        'reportlab.graphics.barcode.code93',
        'reportlab.graphics.barcode.ean13',
        'reportlab.graphics.barcode.ean8',
        'reportlab.graphics.barcode.qr',
        'reportlab.pdfbase',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.pdfbase._fontdata',
        'reportlab.pdfbase.ttfonts',
        'reportlab.rl_config',
        
        # PIL/Pillow modülleri (görüntü işleme)
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw', 
        'PIL.ImageFont',
        'PIL.ImageFilter',
        'PIL.ImageEnhance',
        'PIL.ImageOps',
        'PIL.PngImagePlugin',
        'PIL.JpegImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.TiffImagePlugin',
        'PIL._imaging',
        'PIL._util',
        
        # QR Code modülleri
        'qrcode',
        'qrcode.image.pil',
        'qrcode.image.base',
        'qrcode.constants',
        'qrcode.util',
        'qrcode.main',
        
        # Veritabanı modülleri
        'pyodbc',
        'sqlite3',
        
        # Veri işleme modülleri
        'pandas',
        'openpyxl',
        'xlrd',
        'numpy',
        'numpy.core',
        'numpy.core._methods',
        'numpy.lib.format',
        
        # Web/API modülleri
        'fastapi',
        'python-multipart',
        
        # Sistem modülleri
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
        'configparser',
        'argparse',
        'time',
        'getpass',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Gereksiz modülleri hariç tut (boyut azaltma)
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'unittest',
        'distutils',
        'setuptools',
        'pip',
        'wheel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ dosyası oluştur
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# TEK DOSYA EXE oluştur
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LOGLine_WMS',  # Son exe dosya adı
    debug=False,         # Debug modunu kapat
    bootloader_ignore_signals=False,
    strip=False,         # Sembol tablosunu kaldırma
    upx=True,           # UPX sıkıştırma kullan (boyut azaltır)
    upx_exclude=[
        'qwindows.dll',      # Qt platform pluginlerini sıkıştırma
        'api-ms-*.dll',      # Windows API DLL'lerini sıkıştırma
        'vcruntime*.dll',    # Visual C++ runtime'ları sıkıştırma
    ],
    runtime_tmpdir=None,
    console=False,       # ⭐ Konsol penceresi AÇMASSIN (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # İsterseniz .ico dosyası ekleyebilirsiniz
)
