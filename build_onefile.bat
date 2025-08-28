@echo off
REM ================================================================
REM  LOGLine WMS - Tek Dosya EXE Build Script
REM ================================================================
REM  Bu script, uygulamanızı tek dosya .exe haline çevirir.
REM  Tüm bağımlılıklar exe içine gömülür.
REM ================================================================

cd /d "%~dp0"

echo.
echo ================================================================
echo   LOGLine WMS - Tek Dosya EXE Oluşturuluyor
echo ================================================================
echo.
echo Proje dizini: %CD%
echo.

REM ---- 1. Önce eski build dosyalarını temizle ----
echo [1/5] Eski build dosyalarini temizliyor...
if exist "dist\LOGLine_WMS.exe" del "dist\LOGLine_WMS.exe"
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM ---- 2. Gerekli dizinleri oluştur ----
echo [2/5] Gerekli dizinleri olusturuyor...
if not exist "labels" mkdir "labels"
if not exist "output" mkdir "output"
if not exist "logs" mkdir "logs"
if not exist "app\logs" mkdir "app\logs"

REM ---- 3. Python sanal ortamını kontrol et ----
echo [3/5] Python ortamini kontrol ediyor...
if exist ".venv\Scripts\python.exe" (
    echo ✓ Sanal ortam bulundu: .venv
    set PYTHON_CMD=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
    echo ✓ Sanal ortam bulundu: venv  
    set PYTHON_CMD=venv\Scripts\python.exe
) else (
    echo ✓ Sistem Python kullaniliyor
    set PYTHON_CMD=python
)

echo Python komutu: %PYTHON_CMD%

REM ---- 4. PyInstaller ile tek dosya EXE oluştur ----
echo.
echo [4/5] PyInstaller ile tek dosya EXE olusturuyor...
echo ----------------------------------------------------------------
echo Bu işlem 2-5 dakika sürebilir...
echo ----------------------------------------------------------------

%PYTHON_CMD% -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --log-level=INFO ^
    build_onefile.spec

REM ---- 5. Sonuçları kontrol et ve raporla ----
echo.
echo [5/5] Build sonucunu kontrol ediyor...

if exist "dist\LOGLine_WMS.exe" (
    echo.
    echo ================================================================
    echo   ✅ BUILD BAŞARILI! 
    echo ================================================================
    echo.
    echo 📁 Dosya konumu: dist\LOGLine_WMS.exe
    echo.
    echo 📊 Dosya boyutu:
    dir "dist\LOGLine_WMS.exe" | find "LOGLine_WMS.exe"
    echo.
    echo 🚀 Kullanım:
    echo    - Bu EXE dosyasını istediğiniz bilgisayara kopyalayabilirsiniz
    echo    - Python yüklü olması gerekmez
    echo    - Tek dosya - tüm bağımlılıklar dahil
    echo.
    echo 🔧 Test etmek için:
    echo    dist\LOGLine_WMS.exe
    echo.
    
    REM Exe dosyasını test etmek isteyip istemediğini sor
    set /p TEST_CHOICE="Şimdi test etmek ister misiniz? (e/h): "
    if /i "%TEST_CHOICE%"=="e" (
        echo.
        echo 🔄 Uygulamayi baslatiliyor...
        start "" "dist\LOGLine_WMS.exe"
    )
    
) else (
    echo.
    echo ================================================================
    echo   ❌ BUILD HATALI!
    echo ================================================================
    echo.
    echo Hata nedenleri:
    echo 1. PyInstaller yüklü değil: pip install pyinstaller
    echo 2. Modül eksik: pip install -r requirements.txt  
    echo 3. Bellek yetersizliği: RAM'i kontrol edin
    echo.
    echo Detaylu hata logu için yukarıdaki çıktıyı inceleyin.
    echo.
)

echo.
echo Build işlemi tamamlandı.
pause
