@echo off
cd /d "%~dp0"
echo ========================================
echo   CAN Depo Yonetim Sistemi - Build
echo ========================================
echo.
echo Proje dizini: %CD%
echo.

echo [1/4] Temizlik yapiyor...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [2/4] Gerekli klasorleri olusturuyor...
if not exist labels mkdir labels
if not exist output mkdir output
if not exist logs mkdir logs

echo [3/4] PyInstaller ile exe olusturuyor...
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m PyInstaller --clean build.spec
) else (
    echo HATA: Sanal ortam bulunamadi (.venv\Scripts\python.exe)
    echo Once run_myapp.bat calistirin veya sanal ortam olusturun.
    pause
    exit /b 1
)

echo [4/4] Kurulum dosyalarini kopyaliyor...
if exist dist\CAN_Depo_Yonetim.exe (
    echo.
    echo ========================================
    echo   BUILD BASARILI! 
    echo ========================================
    echo.
    echo Dosya konumu: dist\CAN_Depo_Yonetim.exe
    echo Boyut: 
    dir dist\CAN_Depo_Yonetim.exe | find "CAN_Depo_Yonetim.exe"
    echo.
    echo Test etmek icin: dist\CAN_Depo_Yonetim.exe
    echo.
) else (
    echo.
    echo ========================================
    echo   BUILD HATALI!
    echo ========================================
    echo Lutfen hata mesajlarini kontrol edin.
    echo.
)

pause
