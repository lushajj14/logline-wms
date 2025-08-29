#!/usr/bin/env python3
"""Dashboard Test"""

import sys
import os
from pathlib import Path

# Path ayarları
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_dashboard():
    """Dashboard import test"""
    try:
        from app.ui.pages.dashboard_page import DashboardPage
        print("[OK] DashboardPage import başarılı")
        
        # Widget oluştur (PyQt olmadan sadece class test)
        widget = DashboardPage()
        print("[OK] DashboardPage instance oluşturuldu")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Dashboard test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_dashboard()