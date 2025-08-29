"""
Enhanced PickList Page
======================
Geliştirilmiş picklist sayfası:
- Günlük sipariş özeti
- Kullanıcı bilgisi ile PDF
- İstatistikler
- Gelişmiş filtreleme
"""

from __future__ import annotations
import csv
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, List, Set

from PyQt5.QtCore import Qt, QTimer, QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox,
    QSpinBox, QFileDialog, QDateEdit, QGroupBox, QGridLayout,
    QComboBox, QTextEdit, QSplitter, QTabWidget, QMenu, QAction,
    QDialog, QDialogButtonBox, QLineEdit
)
from PyQt5.QtGui import QFont, QColor, QIcon, QCursor, QPainter, QPen, QBrush

from app.dao.logo import (
    fetch_draft_orders,
    update_order_status,
    fetch_order_lines,
    queue_insert,
    queue_delete,
    fetch_all,
    fetch_one,
    _t,
)
from app.services.enhanced_picklist import (
    create_enhanced_picklist_pdf,
    create_daily_summary_pdf,
    get_daily_statistics,
)


class EnhancedPicklistPage(QWidget):
    """Enhanced Picklist management page."""
    
    # Signals
    order_processed = pyqtSignal(str)  # Order no
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._order_ids: Set[int] = set()
        self.orders: List[Dict] = []
        self._build_ui()
        self._start_timer()
        self._load_initial_data()
    
    def _build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("<h2>Gelişmiş Toplama Listesi</h2>")
        title.setStyleSheet("color: #2C3E50; padding: 10px;")
        layout.addWidget(title)
        
        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Active Orders
        self.orders_tab = QWidget()
        self._build_orders_tab()
        self.tabs.addTab(self.orders_tab, "Aktif Siparişler")
        
        # Tab 2: Daily Summary
        self.summary_tab = QWidget()
        self._build_summary_tab()
        self.tabs.addTab(self.summary_tab, "Günlük Özet")
        
        # Tab 3: Statistics
        self.stats_tab = QWidget()
        self._build_stats_tab()
        self.tabs.addTab(self.stats_tab, "İstatistikler")
    
    def _build_orders_tab(self):
        """Build active orders tab."""
        layout = QVBoxLayout(self.orders_tab)
        
        # Control panel
        ctrl_panel = QHBoxLayout()
        
        # Date filters
        ctrl_panel.addWidget(QLabel("Başlangıç:"))
        self.dt_from = QDateEdit(QDate.currentDate())
        self.dt_from.setCalendarPopup(True)
        self.dt_from.dateChanged.connect(self.refresh_orders)
        ctrl_panel.addWidget(self.dt_from)
        
        ctrl_panel.addWidget(QLabel("Bitiş:"))
        self.dt_to = QDateEdit(QDate.currentDate())
        self.dt_to.setCalendarPopup(True)
        self.dt_to.dateChanged.connect(self.refresh_orders)
        ctrl_panel.addWidget(self.dt_to)
        
        # Status filter
        ctrl_panel.addWidget(QLabel("Durum:"))
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Tümü", "Taslak", "Toplanıyor", "Hazır", "Tamamlandı"])
        self.cmb_status.currentIndexChanged.connect(self.refresh_orders)
        ctrl_panel.addWidget(self.cmb_status)
        
        # Quick search
        ctrl_panel.addWidget(QLabel("Hızlı Ara:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Sipariş no veya müşteri adı...")
        self.txt_search.setMinimumWidth(200)
        self.txt_search.textChanged.connect(self.filter_table)
        ctrl_panel.addWidget(self.txt_search)
        
        ctrl_panel.addStretch()
        
        # Action buttons
        self.btn_refresh = QPushButton("Yenile")
        self.btn_refresh.clicked.connect(self.refresh_orders)
        ctrl_panel.addWidget(self.btn_refresh)
        
        self.btn_create_pdf = QPushButton("PDF Oluştur")
        self.btn_create_pdf.clicked.connect(self.create_selected_pdfs)
        ctrl_panel.addWidget(self.btn_create_pdf)
        
        self.btn_print_batch = QPushButton("Toplu Yazdır")
        self.btn_print_batch.clicked.connect(self.batch_print_pdfs)
        ctrl_panel.addWidget(self.btn_print_batch)
        
        self.btn_export_csv = QPushButton("CSV Export")
        self.btn_export_csv.clicked.connect(self.export_csv)
        ctrl_panel.addWidget(self.btn_export_csv)
        
        layout.addLayout(ctrl_panel)
        
        # Orders table
        self.tbl_orders = QTableWidget()
        self.tbl_orders.setColumnCount(8)
        self.tbl_orders.setHorizontalHeaderLabels([
            "Sipariş No", "Müşteri", "Tarih", "Durum", 
            "Kalem", "Toplam", "Bölge", "İşlem"
        ])
        
        # Table settings
        self.tbl_orders.setAlternatingRowColors(True)
        self.tbl_orders.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_orders.setSortingEnabled(True)
        
        # Set column widths for better visibility
        self.tbl_orders.setColumnWidth(0, 150)  # Sipariş No - wider for full visibility
        self.tbl_orders.setColumnWidth(1, 250)  # Müşteri
        self.tbl_orders.setColumnWidth(2, 100)  # Tarih
        self.tbl_orders.setColumnWidth(3, 100)  # Durum
        self.tbl_orders.setColumnWidth(4, 80)   # Kalem
        self.tbl_orders.setColumnWidth(5, 120)  # Toplam
        self.tbl_orders.setColumnWidth(6, 150)  # Bölge
        self.tbl_orders.setColumnWidth(7, 80)   # PDF button - narrower
        
        # Add context menu for table
        self.tbl_orders.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_orders.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.tbl_orders)
        
        # Status bar
        self.lbl_status = QLabel("Hazır")
        self.lbl_status.setStyleSheet("padding: 5px; background: #ECF0F1;")
        layout.addWidget(self.lbl_status)
    
    def _build_summary_tab(self):
        """Build daily summary tab."""
        layout = QVBoxLayout(self.summary_tab)
        
        # Summary controls
        ctrl_layout = QHBoxLayout()
        
        ctrl_layout.addWidget(QLabel("Özet Tarihi:"))
        self.dt_summary = QDateEdit(QDate.currentDate())
        self.dt_summary.setCalendarPopup(True)
        ctrl_layout.addWidget(self.dt_summary)
        
        self.btn_daily_summary = QPushButton("Günlük Özet PDF")
        self.btn_daily_summary.clicked.connect(self.create_daily_summary)
        ctrl_layout.addWidget(self.btn_daily_summary)
        
        self.btn_weekly_report = QPushButton("Haftalık Rapor")
        self.btn_weekly_report.clicked.connect(self.create_weekly_report)
        ctrl_layout.addWidget(self.btn_weekly_report)
        
        ctrl_layout.addStretch()
        
        layout.addLayout(ctrl_layout)
        
        # Summary display
        self.summary_display = QTextEdit()
        self.summary_display.setReadOnly(True)
        self.summary_display.setStyleSheet("""
            QTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 10pt;
                background-color: #F8F9FA;
                border: 1px solid #DEE2E6;
                padding: 10px;
            }
        """)
        layout.addWidget(self.summary_display)
    
    def _build_stats_tab(self):
        """Build statistics tab."""
        layout = QVBoxLayout(self.stats_tab)
        
        # Statistics grid
        stats_grid = QGridLayout()
        
        # Today's stats
        today_group = QGroupBox("Bugünkü İstatistikler")
        today_layout = QGridLayout(today_group)
        
        self.lbl_today_total = QLabel("Toplam: 0")
        self.lbl_today_draft = QLabel("Taslak: 0")
        self.lbl_today_picking = QLabel("Toplanıyor: 0")
        self.lbl_today_completed = QLabel("Tamamlandı: 0")
        
        today_layout.addWidget(self.lbl_today_total, 0, 0)
        today_layout.addWidget(self.lbl_today_draft, 0, 1)
        today_layout.addWidget(self.lbl_today_picking, 1, 0)
        today_layout.addWidget(self.lbl_today_completed, 1, 1)
        
        stats_grid.addWidget(today_group, 0, 0)
        
        # Weekly stats
        week_group = QGroupBox("Haftalık İstatistikler")
        week_layout = QGridLayout(week_group)
        
        self.lbl_week_total = QLabel("Toplam: 0")
        self.lbl_week_avg = QLabel("Günlük Ort: 0")
        self.lbl_week_pending = QLabel("Bekleyen: 0")
        self.lbl_week_efficiency = QLabel("Verimlilik: %0")
        
        week_layout.addWidget(self.lbl_week_total, 0, 0)
        week_layout.addWidget(self.lbl_week_avg, 0, 1)
        week_layout.addWidget(self.lbl_week_pending, 1, 0)
        week_layout.addWidget(self.lbl_week_efficiency, 1, 1)
        
        stats_grid.addWidget(week_group, 0, 1)
        
        layout.addLayout(stats_grid)
        
        # Performance chart
        self.chart_widget = QWidget()
        self.chart_widget.setMinimumHeight(250)
        self.chart_widget.setStyleSheet("background-color: white; border: 1px solid #ddd;")
        layout.addWidget(self.chart_widget)
        
        # Initialize chart
        self.update_performance_chart()
        
        # Refresh button
        btn_refresh_stats = QPushButton("İstatistikleri Güncelle")
        btn_refresh_stats.clicked.connect(self.update_statistics)
        layout.addWidget(btn_refresh_stats)
        
        layout.addStretch()
    
    def _start_timer(self):
        """Start auto-refresh timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_refresh)
        self.timer.start(30000)  # 30 seconds
    
    def _load_initial_data(self):
        """Load initial data."""
        self.refresh_orders()
        self.update_statistics()
        self.update_summary_display()
    
    def refresh_orders(self):
        """Refresh orders table."""
        try:
            # Save current selection
            selected_orders = []
            for item in self.tbl_orders.selectedItems():
                row = item.row()
                if row < len(self.orders) and row not in [o[0] for o in selected_orders]:
                    selected_orders.append((row, self.orders[row].get("order_no")))
            
            # Get date range
            from_date = self.dt_from.date().toPyDate()
            to_date = self.dt_to.date().toPyDate()
            
            # Get status filter
            status_map = {
                "Tümü": None,
                "Taslak": 1,
                "Toplanıyor": 2,
                "Hazır": 3,
                "Tamamlandı": 4,
            }
            status_filter = status_map.get(self.cmb_status.currentText())
            
            # Fetch orders
            if status_filter == 1:
                # Use special function for draft orders (already has customer name)
                orders = fetch_draft_orders(limit=500)
            else:
                # Fetch all orders with filter and date range
                where_clause = "WHERE F.CANCELLED = 0"
                if status_filter:
                    where_clause += f" AND F.STATUS = {status_filter}"
                
                # Add date filter
                where_clause += f" AND CAST(F.DATE_ AS DATE) BETWEEN '{from_date}' AND '{to_date}'"
                
                orders = fetch_all(f"""
                    SELECT F.LOGICALREF as order_id,
                           F.FICHENO as order_no,
                           F.DATE_ as order_date,
                           F.STATUS as status,
                           F.DOCODE as customer_code,
                           C.DEFINITION_ as customer_name,
                           F.NETTOTAL as total_amount,
                           F.GENEXP2 as region,
                           F.CLIENTREF as client_ref
                    FROM {_t('ORFICHE')} F
                    LEFT JOIN {_t('CLCARD', period_dependent=False)} C 
                         ON C.LOGICALREF = F.CLIENTREF
                    {where_clause}
                    AND F.FICHENO LIKE 'S%2025%'
                    ORDER BY F.LOGICALREF DESC
                """)
            
            # Update table
            self.update_orders_table(orders)
            
            # Update line counts for all orders
            self.update_line_counts()
            
            # Restore selection
            self.tbl_orders.clearSelection()
            for _, order_no in selected_orders:
                for row in range(self.tbl_orders.rowCount()):
                    if row < len(self.orders) and self.orders[row].get("order_no") == order_no:
                        self.tbl_orders.selectRow(row)
                        break
            
            # Update status
            self.lbl_status.setText(f"{len(orders)} sipariş listelendi")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Siparişler yüklenemedi: {str(e)}")
    
    def _apply_row_colors(self):
        """Apply status-based colors to table rows - OPTIMIZED."""
        # Define status colors
        status_colors = {
            1: QColor("#FFF3CD"),  # Taslak - Light yellow
            2: QColor("#CCE5FF"),  # Toplanıyor - Light blue  
            3: QColor("#D4EDDA"),  # Hazır - Light green
            4: QColor("#90EE90"),  # Tamamlandı - Strong green
        }
        
        # Apply colors in batch
        for row in range(self.tbl_orders.rowCount()):
            if row < len(self.orders):
                status = self.orders[row].get("status", 0)
                color = status_colors.get(status)
                
                if color:
                    # Color all cells in the row except button column
                    for col in range(7):  # 0-6 columns (skip 7 which is button)
                        item = self.tbl_orders.item(row, col)
                        if item:
                            item.setBackground(color)
    
    def update_line_counts(self):
        """Update line counts for all displayed orders - OPTIMIZED VERSION."""
        try:
            if not self.orders:
                return
            
            # Get all order IDs
            order_ids = [order["order_id"] for order in self.orders]
            if not order_ids:
                return
            
            # Single query to get all line counts
            order_ids_str = ",".join(map(str, order_ids))
            query = f"""
                SELECT 
                    ORDFICHEREF as order_id,
                    COUNT(*) as line_count
                FROM {_t('ORFLINE')}
                WHERE ORDFICHEREF IN ({order_ids_str})
                GROUP BY ORDFICHEREF
            """
            
            # Get line counts in one query
            line_counts = fetch_all(query)
            
            # Create a dictionary for fast lookup
            counts_dict = {lc["order_id"]: lc["line_count"] for lc in line_counts}
            
            # Update table with line counts
            for row in range(self.tbl_orders.rowCount()):
                if row < len(self.orders):
                    order_id = self.orders[row]["order_id"]
                    line_count = counts_dict.get(order_id, 0)
                    self.tbl_orders.setItem(row, 4, QTableWidgetItem(f"{line_count} kalem"))
        except Exception as e:
            # If error, set default values
            for row in range(self.tbl_orders.rowCount()):
                self.tbl_orders.setItem(row, 4, QTableWidgetItem("? kalem"))
    
    def update_orders_table(self, orders):
        """Update orders table with data."""
        self.tbl_orders.setRowCount(0)
        self.orders = orders
        
        status_names = {
            1: "Taslak",
            2: "Toplanıyor",
            3: "Hazır",
            4: "Tamamlandı",
        }
        
        for order in orders:
            row = self.tbl_orders.rowCount()
            self.tbl_orders.insertRow(row)
            
            # Order No
            self.tbl_orders.setItem(row, 0, QTableWidgetItem(str(order.get("order_no", ""))))
            
            # Customer - Show customer name, fallback to code if name is missing
            customer_name = order.get("customer_name", "")
            if not customer_name:
                customer_name = order.get("customer_code", "")
            self.tbl_orders.setItem(row, 1, QTableWidgetItem(str(customer_name)[:30]))
            
            # Date
            order_date = order.get("order_date")
            if order_date:
                if hasattr(order_date, 'strftime'):
                    date_str = order_date.strftime("%d.%m.%Y")
                else:
                    date_str = str(order_date)
            else:
                date_str = ""
            self.tbl_orders.setItem(row, 2, QTableWidgetItem(date_str))
            
            # Status
            status = status_names.get(order.get("status", 0), "Bilinmiyor")
            status_item = QTableWidgetItem(status)
            self.tbl_orders.setItem(row, 3, status_item)
            
            # Line count (will be updated later)
            self.tbl_orders.setItem(row, 4, QTableWidgetItem("?"))
            
            # Total
            total = order.get("total_amount", 0)
            if total:
                total_str = f"{total:,.2f} TL"
            else:
                total_str = "0.00 TL"
            self.tbl_orders.setItem(row, 5, QTableWidgetItem(total_str))
            
            # Region - Remove KRD prefix if exists (e.g., "KRD-BOL1-GEREDE" -> "BOL1-GEREDE")
            region_full = str(order.get("region", ""))
            if region_full.startswith("KRD-"):
                region = region_full[4:]  # Remove "KRD-" prefix (4 characters)
            elif region_full.startswith("KRD "):
                region = region_full[4:]  # Remove "KRD " prefix
            else:
                region = region_full  # Keep as is if no KRD prefix
            self.tbl_orders.setItem(row, 6, QTableWidgetItem(region))
            
            # Action button
            btn_pdf = QPushButton("PDF")
            btn_pdf.clicked.connect(lambda checked, o=order: self.create_single_pdf(o))
            self.tbl_orders.setCellWidget(row, 7, btn_pdf)
        
        # Apply row colors AFTER all rows are created (more efficient)
        self._apply_row_colors()
    
    def create_selected_pdfs(self):
        """Create PDFs for selected orders."""
        selected_rows = set()
        for item in self.tbl_orders.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir sipariş seçin")
            return
        
        processed = 0
        for row in selected_rows:
            if row < len(self.orders):
                order = self.orders[row]
                try:
                    self.create_single_pdf(order)
                    processed += 1
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı: {str(e)}")
        
        if processed > 0:
            QMessageBox.information(self, "Başarılı", f"{processed} adet PDF oluşturuldu")
            self.refresh_orders()
    
    def create_single_pdf(self, order):
        """Create PDF for single order."""
        try:
            # Get order lines
            lines = fetch_order_lines(order["order_id"])
            
            # Create enhanced PDF
            pdf_path = create_enhanced_picklist_pdf(order, lines)
            
            # Update status to picking
            if order.get("status") == 1:
                update_order_status(order["order_id"], 2)
                queue_insert(order["order_id"])
            
            # Emit signal
            self.order_processed.emit(order.get("order_no", ""))
            
            # Show success
            QMessageBox.information(self, "Başarılı", 
                f"PDF oluşturuldu:\n{pdf_path.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı: {str(e)}")
    
    def create_daily_summary(self):
        """Create daily summary PDF."""
        try:
            pdf_path = create_daily_summary_pdf()
            QMessageBox.information(self, "Başarılı", 
                f"Günlük özet oluşturuldu:\n{pdf_path.name}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Özet oluşturulamadı: {str(e)}")
    
    def create_weekly_report(self):
        """Create weekly report."""
        QMessageBox.information(self, "Bilgi", "Haftalık rapor özelliği yakında eklenecek!")
    
    def export_csv(self):
        """Export table to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "CSV Kaydet", f"siparisler_{datetime.now():%Y%m%d}.csv",
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # Headers
                headers = []
                for col in range(self.tbl_orders.columnCount() - 1):  # Skip action column
                    headers.append(self.tbl_orders.horizontalHeaderItem(col).text())
                writer.writerow(headers)
                
                # Data
                for row in range(self.tbl_orders.rowCount()):
                    row_data = []
                    for col in range(self.tbl_orders.columnCount() - 1):
                        item = self.tbl_orders.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            
            QMessageBox.information(self, "Başarılı", "CSV dosyası kaydedildi")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"CSV kaydedilemedi: {str(e)}")
    
    def update_statistics(self):
        """Update statistics display."""
        try:
            from app.services.enhanced_picklist import get_daily_statistics
            
            # Get today's stats
            stats = get_daily_statistics()
            
            self.lbl_today_total.setText(f"Toplam: {stats.get('total', 0)}")
            self.lbl_today_draft.setText(f"Taslak: {stats.get('draft', 0)}")
            self.lbl_today_picking.setText(f"Toplanıyor: {stats.get('picking', 0)}")
            self.lbl_today_completed.setText(f"Tamamlandı: {stats.get('completed', 0)}")
            
            # Calculate weekly stats (simplified)
            total_week = stats.get('total', 0) * 5  # Rough estimate
            avg_daily = stats.get('total', 0)
            pending = stats.get('draft', 0) + stats.get('picking', 0)
            
            if stats.get('total', 0) > 0:
                efficiency = (stats.get('completed', 0) / stats.get('total', 0)) * 100
            else:
                efficiency = 0
            
            self.lbl_week_total.setText(f"Toplam: {total_week}")
            self.lbl_week_avg.setText(f"Günlük Ort: {avg_daily}")
            self.lbl_week_pending.setText(f"Bekleyen: {pending}")
            self.lbl_week_efficiency.setText(f"Verimlilik: %{efficiency:.0f}")
            
        except Exception as e:
            print(f"İstatistik güncellenemedi: {e}")
    
    def update_summary_display(self):
        """Update summary display text."""
        try:
            from app.services.enhanced_picklist import get_daily_statistics
            
            stats = get_daily_statistics()
            
            summary_text = f"""
╔════════════════════════════════════════╗
║         GÜNLÜK SİPARİŞ ÖZETİ          ║
║            {stats.get('date', '')}            ║
╠════════════════════════════════════════╣
║                                        ║
║  📊 GENEL DURUM                       ║
║  ─────────────────────────────────    ║
║  Toplam Sipariş    : {stats.get('total', 0):>5}             ║
║  Taslak           : {stats.get('draft', 0):>5}             ║
║  Toplanıyor       : {stats.get('picking', 0):>5}             ║
║  Tamamlandı       : {stats.get('completed', 0):>5}             ║
║                                        ║
║  📈 PERFORMANS                        ║
║  ─────────────────────────────────    ║
║  Tamamlanma Oranı : %{((stats.get('completed', 0) / stats.get('total', 1)) * 100):>4.0f}             ║
║  Bekleyen         : {stats.get('draft', 0) + stats.get('picking', 0):>5}             ║
║                                        ║
╚════════════════════════════════════════╝

Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}
"""
            self.summary_display.setPlainText(summary_text)
            
        except Exception as e:
            self.summary_display.setPlainText(f"Özet yüklenemedi: {str(e)}")
    
    def auto_refresh(self):
        """Auto refresh data."""
        if self.tabs.currentIndex() == 0:  # Orders tab
            self.refresh_orders()
        elif self.tabs.currentIndex() == 1:  # Summary tab
            self.update_summary_display()
        elif self.tabs.currentIndex() == 2:  # Stats tab
            self.update_statistics()
    
    def show_context_menu(self, position):
        """Show context menu for table."""
        item = self.tbl_orders.itemAt(position)
        if not item:
            return
        
        row = item.row()
        if row >= len(self.orders):
            return
        
        order = self.orders[row]
        
        # Create context menu
        menu = QMenu(self)
        
        # Status change menu
        status_menu = menu.addMenu("Durum Değiştir")
        
        # Add status options
        statuses = [
            (1, "Taslak", "#FFF3CD"),
            (2, "Toplanıyor", "#CCE5FF"),
            (3, "Hazır", "#D4EDDA"),
            (4, "Tamamlandı", "#D1ECF1"),
        ]
        
        current_status = order.get("status", 0)
        
        for status_code, status_name, color in statuses:
            action = QAction(status_name, self)
            action.setEnabled(status_code != current_status)
            action.triggered.connect(lambda checked, s=status_code, o=order: self.change_order_status(o, s))
            status_menu.addAction(action)
        
        menu.addSeparator()
        
        # Other actions
        pdf_action = QAction("PDF Oluştur", self)
        pdf_action.triggered.connect(lambda: self.create_single_pdf(order))
        menu.addAction(pdf_action)
        
        # Add to queue action (only for non-draft orders)
        if current_status != 1:
            queue_action = QAction("Scanner Kuyruğuna Ekle", self)
            queue_action.triggered.connect(lambda: self.add_to_queue(order))
            menu.addAction(queue_action)
        
        # Remove from queue action
        remove_queue_action = QAction("Kuyruktan Çıkar", self)
        remove_queue_action.triggered.connect(lambda: self.remove_from_queue(order))
        menu.addAction(remove_queue_action)
        
        menu.addSeparator()
        
        # Details action
        details_action = QAction("Detayları Göster", self)
        details_action.triggered.connect(lambda: self.show_order_details(order))
        menu.addAction(details_action)
        
        # Show menu at cursor position
        menu.exec_(QCursor.pos())
    
    def change_order_status(self, order, new_status):
        """Change order status manually."""
        try:
            # Confirm dialog
            status_names = {1: "Taslak", 2: "Toplanıyor", 3: "Hazır", 4: "Tamamlandı"}
            old_status = status_names.get(order.get("status", 0), "Bilinmiyor")
            new_status_name = status_names.get(new_status, "Bilinmiyor")
            
            reply = QMessageBox.question(
                self, 
                "Durum Değiştir",
                f"Sipariş: {order.get('order_no')}\n"
                f"Mevcut durum: {old_status}\n"
                f"Yeni durum: {new_status_name}\n\n"
                f"Durumu değiştirmek istediğinize emin misiniz?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Update status
            update_order_status(order["order_id"], new_status)
            
            # If changing to draft (1), add to queue
            if new_status == 2 and order.get("status") != 2:
                queue_insert(order["order_id"])
                QMessageBox.information(self, "Bilgi", "Sipariş scanner kuyruğuna eklendi")
            
            # If changing from draft to completed, remove from queue
            if new_status == 4:
                from app.dao.logo import queue_delete
                queue_delete(order["order_id"])
            
            # Refresh table
            self.refresh_orders()
            
            QMessageBox.information(self, "Başarılı", f"Sipariş durumu güncellendi: {new_status_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Durum güncellenemedi: {str(e)}")
    
    def add_to_queue(self, order):
        """Add order to scanner queue."""
        try:
            queue_insert(order["order_id"])
            QMessageBox.information(self, "Başarılı", "Sipariş scanner kuyruğuna eklendi")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kuyruğa eklenemedi: {str(e)}")
    
    def remove_from_queue(self, order):
        """Remove order from scanner queue."""
        try:
            from app.dao.logo import queue_delete
            queue_delete(order["order_id"])
            QMessageBox.information(self, "Başarılı", "Sipariş kuyruktan çıkarıldı")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kuyruktan çıkarılamadı: {str(e)}")
    
    def filter_table(self, text):
        """Filter table rows based on search text."""
        search_text = text.lower()
        
        for row in range(self.tbl_orders.rowCount()):
            # Check order no and customer name columns
            order_no = self.tbl_orders.item(row, 0)
            customer = self.tbl_orders.item(row, 1)
            
            show_row = False
            if order_no and search_text in order_no.text().lower():
                show_row = True
            elif customer and search_text in customer.text().lower():
                show_row = True
            
            # Show or hide row
            self.tbl_orders.setRowHidden(row, not show_row)
    
    def batch_print_pdfs(self):
        """Print multiple PDFs for selected orders."""
        selected_rows = set()
        for item in self.tbl_orders.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "Uyarı", "Lütfen yazdırmak için sipariş seçin")
            return
        
        try:
            import subprocess
            import os
            from pathlib import Path
            
            pdf_files = []
            for row in selected_rows:
                if row < len(self.orders):
                    order = self.orders[row]
                    # Get order lines
                    lines = fetch_order_lines(order["order_id"])
                    # Create PDF
                    pdf_path = create_enhanced_picklist_pdf(order, lines)
                    pdf_files.append(str(pdf_path))
            
            if pdf_files:
                # Open print dialog for each PDF
                for pdf_file in pdf_files:
                    if os.path.exists(pdf_file):
                        # Windows print command
                        subprocess.Popen(['start', '/min', pdf_file], shell=True)
                
                QMessageBox.information(self, "Başarılı", 
                    f"{len(pdf_files)} adet PDF yazdırma kuyruğuna gönderildi.\n"
                    "Yazıcı ayarlarınızı kontrol edin.")
        
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yazdırma hatası: {str(e)}")
    
    def show_order_details(self, order):
        """Show order details in a dialog."""
        try:
            # Get order lines
            lines = fetch_order_lines(order["order_id"])
            
            # Create dialog - WIDER for stock code visibility
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Sipariş Detayları - {order.get('order_no')}")
            dialog.setMinimumSize(900, 500)  # Increased width from 600 to 900
            
            layout = QVBoxLayout(dialog)
            
            # Order info with actual line count
            line_count = len(lines)
            status_names = {1: "Taslak", 2: "Toplanıyor", 3: "Hazır", 4: "Tamamlandı"}
            status_text = status_names.get(order.get('status', 0), "Bilinmiyor")
            
            # Extract region - Remove KRD prefix if exists
            region_full = str(order.get("region", ""))
            if region_full.startswith("KRD-"):
                region = region_full[4:]  # Remove "KRD-" prefix
            elif region_full.startswith("KRD "):
                region = region_full[4:]  # Remove "KRD " prefix
            else:
                region = region_full
            
            info_text = f"""
            Sipariş No: {order.get('order_no')}
            Müşteri: {order.get('customer_name', order.get('customer_code', 'N/A'))}
            Tarih: {order.get('order_date')}
            Durum: {status_text}
            Bölge: {region}
            Kalem Sayısı: {line_count} kalem
            """
            info_label = QLabel(info_text)
            info_label.setStyleSheet("font-size: 11pt; padding: 10px;")
            layout.addWidget(info_label)
            
            # Lines table with better column widths
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Stok Kodu", "Stok Adı", "Miktar", "Birim"])
            table.setRowCount(len(lines))
            
            # Set column widths for better visibility
            table.setColumnWidth(0, 200)  # Stock code - wide enough
            table.setColumnWidth(1, 400)  # Stock name
            table.setColumnWidth(2, 100)  # Quantity
            table.setColumnWidth(3, 80)   # Unit
            
            for i, line in enumerate(lines):
                # Stock code
                item_code = QTableWidgetItem(str(line.get("item_code", "")))
                item_code.setToolTip(str(line.get("item_code", "")))  # Full code on hover
                table.setItem(i, 0, item_code)
                
                # Stock name
                item_name = QTableWidgetItem(str(line.get("item_name", "")))
                item_name.setToolTip(str(line.get("item_name", "")))  # Full name on hover
                table.setItem(i, 1, item_name)
                
                # Quantity
                qty = line.get("qty_ordered", 0)
                qty_item = QTableWidgetItem(f"{qty:,.2f}")
                qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(i, 2, qty_item)
                
                # Unit
                unit = line.get("unit_code", "ADET")
                table.setItem(i, 3, QTableWidgetItem(unit))
            
            # Make table stretch to fill dialog
            table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(table)
            
            # Summary
            summary_label = QLabel(f"Toplam: {line_count} kalem ürün")
            summary_label.setStyleSheet("font-weight: bold; padding: 5px;")
            layout.addWidget(summary_label)
            
            # Buttons
            buttons = QDialogButtonBox(QDialogButtonBox.Ok)
            buttons.accepted.connect(dialog.accept)
            layout.addWidget(buttons)
            
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Detaylar yüklenemedi: {str(e)}")
    
    def update_performance_chart(self):
        """Update performance chart with weekly data."""
        try:
            # Get last 7 days data
            from datetime import datetime, timedelta
            
            weekly_data = []
            labels = []
            
            for i in range(6, -1, -1):
                date = datetime.now().date() - timedelta(days=i)
                
                # Get stats for this date
                day_stats = fetch_one(f"""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN STATUS = 4 THEN 1 ELSE 0 END) as completed
                    FROM {_t('ORFICHE')}
                    WHERE CAST(DATE_ AS DATE) = '{date}'
                    AND FICHENO LIKE 'S%2025%'
                """)
                
                if day_stats:
                    weekly_data.append(day_stats.get("total", 0))
                    labels.append(date.strftime("%d/%m"))
                else:
                    weekly_data.append(0)
                    labels.append(date.strftime("%d/%m"))
            
            # Paint the chart
            self.chart_data = weekly_data
            self.chart_labels = labels
            self.chart_widget.paintEvent = self.paint_chart
            self.chart_widget.update()
            
        except Exception as e:
            print(f"Chart güncellenemedi: {e}")
    
    def paint_chart(self, event):
        """Paint performance chart."""
        if not hasattr(self, 'chart_data'):
            return
        
        painter = QPainter(self.chart_widget)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Chart dimensions
        width = self.chart_widget.width()
        height = self.chart_widget.height()
        margin = 40
        chart_width = width - 2 * margin
        chart_height = height - 2 * margin
        
        # Background
        painter.fillRect(0, 0, width, height, QColor("#FFFFFF"))
        
        # Title
        painter.setPen(QPen(QColor("#2C3E50"), 2))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(margin, 20, "Haftalık Sipariş Performansı")
        
        # Draw axes
        painter.setPen(QPen(QColor("#34495E"), 2))
        painter.drawLine(margin, height - margin, width - margin, height - margin)  # X axis
        painter.drawLine(margin, margin, margin, height - margin)  # Y axis
        
        # Calculate bar dimensions
        if self.chart_data:
            max_value = max(self.chart_data) if max(self.chart_data) > 0 else 10
            bar_width = chart_width / len(self.chart_data) * 0.6
            spacing = chart_width / len(self.chart_data) * 0.4
            
            # Draw bars
            for i, value in enumerate(self.chart_data):
                x = margin + i * (bar_width + spacing) + spacing/2
                bar_height = (value / max_value) * chart_height if max_value > 0 else 0
                y = height - margin - bar_height
                
                # Bar color based on value
                if value == 0:
                    color = QColor("#95A5A6")
                elif value < 5:
                    color = QColor("#E74C3C")
                elif value < 10:
                    color = QColor("#F39C12")
                else:
                    color = QColor("#27AE60")
                
                painter.fillRect(int(x), int(y), int(bar_width), int(bar_height), color)
                
                # Value on top of bar
                painter.setPen(QPen(QColor("#2C3E50"), 1))
                painter.setFont(QFont("Arial", 9))
                painter.drawText(int(x + bar_width/2 - 10), int(y - 5), str(value))
                
                # Label below bar
                painter.setFont(QFont("Arial", 8))
                painter.drawText(int(x + bar_width/2 - 15), height - margin + 15, self.chart_labels[i])
        
        painter.end()