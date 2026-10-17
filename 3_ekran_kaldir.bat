@echo off
cd /d "%~dp0"

net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
    exit /b
)

echo Removing 3rd Virtual Display (Root\MttVDD)...
"%~dp0tools\vdd\nefcon\x64\nefconc.exe" --remove-device-node --hardware-id Root\MttVDD --class-guid 4D36E968-E325-11CE-BFC1-08002BE10318
echo [OK] 3rd Virtual Display removed.
timeout /t 2 >nul
