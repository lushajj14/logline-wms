"""
Dashboard Page for WMS Application
===================================
Real-time statistics and metrics display.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QGroupBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor
from typing import Dict, List
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class StatCard(QFrame):
    """İstatistik kartı widget'ı"""
    
    def __init__(self, title: str, value: str = "0", icon: str = "📊", color: str = "#3498db"):
        super().__init__()
        self.title = title
        self._value = value
        self.color = color
        self._setup_ui(icon)
    
    def _setup_ui(self, icon: str):
        """UI setup"""
        self.setFrameStyle(QFrame.StyledPanel)
        self.setMinimumSize(180, 100)  # İlk boyuta döndür
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 12px;
                border-left: 4px solid {self.color};
                min-height: 100px;
            }}
            QFrame:hover {{
                background: #f8f9fa;
                border: 1px solid {self.color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(5)
        
        # Header
        header = QHBoxLayout()
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 20px; color: {self.color};")
        header.addWidget(icon_label)
        
        header.addStretch()
        
        # Title
        title_label = QLabel(self.title)
        title_label.setStyleSheet("""
            font-size: 11px; 
            color: #666; 
            font-weight: bold;
        """)
        title_label.setWordWrap(True)
        header.addWidget(title_label)
        
        layout.addLayout(header)
        
        # Value
        self.value_label = QLabel(self._value)
        self.value_label.setStyleSheet(f"""
            font-size: 24px; 
            font-weight: bold; 
            color: {self.color};
            margin: 8px 0;
        """)
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)
        
        layout.addStretch()
    
    def set_value(self, value: str):
        """Değeri güncelle"""
        self._value = value
        # Uzun sayıları kısalt
        formatted_value = self._format_large_number(value)
        self.value_label.setText(formatted_value)
    
    def _format_large_number(self, value: str) -> str:
        """Büyük sayıları kısalt (45146 -> 45.1K)"""
        try:
            num = int(value.replace(',', '').replace('.', ''))
            
            if num >= 1000000:
                return f"{num/1000000:.1f}M"
            elif num >= 1000:
                return f"{num/1000:.1f}K"
            else:
                return str(num)
        except (ValueError, TypeError):
            # Sayı değilse olduğu gibi döndür
            return str(value)


class DashboardPage(QWidget):
    """Dashboard ana sayfası"""
    
    # Signals
    refresh_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user = None
        self._setup_ui()
        self._setup_timer()
        self._load_initial_data()
    
    def _setup_ui(self):
        """UI kurulumu"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        self._create_header(main_layout)
        
        # Stats cards
        self._create_stats_section(main_layout)
        
        # Content splitter - responsive
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)  # Paneller gizlenemez
        
        # Sol panel - Son aktiviteler
        self._create_activities_panel(splitter)
        
        # Sağ panel - Sistem durumu
        self._create_system_panel(splitter)
        
        # Splitter oranı (aktiviteler:sistem = 60:40) - sistem paneli büyük
        splitter.setSizes([60, 40])
        
        main_layout.addWidget(splitter)
    
    def _create_header(self, layout):
        """Header oluştur"""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: #2c3e50;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Başlık
        title = QLabel("📊 Dashboard")
        title.setStyleSheet("""
            color: white;
            font-size: 24px;
            font-weight: bold;
            padding: 10px;
        """)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Kullanıcı bilgisi
        self.user_label = QLabel("Kullanıcı: -")
        self.user_label.setStyleSheet("""
            color: #ecf0f1;
            font-size: 14px;
            padding: 5px 10px;
        """)
        header_layout.addWidget(self.user_label)
        
        # Son güncelleme
        self.last_update_label = QLabel("Son güncelleme: -")
        self.last_update_label.setStyleSheet("""
            color: #bdc3c7;
            font-size: 12px;
            padding: 5px 10px;
        """)
        header_layout.addWidget(self.last_update_label)
        
        # Yenile butonu
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(refresh_btn)
        
        layout.addWidget(header_frame)
    
    def _create_stats_section(self, layout):
        """İstatistik kartları oluştur"""
        stats_frame = QFrame()
        stats_frame.setMinimumHeight(220)  # İlk boyuta döndür
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setSpacing(12)  # İlk spacing
        stats_layout.setContentsMargins(5, 5, 5, 5)
        
        # Grid yerleştirme (2x3) - ilk hali
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
        
        # İstatistik kartları
        self.stats_cards = {
            'orders': StatCard("Toplam Sipariş", "0", "📦", "#e74c3c"),
            'items': StatCard("Stok Kalemleri", "0", "📋", "#9b59b6"),
            'users': StatCard("Aktif Kullanıcı", "0", "👥", "#3498db"),
            'activities': StatCard("Bugün Aktivite", "0", "📈", "#2ecc71"),
            'alerts': StatCard("Sistem Uyarı", "0", "⚠️", "#f39c12"),
            'warehouse': StatCard("Ambar İşlem", "0", "🏭", "#16a085")
        }
        
        # Grid yerleştirme (2x3) - ilk hali
        for (card_key, card), (row, col) in zip(self.stats_cards.items(), positions):
            stats_layout.addWidget(card, row, col)
        
        layout.addWidget(stats_frame)
    
    def _create_activities_panel(self, splitter):
        """Aktiviteler paneli"""
        activities_group = QGroupBox("Son Kullanıcı Aktiviteleri")
        activities_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(activities_group)
        
        # Aktiviteler tablosu
        self.activities_table = QTableWidget(0, 4)
        self.activities_table.setHorizontalHeaderLabels([
            "Zaman", "Kullanıcı", "Aktivite", "Detay"
        ])
        
        # Tablo styling
        self.activities_table.setStyleSheet("""
            QTableWidget {
                background: white;
                alternate-background-color: #f2f2f2;
                selection-background-color: #3498db;
                gridline-color: #ddd;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            QHeaderView::section {
                background: #34495e;
                color: white;
                padding: 8px;
                font-weight: bold;
                border: none;
            }
        """)
        
        self.activities_table.setAlternatingRowColors(True)
        self.activities_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.activities_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activities_table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.activities_table)
        
        splitter.addWidget(activities_group)
    
    def _create_system_panel(self, splitter):
        """Sistem durumu paneli"""
        system_group = QGroupBox("Sistem Durumu")
        system_group.setMinimumWidth(280)  # İlk küçük boyut
        system_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(system_group)
        
        # Veritabanı durumu
        db_frame = QFrame()
        db_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                margin: 3px;
            }
        """)
        db_layout = QVBoxLayout(db_frame)
        
        db_label = QLabel("🗄️ Veritabanı Bağlantısı")
        db_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        db_layout.addWidget(db_label)
        
        self.db_status_label = QLabel("Kontrol ediliyor...")
        self.db_status_label.setStyleSheet("color: #666; font-size: 10px;")
        db_layout.addWidget(self.db_status_label)
        
        layout.addWidget(db_frame)
        
        # Connection Pool durumu
        pool_frame = QFrame()
        pool_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                margin: 3px;
            }
        """)
        pool_layout = QVBoxLayout(pool_frame)
        
        pool_label = QLabel("🔗 Connection Pool")
        pool_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        pool_layout.addWidget(pool_label)
        
        self.pool_progress = QProgressBar()
        self.pool_progress.setMinimumHeight(15)
        self.pool_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background: #3498db;
                border-radius: 2px;
            }
        """)
        pool_layout.addWidget(self.pool_progress)
        
        self.pool_info_label = QLabel("Yükleniyor...")
        self.pool_info_label.setStyleSheet("color: #666; font-size: 10px;")
        pool_layout.addWidget(self.pool_info_label)
        
        layout.addWidget(pool_frame)
        
        # LOGO veritabanı durumu
        logo_frame = QFrame()
        logo_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                margin: 3px;
            }
        """)
        logo_layout = QVBoxLayout(logo_frame)
        
        logo_label = QLabel("🏢 LOGO Veritabanı")
        logo_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        logo_layout.addWidget(logo_label)
        
        self.logo_status_label = QLabel("Kontrol ediliyor...")
        self.logo_status_label.setStyleSheet("color: #666; font-size: 10px;")
        logo_layout.addWidget(self.logo_status_label)
        
        layout.addWidget(logo_frame)
        
        layout.addStretch()
        
        splitter.addWidget(system_group)
    
    def _setup_timer(self):
        """Otomatik güncelleme timer'ı"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # 30 saniye
    
    def _load_initial_data(self):
        """İlk veri yükleme"""
        self.refresh_data()
    
    def refresh_data(self):
        """Verileri yenile"""
        try:
            # Kullanıcı bilgisini güncelle
            self._update_user_info()
            
            # İstatistikleri güncelle
            self._update_statistics()
            
            # Son aktiviteleri güncelle
            self._update_activities()
            
            # Sistem durumunu güncelle
            self._update_system_status()
            
            # Son güncelleme zamanını göster
            self.last_update_label.setText(
                f"Son güncelleme: {datetime.now().strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            logger.error(f"Dashboard refresh error: {e}")
    
    def _update_user_info(self):
        """Kullanıcı bilgisini güncelle"""
        if hasattr(self.parent(), 'current_user') and self.parent().current_user:
            user = self.parent().current_user
            self.user_label.setText(f"Kullanıcı: {user.full_name} ({user.role})")
        else:
            self.user_label.setText("Kullanıcı: Sistem")
    
    def _update_statistics(self):
        """İstatistikleri güncelle"""
        try:
            from app.dao.logo import fetch_one, fetch_all
            
            # Sipariş sayısı (LOGO tablosu)
            try:
                orders_result = fetch_one("SELECT COUNT(*) as count FROM LG_025_01_ORFICHE WHERE TRCODE IN (1,2,3,4)")
                self.stats_cards['orders'].set_value(str(orders_result.get('count', 0) if orders_result else 0))
            except Exception as e:
                logger.error(f"Orders count error: {e}")
                # Fallback - başka bir tablo deneyelim
                try:
                    orders_result = fetch_one("SELECT COUNT(*) as count FROM LG_025_01_ORFLINE")
                    self.stats_cards['orders'].set_value(f"{orders_result.get('count', 0) if orders_result else 0}")
                except:
                    self.stats_cards['orders'].set_value("N/A")
            
            # Stok kalemleri sayısı
            try:
                items_result = fetch_one("SELECT COUNT(*) as count FROM LG_025_ITEMS WHERE ACTIVE = 0")
                self.stats_cards['items'].set_value(str(items_result.get('count', 0) if items_result else 0))
            except Exception as e:
                logger.error(f"Items count error: {e}")
                self.stats_cards['items'].set_value("N/A")
            
            # Kullanıcı sayısı
            try:
                users_result = fetch_one("SELECT COUNT(*) as count FROM WMS_KULLANICILAR WHERE AKTIF = 1")
                self.stats_cards['users'].set_value(str(users_result.get('count', 0) if users_result else 0))
            except:
                self.stats_cards['users'].set_value("N/A")
            
            # Aktivite sayısı (bugün)
            try:
                activities_result = fetch_one("""
                    SELECT COUNT(*) as count 
                    FROM WMS_KULLANICI_AKTIVITELERI 
                    WHERE TARIH >= CAST(GETDATE() AS DATE)
                """)
                self.stats_cards['activities'].set_value(str(activities_result.get('count', 0) if activities_result else 0))
            except:
                self.stats_cards['activities'].set_value("N/A")
            
            # Uyarı sayısı (aktif kilitli kullanıcılar)
            try:
                alerts_result = fetch_one("""
                    SELECT COUNT(*) as count 
                    FROM WMS_KULLANICILAR 
                    WHERE KILITLI_TARIH > GETDATE()
                """)
                self.stats_cards['alerts'].set_value(str(alerts_result.get('count', 0) if alerts_result else 0))
            except:
                self.stats_cards['alerts'].set_value("0")
            
            # Ambar işlemleri (bugün)
            try:
                warehouse_result = fetch_one("""
                    SELECT COUNT(*) as count 
                    FROM LG_025_01_STFICHE 
                    WHERE CONVERT(DATE, DATE_) = CONVERT(DATE, GETDATE())
                """)
                self.stats_cards['warehouse'].set_value(str(warehouse_result.get('count', 0) if warehouse_result else 0))
            except Exception as e:
                logger.error(f"Warehouse count error: {e}")
                self.stats_cards['warehouse'].set_value("N/A")
                
        except Exception as e:
            logger.error(f"Statistics update error: {e}")
    
    def _update_activities(self):
        """Son aktiviteleri güncelle"""
        try:
            from app.dao.logo import fetch_all
            
            activities = fetch_all("""
                SELECT TOP 10
                    a.TARIH,
                    k.KULLANICI_ADI,
                    a.AKTIVITE,
                    a.DETAY
                FROM WMS_KULLANICI_AKTIVITELERI a
                JOIN WMS_KULLANICILAR k ON a.KULLANICI_REF = k.LOGICALREF
                ORDER BY a.TARIH DESC
            """)
            
            # Tabloyu temizle
            self.activities_table.setRowCount(0)
            
            # Aktiviteleri ekle
            for i, activity in enumerate(activities):
                self.activities_table.insertRow(i)
                
                # Zaman
                time_str = activity['tarih'].strftime('%H:%M:%S') if activity.get('tarih') else '-'
                self.activities_table.setItem(i, 0, QTableWidgetItem(time_str))
                
                # Kullanıcı
                self.activities_table.setItem(i, 1, QTableWidgetItem(activity.get('kullanici_adi', '-')))
                
                # Aktivite
                self.activities_table.setItem(i, 2, QTableWidgetItem(activity.get('aktivite', '-')))
                
                # Detay
                detail = activity.get('detay', '-')
                if len(detail) > 50:
                    detail = detail[:47] + "..."
                self.activities_table.setItem(i, 3, QTableWidgetItem(detail))
            
        except Exception as e:
            logger.error(f"Activities update error: {e}")
            # Hata durumunda boş tablo göster
            self.activities_table.setRowCount(1)
            self.activities_table.setItem(0, 0, QTableWidgetItem("Hata"))
            self.activities_table.setItem(0, 1, QTableWidgetItem("Sistem"))
            self.activities_table.setItem(0, 2, QTableWidgetItem("Veri yüklenemiyor"))
            self.activities_table.setItem(0, 3, QTableWidgetItem(str(e)[:50]))
    
    def _update_system_status(self):
        """Sistem durumunu güncelle"""
        try:
            # Veritabanı durumu
            from app.dao.logo import fetch_one
            
            try:
                fetch_one("SELECT 1")
                self.db_status_label.setText("✅ Bağlantı aktif")
                self.db_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            except Exception as e:
                self.db_status_label.setText(f"❌ Bağlantı hatası: {str(e)[:30]}")
                self.db_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            
            # Connection Pool durumu
            try:
                from app.dao.connection_pool import get_pool_stats
                stats = get_pool_stats()
                
                if stats:
                    active = stats.get('active_connections', 0)
                    total = stats.get('max_connections', 10)
                    
                    self.pool_progress.setMaximum(total)
                    self.pool_progress.setValue(active)
                    
                    self.pool_info_label.setText(
                        f"Aktif: {active}/{total} | "
                        f"Toplam istek: {stats.get('total_requests', 0)}"
                    )
                else:
                    self.pool_info_label.setText("Pool bilgisi alınamıyor")
                    
            except Exception as e:
                self.pool_info_label.setText(f"Pool durumu: {str(e)[:30]}")
            
            # LOGO veritabanı tablo kontrolü
            try:
                from app.dao.logo import fetch_one
                
                # LOGO tabloları test
                logo_tests = [
                    ("Sipariş Tablosu", "SELECT COUNT(*) as count FROM LG_025_01_ORFICHE"),
                    ("Stok Tablosu", "SELECT COUNT(*) as count FROM LG_025_ITEMS"),
                    ("Ambar Tablosu", "SELECT COUNT(*) as count FROM LG_025_01_STFICHE")
                ]
                
                logo_status = []
                for test_name, query in logo_tests:
                    try:
                        result = fetch_one(query)
                        count = result.get('count', 0) if result else 0
                        logo_status.append(f"{test_name}: {count}")
                    except:
                        logo_status.append(f"{test_name}: ❌")
                
                if logo_status:
                    self.logo_status_label.setText(" | ".join(logo_status[:2]))  # İlk 2 test
                    self.logo_status_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
                else:
                    self.logo_status_label.setText("❌ Tablo erişimi yok")
                    self.logo_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                    
            except Exception as e:
                self.logo_status_label.setText(f"❌ LOGO hatası: {str(e)[:25]}")
                self.logo_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                
        except Exception as e:
            logger.error(f"System status update error: {e}")
    
    def set_current_user(self, user):
        """Aktif kullanıcıyı ayarla"""
        self.current_user = user
        self._update_user_info()