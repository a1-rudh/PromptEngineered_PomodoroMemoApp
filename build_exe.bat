@echo off
REM Build a single-file Windows GUI executable (no console) using PyInstaller
python -m pip install --upgrade pip
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed src\pomodoro.py
echo.
echo Build complete. Find your EXE at: dist\pomodoro.exe
pause