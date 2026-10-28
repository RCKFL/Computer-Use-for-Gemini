@echo off
chcp 65001 > nul
title Установка зависимостей Gemini Computer Use

echo ===================================================
echo   Установка библиотеки Pillow для быстрого захвата
echo ===================================================
echo.

python -m pip install -r requirements.txt

echo.
echo Установка завершена! Теперь можно запускать run.bat.
pause
