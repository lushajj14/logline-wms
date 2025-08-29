@echo off
echo ===========================================
echo LOGLine Web Development Server
echo ===========================================
echo.

echo [1/3] Backend server baslatiliyor (Port 8002)...
cd /d "C:\Users\User\Desktop\your_project2\web\backend"
start "Backend Server" cmd /k "python main.py"

echo [2/3] 5 saniye bekleniyor...
timeout /t 5 /nobreak >nul

echo [3/3] Frontend server baslatiliyor (Port 3000)...
cd /d "C:\Users\User\Desktop\your_project2\web\frontend"
start "Frontend Server" cmd /k "npm start"

echo.
echo ===========================================
echo Web Development Environment Hazir!
echo ===========================================
echo Backend:  http://localhost:8002
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8002/docs
echo ===========================================
echo.
echo Her iki server acilana kadar bekleyin...
echo Tarayicinizda http://localhost:3000 adresine gidin
echo.
pause