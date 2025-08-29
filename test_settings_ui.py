#!/usr/bin/env python3
"""Test script for Enhanced Settings UI"""

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from app.ui.pages.enhanced_settings_page import EnhancedSettingsPage

def main():
    app = QApplication(sys.argv)
    
    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Enhanced Settings Test")
    window.resize(900, 700)
    
    # Create and set settings page
    settings_page = EnhancedSettingsPage()
    window.setCentralWidget(settings_page)
    
    # Connect signal
    settings_page.settings_saved.connect(lambda: print("Settings saved signal received!"))
    
    # Show window
    window.show()
    
    print("\nEnhanced Settings Page Test")
    print("="*50)
    print(f"Total tabs: {settings_page.tabs.count()}")
    print("\nAvailable tabs:")
    for i in range(settings_page.tabs.count()):
        print(f"  {i+1}. {settings_page.tabs.tabText(i)}")
    print("\nFeatures:")
    print("  - Import/Export settings")
    print("  - Reset to defaults")
    print("  - Database connection test")
    print("  - Cache management")
    print("  - Connection pool settings")
    print("  - Performance tuning")
    print("="*50)
    print("\nWindow is now open. Test the settings interface!")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()