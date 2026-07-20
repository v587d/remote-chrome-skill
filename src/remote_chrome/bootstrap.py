"""Windows one-time bootstrap configuration generator.

This module does not execute anything on Windows. It returns the exact
commands the user must run ONCE in a PowerShell window launched as
Administrator on the Windows host.

Three things get configured:
  1. Port proxy: forward 0.0.0.0:9223 -> 127.0.0.1:9222 so WSL can reach Chrome
  2. Firewall rule: allow inbound TCP on 9223 from WSL subnet
  3. Desktop shortcut "Chrome Debug" so the user has a one-click launcher

The user can also use `remote-chrome start-chrome` from WSL instead of
clicking the shortcut, so the shortcut is optional.
"""

BOOTSTRAP_PS_TEMPLATE = r"""\
# ============================================================
# remote-chrome-skill: Windows one-time setup
# Run this in a PowerShell window launched AS ADMINISTRATOR.
# ============================================================

# 1) Port proxy: forward 0.0.0.0:9223 -> 127.0.0.1:9222
#    (Chrome CDP only binds 127.0.0.1; this exposes it to WSL)
netsh interface portproxy add v4tov4 `
    listenaddress=0.0.0.0 listenport=9223 `
    connectaddress=127.0.0.1 connectport=9222

# 2) Firewall rule: allow WSL to reach 9223
netsh advfirewall firewall add rule `
    name="WSL Chrome Debug" dir=in action=allow `
    protocol=TCP localport=9223

# 3) Create desktop shortcut "Chrome Debug" (optional but handy)
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Chrome Debug.lnk")
$Shortcut.TargetPath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$Shortcut.Arguments = '--remote-debugging-port=9222 --user-data-dir="C:\temp\chrome-debug-profile"'
$Shortcut.Save()

# 4) Create the chrome-debug-profile directory if it does not exist
New-Item -ItemType Directory -Force -Path "C:\temp\chrome-debug-profile" | Out-Null

Write-Host ""
Write-Host "Setup complete. Next:" -ForegroundColor Green
Write-Host "  Double-click 'Chrome Debug' on your desktop, or run:"
Write-Host "    remote-chrome start-chrome   (from WSL)"
"""


def generate_bootstrap() -> dict:
    """Return a dict with the bootstrap PS script and explanation."""
    return {
        "instructions": "Run the PowerShell script below in an Administrator "
                         "PowerShell window on the Windows host.",
        "powershell_script": BOOTSTRAP_PS_TEMPLATE,
        "steps_summary": [
            "1. netsh portproxy 0.0.0.0:9223 -> 127.0.0.1:9222",
            "2. Firewall rule allow TCP 9223 inbound",
            "3. Desktop shortcut 'Chrome Debug'",
            "4. Create C:\\temp\\chrome-debug-profile directory",
        ],
        "notes": [
            "Requires Administrator privileges for netsh and firewall changes.",
            "Configuration persists across reboots.",
            "The shortcut and profile dir are optional if you start Chrome via "
            "`remote-chrome start-chrome` instead.",
        ],
    }

