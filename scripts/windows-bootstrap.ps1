# ============================================================
# remote-chrome-skill: Windows one-time setup
# Run this in a PowerShell window LAUNCHED AS ADMINISTRATOR.
# ============================================================

# Requires Administrator privileges
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell -> Run as Administrator -> re-run this file." -ForegroundColor Yellow
    exit 1
}

# 1) Port proxy: forward 0.0.0.0:9223 -> 127.0.0.1:9222 so WSL can reach Chrome CDP
netsh interface portproxy add v4tov4 `
    listenaddress=0.0.0.0 listenport=9223 `
    connectaddress=127.0.0.1 connectport=9222

# 2) Firewall rule: allow inbound TCP on 9223 from WSL subnet
netsh advfirewall firewall add rule `
    name="WSL Chrome Debug" dir=in action=allow `
    protocol=TCP localport=9223

# 3) Create the chrome-debug-profile directory if it does not exist
New-Item -ItemType Directory -Force -Path "C:\temp\chrome-debug-profile" | Out-Null

# 4) Create desktop shortcut "Chrome Debug" (optional, handy one-click launcher)
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Chrome Debug.lnk")
$Shortcut.TargetPath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$Shortcut.Arguments = '--remote-debugging-port=9222 --user-data-dir="C:\temp\chrome-debug-profile"'
$Shortcut.Save()

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Double-click 'Chrome Debug' on your desktop, OR from WSL run:"
Write-Host "       remote-chrome start-chrome"
Write-Host "  2. From WSL, test connectivity:"
Write-Host "       remote-chrome status"

