# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/fonts', 'app/fonts'),
        ('app/sounds', 'app/sounds'),
        ('app/resources', 'app/resources'),
        ('labels', 'labels'),
        ('output', 'output'),
        ('logs', 'logs'),
        ('fonts', 'fonts'),
        ('sounds', 'sounds'),
        ('settings.json', '.'),
    ],
    hiddenimports=[
        # PyQt5 modülleri
        'PyQt5.QtCore',
        'PyQt5.QtWidgets', 
        'PyQt5.QtGui',
        'PyQt5.QtMultimedia',
        'PyQt5.QtPrintSupport',
        
        # Veritabanı ve veri işleme
        'pyodbc',
        'pandas',
        'openpyxl',
        'xlrd',
        
        # PDF ve rapor işleme
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.lib.utils',
        'reportlab.platypus',
        'reportlab.platypus.doctemplate',
        'reportlab.platypus.flowables',
        'reportlab.graphics',
        'reportlab.graphics.barcode',
        'reportlab.graphics.barcode.code128',
        'reportlab.graphics.barcode.code93',
        'reportlab.graphics.barcode.code39',
        'reportlab.graphics.barcode.common',
        'reportlab.graphics.barcode.qr',
        'reportlab.graphics.barcode.code11',
        'reportlab.graphics.barcode.ean13',
        'reportlab.graphics.barcode.ean8',
        'reportlab.graphics.barcode.usps',
        'reportlab.graphics.barcode.usps4s',
        'reportlab.graphics.barcode.dmtx',
        'reportlab.graphics.barcode.lto',
        'reportlab.graphics.barcode.ecc200datamatrix',
        'reportlab.pdfbase',
        'reportlab.pdfbase.ttfonts',
        'reportlab.pdfbase.pdfmetrics',
        
        # Numpy - PDF/rapor işlemleri için gerekli
        'numpy',
        'numpy.core',
        'numpy.core._methods',
        'numpy.lib.format',
        
        # QR Code ve barcode desteği
        'qrcode',
        'qrcode.image.pil',
        'qrcode.image.base',
        'qrcode.constants',
        'qrcode.util',
        'qrcode.main',
        
        # UI sayfaları
        'app.ui.pages',
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
        
        # Servisler - TÜM SERVİSLER EKLENDİ
        'app.services.label_service',
        'app.services.picklist',
        'app.services.backorder_label_service',
        'app.services.import_barcodes',
        'app.services.backorder_picklist',
        'app.services.backorder_reporter',
        'app.services.backorder_worker',
        
        # Ana modüller
        'app',
        'app.backorder',
        'app.shipment',
        'app.settings',
        'app.sound',
        'app.config',
        'app.ddl',
        
        # DAO modülleri
        'app.dao',
        'app.dao.logo',
        
        # UI modülleri
        'app.ui',
        'app.ui.main_window',
        'app.ui.toast',
        'app.ui.models',
        'app.ui.models.schemas',
        'app.ui.dialogs',
        'app.ui.dialogs.activity_viewer',
        
        # Utils modülleri
        'app.utils',
        'app.utils.fonts',
        'app.utils.pdf_utils',
        'app.utils.zpl_utils',
        
        # Scanner modülleri
        'app.scanner.scanner_ui',
        'app.scanner.services',
        
        # Worker modülleri
        'app.workers',
        
        # Standart Python modülleri
        'datetime',
        'os',
        'sys',
        'pathlib',
        'logging',
        'json',
        'csv',
        'time',
        'typing',
        'uuid',
        'contextlib',
        'argparse',
        'io',
        'threading',
        'queue',
        'sqlite3',
        'configparser',
        
        # PIL modülleri
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.PngImagePlugin',
        'PIL.TiffImagePlugin',
        'PIL.JpegImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.GifImagePlugin',
        'PIL._imaging',
        'PIL._util',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
    ],
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
    name='CAN_Depo_Yonetim',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI uygulaması - konsol penceresi açmasın
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
