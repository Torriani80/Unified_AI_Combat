@echo off
title Unified Combat Launcher
echo ====================================================
echo    UNIFIED COMBAT - AUTO-LAUNCHER
echo ====================================================
echo.

echo [1/3] Verificando dependencias...
python -m pip install PyQt5 numpy opencv-python mss onnxruntime

echo.
echo [2/3] Iniciando sistema...
echo.
python UnifiedMain.py

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Ocorreu um problema ao iniciar.
    echo Tente executar o arquivo Unified_Combat_V1.exe na pasta dist.
)

echo.
pause
