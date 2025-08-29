"""
Pagination Widget for PyQt5
============================
Reusable pagination controls for tables.
"""
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QSpinBox,
    QComboBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional, Dict, Any


class PaginationWidget(QWidget):
    """Pagination control widget for tables."""
    
    # Signals
    pageChanged = pyqtSignal(int)  # Emitted when page changes
    pageSizeChanged = pyqtSignal(int)  # Emitted when page size changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_page = 1
        self._total_pages = 1
        self._total_items = 0
        self._page_size = 50
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Previous button
        self.btn_prev = QPushButton("◀ Önceki")
        self.btn_prev.clicked.connect(self.previous_page)
        self.btn_prev.setEnabled(False)
        layout.addWidget(self.btn_prev)
        
        # Page info label
        self.lbl_page_info = QLabel("Sayfa 1 / 1")
        self.lbl_page_info.setAlignment(Qt.AlignCenter)
        self.lbl_page_info.setMinimumWidth(100)
        layout.addWidget(self.lbl_page_info)
        
        # Page number input
        self.spin_page = QSpinBox()
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.setValue(1)
        self.spin_page.setMaximumWidth(60)
        self.spin_page.valueChanged.connect(self.go_to_page)
        layout.addWidget(self.spin_page)
        
        # Next button
        self.btn_next = QPushButton("Sonraki ▶")
        self.btn_next.clicked.connect(self.next_page)
        self.btn_next.setEnabled(False)
        layout.addWidget(self.btn_next)
        
        # Spacer
        layout.addStretch()
        
        # Total items label
        self.lbl_total = QLabel("Toplam: 0 kayıt")
        layout.addWidget(self.lbl_total)
        
        # Page size selector
        layout.addWidget(QLabel("Sayfa boyutu:"))
        self.cmb_page_size = QComboBox()
        self.cmb_page_size.addItems(["10", "25", "50", "100", "200"])
        self.cmb_page_size.setCurrentText(str(self._page_size))
        self.cmb_page_size.currentTextChanged.connect(self._on_page_size_changed)
        self.cmb_page_size.setMaximumWidth(70)
        layout.addWidget(self.cmb_page_size)
    
    def update_pagination(self, pagination_info: Dict[str, Any]):
        """
        Update pagination controls with new info.
        
        Args:
            pagination_info: Dictionary with pagination metadata
                - current_page: Current page number
                - total_pages: Total number of pages
                - total_count: Total number of items
                - page_size: Items per page
                - has_next: Whether there's a next page
                - has_previous: Whether there's a previous page
        """
        self._current_page = pagination_info.get('current_page', 1)
        self._total_pages = pagination_info.get('total_pages', 1)
        self._total_items = pagination_info.get('total_count', 0)
        self._page_size = pagination_info.get('page_size', 50)
        
        # Update controls
        self.spin_page.setMaximum(self._total_pages)
        self.spin_page.setValue(self._current_page)
        
        # Update labels
        self.lbl_page_info.setText(f"Sayfa {self._current_page} / {self._total_pages}")
        self.lbl_total.setText(f"Toplam: {self._total_items} kayıt")
        
        # Update buttons
        self.btn_prev.setEnabled(pagination_info.get('has_previous', False))
        self.btn_next.setEnabled(pagination_info.get('has_next', False))
        
        # Update page size combo (without triggering signal)
        self.cmb_page_size.blockSignals(True)
        self.cmb_page_size.setCurrentText(str(self._page_size))
        self.cmb_page_size.blockSignals(False)
    
    def previous_page(self):
        """Go to previous page."""
        if self._current_page > 1:
            self.go_to_page(self._current_page - 1)
    
    def next_page(self):
        """Go to next page."""
        if self._current_page < self._total_pages:
            self.go_to_page(self._current_page + 1)
    
    def go_to_page(self, page: int):
        """
        Navigate to specific page.
        
        Args:
            page: Page number to navigate to
        """
        page = max(1, min(page, self._total_pages))
        if page != self._current_page:
            self._current_page = page
            self.pageChanged.emit(page)
    
    def _on_page_size_changed(self, text: str):
        """Handle page size change."""
        try:
            new_size = int(text)
            if new_size != self._page_size:
                self._page_size = new_size
                self._current_page = 1  # Reset to first page
                self.pageSizeChanged.emit(new_size)
        except ValueError:
            pass
    
    def get_current_page(self) -> int:
        """Get current page number."""
        return self._current_page
    
    def get_page_size(self) -> int:
        """Get current page size."""
        return self._page_size
    
    def reset(self):
        """Reset pagination to initial state."""
        self._current_page = 1
        self._total_pages = 1
        self._total_items = 0
        self.update_pagination({
            'current_page': 1,
            'total_pages': 1,
            'total_count': 0,
            'page_size': self._page_size,
            'has_next': False,
            'has_previous': False
        })