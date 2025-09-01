@echo off
echo ========================================
echo WMS Config Server Baslatiliyor...
echo ========================================
echo.

REM Environment variables ayarla
set LOGO_SQL_SERVER=192.168.5.100,1433
set LOGO_SQL_DB=logo
set LOGO_SQL_USER=barkod1
set LOGO_SQL_PASSWORD=Barkod14*

echo Config Server baslatiliyor (Port 8001)...
python -m uvicorn config_server:app --host 0.0.0.0 --port 8001 --reload

pause