"""
User Management Page
====================
Comprehensive user management interface for WMS.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QDialog,
    QDialogButtonBox, QFormLayout, QMessageBox, QHeaderView, QGroupBox,
    QTabWidget, QTextEdit, QSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QColor, QFont
from typing import Optional, Dict, List
from datetime import datetime
import logging
import bcrypt

from app.dao.users_new import UserDAO
from app.models.user import User, get_auth_manager

logger = logging.getLogger(__name__)


class UserManagementPage(QWidget):
    """User management page."""
    
    # Signals
    user_updated = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dao = UserDAO()
        self.auth_manager = get_auth_manager()
        self.current_user = self.auth_manager.get_current_user()
        self._setup_ui()
        self._load_users()
    
    def _setup_ui(self):
        """Setup user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("👥 Kullanıcı Yönetimi")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Kullanıcı ara...")
        self.search_input.setMaximumWidth(250)
        self.search_input.textChanged.connect(self._filter_users)
        header_layout.addWidget(self.search_input)
        
        # Refresh button
        self.btn_refresh = QPushButton("🔄 Yenile")
        self.btn_refresh.clicked.connect(self._load_users)
        header_layout.addWidget(self.btn_refresh)
        
        # Add user button
        self.btn_add = QPushButton("➕ Yeni Kullanıcı")
        self.btn_add.clicked.connect(self._add_user)
        header_layout.addWidget(self.btn_add)
        
        layout.addLayout(header_layout)
        
        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 5px;")
        layout.addWidget(self.stats_label)
        
        # User table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Table columns
        columns = [
            "ID", "Kullanıcı Adı", "Ad Soyad", "Email", 
            "Rol", "Durum", "Son Giriş", "Oluşturma", "İşlemler"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Column widths
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Ad Soyad
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Email
        
        self.table.setColumnWidth(0, 60)   # ID
        self.table.setColumnWidth(1, 120)  # Kullanıcı Adı
        self.table.setColumnWidth(4, 100)  # Rol
        self.table.setColumnWidth(5, 80)   # Durum
        self.table.setColumnWidth(6, 120)  # Son Giriş
        self.table.setColumnWidth(7, 120)  # Oluşturma
        self.table.setColumnWidth(8, 150)  # İşlemler
        
        layout.addWidget(self.table)
        
        # Check permissions
        if not self.current_user or not self.current_user.is_admin:
            self.btn_add.setEnabled(False)
            self.btn_add.setToolTip("Sadece adminler kullanıcı ekleyebilir")
    
    def _load_users(self):
        """Load users from database."""
        try:
            users = self.dao.get_all_users()
            self._populate_table(users)
            self._update_stats(users)
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            QMessageBox.critical(self, "Hata", f"Kullanıcılar yüklenemedi:\n{str(e)}")
    
    def _populate_table(self, users: List[Dict]):
        """Populate table with users."""
        self.table.setRowCount(len(users))
        
        for row, user in enumerate(users):
            # ID
            self.table.setItem(row, 0, QTableWidgetItem(str(user.get('id', ''))))
            
            # Username
            self.table.setItem(row, 1, QTableWidgetItem(user.get('username', '')))
            
            # Full Name
            self.table.setItem(row, 2, QTableWidgetItem(user.get('full_name', '')))
            
            # Email
            self.table.setItem(row, 3, QTableWidgetItem(user.get('email', '')))
            
            # Role
            role = user.get('role', 'operator')
            role_item = QTableWidgetItem(self._get_role_display(role))
            role_item.setData(Qt.UserRole, role)
            self.table.setItem(row, 4, role_item)
            
            # Status
            is_active = user.get('is_active', False)
            status_item = QTableWidgetItem("✅ Aktif" if is_active else "❌ Pasif")
            status_item.setForeground(QColor("green" if is_active else "red"))
            self.table.setItem(row, 5, status_item)
            
            # Last Login
            last_login = user.get('last_login')
            if last_login:
                try:
                    if isinstance(last_login, str):
                        last_login_dt = datetime.fromisoformat(last_login)
                    else:
                        last_login_dt = last_login
                    last_login_str = last_login_dt.strftime("%d.%m.%Y %H:%M")
                except:
                    last_login_str = str(last_login)[:16] if last_login else "-"
            else:
                last_login_str = "-"
            self.table.setItem(row, 6, QTableWidgetItem(last_login_str))
            
            # Created Date
            created = user.get('created_at')
            if created:
                try:
                    if isinstance(created, str):
                        created_dt = datetime.fromisoformat(created)
                    else:
                        created_dt = created
                    created_str = created_dt.strftime("%d.%m.%Y")
                except:
                    created_str = str(created)[:10] if created else "-"
            else:
                created_str = "-"
            self.table.setItem(row, 7, QTableWidgetItem(created_str))
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 0, 5, 0)
            
            # Edit button
            btn_edit = QPushButton("✏️")
            btn_edit.setToolTip("Düzenle")
            btn_edit.setMaximumWidth(30)
            btn_edit.clicked.connect(lambda checked, u=user: self._edit_user(u))
            actions_layout.addWidget(btn_edit)
            
            # Reset password button
            btn_reset = QPushButton("🔑")
            btn_reset.setToolTip("Şifre Sıfırla")
            btn_reset.setMaximumWidth(30)
            btn_reset.clicked.connect(lambda checked, u=user: self._reset_password(u))
            actions_layout.addWidget(btn_reset)
            
            # Delete button
            btn_delete = QPushButton("🗑️")
            btn_delete.setToolTip("Sil")
            btn_delete.setMaximumWidth(30)
            btn_delete.clicked.connect(lambda checked, u=user: self._delete_user(u))
            actions_layout.addWidget(btn_delete)
            
            # Disable actions for non-admins
            if not self.current_user or not self.current_user.is_admin:
                btn_edit.setEnabled(False)
                btn_reset.setEnabled(False)
                btn_delete.setEnabled(False)
            
            # Don't allow deleting yourself
            if self.current_user and user.get('id') == self.current_user.id:
                btn_delete.setEnabled(False)
            
            self.table.setCellWidget(row, 8, actions_widget)
    
    def _update_stats(self, users: List[Dict]):
        """Update statistics label."""
        total = len(users)
        active = sum(1 for u in users if u.get('is_active'))
        admins = sum(1 for u in users if u.get('role') == 'admin')
        
        stats_text = (
            f"📊 Toplam: {total} kullanıcı | "
            f"✅ Aktif: {active} | "
            f"👑 Admin: {admins}"
        )
        self.stats_label.setText(stats_text)
    
    def _get_role_display(self, role: str) -> str:
        """Get display name for role."""
        roles = {
            'admin': '👑 Admin',
            'supervisor': '👔 Supervisor',
            'operator': '👷 Operatör',
            'viewer': '👁️ İzleyici'
        }
        return roles.get(role, role)
    
    def _filter_users(self):
        """Filter users based on search text."""
        search_text = self.search_input.text().lower()
        
        for row in range(self.table.rowCount()):
            show = False
            
            if not search_text:
                show = True
            else:
                # Check username, full name, email
                for col in [1, 2, 3]:
                    item = self.table.item(row, col)
                    if item and search_text in item.text().lower():
                        show = True
                        break
            
            self.table.setRowHidden(row, not show)
    
    def _add_user(self):
        """Show add user dialog."""
        dialog = UserEditDialog(self)
        if dialog.exec_():
            user_data = dialog.get_user_data()
            try:
                self.dao.create_user(user_data)
                QMessageBox.information(self, "Başarılı", "Kullanıcı eklendi!")
                self._load_users()
                self.user_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kullanıcı eklenemedi:\n{str(e)}")
    
    def _edit_user(self, user: Dict):
        """Show edit user dialog."""
        dialog = UserEditDialog(self, user)
        if dialog.exec_():
            user_data = dialog.get_user_data()
            try:
                self.dao.update_user(user['id'], user_data)
                QMessageBox.information(self, "Başarılı", "Kullanıcı güncellendi!")
                self._load_users()
                self.user_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kullanıcı güncellenemedi:\n{str(e)}")
    
    def _reset_password(self, user: Dict):
        """Reset user password."""
        dialog = PasswordResetDialog(self, user)
        if dialog.exec_():
            new_password = dialog.get_password()
            try:
                # Hash password
                password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                self.dao.update_password(user['id'], password_hash)
                QMessageBox.information(self, "Başarılı", 
                    f"Şifre sıfırlandı!\n\nKullanıcı: {user['username']}\nYeni şifre: {new_password}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Şifre sıfırlanamadı:\n{str(e)}")
    
    def _delete_user(self, user: Dict):
        """Delete user after confirmation."""
        reply = QMessageBox.question(
            self, "Onay",
            f"'{user['username']}' kullanıcısını silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.dao.delete_user(user['id'])
                QMessageBox.information(self, "Başarılı", "Kullanıcı silindi!")
                self._load_users()
                self.user_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kullanıcı silinemedi:\n{str(e)}")


class UserEditDialog(QDialog):
    """User edit dialog."""
    
    def __init__(self, parent=None, user: Optional[Dict] = None):
        super().__init__(parent)
        self.user = user
        self.is_edit = user is not None
        self._setup_ui()
        
        if self.is_edit:
            self._load_user_data()
    
    def _setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Kullanıcı Düzenle" if self.is_edit else "Yeni Kullanıcı")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        # Username
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Kullanıcı adı")
        layout.addRow("Kullanıcı Adı:", self.username_input)
        
        # Full Name
        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("Ad Soyad")
        layout.addRow("Ad Soyad:", self.fullname_input)
        
        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        layout.addRow("Email:", self.email_input)
        
        # Password (only for new users)
        if not self.is_edit:
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            self.password_input.setPlaceholderText("Şifre")
            layout.addRow("Şifre:", self.password_input)
        
        # Role
        self.role_combo = QComboBox()
        self.role_combo.addItem("👑 Admin", "admin")
        self.role_combo.addItem("👔 Supervisor", "supervisor")
        self.role_combo.addItem("👷 Operatör", "operator")
        self.role_combo.addItem("👁️ İzleyici", "viewer")
        layout.addRow("Rol:", self.role_combo)
        
        # Active status
        self.active_check = QCheckBox("Aktif")
        self.active_check.setChecked(True)
        layout.addRow("Durum:", self.active_check)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def _load_user_data(self):
        """Load existing user data."""
        self.username_input.setText(self.user.get('username', ''))
        self.fullname_input.setText(self.user.get('full_name', ''))
        self.email_input.setText(self.user.get('email', ''))
        
        # Set role
        role = self.user.get('role', 'operator')
        for i in range(self.role_combo.count()):
            if self.role_combo.itemData(i) == role:
                self.role_combo.setCurrentIndex(i)
                break
        
        self.active_check.setChecked(self.user.get('is_active', True))
    
    def get_user_data(self) -> Dict:
        """Get user data from form."""
        data = {
            'username': self.username_input.text().strip(),
            'full_name': self.fullname_input.text().strip(),
            'email': self.email_input.text().strip(),
            'role': self.role_combo.currentData(),
            'is_active': self.active_check.isChecked()
        }
        
        if not self.is_edit:
            password = self.password_input.text()
            data['password_hash'] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        return data


class PasswordResetDialog(QDialog):
    """Password reset dialog."""
    
    def __init__(self, parent=None, user: Optional[Dict] = None):
        super().__init__(parent)
        self.user = user
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Şifre Sıfırla")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        
        # Info
        info_label = QLabel(f"Kullanıcı: {self.user['username']}")
        info_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(info_label)
        
        # Password options
        self.auto_radio = QCheckBox("Otomatik şifre oluştur")
        self.auto_radio.setChecked(True)
        self.auto_radio.toggled.connect(self._toggle_password_input)
        layout.addWidget(self.auto_radio)
        
        # Manual password input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Yeni şifre")
        self.password_input.setEnabled(False)
        layout.addWidget(self.password_input)
        
        # Generated password display
        self.generated_label = QLabel()
        self.generated_label.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 5px;")
        self.generated_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.generated_label)
        
        # Generate button
        self.btn_generate = QPushButton("🔄 Yeni Şifre Oluştur")
        self.btn_generate.clicked.connect(self._generate_password)
        layout.addWidget(self.btn_generate)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Generate initial password
        self._generate_password()
    
    def _toggle_password_input(self):
        """Toggle between auto and manual password."""
        is_auto = self.auto_radio.isChecked()
        self.password_input.setEnabled(not is_auto)
        self.btn_generate.setEnabled(is_auto)
        self.generated_label.setVisible(is_auto)
        
        if is_auto:
            self._generate_password()
    
    def _generate_password(self):
        """Generate random password."""
        import random
        import string
        
        # Generate 8 character password
        chars = string.ascii_letters + string.digits
        password = ''.join(random.choice(chars) for _ in range(8))
        
        self.generated_password = password
        self.generated_label.setText(f"Oluşturulan şifre: {password}")
    
    def get_password(self) -> str:
        """Get the password."""
        if self.auto_radio.isChecked():
            return self.generated_password
        else:
            return self.password_input.text()