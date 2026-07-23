# Architecture, Installation & Scenarios

> **Navigation**: [Back to index](../SKILL.md) • [API Reference](api.md) • [Events](events.md) • [SPA Patterns](spa-patterns.md) • [Troubleshooting](troubleshooting.md) • [Security](security.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  WSL Ubuntu (this skill)                                        │
│  ┌─────────────────┐    HTTP/WS    ┌─────────────────────────┐  │
│  │  remote-chrome  │ ────────────► │  172.x.x.1:9223         │  │
│  │  (Python CLI)   │               │  (Windows host IP)      │  │
│  └─────────────────┘               └───────────┬─────────────┘  │
└────────────────────────────────────────────────┼────────────────┘
                                                 │ netsh portproxy
                                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Windows Host                                                   │
│  ┌─────────────────┐    WS (127.0.0.1:9222)    ┌─────────────┐  │
│  │  netsh portproxy│ ◄──────────────────────── │  Chrome     │  │
│  │  9223 → 9222    │                          │  --remote-  │  │
│  └─────────────────┘                          │  debugging- │  │
│                                               │  port=9222  │  │
│  Firewall: Allow inbound TCP 9223             │  --user-    │  │
│  from WSL subnet                              │  data-dir=  │  │
│                                               │  C:\temp\   │  │
│                                               │  chrome-    │  │
│                                               │  debug-     │  │
│                                               │  profile    │  │
│                                               └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Key points**:
- Chrome CDP binds **only `127.0.0.1:9222`** (security default)
- `netsh portproxy` forwards `0.0.0.0:9223` → `127.0.0.1:9222`
- Firewall allows WSL subnet → Windows host TCP 9223
- WSL auto-detects Windows IP via `/etc/resolv.conf` nameserver

---

## Installation

### WSL Ubuntu (one-time)

```bash
git clone https://github.com/v587d/remote-chrome-skill
cd remote-chrome-skill
uv sync                      # creates .venv with websockets
```

Optional — install on PATH:

```bash
uv pip install -e .          # exposes `remote-chrome` globally
# or just use: uv run remote-chrome <command>
```

### Python requirements

- Python ≥ 3.10
- `websockets` (installed via `uv sync`)

---

## Windows one-time setup (run ONCE as Administrator)

### Option A: Auto-generated script

```bash
# From WSL
uv run remote-chrome bootstrap
```

Copy the printed `powershell_script` to a Windows **Administrator PowerShell** window.

### Option B: Manual script

Copy `scripts/windows-bootstrap.ps1` to Windows and run as Administrator.

### What it configures

| # | Action | Command |
|---|--------|---------|
| 1 | Port proxy 9223→9222 | `netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=9223 connectaddress=127.0.0.1 connectport=9222` |
| 2 | Firewall rule | `netsh advfirewall firewall add rule name="WSL Chrome Debug" dir=in action=allow protocol=TCP localport=9223` |
| 3 | Desktop shortcut | "Chrome Debug" → `chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\temp\chrome-debug-profile"` |
| 4 | Profile directory | `New-Item -ItemType Directory -Force -Path "C:\temp\chrome-debug-profile"` |

**Persists across reboots**.

---

## Daily usage flow

```bash
# 1. Start Chrome (if not running)
uv run remote-chrome start-chrome

# 2. Navigate with SPA-aware waits
uv run remote-chrome navigate "https://example.com" --wait-for-selector "body"

# 3. Interact
uv run remote-chrome click "#submit-btn"
uv run remote-chrome type "#search" "query"

# 4. Extract data
uv run remote-chrome cookies
uv run remote-chrome localstorage
uv run remote-chrome eval "document.title"

# 5. Visual verification
uv run remote-chrome screenshot --format png
uv run remote-chrome screenshot --full-page --format jpeg --quality 80

# 6. Network debugging
uv run remote-chrome network-monitor start --url-filter "/api/" --resource-types "XHR,Fetch"
# ... interact ...
uv run remote-chrome network-monitor get
uv run remote-chrome network-monitor stop

# 7. Event subscription (console logs, DOM mutations, etc.)
uv run remote-chrome event subscribe --event-types "Runtime.consoleAPICalled,Page.loadEventFired"
# ... interact ...
uv run remote-chrome event poll --clear
uv run remote-chrome event unsubscribe

# 8. Tab management
uv run remote-chrome tab-new --url "https://other.com"
uv run remote-chrome list-tabs
uv run remote-chrome tab-switch <tab_id>

# 9. Debug profile download dir
uv run remote-chrome get-download-dir
```

---

## Login flow (human-in-the-loop)

> **Rule**: Agent never handles passwords/2FA.

```bash
# 1. Navigate to login page (SPA-aware)
uv run remote-chrome navigate "https://accounts.google.com/" --wait-for-selector "input[type=email]"

# 2. Human types email/password/2FA in the REAL Chrome window

# 3. Wait for auth cookie (defaults: SID on .google.com)
uv run remote-chrome wait-for-auth --cookie-name SID --cookie-domain .google.com --timeout 300

# 4. Read cookies for current page origin (safe default)
uv run remote-chrome cookies
# Or explicit domain
uv run remote-chrome cookies --domain google.com
```

**Custom auth cookies**: Pass `--cookie-name` / `--cookie-domain` to `wait-for-auth`.

---

## Auto-detection of Windows host IP

When `--host` omitted, CLI reads `/etc/resolv.conf`:

```bash
# Typical WSL2 output:
# nameserver 172.25.112.1
# → uses 172.25.112.1:9223
```

If your WSL config differs (e.g., mirrored mode, custom DNS), pass explicitly:

```bash
uv run remote-chrome --host 192.168.1.100 status
```

---

## Quick-reference scenarios

### Visual verification after interaction

```bash
uv run remote-chrome click "#submit"
uv run remote-chrome screenshot --format png
```

### Debug "element not found"

```bash
# Navigate + immediate full-page screenshot to see actual DOM state
uv run remote-chrome navigate "https://example.com" --wait-for-selector "body"
uv run remote-chrome screenshot --full-page --format jpeg --quality 60
```

### Document archival (full article → PDF later)

```bash
uv run remote-chrome navigate "https://example.com/article" --wait-for-selector "article"
uv run remote-chrome screenshot --full-page --format png
# Output: data_base64 → decode & save as PNG → print to PDF
```

### SPA data extraction (X/Twitter style)

```bash
# 1. Wait for content
uv run remote-chrome navigate "https://x.com/home" --wait-for-title "Home"

# 2. Wait for tweets to render
uv run remote-chrome eval "(async()=>{for(let i=0;i<20;i++){if(document.querySelectorAll('article').length>0)return true;await new Promise(r=>setTimeout(r,200))}return false})()"

# 3. Extract
uv run remote-chrome eval "Array.from(document.querySelectorAll('article')).map(a=>a.innerText).join('|||')"
```

### Console error monitoring

```bash
uv run remote-chrome event subscribe --event-types "Runtime.consoleAPICalled,Runtime.exceptionThrown" --timeout 300
# ... reproduce bug ...
uv run remote-chrome event poll --clear | jq 'select(.method=="Runtime.consoleAPICalled" and .params.type=="error")'
uv run remote-chrome event unsubscribe
```

### Network API debugging

```bash
uv run remote-chrome network-monitor start --url-filter "/api/" --resource-types "XHR,Fetch"
uv run remote-chrome click "#search-btn"
uv run remote-chrome network-monitor get | jq '.requests[] | {url: .url, status: .status, method: .method, body: .responseBody}'
uv run remote-chrome network-monitor stop
```

### Tab management for parallel tasks

```bash
# Open background tab for later
uv run remote-chrome tab-new --url "https://api.docs.example.com"

# Switch, work, switch back
uv run remote-chrome list-tabs
uv run remote-chrome tab-switch <other_tab_id>
# ... work ...
uv run remote-chrome tab-switch <original_tab_id>
```

### Download directory inspection

```bash
uv run remote-chrome get-download-dir
# Returns: {found: true, path: "C:\\Users\\user\\Downloads", source: "profile_preferences"}
```

---

## Configuration via environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REMOTE_CHROME_EXE` | `C:\Program Files\Google\Chrome\Application\chrome.exe` | Chrome binary path |
| `REMOTE_CHROME_PROFILE_DIR` | `C:\temp\chrome-debug-profile` | Debug profile directory |

Override in shell:

```bash
export REMOTE_CHROME_EXE="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
uv run remote-chrome start-chrome
```

---

## Version compatibility

| Component | Tested version |
|-----------|----------------|
| Chrome | 120+ (CDP 1.3) |
| Python | 3.10, 3.11, 3.12 |
| WSL | WSL2 (Ubuntu 22.04/24.04) |
| Windows | 10/11 (Admin for bootstrap) |

CDP protocol version negotiated at connect; skill works with any Chrome ≥ 120.

---

## License

MIT — see `LICENSE`.