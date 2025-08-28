"""MainWindow – modüler PyQt5 çerçevesi
================================================
Bu dosya yalnızca **sidebar + lazy‑load QStackedWidget** barındırır.
Her sekme kendi modülünde:

    app/ui/pages/picklist_page.py
    app/ui/pages/scanner_page.py
    ...

Yeni sekme eklemek = sadece module + class adı listesine eklemek.
"""
from importlib import import_module
from pathlib import Path
from typing import Dict
from app import register_toast            # <–– EKLE
from app.ui.toast import Toast            # <–– EKLE
from app.ui.dialogs.activity_viewer import ActivityViewer  

from PyQt5.QtWidgets import (       # ⬅ import bloğuna ekle
    QMainWindow, QWidget, QListWidget, QListWidgetItem, QStackedWidget,
    QHBoxLayout, QSizePolicy, QAction, QTextEdit, QDialog, QVBoxLayout,QApplication           # ★ QAction, QDialog, QVBoxLayout eklendi
    
)
from PyQt5.QtGui import QFont               # 🔸 font büyütme için
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtCore import QSize, Qt


# ---- Sidebar tanımı ---------------------------------------------
_PAGES = [
    ("Pick-List",    "document-print",   "picklist_page",   "PicklistPage"),
    ("Scanner",       "system-search",    "scanner_page",    "ScannerPage"),
    ("Back-Orders",   "view-list",        "backorders_page", "BackordersPage"),
    ("Rapor",         "x-office-spreadsheet", "report_page", "ReportPage"),
    ("Etiket",        "emblem-ok",        "label_page",     "LabelPage"),
    ("Loader", "folder-download", "loader_page", "LoaderPage"),
    ("Sevkiyat", "truck", "shipment_page", "ShipmentPage"),
    ("Ayarlar",       "preferences-system", "settings_page", "SettingsPage"),
    ("Görevler", "view-task", "taskboard_page", "TaskBoardPage"),
    ("Kullanıcılar", "user-group", "user_page", "UserPage"),
    ("Yardım",        "help-about",       "help_page",       "HelpPage"),
    ("Barkodlar",     "qrcode",           "barcode_page",    "BarcodePage"),
    
    
]

BASE_DIR = Path(__file__).resolve().parent


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kısayol Kılavuzu")
        self.resize(400, 300)
        txt = QTextEdit(readOnly=True)
        txt.setHtml("""
        <h3>Klavye Kısayolları</h3>
        <ul>
          <li><b>Ctrl + +</b> → Yazı büyüt</li>
          <li><b>Ctrl + -</b> → Yazı küçült</li>
          <li><b>Ctrl + D</b> → Koyu Tema</li>
          <li><b>F5</b> → Elle Yenile (Loader)</li>
          <li><b>F1</b> → Bu pencere</li>
        </ul>
        """)
        lay = QVBoxLayout(self); lay.addWidget(txt)



from importlib import import_module
from pathlib import Path
from typing import Dict
from app import register_toast
from app.ui.toast import Toast
from app.ui.dialogs.activity_viewer import ActivityViewer

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QListWidget, QListWidgetItem, QStackedWidget,
    QHBoxLayout, QSizePolicy, QAction, QLabel, QDialog, QVBoxLayout, QTextEdit
)
from PyQt5.QtGui  import QIcon, QPalette, QColor
from PyQt5.QtCore import QSize, Qt, QTimer

# ---------------------------------------------------------------------------
#  Yardım (F1) penceresi
# ---------------------------------------------------------------------------
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kısayol Kılavuzu")
        self.resize(400, 270)
        t = QTextEdit(readOnly=True)
        t.setHtml("""
        <h3>Klavye Kısayolları</h3>
        <ul>
          <li><b>Ctrl + + / Ctrl + -</b> – Yazı boyutu büyüt/küçült</li>
          <li><b>Ctrl + D</b> – Koyu Tema Aç/Kapat</li>
          <li><b>F5</b> – Listeyi yenile (Loader)</li>
          <li><b>F1</b> – Bu pencere</li>
        </ul>
        """)
        lay = QVBoxLayout(self); lay.addWidget(t)

# ---------------------------------------------------------------------------
_PAGES = [
    ("Pick-List",  "document-print",       "picklist_page",   "PicklistPage"),
    ("Scanner",    "system-search",        "scanner_page",    "ScannerPage"),
    ("Back-Orders","view-list",            "backorders_page", "BackordersPage"),
    ("Rapor",      "x-office-spreadsheet", "report_page",     "ReportPage"),
    ("Etiket",     "emblem-ok",            "label_page",      "LabelPage"),
    ("Loader",     "folder-download",      "loader_page",     "LoaderPage"),
    ("Sevkiyat",   "truck",                "shipment_page",   "ShipmentPage"),
    ("Ayarlar",    "preferences-system",   "settings_page",   "SettingsPage"),
    ("Görevler", "view-task", "taskboard_page", "TaskBoardPage"),
    ("Kullanıcılar", "user-group", "user_page", "UserPage"),
    ("Yardım",     "help-about",           "help_page",       "HelpPage"),
    ("Barkodlar",   "qrcode",                "barcode_page",    "BarcodePage"), 
]

BASE_DIR = Path(__file__).resolve().parent

# Basit bir koyu tema stylesheet'i
DARK_CSS = """
QWidget        { background:#232629; color:#ECECEC; }
QLineEdit      { background:#2B2E31; border:1px solid #555; }
QTableWidget::item:selected { background:#3A5FCD; }
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        register_toast(self._show_toast)
        self.setWindowTitle("LOGLine Yönetim Paneli (Modüler)")
        self.resize(1400, 900)  # Daha geniş başlangıç boyutu
        self.setMinimumSize(1200, 700)  # Minimum boyut belirle
        self._pages: Dict[str, QWidget] = {}
        self._init_ui()

    # ─────────── Toast callback
    def _show_toast(self, title: str, msg: str | None = None):
        Toast(title, msg, parent=self).popup()

    # ------------------------------------------------------------------
    def _init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        lay = QHBoxLayout(central); lay.setContentsMargins(0, 0, 0, 0)

        # -------- Sidebar --------
        self.sidebar = QListWidget(); self.sidebar.setFixedWidth(180)  # Sidebar'ı daralt
        pal = QPalette(); pal.setColor(QPalette.Base, QColor("#2C3E50"))
        pal.setColor(QPalette.Text, QColor("#ECF0F1")); self.sidebar.setPalette(pal)
        for title, icon, *_ in _PAGES:
            itm = QListWidgetItem(QIcon.fromTheme(icon), title)
            itm.setSizeHint(QSize(180, 40)); self.sidebar.addItem(itm)
        self.sidebar.currentRowChanged.connect(self._change_page)
        lay.addWidget(self.sidebar)

        # -------- Orta alan --------
        self.stack = QStackedWidget(); self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.stack)

        # İlk sayfa
        self.sidebar.setCurrentRow(0)

        # ===== Menü Çubuğu =====
        bar = self.menuBar()

        # Günlükler
        log_menu = bar.addMenu("Günlükler")
        act_logs = QAction("Kullanıcı Aktiviteleri", self)
        act_logs.triggered.connect(self._open_activity_viewer)
        log_menu.addAction(act_logs)

        # Görünüm
        view_menu = bar.addMenu("Görünüm")
        self.act_dark = QAction("Koyu Tema", self, checkable=True, shortcut="Ctrl+D")
        self.act_dark.triggered.connect(self.toggle_dark)
        view_menu.addAction(self.act_dark)

        self.act_font_inc = QAction("Yazı +1", self, shortcut="Ctrl++")
        self.act_font_dec = QAction("Yazı -1", self, shortcut="Ctrl+-")
        self.act_font_inc.triggered.connect(lambda: self.bump_font(+1))
        self.act_font_dec.triggered.connect(lambda: self.bump_font(-1))
        view_menu.addAction(self.act_font_inc); view_menu.addAction(self.act_font_dec)

        # Yardım
        help_menu = bar.addMenu("Yardım")
        act_help = QAction("Kısayol Kılavuzu", self, shortcut="F1")
        act_help.triggered.connect(lambda: HelpDialog(self).exec_())
        help_menu.addAction(act_help)

        # -------- Status-Bar • SQL Health --------
        self.lbl_db = QLabel("●"); self.lbl_db.setStyleSheet("color:grey")
        self.statusBar().addPermanentWidget(self.lbl_db)

        self._db_timer = QTimer(self)
        self._db_timer.timeout.connect(self._update_db_status)
        self._db_timer.start(10_000)          # 10 sn
        self._update_db_status()

    # ------------------------------------------------------------------
    def _open_activity_viewer(self):
        ActivityViewer(self).exec_()

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _load_page(self, idx: int):
        """
        • İlk tıklamada sayfanın modülünü import eder, widget’ı yaratır.
        • Tekrar tıklamalarda önceden üretilen widget önbellekten alınır.
        • Ayarlar sekmesi kaydedilince MainWindow’da global ayarlar yeniden uygulanır.
        """
        title, _icon, mod_name, cls_name = _PAGES[idx]

        # Daha önce oluşturulduysa önbellekten ver
        if title in self._pages:
            return self._pages[title]

        try:
            mod     = import_module(f"app.ui.pages.{mod_name}")   # dinamik import
            widget  = getattr(mod, cls_name)()                    # widget instance
        except Exception as exc:                                  # Hata → placeholder
            from PyQt5.QtWidgets import QLabel
            widget = QLabel(f"<b>{title}</b><br>Yükleme hatası:<br>{exc}")
            widget.setAlignment(Qt.AlignCenter)

        # Özel bir “apply_settings()” varsa (örn. font/theme farkı), ilk açılışta uygula
        if hasattr(widget, "apply_settings") and callable(widget.apply_settings):
            widget.apply_settings()

        # Ayarlar paneli ise kaydet sinyalini yakala
        if title == "Ayarlar" and hasattr(widget, "settings_saved"):
            widget.settings_saved.connect(self._apply_global_settings)

        self.stack.addWidget(widget)
        self._pages[title] = widget
        return widget



    # MainWindow içinde - class seviyesinde
# --------------------------------------
    def _apply_global_settings(self) -> None:
        """settings.json’daki son değerlere göre tema, font, ses vb. güncelle."""
        import app.settings as st            # tek referans noktası

        # ---------- Tema ----------
        theme = st.get("ui.theme", "system")
        if theme == "dark":
            QApplication.instance().setStyleSheet(DARK_CSS)
        elif theme == "light":
            QApplication.instance().setStyleSheet("")
        # 'system' → stylesheet’e dokunma (OS temasını kullan)

        # ---------- Yazı tipi ----------
        base_font = QApplication.instance().font()
        base_font.setPointSize(st.get("ui.font_pt", base_font.pointSize()))
        QApplication.instance().setFont(base_font)

        # ---------- Toast süresi ----------
        from app.ui import toast
        toast.DEFAULT_SECS = st.get("ui.toast_secs", 3)

        # ---------- Ses ayarları ----------
        try:
            from app.sound import set_global_volume          # varsa
            set_global_volume(
                st.get("ui.sounds.volume", 0.9),
                enabled=st.get("ui.sounds.enabled", True)
            )
        except ImportError:
            pass   # sound.py yoksa sessiz geç

        # ---------- Açık tüm sayfalara yeni ayarları ilet ----------
        for w in self._pages.values():
            if hasattr(w, "apply_settings") and callable(w.apply_settings):
                w.apply_settings()

    # ------------------------------------------------------------------
    def _change_page(self, idx: int) -> None:
        """Sidebar’da seçilen satıra karşılık gelen sayfayı gösterir."""
        self.stack.setCurrentWidget(self._load_page(idx))


    # -------- Tema toggle --------------------------------------------
    def toggle_dark(self, checked: bool):
        if checked:
            self.setStyleSheet("""
                QWidget        { background:#232629; color:#ECECEC; }
                QLineEdit      { background:#2B2E31; border:1px solid #555; }
                QTableWidget::item:selected { background:#3A5FCD; }
            """)
        else:
            self.setStyleSheet("")

    # -------- Yazı boyutu ± ------------------------------------------
    def bump_font(self, delta: int = 1):
        f = self.font(); f.setPointSize(max(7, f.pointSize() + delta))
        self.setFont(f); self.sidebar.setFont(f); self.stack.setFont(f)

    def _update_db_status(self):
        from app.dao.logo import fetch_one   # içerde import = çevrimsel bağı koparır
        try:
            fetch_one("SELECT 1")            # ping
            self.lbl_db.setStyleSheet("color:lime")   # ● yeşil
            self._db_err_warned = False
        except Exception as exc:
            self.lbl_db.setStyleSheet("color:red")    # ● kırmızı
            # sadece ilk kopmada toast göster
            if not getattr(self, "_db_err_warned", False):
                self._show_toast("DB Bağlantı Hatası", str(exc)[:120])
                self._db_err_warned = True

# --------------------------------------------------------------------
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec_())
        