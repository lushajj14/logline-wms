# -*- mode: python ; coding: utf-8 -*-
"""
WMS System - PyInstaller Specification File
===========================================
Complete build configuration for creating a single EXE file with all features working.

This .spec file includes:
- All hidden imports for dynamic imports
- All data files (fonts, sounds, PDFs, etc.)
- Environment file inclusion
- Version information
- Qt platform plugins
- ReportLab resources
- ODBC driver support
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# Build paths
block_cipher = None
project_root = Path(SPECPATH).resolve()

# Collect all app.services submodules
all_services = collect_submodules('app.services')
all_dao = collect_submodules('app.dao')
all_ui = collect_submodules('app.ui')

# Collect all Python source files and their dependencies
a = Analysis(
    # Main entry point
    ['main.py'],
    
    # Additional paths to search for modules
    pathex=[
        str(project_root),
        str(project_root / 'app'),
        str(project_root / 'api'),
    ],
    
    # Binary dependencies (DLLs, shared objects)
    binaries=[
        # ODBC drivers - Windows specific
        # ('C:\\Windows\\System32\\msodbcsql17.dll', '.'),  # Uncomment if you have SQL Server driver
        # ('C:\\Windows\\System32\\msvcr120.dll', '.'),     # Visual C++ redistributable
    ],
    
    # Data files to include in the bundle
    datas=[
        # Environment configuration
        # ('.env', '.'),  # REMOTE CONFIG kullanıyoruz, .env gerekmez
        # ('config.ini', '.'),  # HARDCODED server URL, config.ini gerekmez
        
        # Application configuration
        ('app/config.json', 'app/'),
        
        # Fonts
        ('app/fonts/DejaVuSans.ttf', 'app/fonts/'),
        ('fonts/DejaVuSans.ttf', 'fonts/'),
        
        # Sound files
        ('app/sounds/*.wav', 'app/sounds/'),
        ('sounds/*.wav', 'sounds/'),
        
        # Empty directories for output (will be created at runtime)
        # Note: PyInstaller can't create empty directories, these will be created by the app
        
        # Database migration scripts
        ('app/migrations/*.sql', 'app/migrations/'),
        
        # Any additional resource files
        ('pytest.ini', '.'),
    ],
    
    # Hidden imports - modules that are imported dynamically or not detected by PyInstaller
    hiddenimports=all_services + all_dao + all_ui + [
        # Qt platform plugins
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtMultimedia',
        'PyQt5.sip',
        
        # Database drivers
        'pyodbc',
        'sqlite3',
        
        # PDF and reporting
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.lib.utils',
        'reportlab.platypus',
        'reportlab.graphics',
        'reportlab.graphics.barcode',
        'reportlab.graphics.barcode.code128',
        'reportlab.graphics.barcode.code93',
        'reportlab.graphics.barcode.code39',
        'reportlab.graphics.barcode.common',
        'reportlab.graphics.barcode.dmtx',
        'reportlab.graphics.barcode.eanbc',
        'reportlab.graphics.barcode.ecc200datamatrix',
        'reportlab.graphics.barcode.fourstate',
        'reportlab.graphics.barcode.lto',
        'reportlab.graphics.barcode.qr',
        'reportlab.graphics.barcode.qrencoder',
        'reportlab.graphics.barcode.usps',
        'reportlab.graphics.barcode.usps4s',
        'reportlab.graphics.barcode.widgets',
        'reportlab.pdfbase',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.pdfbase.ttfonts',
        'reportlab.pdfbase.pdfutils',
        
        # Data processing
        'pandas',
        'numpy',
        'openpyxl',
        'xlrd',
        
        # QR Code generation
        'qrcode',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        
        # Web framework (for API)
        'fastapi',
        'uvicorn',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.websockets',
        
        # Security
        'jose',
        'jose.jwt',
        'bcrypt',
        'cryptography',
        'cryptography.fernet',
        'hashlib',
        'secrets',
        
        # Environment and configuration
        'dotenv',
        'json',
        'configparser',
        
        # System modules that might be missed
        'threading',
        'multiprocessing',
        'concurrent',
        'concurrent.futures',
        'queue',
        'collections',
        'collections.defaultdict',
        'functools',
        'itertools',
        'weakref',
        'contextlib',
        'datetime',
        'pathlib',
        'logging',
        'logging.handlers',
        'logging.config',
        'uuid',
        'getpass',
        'socket',
        'urllib',
        'urllib.parse',
        'http',
        'http.server',
        
        # Application specific modules that might be dynamically imported
        'app',
        'app.config',
        'app.config.env_config',
        'app.config.validate_env',
        'app.dao',
        'app.dao.logo',
        'app.dao.users_new',
        'app.dao.transactions',
        'app.dao.connection_pool',
        'app.dao.connection_fallback',
        'app.dao.pagination',
        'app.models',
        'app.models.user',
        'app.models.schemas',
        'app.services',
        'app.services.picklist',
        'app.services.enhanced_picklist',
        'app.services.label_service',
        'app.services.barcode_service',
        'app.services.backorder_label_service',
        'app.services.backorder_picklist',
        'app.services.backorder_reporter',
        'app.services.backorder_worker',
        'app.services.import_barcodes',
        'app.ui',
        'app.ui.main_window',
        'app.ui.toast',
        'app.ui.pages',
        'app.ui.pages.login_page',
        'app.ui.pages.dashboard_page',
        'app.ui.pages.picklist_page',
        'app.ui.pages.enhanced_picklist_page',
        'app.ui.pages.label_page',
        'app.ui.pages.loader_page',
        'app.ui.pages.scanner_page',
        'app.ui.pages.shipment_page',
        'app.ui.pages.backorders_page',
        'app.ui.pages.barcode_page',
        'app.ui.pages.user_management_page',
        'app.ui.pages.report_page',
        'app.ui.pages.taskboard_page',
        'app.ui.pages.enhanced_settings_page',
        'app.ui.dialogs',
        'app.ui.dialogs.activity_viewer',
        'app.ui.widgets',
        'app.ui.widgets.pagination_widget',
        'app.ui.models',
        'app.ui.models.xref_model',
        'app.utils',
        'app.utils.common',
        'app.utils.fonts',
        'app.utils.pdf_utils',
        'app.utils.resource_manager',
        'app.utils.sound_manager',
        'app.utils.thread_safe_cache',
        'app.utils.zpl_utils',
        'app.utils.wms_paths',
        'app.workers',
        'app.workers.celery_app',
        'app.settings',
        'app.settings_manager',
        'app.backorder',
        'app.shipment',
        'app.shipment_safe_sync',
        'app.sound',
        'app.ddl',
        'startup_validator',
        
        # API modules
        'api',
        'api.main',
        'api.routes',
        
        # Scanner modules
        'app.scanner',
        'app.scanner.scanner_ui',
        'app.scanner.services',
        
        # Tkinter (for scanner UI)
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.simpledialog',
    ],
    
    # Hooks directory (PyInstaller hooks for specific packages)
    hookspath=[],
    
    # Additional directories where PyInstaller should look for hooks
    hooksconfig={},
    
    # Runtime hooks
    runtime_hooks=[],
    
    # Modules to exclude from the build
    excludes=[
        # Exclude test modules
        'pytest',
        'pytest_cov',
        'pytest_env',
        'pytest_mock',
        
        # Exclude security scanning tools
        'bandit',
        'safety',
        
        # Exclude development tools
        'setuptools',
        'pip',
        'wheel',
        
        # Exclude unused GUI toolkits
        'tkinter',  # Remove this if you need the scanner UI
        # 'wx',
        # 'PySide2',
        # 'PySide6',
        # 'PyQt6',
    ],
    
    # Whether to include non-standard library modules
    noarchive=False,
    
    # Optimize imports
    optimize=0,
)

# Process collected files
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    # Executable name
    name='WMS_System',
    
    # Debug options
    debug=False,
    bootloader_ignore_signals=False,
    
    # Strip debug symbols for smaller size
    strip=False,
    
    # UPX compression (set to False if you don't have UPX)
    upx=False,
    
    # UPX exclude files
    upx_exclude=[],
    
    # Runtime options
    runtime_tmpdir=None,
    
    # Console window (set to True for debugging, False for GUI-only)
    console=False,
    
    # Windows specific options
    disable_windowed_traceback=False,
    
    # Target architecture
    target_arch=None,
    
    # Codesigning
    codesign_identity=None,
    entitlements_file=None,
    
    # Version information (Windows only)
    # version='version.txt',  # Disabled for now
    
    # Icon file (add your icon here)
    # icon='app/resources/icon.ico',
)