@echo off
chcp 65001 > nul
title Gemini Computer Use for Windows

echo ===================================================
echo     Запуск Gemini Computer Use для Windows
echo ===================================================
echo.

python run.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ошибка при запуске. Убедитесь, что Python установлен.
    pause
)
