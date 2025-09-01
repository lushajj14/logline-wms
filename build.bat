@echo off
REM ================================================================
REM WMS System - PyInstaller Build Script for Windows
REM ================================================================
REM This script creates a single EXE file with all dependencies
REM and resources bundled. Run this script from the project root.
REM ================================================================

setlocal enabledelayedexpansion

echo.
echo ================================================================
echo WMS System - PyInstaller Build Script
echo ================================================================
echo.

REM Get current directory and set variables
set PROJECT_DIR=%~dp0
set BUILD_DIR=%PROJECT_DIR%build
set DIST_DIR=%PROJECT_DIR%dist
set SPEC_FILE=%PROJECT_DIR%wms.spec
set MAIN_FILE=%PROJECT_DIR%main.py
set REQUIREMENTS_FILE=%PROJECT_DIR%requirements.txt

echo Project Directory: %PROJECT_DIR%
echo Build Directory: %BUILD_DIR%
echo Distribution Directory: %DIST_DIR%
echo.

REM ================================================================
REM Step 1: Validate Environment
REM ================================================================
echo [1/7] Validating environment...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher and add it to PATH
    pause
    exit /b 1
)

REM Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not available
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)

echo Python and pip are available.

REM Check if we're in a virtual environment (recommended)
python -c "import sys; exit(0 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 1)" >nul 2>&1
if errorlevel 1 (
    echo WARNING: You are not in a virtual environment.
    echo It's recommended to create and activate a virtual environment before building.
    echo.
    echo To create a virtual environment:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo.
    set /p continue="Continue anyway? (y/N): "
    if /i not "!continue!"=="y" (
        echo Build cancelled.
        pause
        exit /b 0
    )
)

REM ================================================================
REM Step 2: Clean Previous Builds
REM ================================================================
echo.
echo [2/7] Cleaning previous builds...

if exist "%BUILD_DIR%" (
    echo Removing build directory...
    rmdir /s /q "%BUILD_DIR%" 2>nul
    if exist "%BUILD_DIR%" (
        echo WARNING: Could not completely remove build directory
        echo Some files may be in use. Try closing all applications and run again.
    )
)

if exist "%DIST_DIR%" (
    echo Removing dist directory...
    rmdir /s /q "%DIST_DIR%" 2>nul
    if exist "%DIST_DIR%" (
        echo WARNING: Could not completely remove dist directory
        echo Some files may be in use. Try closing all applications and run again.
    )
)

echo Previous builds cleaned.

REM ================================================================
REM Step 3: Validate Required Files
REM ================================================================
echo.
echo [3/7] Validating required files...

if not exist "%MAIN_FILE%" (
    echo ERROR: Main file not found: %MAIN_FILE%
    echo Please ensure you're running this script from the project root directory.
    pause
    exit /b 1
)

if not exist "%SPEC_FILE%" (
    echo ERROR: PyInstaller spec file not found: %SPEC_FILE%
    echo Please ensure wms.spec exists in the project root directory.
    pause
    exit /b 1
)

if not exist "%REQUIREMENTS_FILE%" (
    echo ERROR: Requirements file not found: %REQUIREMENTS_FILE%
    echo Please ensure requirements.txt exists in the project root directory.
    pause
    exit /b 1
)

REM .env file is not needed anymore - using remote config
echo INFO: Using remote config server - no .env file needed

echo Required files validated.

REM ================================================================
REM Step 4: Install/Update Dependencies
REM ================================================================
echo.
echo [4/7] Installing/updating dependencies...

echo Installing requirements from %REQUIREMENTS_FILE%...
pip install -r "%REQUIREMENTS_FILE%" --upgrade

if errorlevel 1 (
    echo ERROR: Failed to install requirements
    echo Please check the requirements.txt file and your internet connection
    pause
    exit /b 1
)

echo Dependencies installed successfully.

REM ================================================================
REM Step 5: Create Required Directories
REM ================================================================
echo.
echo [5/7] Creating required directories...

REM Create directories that the application expects
if not exist "app\picklists" mkdir "app\picklists"
if not exist "app\labels" mkdir "app\labels"
if not exist "app\reports" mkdir "app\reports"
if not exist "app\logs" mkdir "app\logs"
if not exist "labels" mkdir "labels"
if not exist "logs" mkdir "logs"
if not exist "output" mkdir "output"
if not exist "temp" mkdir "temp"

echo Required directories created.

REM ================================================================
REM Step 6: Run PyInstaller
REM ================================================================
echo.
echo [6/7] Running PyInstaller...
echo This may take several minutes...

REM Run PyInstaller with the spec file
pyinstaller --clean --noconfirm "%SPEC_FILE%"

if errorlevel 1 (
    echo ERROR: PyInstaller failed to build the executable
    echo Please check the output above for error details
    echo.
    echo Common issues and solutions:
    echo - Missing dependencies: Check requirements.txt
    echo - Missing data files: Check wms.spec datas section
    echo - Import errors: Check wms.spec hiddenimports section
    echo - Permission issues: Run as administrator
    pause
    exit /b 1
)

echo PyInstaller completed successfully.

REM ================================================================
REM Step 7: Post-Build Validation and Cleanup
REM ================================================================
echo.
echo [7/7] Validating build and cleanup...

set EXE_FILE=%DIST_DIR%\WMS_System.exe

if not exist "%EXE_FILE%" (
    echo ERROR: Expected executable not found: %EXE_FILE%
    echo Build may have failed. Please check the PyInstaller output above.
    pause
    exit /b 1
)

REM Get file size
for %%A in ("%EXE_FILE%") do set EXE_SIZE=%%~zA
set /a EXE_SIZE_MB=%EXE_SIZE%/1024/1024

echo.
echo ================================================================
echo BUILD COMPLETED SUCCESSFULLY!
echo ================================================================
echo.
echo Executable created: %EXE_FILE%
echo File size: %EXE_SIZE_MB% MB
echo.
echo IMPORTANT NOTES:
echo.
echo 1. TESTING:
echo    - Test the executable on a clean Windows machine
echo    - Ensure all features work (PDF generation, database, sounds)
echo    - Test with different user permissions
echo.
echo 2. DEPLOYMENT:
echo    - NO .env or config.ini needed! (uses remote config)
echo    - Ensure target machines have required ODBC drivers
echo    - Consider including Visual C++ Redistributable
echo    - Config Server must be running on 192.168.5.100:8001
echo.
echo 3. TROUBLESHOOTING:
echo    - If the app doesn't start, check Windows Event Viewer
echo    - For missing DLL errors, check the build machine dependencies
echo    - For database issues, verify ODBC driver installation
echo.
echo 4. DIRECTORIES:
echo    - The executable will create these directories on first run:
echo      * picklists\
echo      * labels\  
echo      * reports\
echo      * logs\
echo      * output\
echo      * temp\
echo.

REM Offer to open the dist directory
echo [Optional] Would you like to open the dist directory?
set /p open_dist="Open dist directory? (y/N): "
if /i "!open_dist!"=="y" (
    explorer "%DIST_DIR%"
)

echo.
echo Build script completed.
pause
exit /b 0

REM ================================================================
REM Error Handling Functions
REM ================================================================
:handle_error
echo.
echo ERROR: %1
echo Build failed. Please check the error message above.
pause
exit /b 1