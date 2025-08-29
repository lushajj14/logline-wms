"""
Enhanced Settings Page with Advanced Features
==============================================
Comprehensive settings management with:
- Database connection testing
- Performance tuning
- Import/Export settings
- Reset to defaults
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import json

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QGridLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QFileDialog, QMessageBox, QHBoxLayout,
    QTableWidget, QHeaderView, QTableWidgetItem, QLineEdit, QGroupBox,
    QTextEdit, QProgressBar, QSlider
)
from PyQt5.QtGui import QIcon, QColor

import app.settings as st
from app.settings_manager import get_manager


class EnhancedSettingsPage(QWidget):
    """Enhanced settings page with advanced features."""
    
    settings_saved = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.manager = get_manager()
        self._build_ui()
        self.load_settings()
    
    def _build_ui(self) -> None:
        """Build the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create tabs
        self._create_appearance_tab()
        self._create_database_tab()
        self._create_performance_tab()
        self._create_scanner_tab()
        self._create_loader_tab()
        self._create_printing_tab()
        self._create_paths_tab()
        self._create_advanced_tab()
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        
        # Left side buttons
        self.btn_import = QPushButton("İçe Aktar")
        self.btn_import.clicked.connect(self.import_settings)
        button_layout.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("Dışa Aktar")
        self.btn_export.clicked.connect(self.export_settings)
        button_layout.addWidget(self.btn_export)
        
        self.btn_reset = QPushButton("Varsayılanlara Dön")
        self.btn_reset.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(self.btn_reset)
        
        button_layout.addStretch()
        
        # Right side buttons
        self.btn_cancel = QPushButton("Vazgeç")
        self.btn_cancel.clicked.connect(self.load_settings)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_save = QPushButton("Kaydet")
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_save.setDefault(True)
        button_layout.addWidget(self.btn_save)
    
    def _create_appearance_tab(self) -> None:
        """Create appearance settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Görünüm")
        
        layout = QGridLayout(tab)
        row = 0
        
        # Theme
        layout.addWidget(QLabel("Tema:"), row, 0)
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["light", "dark", "system"])
        layout.addWidget(self.cmb_theme, row, 1)
        row += 1
        
        # Font size
        layout.addWidget(QLabel("Yazı Boyutu:"), row, 0)
        self.spin_font = QSpinBox()
        self.spin_font.setRange(7, 24)
        self.spin_font.setSuffix(" pt")
        layout.addWidget(self.spin_font, row, 1)
        row += 1
        
        # Toast duration
        layout.addWidget(QLabel("Bildirim Süresi:"), row, 0)
        self.spin_toast = QSpinBox()
        self.spin_toast.setRange(1, 10)
        self.spin_toast.setSuffix(" saniye")
        layout.addWidget(self.spin_toast, row, 1)
        row += 1
        
        # Language
        layout.addWidget(QLabel("Dil:"), row, 0)
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["TR", "EN"])
        layout.addWidget(self.cmb_lang, row, 1)
        row += 1
        
        # Sound settings group
        sound_group = QGroupBox("Ses Ayarları")
        sound_layout = QGridLayout(sound_group)
        
        self.chk_sound = QCheckBox("Sesli uyarılar aktif")
        sound_layout.addWidget(self.chk_sound, 0, 0, 1, 2)
        
        sound_layout.addWidget(QLabel("Ses Seviyesi:"), 1, 0)
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setTickPosition(QSlider.TicksBelow)
        self.slider_volume.setTickInterval(10)
        sound_layout.addWidget(self.slider_volume, 1, 1)
        
        self.lbl_volume = QLabel("50%")
        sound_layout.addWidget(self.lbl_volume, 1, 2)
        self.slider_volume.valueChanged.connect(lambda v: self.lbl_volume.setText(f"{v}%"))
        
        layout.addWidget(sound_group, row, 0, 1, 3)
        row += 1
        
        # Auto focus
        self.chk_focus = QCheckBox("Barkod alanına otomatik odaklan")
        layout.addWidget(self.chk_focus, row, 0, 1, 2)
        
        layout.setRowStretch(row + 1, 1)
    
    def _create_database_tab(self) -> None:
        """Create database settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Veritabanı")
        
        layout = QVBoxLayout(tab)
        
        # Connection info (read-only from env)
        info_group = QGroupBox("Bağlantı Bilgileri (Environment)")
        info_layout = QGridLayout(info_group)
        
        # Get values from environment
        import os
        info_layout.addWidget(QLabel("Sunucu:"), 0, 0)
        self.lbl_server = QLabel(os.getenv("LOGO_SQL_SERVER", "Not configured"))
        self.lbl_server.setStyleSheet("color: blue;")
        info_layout.addWidget(self.lbl_server, 0, 1)
        
        info_layout.addWidget(QLabel("Veritabanı:"), 1, 0)
        self.lbl_database = QLabel(os.getenv("LOGO_SQL_DB", "Not configured"))
        self.lbl_database.setStyleSheet("color: blue;")
        info_layout.addWidget(self.lbl_database, 1, 1)
        
        info_layout.addWidget(QLabel("Kullanıcı:"), 2, 0)
        self.lbl_user = QLabel(os.getenv("LOGO_SQL_USER", "Not configured"))
        self.lbl_user.setStyleSheet("color: blue;")
        info_layout.addWidget(self.lbl_user, 2, 1)
        
        # Test connection button
        self.btn_test_db = QPushButton("Bağlantıyı Test Et")
        self.btn_test_db.clicked.connect(self.test_database_connection)
        info_layout.addWidget(self.btn_test_db, 3, 0, 1, 2)
        
        layout.addWidget(info_group)
        
        # Connection settings
        conn_group = QGroupBox("Bağlantı Ayarları")
        conn_layout = QGridLayout(conn_group)
        
        conn_layout.addWidget(QLabel("Yeniden Deneme:"), 0, 0)
        self.spin_retry = QSpinBox()
        self.spin_retry.setRange(0, 10)
        conn_layout.addWidget(self.spin_retry, 0, 1)
        
        conn_layout.addWidget(QLabel("Heartbeat:"), 1, 0)
        self.spin_heartbeat = QSpinBox()
        self.spin_heartbeat.setRange(5, 120)
        self.spin_heartbeat.setSuffix(" saniye")
        conn_layout.addWidget(self.spin_heartbeat, 1, 1)
        
        layout.addWidget(conn_group)
        
        # Connection pool settings
        pool_group = QGroupBox("Connection Pool")
        pool_layout = QGridLayout(pool_group)
        
        self.chk_pool = QCheckBox("Connection Pool kullan")
        pool_layout.addWidget(self.chk_pool, 0, 0, 1, 2)
        
        pool_layout.addWidget(QLabel("Min Connections:"), 1, 0)
        self.spin_pool_min = QSpinBox()
        self.spin_pool_min.setRange(1, 10)
        pool_layout.addWidget(self.spin_pool_min, 1, 1)
        
        pool_layout.addWidget(QLabel("Max Connections:"), 2, 0)
        self.spin_pool_max = QSpinBox()
        self.spin_pool_max.setRange(2, 50)
        pool_layout.addWidget(self.spin_pool_max, 2, 1)
        
        layout.addWidget(pool_group)
        layout.addStretch()
    
    def _create_performance_tab(self) -> None:
        """Create performance settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Performans")
        
        layout = QVBoxLayout(tab)
        
        # Cache settings
        cache_group = QGroupBox("Önbellek Ayarları")
        cache_layout = QGridLayout(cache_group)
        
        self.chk_cache = QCheckBox("Önbellek kullan")
        cache_layout.addWidget(self.chk_cache, 0, 0, 1, 2)
        
        cache_layout.addWidget(QLabel("Önbellek Süresi:"), 1, 0)
        self.spin_cache_ttl = QSpinBox()
        self.spin_cache_ttl.setRange(60, 3600)
        self.spin_cache_ttl.setSuffix(" saniye")
        cache_layout.addWidget(self.spin_cache_ttl, 1, 1)
        
        cache_layout.addWidget(QLabel("Max Önbellek Boyutu:"), 2, 0)
        self.spin_cache_size = QSpinBox()
        self.spin_cache_size.setRange(100, 10000)
        self.spin_cache_size.setSuffix(" kayıt")
        cache_layout.addWidget(self.spin_cache_size, 2, 1)
        
        layout.addWidget(cache_group)
        
        # Auto refresh settings
        refresh_group = QGroupBox("Otomatik Yenileme")
        refresh_layout = QGridLayout(refresh_group)
        
        refresh_layout.addWidget(QLabel("UI Yenileme:"), 0, 0)
        self.spin_ui_refresh = QSpinBox()
        self.spin_ui_refresh.setRange(5, 300)
        self.spin_ui_refresh.setSuffix(" saniye")
        refresh_layout.addWidget(self.spin_ui_refresh, 0, 1)
        
        layout.addWidget(refresh_group)
        
        # Memory usage info
        info_group = QGroupBox("Sistem Bilgisi")
        info_layout = QVBoxLayout(info_group)
        
        self.lbl_memory = QLabel("Bellek Kullanımı: Hesaplanıyor...")
        info_layout.addWidget(self.lbl_memory)
        
        self.btn_clear_cache = QPushButton("Önbelleği Temizle")
        self.btn_clear_cache.clicked.connect(self.clear_cache)
        info_layout.addWidget(self.btn_clear_cache)
        
        layout.addWidget(info_group)
        layout.addStretch()
        
        # Update memory info
        self.update_memory_info()
    
    def _create_scanner_tab(self) -> None:
        """Create scanner settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Barkod")
        
        layout = QGridLayout(tab)
        row = 0
        
        # Prefix table
        layout.addWidget(QLabel("Depo Önekleri:"), row, 0, 1, 3)
        row += 1
        
        self.tbl_prefix = QTableWidget(0, 2)
        self.tbl_prefix.setHorizontalHeaderLabels(["Önek", "Depo ID"])
        self.tbl_prefix.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_prefix, row, 0, 4, 3)
        row += 4
        
        btn_add = QPushButton("Ekle")
        btn_add.clicked.connect(self.add_prefix_row)
        layout.addWidget(btn_add, row, 1)
        
        btn_del = QPushButton("Sil")
        btn_del.clicked.connect(self.del_prefix_row)
        layout.addWidget(btn_del, row, 2)
        row += 1
        
        # Scanner settings
        layout.addWidget(QLabel("Fazla Okuma Toleransı:"), row, 0)
        self.spin_tolerance = QSpinBox()
        self.spin_tolerance.setRange(0, 10)
        layout.addWidget(self.spin_tolerance, row, 1)
        row += 1
        
        self.chk_auto_print = QCheckBox("Okutunca otomatik yazdır")
        layout.addWidget(self.chk_auto_print, row, 0, 1, 2)
        row += 1
        
        self.chk_beep = QCheckBox("Okutunca ses çıkar")
        layout.addWidget(self.chk_beep, row, 0, 1, 2)
        
        layout.setRowStretch(row + 1, 1)
    
    def _create_loader_tab(self) -> None:
        """Create loader settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Yükleme")
        
        layout = QGridLayout(tab)
        row = 0
        
        layout.addWidget(QLabel("Otomatik Yenileme:"), row, 0)
        self.spin_loader_refresh = QSpinBox()
        self.spin_loader_refresh.setRange(5, 300)
        self.spin_loader_refresh.setSuffix(" saniye")
        layout.addWidget(self.spin_loader_refresh, row, 1)
        row += 1
        
        self.chk_block_incomplete = QCheckBox("Eksik koli ile kapatmayı engelle")
        layout.addWidget(self.chk_block_incomplete, row, 0, 1, 2)
        row += 1
        
        self.chk_show_completed = QCheckBox("Tamamlananları göster")
        layout.addWidget(self.chk_show_completed, row, 0, 1, 2)
        row += 1
        
        self.chk_auto_close = QCheckBox("Tamamlanınca otomatik kapat")
        layout.addWidget(self.chk_auto_close, row, 0, 1, 2)
        
        layout.setRowStretch(row + 1, 1)
    
    def _create_printing_tab(self) -> None:
        """Create printing settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Yazdırma")
        
        layout = QGridLayout(tab)
        row = 0
        
        # Get available printers
        from PyQt5.QtPrintSupport import QPrinterInfo
        printers = [""] + [p.printerName() for p in QPrinterInfo.availablePrinters()]
        
        layout.addWidget(QLabel("Etiket Yazıcısı:"), row, 0)
        self.cmb_label_printer = QComboBox()
        self.cmb_label_printer.addItems(printers)
        layout.addWidget(self.cmb_label_printer, row, 1)
        row += 1
        
        layout.addWidget(QLabel("Belge Yazıcısı:"), row, 0)
        self.cmb_doc_printer = QComboBox()
        self.cmb_doc_printer.addItems(printers)
        layout.addWidget(self.cmb_doc_printer, row, 1)
        row += 1
        
        layout.addWidget(QLabel("Etiket Şablonu:"), row, 0)
        self.txt_template = QLineEdit()
        layout.addWidget(self.txt_template, row, 1)
        row += 1
        
        layout.addWidget(QLabel("Kopya Sayısı:"), row, 0)
        self.spin_copies = QSpinBox()
        self.spin_copies.setRange(1, 10)
        layout.addWidget(self.spin_copies, row, 1)
        row += 1
        
        layout.addWidget(QLabel("Kağıt Boyutu:"), row, 0)
        self.cmb_paper = QComboBox()
        self.cmb_paper.addItems(["A4", "A5", "Letter", "Legal", "Custom"])
        layout.addWidget(self.cmb_paper, row, 1)
        row += 1
        
        self.chk_auto_open = QCheckBox("Yazdırma sonrası belgeyi aç")
        layout.addWidget(self.chk_auto_open, row, 0, 1, 2)
        
        layout.setRowStretch(row + 1, 1)
    
    def _create_paths_tab(self) -> None:
        """Create file paths settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Dosya Yolları")
        
        layout = QGridLayout(tab)
        row = 0
        
        # Path settings
        paths = [
            ("Etiket Klasörü:", "label_dir"),
            ("Dışa Aktarım:", "export_dir"),
            ("Log Klasörü:", "log_dir"),
            ("Yedekleme Klasörü:", "backup_dir"),
            ("Font Klasörü:", "font_dir")
        ]
        
        self.path_widgets = {}
        
        for label, key in paths:
            layout.addWidget(QLabel(label), row, 0)
            
            line_edit = QLineEdit()
            layout.addWidget(line_edit, row, 1)
            self.path_widgets[key] = line_edit
            
            btn_browse = QPushButton("...")
            btn_browse.clicked.connect(lambda checked, k=key: self.browse_folder(k))
            layout.addWidget(btn_browse, row, 2)
            
            row += 1
        
        layout.setRowStretch(row, 1)
    
    def _create_advanced_tab(self) -> None:
        """Create advanced settings tab."""
        tab = QWidget()
        self.tabs.addTab(tab, "Gelişmiş")
        
        layout = QVBoxLayout(tab)
        
        # Debug settings
        debug_group = QGroupBox("Debug Ayarları")
        debug_layout = QGridLayout(debug_group)
        
        self.chk_debug = QCheckBox("Debug modu aktif")
        debug_layout.addWidget(self.chk_debug, 0, 0, 1, 2)
        
        debug_layout.addWidget(QLabel("Log Seviyesi:"), 1, 0)
        self.cmb_log_level = QComboBox()
        self.cmb_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        debug_layout.addWidget(self.cmb_log_level, 1, 1)
        
        layout.addWidget(debug_group)
        
        # Backup settings
        backup_group = QGroupBox("Yedekleme")
        backup_layout = QGridLayout(backup_group)
        
        self.chk_backup = QCheckBox("Başlangıçta otomatik yedekle")
        backup_layout.addWidget(self.chk_backup, 0, 0, 1, 2)
        
        layout.addWidget(backup_group)
        
        # Update settings
        update_group = QGroupBox("Güncellemeler")
        update_layout = QGridLayout(update_group)
        
        self.chk_updates = QCheckBox("Güncellemeleri kontrol et")
        update_layout.addWidget(self.chk_updates, 0, 0, 1, 2)
        
        self.chk_telemetry = QCheckBox("Anonim kullanım verisi gönder")
        update_layout.addWidget(self.chk_telemetry, 1, 0, 1, 2)
        
        layout.addWidget(update_group)
        
        # Settings info
        info_group = QGroupBox("Ayar Bilgileri")
        info_layout = QVBoxLayout(info_group)
        
        self.txt_info = QTextEdit()
        self.txt_info.setReadOnly(True)
        self.txt_info.setMaximumHeight(100)
        info_layout.addWidget(self.txt_info)
        
        layout.addWidget(info_group)
        layout.addStretch()
        
        self.update_settings_info()
    
    def load_settings(self) -> None:
        """Load settings from manager to UI."""
        # Appearance
        self.cmb_theme.setCurrentText(st.get("ui.theme", "system"))
        self.spin_font.setValue(st.get("ui.font_pt", 10))
        self.spin_toast.setValue(st.get("ui.toast_secs", 3))
        self.cmb_lang.setCurrentText(st.get("ui.lang", "TR"))
        self.chk_sound.setChecked(st.get("ui.sounds.enabled", True))
        self.slider_volume.setValue(int(st.get("ui.sounds.volume", 0.9) * 100))
        self.chk_focus.setChecked(st.get("ui.auto_focus", True))
        
        # Database
        self.spin_retry.setValue(st.get("db.retry", 3))
        self.spin_heartbeat.setValue(st.get("db.heartbeat", 10))
        self.chk_pool.setChecked(st.get("db.pool_enabled", True))
        self.spin_pool_min.setValue(st.get("db.pool_min", 2))
        self.spin_pool_max.setValue(st.get("db.pool_max", 10))
        
        # Performance
        self.chk_cache.setChecked(st.get("db.cache_enabled", True))
        self.spin_cache_ttl.setValue(st.get("db.cache_ttl", 300))
        self.spin_cache_size.setValue(st.get("db.cache_size", 1000))
        self.spin_ui_refresh.setValue(st.get("ui.auto_refresh", 30))
        
        # Scanner
        self.tbl_prefix.setRowCount(0)
        for prefix, warehouse in st.get("scanner.prefixes", {}).items():
            self.add_prefix_row(prefix, warehouse)
        self.spin_tolerance.setValue(st.get("scanner.over_scan_tol", 0))
        self.chk_auto_print.setChecked(st.get("scanner.auto_print", False))
        self.chk_beep.setChecked(st.get("scanner.beep_on_scan", True))
        
        # Loader
        self.spin_loader_refresh.setValue(st.get("loader.auto_refresh", 30))
        self.chk_block_incomplete.setChecked(st.get("loader.block_incomplete", True))
        self.chk_show_completed.setChecked(st.get("loader.show_completed", False))
        self.chk_auto_close.setChecked(st.get("loader.auto_close_on_complete", False))
        
        # Printing
        self.cmb_label_printer.setCurrentText(st.get("print.label_printer", ""))
        self.cmb_doc_printer.setCurrentText(st.get("print.doc_printer", ""))
        self.txt_template.setText(st.get("print.label_tpl", "default.tpl"))
        self.spin_copies.setValue(st.get("print.copies", 1))
        self.cmb_paper.setCurrentText(st.get("print.paper_size", "A4"))
        self.chk_auto_open.setChecked(st.get("print.auto_open", True))
        
        # Paths
        for key, widget in self.path_widgets.items():
            widget.setText(st.get(f"paths.{key}", ""))
        
        # Advanced
        self.chk_debug.setChecked(st.get("advanced.debug_mode", False))
        self.cmb_log_level.setCurrentText(st.get("advanced.log_level", "INFO"))
        self.chk_backup.setChecked(st.get("advanced.backup_on_startup", True))
        self.chk_updates.setChecked(st.get("advanced.check_updates", True))
        self.chk_telemetry.setChecked(st.get("advanced.telemetry_enabled", False))
    
    def save_settings(self) -> None:
        """Save UI values to settings manager."""
        # Get manager and disable auto-save temporarily
        manager = get_manager()
        
        # Appearance (auto_save=False for batch update)
        manager.set("ui.theme", self.cmb_theme.currentText(), auto_save=False)
        manager.set("ui.font_pt", self.spin_font.value(), auto_save=False)
        manager.set("ui.toast_secs", self.spin_toast.value(), auto_save=False)
        manager.set("ui.lang", self.cmb_lang.currentText(), auto_save=False)
        manager.set("ui.sounds.enabled", self.chk_sound.isChecked(), auto_save=False)
        manager.set("ui.sounds.volume", self.slider_volume.value() / 100, auto_save=False)
        manager.set("ui.auto_focus", self.chk_focus.isChecked(), auto_save=False)
        
        # Database
        manager.set("db.retry", self.spin_retry.value(), auto_save=False)
        manager.set("db.heartbeat", self.spin_heartbeat.value(), auto_save=False)
        manager.set("db.pool_enabled", self.chk_pool.isChecked(), auto_save=False)
        manager.set("db.pool_min", self.spin_pool_min.value(), auto_save=False)
        manager.set("db.pool_max", self.spin_pool_max.value(), auto_save=False)
        
        # Performance
        manager.set("db.cache_enabled", self.chk_cache.isChecked(), auto_save=False)
        manager.set("db.cache_ttl", self.spin_cache_ttl.value(), auto_save=False)
        manager.set("db.cache_size", self.spin_cache_size.value(), auto_save=False)
        manager.set("ui.auto_refresh", self.spin_ui_refresh.value(), auto_save=False)
        
        # Scanner
        prefixes = {}
        for row in range(self.tbl_prefix.rowCount()):
            prefix_item = self.tbl_prefix.item(row, 0)
            warehouse_item = self.tbl_prefix.item(row, 1)
            if prefix_item and warehouse_item:
                prefix = prefix_item.text().strip()
                warehouse = warehouse_item.text().strip()
                if prefix and warehouse:
                    prefixes[prefix] = warehouse
        manager.set("scanner.prefixes", prefixes, auto_save=False)
        manager.set("scanner.over_scan_tol", self.spin_tolerance.value(), auto_save=False)
        manager.set("scanner.auto_print", self.chk_auto_print.isChecked(), auto_save=False)
        manager.set("scanner.beep_on_scan", self.chk_beep.isChecked(), auto_save=False)
        
        # Loader
        manager.set("loader.auto_refresh", self.spin_loader_refresh.value(), auto_save=False)
        manager.set("loader.block_incomplete", self.chk_block_incomplete.isChecked(), auto_save=False)
        manager.set("loader.show_completed", self.chk_show_completed.isChecked(), auto_save=False)
        manager.set("loader.auto_close_on_complete", self.chk_auto_close.isChecked(), auto_save=False)
        
        # Printing
        manager.set("print.label_printer", self.cmb_label_printer.currentText(), auto_save=False)
        manager.set("print.doc_printer", self.cmb_doc_printer.currentText(), auto_save=False)
        manager.set("print.label_tpl", self.txt_template.text(), auto_save=False)
        manager.set("print.copies", self.spin_copies.value(), auto_save=False)
        manager.set("print.paper_size", self.cmb_paper.currentText(), auto_save=False)
        manager.set("print.auto_open", self.chk_auto_open.isChecked(), auto_save=False)
        
        # Paths
        for key, widget in self.path_widgets.items():
            manager.set(f"paths.{key}", widget.text(), auto_save=False)
        
        # Advanced
        manager.set("advanced.debug_mode", self.chk_debug.isChecked(), auto_save=False)
        manager.set("advanced.log_level", self.cmb_log_level.currentText(), auto_save=False)
        manager.set("advanced.backup_on_startup", self.chk_backup.isChecked(), auto_save=False)
        manager.set("advanced.check_updates", self.chk_updates.isChecked(), auto_save=False)
        manager.set("advanced.telemetry_enabled", self.chk_telemetry.isChecked(), auto_save=False)
        
        # Save everything to disk once
        manager.save()
        
        # Emit signal
        self.settings_saved.emit()
        
        QMessageBox.information(self, "Ayarlar", "Ayarlar başarıyla kaydedildi!")
    
    def test_database_connection(self) -> None:
        """Test database connection."""
        try:
            from app.dao.logo import fetch_one
            result = fetch_one("SELECT 1 as test")
            if result:
                QMessageBox.information(self, "Bağlantı Testi", "Veritabanı bağlantısı başarılı!")
            else:
                QMessageBox.warning(self, "Bağlantı Testi", "Bağlantı kuruldu ama test sorgusu başarısız!")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Veritabanına bağlanılamadı!\n\n{str(e)}")
    
    def clear_cache(self) -> None:
        """Clear application cache."""
        try:
            from app.utils.thread_safe_cache import get_global_cache
            cache = get_global_cache()
            cache.clear()
            QMessageBox.information(self, "Önbellek", "Önbellek başarıyla temizlendi!")
            self.update_memory_info()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Önbellek temizlenemedi: {e}")
    
    def update_memory_info(self) -> None:
        """Update memory usage information."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.lbl_memory.setText(f"Bellek Kullanımı: {memory_mb:.1f} MB")
        except:
            self.lbl_memory.setText("Bellek Kullanımı: N/A")
    
    def update_settings_info(self) -> None:
        """Update settings file information."""
        try:
            settings_file = self.manager.settings_file
            if settings_file.exists():
                size = settings_file.stat().st_size / 1024
                modified = settings_file.stat().st_mtime
                from datetime import datetime
                mod_date = datetime.fromtimestamp(modified).strftime("%Y-%m-%d %H:%M")
                
                info = f"Ayar Dosyası: {settings_file}\n"
                info += f"Boyut: {size:.1f} KB\n"
                info += f"Son Değişiklik: {mod_date}"
            else:
                info = "Ayar dosyası henüz oluşturulmamış"
            
            self.txt_info.setText(info)
        except Exception as e:
            self.txt_info.setText(f"Bilgi alınamadı: {e}")
    
    def add_prefix_row(self, prefix: str = "", warehouse: str = "") -> None:
        """Add a new row to prefix table."""
        row = self.tbl_prefix.rowCount()
        self.tbl_prefix.insertRow(row)
        
        if prefix:
            self.tbl_prefix.setItem(row, 0, QTableWidgetItem(prefix))
        if warehouse:
            self.tbl_prefix.setItem(row, 1, QTableWidgetItem(warehouse))
    
    def del_prefix_row(self) -> None:
        """Delete selected rows from prefix table."""
        rows = {idx.row() for idx in self.tbl_prefix.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self.tbl_prefix.removeRow(row)
    
    def browse_folder(self, key: str) -> None:
        """Browse for folder."""
        current = self.path_widgets[key].text()
        folder = QFileDialog.getExistingDirectory(
            self, f"{key.replace('_', ' ').title()} Seç", 
            current or str(Path.home())
        )
        if folder:
            self.path_widgets[key].setText(folder)
    
    def import_settings(self) -> None:
        """Import settings from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Ayarları İçe Aktar", 
            str(Path.home()), 
            "JSON Files (*.json)"
        )
        
        if file_path:
            if self.manager.import_settings(Path(file_path)):
                self.load_settings()
                QMessageBox.information(self, "İçe Aktarma", "Ayarlar başarıyla içe aktarıldı!")
            else:
                QMessageBox.critical(self, "Hata", "Ayarlar içe aktarılamadı!")
    
    def export_settings(self) -> None:
        """Export settings to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Ayarları Dışa Aktar",
            str(Path.home() / "wms_settings_export.json"),
            "JSON Files (*.json)"
        )
        
        if file_path:
            if self.manager.export_settings(Path(file_path)):
                QMessageBox.information(self, "Dışa Aktarma", f"Ayarlar başarıyla dışa aktarıldı!\n{file_path}")
            else:
                QMessageBox.critical(self, "Hata", "Ayarlar dışa aktarılamadı!")
    
    def reset_to_defaults(self) -> None:
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self, "Varsayılanlara Dön",
            "Tüm ayarlar varsayılan değerlere döndürülecek.\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.manager.reset_to_defaults()
            self.load_settings()
            QMessageBox.information(self, "Sıfırlama", "Ayarlar varsayılan değerlere döndürüldü!")
    
    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.load_settings()
        else:
            super().keyPressEvent(event)