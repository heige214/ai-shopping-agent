@echo off
cd /d "%~dp0"
if exist "D:\develop\vibecoding\.venv\Scripts\python.exe" (
  "D:\develop\vibecoding\.venv\Scripts\python.exe" app.py
) else (
  python app.py
)
pause
