@echo off
setlocal

:: Sanal ortam klasörü
set VENV_DIR=.venv

:: Ana Python dosyası
set ENTRY=main.py

:: Eğer sanal ortam yoksa oluştur
if not exist %VENV_DIR%\Scripts\python.exe (
    echo [1/3] Sanal ortam oluşturuluyor...
    py -m venv %VENV_DIR%
)

:: Sanal ortamı aktive et
call %VENV_DIR%\Scripts\activate.bat

:: Gerekli paketler yüklü mü kontrol et, değilse yükle
echo [2/3] Gerekli bağımlılıklar yükleniyor...
pip install -r requirements.txt >nul 2>&1

:: Uygulama başlatılıyor
echo [3/3] Program çalıştırılıyor...
python %ENTRY%

pause
