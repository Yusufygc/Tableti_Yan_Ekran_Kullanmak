@echo off
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
if exist "venv\Scripts\pythonw.exe" (
    start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py" %*
) else if exist "venv\Scripts\python.exe" (
    start "" "%~dp0venv\Scripts\python.exe" "%~dp0main.py" %*
) else (
    start "" pythonw main.py %*
)
exit /b 0
