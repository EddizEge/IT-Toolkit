@echo off
setlocal
cd /d "%~dp0"

title IT Toolkit v2 Derleyici
color 0A

echo =======================================
echo IT Toolkit v2 - PySide6 Derleyici
echo =======================================
echo.

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo Bagimliliklar kurulurken hata olustu.
    pause
    exit /b 1
)

set /p VER="Surum etiketi (varsayilan: v0.6.0-beta.2): "
if "%VER%"=="" set VER=v0.6.0-beta.2

set "APP_NAME=IT_Toolkit_%VER%"
taskkill /F /IM "%APP_NAME%.exe" /T >nul 2>&1

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --icon "assets\brand\it_toolkit.ico" ^
    --add-data "assets\brand\it_toolkit.ico;assets\brand" ^
    "main_v2.py"

if errorlevel 1 (
    echo.
    echo Derleme basarisiz oldu.
    pause
    exit /b 1
)

echo.
echo Derleme tamamlandi:
echo dist\%APP_NAME%.exe
pause
