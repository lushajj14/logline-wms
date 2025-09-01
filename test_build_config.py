#!/usr/bin/env python3
"""
WMS System - Build Configuration Test
====================================
This script tests the build configuration to identify potential issues
before running the full PyInstaller build.
"""

import sys
import os
import importlib
import subprocess
from pathlib import Path


def test_imports():
    """Test all critical imports that need to be included in the build."""
    print("Testing critical imports...")
    
    critical_imports = [
        # Core PyQt5
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'PyQt5.QtMultimedia',
        
        # Database
        'pyodbc',
        
        # PDF Generation
        'reportlab',
        'reportlab.pdfgen.canvas',
        'reportlab.lib.pagesizes',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.pdfbase.ttfonts',
        'reportlab.graphics.barcode.code128',
        
        # Data processing
        'pandas',
        'numpy',
        'openpyxl',
        
        # QR Code
        'qrcode',
        'PIL.Image',
        
        # Environment
        'dotenv',
        
        # Security
        'jose.jwt',
        'bcrypt',
        
        # Web framework
        'fastapi',
        'uvicorn',
        
        # Application modules
        'app.config.env_config',
        'app.dao.logo',
        'app.models.user',
        'app.ui.main_window',
        'app.services.picklist',
        'app.utils.sound_manager',
    ]
    
    failed_imports = []
    
    for module_name in critical_imports:
        try:
            importlib.import_module(module_name)
            print(f"  ✓ {module_name}")
        except ImportError as e:
            print(f"  ✗ {module_name} - {e}")
            failed_imports.append(module_name)
        except Exception as e:
            print(f"  ⚠ {module_name} - {e}")
    
    if failed_imports:
        print(f"\n❌ {len(failed_imports)} critical imports failed!")
        print("These modules need to be installed or fixed before building.")
        return False
    else:
        print(f"\n✅ All {len(critical_imports)} critical imports successful!")
        return True


def test_files():
    """Test that all required files and directories exist."""
    print("\nTesting required files and directories...")
    
    required_files = [
        'main.py',
        'requirements.txt',
        'wms.spec',
        'version.txt',
        'build.bat',
        '.env.example',
    ]
    
    optional_files = [
        '.env',
        'app/config.json',
    ]
    
    required_dirs = [
        'app',
        'app/config',
        'app/dao', 
        'app/models',
        'app/services',
        'app/ui',
        'app/ui/pages',
        'app/utils',
    ]
    
    data_files = [
        'app/fonts/DejaVuSans.ttf',
        'fonts/DejaVuSans.ttf',
        'app/sounds/bip.wav',
        'app/sounds/ding.wav', 
        'app/sounds/error.wav',
        'sounds/bip.wav',
        'sounds/ding.wav',
        'sounds/error.wav',
    ]
    
    missing_files = []
    
    # Check required files
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} (REQUIRED)")
            missing_files.append(file_path)
    
    # Check optional files
    for file_path in optional_files:
        if Path(file_path).exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ⚠ {file_path} (optional)")
    
    # Check required directories
    for dir_path in required_dirs:
        if Path(dir_path).is_dir():
            print(f"  ✓ {dir_path}/")
        else:
            print(f"  ✗ {dir_path}/ (REQUIRED)")
            missing_files.append(dir_path)
    
    # Check data files
    missing_data = []
    for file_path in data_files:
        if Path(file_path).exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ⚠ {file_path} (data file)")
            missing_data.append(file_path)
    
    if missing_files:
        print(f"\n❌ {len(missing_files)} required files/directories missing!")
        return False
    elif missing_data:
        print(f"\n⚠ {len(missing_data)} data files missing (may cause runtime issues)")
        return True
    else:
        print(f"\n✅ All required files and directories found!")
        return True


def test_pyinstaller():
    """Test PyInstaller availability and version."""
    print("\nTesting PyInstaller...")
    
    try:
        result = subprocess.run(['pyinstaller', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  ✓ PyInstaller {version} available")
            
            # Check if version is recent enough
            try:
                version_parts = version.split('.')
                major = int(version_parts[0])
                minor = int(version_parts[1])
                
                if major > 6 or (major == 6 and minor >= 3):
                    print(f"  ✓ Version is compatible")
                    return True
                else:
                    print(f"  ⚠ Version {version} is old, recommend 6.3.0+")
                    return True
            except (ValueError, IndexError):
                print(f"  ⚠ Could not parse version: {version}")
                return True
        else:
            print(f"  ✗ PyInstaller error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ✗ PyInstaller not found in PATH")
        print("    Install with: pip install pyinstaller")
        return False
    except subprocess.TimeoutExpired:
        print("  ✗ PyInstaller command timed out")
        return False
    except Exception as e:
        print(f"  ✗ Error testing PyInstaller: {e}")
        return False


def test_environment():
    """Test Python environment and virtual environment."""
    print("\nTesting Python environment...")
    
    # Python version
    python_version = sys.version_info
    print(f"  ✓ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major != 3 or python_version.minor < 8:
        print("  ⚠ Python 3.8+ recommended")
    
    # Virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if in_venv:
        print("  ✓ Running in virtual environment")
    else:
        print("  ⚠ Not in virtual environment (recommended for building)")
    
    # Platform
    import platform
    print(f"  ✓ Platform: {platform.system()} {platform.release()}")
    
    return True


def test_spec_file():
    """Test the PyInstaller spec file for common issues."""
    print("\nTesting PyInstaller spec file...")
    
    spec_file = Path('wms.spec')
    if not spec_file.exists():
        print("  ✗ wms.spec not found")
        return False
    
    try:
        with open(spec_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for critical sections
        if 'hiddenimports=' in content:
            print("  ✓ Hidden imports section found")
        else:
            print("  ⚠ Hidden imports section missing")
        
        if 'datas=' in content:
            print("  ✓ Data files section found")
        else:
            print("  ⚠ Data files section missing")
        
        if 'binaries=' in content:
            print("  ✓ Binaries section found")
        else:
            print("  ⚠ Binaries section found (may be empty)")
        
        # Check for main.py reference
        if 'main.py' in content:
            print("  ✓ Main entry point found")
        else:
            print("  ✗ Main entry point not found")
        
        print("  ✓ Spec file appears valid")
        return True
        
    except Exception as e:
        print(f"  ✗ Error reading spec file: {e}")
        return False


def main():
    """Run all tests."""
    print("WMS System - Build Configuration Test")
    print("=" * 50)
    
    tests = [
        ("Python Environment", test_environment),
        ("Required Files", test_files),
        ("Critical Imports", test_imports),
        ("PyInstaller", test_pyinstaller),
        ("Spec File", test_spec_file),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * (len(test_name) + 1))
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Ready to build.")
        print("\nRun the build script: build.bat")
    else:
        print("❌ Some tests failed. Fix issues before building.")
        print("\nCommon solutions:")
        print("  - Install missing packages: pip install -r requirements.txt")
        print("  - Create .env file from .env.example")
        print("  - Check file paths and permissions")
        print("  - Ensure you're in the project root directory")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)