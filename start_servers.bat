@echo off
echo ========================================
echo WMS Server Baslatiliyor...
echo ========================================
echo.

REM Environment variables ayarla
set LOGO_SQL_SERVER=192.168.5.100,1433
set LOGO_SQL_DB=logo
set LOGO_SQL_USER=barkod1
set LOGO_SQL_PASSWORD=Barkod14*

echo [1/2] Config Server baslatiliyor (Port 8001)...
start "WMS Config Server" cmd /k "cd /d %~dp0 && python -m uvicorn config_server:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 3 /nobreak > nul

echo [2/2] Mobile API baslatiliyor (Port 8000)...
start "WMS Mobile API" cmd /k "cd /d %~dp0 && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo ========================================
echo Serverlar baslatildi!
echo ========================================
echo.
echo Config Server: http://localhost:8001
echo Mobile API:    http://localhost:8000
echo.
echo Durdurmak icin acilan pencereleri kapatin.
echo.
pause