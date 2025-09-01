#!/usr/bin/env python3
# ──────────────────────────────────────────────────────────
#  Uygulama giriş noktası
# ──────────────────────────────────────────────────────────
import sys, traceback, logging
from pathlib import Path

from PyQt5.QtCore    import Qt, QCoreApplication
from PyQt5.QtGui     import QFont
from PyQt5.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import MainWindow
import app.settings as settings            # ‹ settings.py içindeki fonksiyonlara erişim

# Validate database configuration before environment
from startup_validator import validate_startup_config
if not validate_startup_config():
    sys.exit("Database configuration validation failed.")

# Validate environment configuration at startup
from app.config.validate_env import run_validation
if not run_validation(exit_on_error=True):
    sys.exit("Environment validation failed. Please check your configuration.")

# Initialize WMS folder structure
try:
    from app.utils.wms_paths import ensure_wms_structure
    wms_folders = ensure_wms_structure()
    print(f"WMS folders initialized at: {wms_folders['base']}")
except Exception as e:
    print(f"Warning: Could not initialize WMS folders: {e}")

# ──────────────────────────────────────────────────────────
# 1) 4K / yüksek-DPI ekran desteği
# ──────────────────────────────────────────────────────────
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,   True)

# ──────────────────────────────────────────────────────────
# 2) Ayarları oku  (settings.reload()  → backward compat: load = reload)
# ──────────────────────────────────────────────────────────
CFG = settings.reload()

# ──────────────────────────────────────────────────────────
# 3) QApplication + tema & font
# ──────────────────────────────────────────────────────────
app = QApplication(sys.argv)

# —— Tema ——
theme = CFG["ui"].get("theme", "system")
if theme == "dark":
    app.setStyleSheet("""
        QWidget        { background:#232629; color:#ECECEC; }
        QLineEdit      { background:#2B2E31; border:1px solid #555; }
        QTableWidget::item:selected { background:#3A5FCD; }
    """)
elif theme == "light":
    app.setStyleSheet("")        # Qt’nin varsayılan açık teması
# “system” → işletim sisteminin temasını kullan (hiçbir şey yapma)

# —— Font ——
base_font: QFont = app.font()
base_font.setPointSize(CFG["ui"].get("font_pt", base_font.pointSize()))
app.setFont(base_font)

# ──────────────────────────────────────────────────────────
# 4) Küresel (uncaught) hata yakalayıcı → MessageBox + log
# ──────────────────────────────────────────────────────────
# Use WMS logs directory
from app.utils.wms_paths import get_wms_folders
wms_folders = get_wms_folders()
LOG_DIR = wms_folders['logs']

logging.basicConfig(
    filename = LOG_DIR / "crash.log",
    level    = logging.ERROR,
    format   = "%(asctime)s %(levelname)s: %(message)s"
)

def _excepthook(exctype, value, tb):
    msg = "".join(traceback.format_exception(exctype, value, tb))
    logging.error("UNCAUGHT EXCEPTION:\n%s", msg)
    QMessageBox.critical(None, "Beklenmeyen Hata", msg)
    # sys.__excepthook__ uygulamayı sonlandırır; biz diyalog sonrası devam ediyoruz
sys.excepthook = _excepthook

# ──────────────────────────────────────────────────────────
# 5) Login sistemi ve ana pencere
# ──────────────────────────────────────────────────────────
from app.ui.pages.login_page import LoginPage
from app.models.user import get_auth_manager

def show_main_window(user):
    """Ana pencereyi kullanıcı ile birlikte göster"""
    global main_window
    main_window = MainWindow(user=user)
    main_window.show()
    login_window.hide()

def show_login_error():
    """Login hata mesajı"""
    QMessageBox.warning(login_window, "Giriş Hatası", "Kullanıcı adı veya şifre hatalı!")

# Login penceresi oluştur
login_window = LoginPage()
login_window.login_successful.connect(show_main_window)
login_window.show()

# Global referans
main_window = None

# ──────────────────────────────────────────────────────────
# 6) Çıkış
# ──────────────────────────────────────────────────────────
sys.exit(app.exec_())
