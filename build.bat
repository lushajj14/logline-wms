@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo ========================================
echo   CAN Depo Yonetim - EXE Build (.venv)
echo ========================================
echo.
echo Proje dizini: %CD%
echo Build tipi: Klasik .venv yapısı ile EXE
echo.

REM Python ve PyInstaller kontrolü
echo [0/5] Python ve PyInstaller kontrol ediliyor...

REM Önce .venv var mı kontrol et, yoksa oluştur
if not exist .venv\Scripts\python.exe (
    echo .venv bulunamadi, olusturuluyor...
    python -m venv .venv
    if errorlevel 1 (
        echo HATA: .venv olusturulamadi!
        echo Python yuklu mu kontrol edin: python --version
        pause
        exit /b 1
    )
    echo .venv basariyla olusturuldu.
    
    echo Gereksinimler yukleniyor...
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo HATA: Gereksinimler yuklenemedi!
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%i in ('.venv\Scripts\python.exe --version 2^>^&1') do set PYTHON_VER=%%i
echo Python: !PYTHON_VER!
echo Sanal ortam: .venv TAMAM

REM PyInstaller kontrolü
.venv\Scripts\python.exe -c "import PyInstaller; print('PyInstaller:', PyInstaller.__version__)" 2>nul
if errorlevel 1 (
    echo PyInstaller bulunamadi, yukleniyor...
    echo Bu islem birkaç dakika surebilir...
    .venv\Scripts\python.exe -m pip install pyinstaller
    if errorlevel 1 (
        echo HATA: PyInstaller yuklenemedi!
        echo Network baglantinizi kontrol edin.
        pause
        exit /b 1
    )
    echo PyInstaller basariyla yuklendi.
    
    REM Tekrar kontrol et
    .venv\Scripts\python.exe -c "import PyInstaller; print('PyInstaller:', PyInstaller.__version__)"
    if errorlevel 1 (
        echo HATA: PyInstaller yuklemede sorun var!
        pause
        exit /b 1
    )
) else (
    for /f "tokens=*" %%j in ('.venv\Scripts\python.exe -c "import PyInstaller; print(PyInstaller.__version__)" 2^>^&1') do set PYINST_VER=%%j
    echo PyInstaller: !PYINST_VER! TAMAM
)

echo [1/5] Eski build dosyalari temizleniyor...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
echo Temizlik tamamlandi.

echo [2/5] Gerekli klasorler ve dosyalar kontrol ediliyor...
if not exist labels mkdir labels
if not exist output mkdir output
if not exist logs mkdir logs
if not exist fonts mkdir fonts
if not exist sounds mkdir sounds

REM Font dosyası kontrolü
if not exist fonts\DejaVuSans.ttf (
    if exist app\fonts\DejaVuSans.ttf (
        copy /Y app\fonts\DejaVuSans.ttf fonts\
        echo Font kopyalandi: fonts\DejaVuSans.ttf
    ) else (
        echo UYARI: DejaVuSans.ttf font dosyasi bulunamadi
    )
)

REM Ses dosyaları kontrolü  
if not exist sounds\ding.wav (
    if exist app\sounds (
        xcopy /Y /E app\sounds sounds\ >nul 2>&1
        echo Ses dosyalari kopyalandi.
    )
)

echo Dosyalar hazir.

echo [3/5] PyInstaller ile .venv yapısı EXE olusturuyor...
echo Bu islem birkaç dakika surebilir...
echo .venv içindeki bağımlılıkları kullanarak build yapılıyor...

.venv\Scripts\python.exe -m PyInstaller --clean build.spec

if errorlevel 1 (
    echo.
    echo ========================================
    echo   BUILD HATALI!
    echo ========================================
    echo PyInstaller hatasi olustu. Hata mesajlarini kontrol edin.
    echo.
    pause
    exit /b 1
)

echo [4/5] Build sonuclari kontrol ediliyor...
if exist dist\CAN_Depo_Yonetim\CAN_Depo_Yonetim.exe (
    echo.
    echo ========================================
    echo   BUILD BASARILI! 
    echo ========================================
    echo.
    echo .venv yapısı ile EXE hazir: dist\CAN_Depo_Yonetim\
    echo Ana dosya: CAN_Depo_Yonetim.exe
    
    REM Dosya boyutunu hesapla
    for %%F in (dist\CAN_Depo_Yonetim\CAN_Depo_Yonetim.exe) do (
        set /a size=%%~zF/1024/1024
        echo Dosya boyutu: !size! MB (%%~zF bytes)
    )
    
    echo.
    echo [5/5] Destekleyici dosyalar kopyalaniyor...
    copy /Y settings.json "dist\CAN_Depo_Yonetim\"
    echo settings.json kopyalandi.
    
    echo.
    echo ========================================
    echo   DEPLOYMENT HAZIR!
    echo ========================================
    echo.
    echo Build klasoru: dist\CAN_Depo_Yonetim\
    echo Ana dosya: CAN_Depo_Yonetim.exe
    echo Ayar dosyasi: settings.json
    echo DLL'ler ve kutuphaneler: _internal\
    echo.
    echo ÇALIŞTIRMA:
    echo 1. dist\CAN_Depo_Yonetim\CAN_Depo_Yonetim.exe çift tıkla
    echo 2. Tum klasoru (CAN_Depo_Yonetim) kopyalayip kullan
    echo.
    
    REM Manuel test seçeneği
    set /p "test=Test etmek ister misiniz? (y/n): "
    if /i "!test!"=="y" (
        echo Test başlatılıyor...
        start "" "dist\CAN_Depo_Yonetim\CAN_Depo_Yonetim.exe"
    )
    
) else (
    echo.
    echo ========================================
    echo   BUILD HATALI!
    echo ========================================
    echo dist\CAN_Depo_Yonetim\CAN_Depo_Yonetim.exe olusturulamadi.
    echo Build log'unu kontrol edin.
    echo PyInstaller hata mesajlarini okuyun.
    echo.
)

echo.
echo Build islemi tamamlandi.
pause
