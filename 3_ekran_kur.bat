@echo off
cd /d "%~dp0"

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Requesting Administrator privileges to install 3rd Virtual Display...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
    exit /b
)

echo [1/3] Copying vdd_settings.xml to C:\VirtualDisplayDriver...
if not exist "C:\VirtualDisplayDriver" mkdir "C:\VirtualDisplayDriver"
copy /Y "%~dp0third_party\vdd\VirtualDisplayDriver\vdd_settings.xml" "C:\VirtualDisplayDriver\vdd_settings.xml" >nul

echo [2/3] Installing Virtual Display Driver (Root\MttVDD)...
"%~dp0third_party\vdd\nefcon\x64\nefconc.exe" --remove-device-node --hardware-id Root\MttVDD --class-guid 4D36E968-E325-11CE-BFC1-08002BE10318 >nul 2>&1
"%~dp0third_party\vdd\nefcon\x64\nefconc.exe" --create-device-node --hardware-id Root\MttVDD --class-name Display --class-guid 4D36E968-E325-11CE-BFC1-08002BE10318
"%~dp0third_party\vdd\nefcon\x64\nefconc.exe" --install-driver --inf-path "%~dp0third_party\vdd\VirtualDisplayDriver\MttVDD.inf"

echo [3/3] Switching Windows display mode to Extend...
"%SystemRoot%\System32\DisplaySwitch.exe" /extend
echo [OK] 3rd Virtual Display is now active!
timeout /t 3 >nul
