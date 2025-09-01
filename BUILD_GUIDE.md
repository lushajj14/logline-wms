# WMS System - PyInstaller Build Guide

This guide provides comprehensive instructions for building the WMS System into a single executable file using PyInstaller.

## Quick Start

1. **Install dependencies:**
   ```batch
   pip install -r requirements.txt
   ```

2. **Run the build script:**
   ```batch
   build.bat
   ```

3. **Find your executable in:**
   ```
   dist\WMS_System.exe
   ```

## Files Created

This build configuration creates the following files:

- **`requirements.txt`** - Complete Python dependencies with versions
- **`wms.spec`** - PyInstaller specification file with all configurations
- **`build.bat`** - Windows build script with error handling
- **`version.txt`** - Windows executable version information
- **`build_config.py`** - Runtime configuration helper for path resolution
- **`BUILD_GUIDE.md`** - This comprehensive guide

## Build Process Details

### Step 1: Environment Validation
- Checks Python and pip availability
- Warns if not in virtual environment (recommended)
- Validates required files exist

### Step 2: Clean Previous Builds
- Removes old `build/` and `dist/` directories
- Ensures clean build environment

### Step 3: Install Dependencies
- Installs/updates all requirements from `requirements.txt`
- Includes PyQt5, database drivers, PDF generation, etc.

### Step 4: Create Required Directories
- Creates all directories the application expects:
  - `app/picklists/` - Generated picklist PDFs
  - `app/labels/` - Generated label PDFs  
  - `app/reports/` - Report outputs
  - `app/logs/` - Application logs
  - `labels/` - Additional label outputs
  - `logs/` - System logs
  - `output/` - General output files
  - `temp/` - Temporary files

### Step 5: Run PyInstaller
- Uses the comprehensive `wms.spec` file
- Includes all hidden imports and data files
- Creates single executable with all dependencies

### Step 6: Validation
- Checks executable was created successfully
- Reports file size and location

## What's Included in the Executable

The PyInstaller configuration includes:

### Core Dependencies
- **PyQt5** - Complete GUI framework with multimedia support
- **pyodbc** - Database connectivity 
- **ReportLab** - PDF generation with fonts and graphics
- **pandas/numpy** - Data processing
- **qrcode/Pillow** - QR code and image processing
- **FastAPI/uvicorn** - Web API framework
- **python-jose/bcrypt** - Security and authentication

### Data Files
- **Environment file** (`.env`) - Configuration
- **Fonts** (`DejaVuSans.ttf`) - PDF font support
- **Sound files** (`.wav`) - Audio feedback
- **SQL migration scripts** - Database setup
- **Application configuration** - Settings

### All Python Modules
- Complete application module tree
- All UI pages and dialogs
- All services and utilities
- Database access objects
- Configuration and validation

## Critical Features Supported

✅ **All UI Pages:**
- Login system with authentication
- Dashboard with real-time data
- Picklist generation and management
- Label printing and management
- Loader functionality
- Scanner/barcode validation
- Shipment tracking
- User management
- Settings and configuration

✅ **PDF Generation:**
- Picklist PDFs with barcodes
- Shipping labels with QR codes
- Report generation
- Custom fonts (DejaVuSans.ttf)

✅ **Database:**
- ODBC connections to SQL Server
- Connection pooling
- Transaction management
- Fallback connections

✅ **Sound System:**
- WAV file playback
- Success/error audio feedback
- Resource management

✅ **Environment:**
- .env file configuration
- Runtime path resolution
- Temporary file handling

## Common Issues and Solutions

### Build Issues

**Problem:** PyInstaller fails with import errors
**Solution:** Check `wms.spec` hiddenimports section, add missing modules

**Problem:** Missing data files in executable
**Solution:** Check `wms.spec` datas section, add file paths

**Problem:** "No module named 'xyz'" at runtime
**Solution:** Add module to hiddenimports in `wms.spec`

### Runtime Issues

**Problem:** Executable won't start
**Solution:** 
- Check Windows Event Viewer for detailed error
- Ensure .env file is present
- Verify ODBC drivers are installed

**Problem:** Database connection fails
**Solution:**
- Verify SQL Server ODBC driver is installed
- Check .env file database configuration
- Test connection string independently

**Problem:** PDF generation fails
**Solution:**
- Ensure fonts are included in build
- Check ReportLab dependencies
- Verify output directory permissions

**Problem:** Sounds don't play
**Solution:**
- Check sound files are included
- Verify PyQt5.QtMultimedia is working
- Test on target machine with different audio settings

**Problem:** Missing files/directories
**Solution:**
- The app creates required directories on first run
- Check file permissions in installation directory
- Ensure antivirus isn't blocking file creation

### Deployment Issues

**Problem:** "MSVCP140.dll missing" error
**Solution:** Install Visual C++ Redistributable 2015-2022

**Problem:** ODBC driver not found
**Solution:** Install "ODBC Driver 17 for SQL Server" on target machine

**Problem:** Antivirus flags executable
**Solution:** 
- Code signing certificate (for production)
- Add exception in antivirus
- Use verified PyInstaller version

## Advanced Configuration

### Custom Icon
Add to `wms.spec`:
```python
exe = EXE(
    # ... other parameters ...
    icon='app/resources/icon.ico',
)
```

### Console Window (for debugging)
Change in `wms.spec`:
```python
exe = EXE(
    # ... other parameters ...
    console=True,  # Shows console window
)
```

### UPX Compression
If you have UPX installed:
```python
exe = EXE(
    # ... other parameters ...
    upx=True,  # Enables compression
)
```

### Additional Hidden Imports
Add to `wms.spec` hiddenimports list:
```python
hiddenimports=[
    # ... existing imports ...
    'your.additional.module',
],
```

### Additional Data Files
Add to `wms.spec` datas list:
```python
datas=[
    # ... existing data ...
    ('path/to/your/file', 'destination/'),
],
```

## Testing Your Build

### Basic Functionality Test
1. Run the executable on a clean Windows machine
2. Check login system works
3. Test database connection
4. Generate a picklist PDF
5. Generate a shipping label
6. Test sound feedback
7. Check all UI pages load

### Stress Testing
1. Generate multiple PDFs rapidly
2. Test with large datasets
3. Test concurrent database operations
4. Leave running for extended periods

### Deployment Testing
1. Test on machines without Python installed
2. Test on different Windows versions
3. Test with different user permissions
4. Test with antivirus software active

## Build Script Output

The `build.bat` script provides detailed output:
- Environment validation results
- Dependency installation progress
- PyInstaller build progress
- Final executable information
- Size and location details

## Support

For build issues:
1. Check this guide first
2. Review the build script output
3. Check Windows Event Viewer for runtime errors
4. Test individual components separately
5. Compare with a working development environment

## File Structure After Build

```
your_project2/
├── dist/
│   └── WMS_System.exe          # Your final executable
├── build/                      # Temporary build files (can be deleted)
├── wms.spec                    # PyInstaller specification
├── requirements.txt            # Python dependencies
├── build.bat                   # Build script
├── version.txt                 # Version information
├── build_config.py             # Runtime configuration helper
└── BUILD_GUIDE.md              # This guide
```

The executable (`WMS_System.exe`) is completely self-contained and includes all dependencies, data files, and Python modules needed to run the WMS system.