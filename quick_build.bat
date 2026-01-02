@echo off
REM ================================================================
REM WMS Quick Build - Hızlı Test Build
REM ================================================================
REM Bu script dependencies yüklemeden direkt build yapar (hızlı test için)
REM ================================================================

echo.
echo ================================================================
echo WMS Quick Build - Hizli Test
echo ================================================================
echo.

REM Clean
echo [1/3] Temizleniyor...
if exist build rmdir /s /q build 2>nul
if exist dist rmdir /s /q dist 2>nul
echo Temizlendi.

REM Build
echo.
echo [2/3] Build yapiliyor...
pyinstaller --clean --noconfirm wms.spec

if errorlevel 1 (
    echo.
    echo [HATA] Build basarisiz!
    pause
    exit /b 1
)

echo.
echo [3/3] Build tamamlandi!
echo.

REM Size check
for %%A in ("dist\WMS_System.exe") do set size=%%~zA
set /a size_mb=%size%/1024/1024
echo EXE boyutu: %size_mb% MB
echo Konum: dist\WMS_System.exe

echo.
echo Build basarili! Test etmek icin dist\WMS_System.exe calistirin.
pause
