"""
Login Page for WMS Application
===============================
User authentication interface.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QMessageBox, QFrame, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPixmap, QPalette, QColor
from app.models.user import get_auth_manager, User
import logging
import json
import base64
from pathlib import Path

logger = logging.getLogger(__name__)


class LoginPage(QWidget):
    """Login page widget."""
    
    # Signals
    login_successful = pyqtSignal(object)  # Emits User object
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth_manager = get_auth_manager()
        self._setup_ui()
        self._failed_attempts = 0
        self._load_saved_credentials()
    
    def _setup_ui(self):
        """Setup user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Login frame
        login_frame = QFrame()
        login_frame.setMaximumWidth(400)
        login_frame.setMinimumWidth(350)
        login_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 20px;
            }
        """)
        
        frame_layout = QVBoxLayout(login_frame)
        
        # Title
        title = QLabel("WMS Giriş")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Lütfen kullanıcı bilgilerinizi girin")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; margin-bottom: 20px;")
        frame_layout.addWidget(subtitle)
        
        # Username field
        self.username_label = QLabel("Kullanıcı Adı:")
        frame_layout.addWidget(self.username_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Kullanıcı adı veya e-posta")
        self.username_input.setMinimumHeight(35)
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 5px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #4CAF50;
            }
        """)
        frame_layout.addWidget(self.username_input)
        
        # Password field
        self.password_label = QLabel("Şifre:")
        self.password_label.setStyleSheet("margin-top: 10px;")
        frame_layout.addWidget(self.password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Şifrenizi girin")
        self.password_input.setMinimumHeight(35)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 5px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #4CAF50;
            }
        """)
        frame_layout.addWidget(self.password_input)
        
        # Remember me checkbox
        self.remember_checkbox = QCheckBox("Beni hatırla")
        self.remember_checkbox.setStyleSheet("margin-top: 10px;")
        frame_layout.addWidget(self.remember_checkbox)
        
        # Login button
        self.login_button = QPushButton("Giriş Yap")
        self.login_button.setMinimumHeight(40)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                margin-top: 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.login_button.clicked.connect(self.handle_login)
        frame_layout.addWidget(self.login_button)
        
        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("""
            color: red;
            margin-top: 10px;
            padding: 5px;
            background-color: #ffebee;
            border: 1px solid #ffcdd2;
            border-radius: 3px;
        """)
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()
        frame_layout.addWidget(self.error_label)
        
        # Success label
        self.success_label = QLabel()
        self.success_label.setStyleSheet("""
            color: green;
            margin-top: 10px;
            padding: 5px;
            background-color: #e8f5e9;
            border: 1px solid #c8e6c9;
            border-radius: 3px;
        """)
        self.success_label.setAlignment(Qt.AlignCenter)
        self.success_label.hide()
        frame_layout.addWidget(self.success_label)
        
        # Add frame to main layout
        main_layout.addWidget(login_frame)
        
        # Footer
        footer = QLabel("© 2024 WMS - Warehouse Management System")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #999; margin-top: 20px;")
        main_layout.addWidget(footer)
        
        # Connect Enter key
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.handle_login)
        
        # Focus username field
        QTimer.singleShot(100, self.username_input.setFocus)
    
    def handle_login(self):
        """Handle login button click."""
        # Clear previous messages
        self.error_label.hide()
        self.success_label.hide()
        
        # Get credentials
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        # Validate input
        if not username:
            self.show_error("Kullanıcı adı boş olamaz")
            self.username_input.setFocus()
            return
        
        if not password:
            self.show_error("Şifre boş olamaz")
            self.password_input.setFocus()
            return
        
        # Disable form during login
        self.set_form_enabled(False)
        
        # Attempt login
        try:
            result = self.auth_manager.login(username, password)
            
            if result:
                user, token = result
                self.show_success(f"Hoş geldiniz, {user.full_name}!")
                
                # Store credentials if remember me is checked
                if self.remember_checkbox.isChecked():
                    self._save_credentials(username, password)
                else:
                    self._clear_saved_credentials()
                
                # Emit success signal after short delay
                QTimer.singleShot(1000, lambda: self.login_successful.emit(user))
                
            else:
                self._failed_attempts += 1
                
                if self._failed_attempts >= 3:
                    self.show_error("Çok fazla başarısız deneme! 30 saniye bekleyin.")
                    QTimer.singleShot(30000, self.reset_failed_attempts)
                else:
                    self.show_error("Kullanıcı adı veya şifre hatalı")
                    self.password_input.clear()
                    self.password_input.setFocus()
                
                self.set_form_enabled(True)
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            self.show_error("Giriş sırasında bir hata oluştu")
            self.set_form_enabled(True)
    
    def show_error(self, message: str):
        """Show error message."""
        self.error_label.setText(message)
        self.error_label.show()
        
        # Auto hide after 5 seconds
        QTimer.singleShot(5000, self.error_label.hide)
    
    def show_success(self, message: str):
        """Show success message."""
        self.success_label.setText(message)
        self.success_label.show()
    
    def set_form_enabled(self, enabled: bool):
        """Enable/disable form elements."""
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.remember_checkbox.setEnabled(enabled)
        self.login_button.setEnabled(enabled)
        
        if not enabled:
            self.login_button.setText("Giriş yapılıyor...")
        else:
            self.login_button.setText("Giriş Yap")
    
    def reset_failed_attempts(self):
        """Reset failed login attempts."""
        self._failed_attempts = 0
        self.set_form_enabled(True)
        self.error_label.hide()
    
    def _save_credentials(self, username: str, password: str):
        """Save encrypted credentials."""
        try:
            # Simple obfuscation (not real encryption, but better than plain text)
            # For production, use proper encryption like cryptography library
            from app.settings_manager import get_manager
            manager = get_manager()
            
            # Encode password (basic obfuscation)
            encoded_password = base64.b64encode(password.encode()).decode()
            
            # Save to settings
            manager.set("login.remember_me", True)
            manager.set("login.last_username", username)
            manager.set("login.saved_password", encoded_password)
            manager.save()
            
            logger.info(f"Credentials saved for user: {username}")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    def _load_saved_credentials(self):
        """Load saved credentials if they exist."""
        try:
            from app.settings_manager import get_manager
            manager = get_manager()
            
            if manager.get("login.remember_me", False):
                username = manager.get("login.last_username", "")
                encoded_password = manager.get("login.saved_password", "")
                
                if username and encoded_password:
                    # Decode password
                    password = base64.b64decode(encoded_password.encode()).decode()
                    
                    # Fill form
                    self.username_input.setText(username)
                    self.password_input.setText(password)
                    self.remember_checkbox.setChecked(True)
                    
                    # Focus on login button instead of password field
                    QTimer.singleShot(100, self.login_button.setFocus)
                    
                    logger.info(f"Credentials loaded for user: {username}")
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            self._clear_saved_credentials()
    
    def _clear_saved_credentials(self):
        """Clear saved credentials."""
        try:
            from app.settings_manager import get_manager
            manager = get_manager()
            
            manager.set("login.remember_me", False)
            manager.set("login.last_username", "")
            manager.set("login.saved_password", "")
            manager.save()
            
            logger.info("Saved credentials cleared")
        except Exception as e:
            logger.error(f"Failed to clear credentials: {e}")
    
    def load_saved_credentials(self):
        """Legacy function for compatibility."""
        self._load_saved_credentials()
    
    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        self.load_saved_credentials()