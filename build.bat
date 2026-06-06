@echo off
setlocal

echo.
echo  Unified Combat System - Build Otimizado
echo.

set PYINST=python -m PyInstaller
%PYINST% --version >nul 2>nul
if %errorlevel% neq 0 (
    echo Instalando PyInstaller...
    pip install pyinstaller
)

set EXCLUDES=^
    --exclude-module torch ^
    --exclude-module tensorflow ^
    --exclude-module transformers ^
    --exclude-module scipy ^
    --exclude-module sklearn ^
    --exclude-module matplotlib ^
    --exclude-module IPython ^
    --exclude-module PIL.ImageFilter ^
    --exclude-module PIL.ImageGrab ^
    --exclude-module tkinter ^
    --exclude-module pygame ^
    --exclude-module sympy ^
    --exclude-module nltk ^
    --exclude-module pandas ^
    --exclude-module scikit_image ^
    --exclude-module onnxruntime ^
    --exclude-module onnxruntime.capi

echo Compilando UnifiedMain (Unified_Combat_V1)...
%PYINST% --onefile --noconsole ^
    --name "Unified_Combat_V1" ^
    --icon "assets/icon.ico" ^
    %EXCLUDES% ^
    --add-data "yolov8n.onnx;." ^
    --add-data "presets.json;." ^
    --add-data "config_pubg.json;." ^
    --add-data "recoil_patterns.json;." ^
    --add-data "sounds;./sounds/" ^
    --add-data "weapon_templates;weapon_templates/" ^
    --add-data "assets/logo.png;assets/" ^
    --add-data "assets/icon.ico;assets/" ^
    --collect-all firebase_admin ^
    --hidden-import TacticalHUD ^
    --hidden-import UnifiedObjectDetector ^
    --hidden-import CombatCore ^
    --hidden-import CombatSecurity ^
    --hidden-import screen_capture ^
    --hidden-import command_executor ^
    --hidden-import aim_tracker ^
    --hidden-import aim_calculation ^
    --hidden-import psutil ^
    UnifiedMain.py

echo.
echo Compilando AdminPanel...
%PYINST% --onedir --noconsole ^
    --name "AdminPanel" ^
    --icon "assets/icon.ico" ^
    %EXCLUDES% ^
    --add-data "assets/icon.ico;assets/" ^
    --hidden-import AdminPanel ^
    AdminPanel.py

if %errorlevel% neq 0 (
    echo BUILD FAILED
    pause
    exit /b 1
)

echo.
echo BUILD READY - Unified_Combat_V1.exe em dist/
pause
