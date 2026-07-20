@echo off
REM ============================================================
REM remote-chrome-skill: Windows one-time setup
REM Right-click this file -> Run as Administrator
REM ============================================================

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click the file -^> Run as Administrator -^> re-run this file.
    pause
    exit /b 1
)

REM 1) Port proxy: forward 0.0.0.0:9223 -> 127.0.0.1:9222
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=9223 connectaddress=127.0.0.1 connectport=9222

REM 2) Firewall rule
netsh advfirewall firewall add rule name="WSL Chrome Debug" dir=in action=allow protocol=TCP localport=9223

REM 3) Create profile dir
if not exist "C:\temp\chrome-debug-profile" mkdir "C:\temp\chrome-debug-profile"

REM 4) Create desktop shortcut - uses PowerShell for COM object, easier than VBScript
powershell -NoProfile -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\Chrome Debug.lnk'); $Shortcut.TargetPath = 'C:\Program Files\Google\Chrome\Application\chrome.exe'; $Shortcut.Arguments = '--remote-debugging-port=9222 --user-data-dir=""C:\temp\chrome-debug-profile""'; $Shortcut.Save()"

echo.
echo Setup complete. Next steps:
echo   1. Double-click "Chrome Debug" on your desktop, OR from WSL run:
echo       remote-chrome start-chrome
echo   2. From WSL, test connectivity:
echo       remote-chrome status
echo.
pause

