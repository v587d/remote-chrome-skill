# API Reference — `remote-chrome` CLI

> **Navigation**: [Back to index](../SKILL.md) • [Events](events.md) • [SPA Patterns](spa-patterns.md) • [Troubleshooting](troubleshooting.md)

---

## Global options

```bash
remote-chrome [--host <ip>] [--port <port>] <command> [args...]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | Auto-detect via `/etc/resolv.conf` nameserver | Windows host IP (WSL2 gateway) |
| `--port` | `9223` | Chrome CDP port (proxied to 9222 on Windows) |

**All commands output JSON to stdout. Errors to stderr.**

---

## Commands

### `status` — Health check

```bash
remote-chrome status
```

```json
{
  "running": true,
  "host": "172.25.112.1",
  "port": 9223,
  "browser": "Chrome/150.0.7871.115",
  "protocol_version": "1.3",
  "tab_count": 3
}
```

---

### `list-tabs` — List page tabs

```bash
remote-chrome list-tabs
```

```json
{
  "tabs": [
    {"index": 0, "id": "TAB1", "url": "https://example.com/", "title": "Example", "type": "page"},
    {"index": 1, "id": "TAB2", "url": "https://github.com/", "title": "GitHub", "type": "page"}
  ]
}
```

---

### `tab-new` — Create new tab

```bash
remote-chrome tab-new [--url <url>] [--new-window]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | `about:blank` | URL to load |
| `--new-window` | false | Open in new window instead of tab |

```json
{"created": {"id": "TAB3", "url": "https://example.com/", "title": "Example"}}
```

---

### `tab-close` — Close tab by ID

```bash
remote-chrome tab-close <tab_id>
```

```json
{"closed": {"id": "TAB3", "success": true}}
```

---

### `tab-switch` — Switch to tab by ID

```bash
remote-chrome tab-switch <tab_id>
```

```json
{"activated": {"id": "TAB2", "url": "https://github.com/", "title": "GitHub"}}
```

---

### `activate` — Activate tab by URL substring or index

```bash
remote-chrome activate [<url_substring>] [--index <n>]
```

| Argument | Description |
|----------|-------------|
| `url_substring` | Match in URL or title (omit if using `--index`) |
| `--index` | 0-based index from `list-tabs` |

```json
{"activated": {"id": "TAB1", "url": "https://example.com/", "title": "Example"}}
```

---

### `navigate` — Navigate current tab

```bash
remote-chrome navigate <url> [--no-wait] [--timeout <sec>] [--wait-for-selector <css>] [--wait-for-title <regex>]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--no-wait` | false | Return immediately after `Page.navigate` |
| `--timeout` | `15` | Wait timeout in seconds |
| `--wait-for-selector` | — | Poll until CSS selector matches |
| `--wait-for-title` | — | Poll until `document.title` matches regex |

```json
{"nav": {"frameId": "123", "loaderId": "456"}, "url": "https://example.com/"}
```

**For SPAs**: Always use `--wait-for-selector` or `--wait-for-title`. See [SPA Patterns](spa-patterns.md).

---

### `click` — Click element by CSS selector

```bash
remote-chrome click <selector>
```

```json
{"x": 412.5, "y": 287.5, "selector": "#submit-button"}
```

**Error if not found**: `element_not_found` with `url` + `readyState` context.

---

### `type` — Type text into input

```bash
remote-chrome type <selector> <text>
```

```json
{"selector": "#username", "text_length": 5, "input_value": "alice"}
```

**Behavior**: Focuses element via JS, then `Input.insertText`. Verifies `input.value` after.

---

### `scroll` — Scroll page or element

```bash
remote-chrome scroll [--dx <n>] [--dy <n>] [--selector <css>] [--method wheel|js] [--wait-ms <ms>]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--dx` | `0` | Horizontal delta |
| `--dy` | `500` | Vertical delta |
| `--selector` | — | Scroll element instead of window (only `--method=js`) |
| `--method` | `wheel` | `wheel` = real CDP mouseWheel (triggers virtual lists); `js` = `window.scrollBy` |
| `--wait-ms` | `200` | Pause after scroll for async renders |

```json
{"scrollX": 0, "scrollY": 1500}
```

---

### `eval` — Evaluate JavaScript

```bash
remote-chrome eval <expression> [--no-await] [--timeout-ms <ms>]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--no-await` | false | Disable `awaitPromise` (default: true, awaits Promises) |
| `--timeout-ms` | `30000` | CDP receive timeout (protects against never-resolving async) |

```json
{"value": "Example Domain"}
```

**Async IIFE pattern** (recommended for polling):

```bash
remote-chrome eval "(async () => { ... })()"
```

---

### `cookies` — Read cookies

```bash
remote-chrome cookies [--domain <domain>] [--url <url>] [--all]
```

| Option | Description |
|--------|-------------|
| `--domain` | Filter by domain (e.g., `google.com`) |
| `--url` | Filter by exact URL |
| `--all` | Return entire browser cookie jar (default: current page origin only) |

```json
{"cookies": [{"name": "SID", "value": "abc", "domain": ".google.com", "path": "/", "secure": true, "http_only": true, "same_site": "Lax"}]}
```

---

### `localstorage` — Read localStorage

```bash
remote-chrome localstorage
```

```json
{"entries": {"theme": "dark", "user_id": "123"}, "count": 2}
```

---

### `screenshot` — Capture screenshot

```bash
remote-chrome screenshot [--format png|jpeg] [--quality <0-100>] [--full-page]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `png` | `png` or `jpeg` |
| `--quality` | — | JPEG quality (only with `--format jpeg`) |
| `--full-page` | false | Capture entire scrollable page |

```json
{"format": "png", "full_page": false, "size_bytes": 45212, "data_base64": "iVBORw0KGgoAAAANSUhEUg..."}
```

---

### `get-download-dir` — Read debug profile download directory

```bash
remote-chrome get-download-dir
```

```json
{"found": true, "path": "C:\\Users\\user\\Downloads", "source": "profile_preferences", "profile": "C:\\temp\\chrome-debug-profile"}
```

Reads `Preferences` file directly — CDP does not expose this.

---

### `wait-for-navigation` — Wait for URL change

```bash
remote-chrome wait-for-navigation [--url-contains <substr>] [--timeout <sec>] [--poll-interval <sec>]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--url-contains` | — | Wait until URL contains substring |
| `--timeout` | `300` | Max wait seconds |
| `--poll-interval` | `1.0` | Poll interval seconds |

```json
{"url": "https://example.com/dashboard", "title": "Dashboard"}
```

**Uses real-time `location.href` baseline**, not HTTP `/json` tab.url.

---

### `wait-for-auth` — Wait for auth cookie

```bash
remote-chrome wait-for-auth [--cookie-name <name>] [--cookie-domain <domain>] [--timeout <sec>] [--poll-interval <sec>]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--cookie-name` | `SID` | Cookie name to watch |
| `--cookie-domain` | `.google.com` | Cookie domain |
| `--timeout` | `300` | Max wait seconds |
| `--poll-interval` | `1.0` | Poll interval seconds |

```json
{"cookie_name": "SID", "cookie_domain": ".google.com", "found": true}
```

---

### `start-chrome` — Launch Chrome from WSL

```bash
remote-chrome start-chrome [--timeout <sec>]
```

```json
{"started": true, "ready": true, "host": "172.25.112.1", "port": 9223}
```

Launches with `--remote-debugging-port=9222 --user-data-dir=C:\temp\chrome-debug-profile` via PowerShell.

---

### `kill-chrome` — Kill ONLY debug Chrome

```bash
remote-chrome kill-chrome
```

```json
{"killed": true}
```

**Safety**: Filters by `--remote-debugging-port=9222` in command line. Never touches your main Chrome.

---

### `bootstrap` — Print Windows setup script

```bash
remote-chrome bootstrap
```

```json
{"instructions": "...", "powershell_script": "...", "steps_summary": [...], "notes": [...]}
```

Run the `powershell_script` in **Administrator PowerShell** on Windows. Configures:
1. `netsh portproxy` 9223 → 9222
2. Firewall rule TCP 9223
3. Desktop shortcut "Chrome Debug"
4. `C:\temp\chrome-debug-profile` directory

---

### `network-monitor` — Monitor network requests

```bash
remote-chrome network-monitor start [--url-filter <substr>] [--resource-types <csv>]
remote-chrome network-monitor get
remote-chrome network-monitor stop
```

| Action | Options |
|--------|---------|
| `start` | `--url-filter` (substring), `--resource-types` (e.g., `XHR,Fetch,Document`) |
| `get` | Returns captured requests as JSON array |
| `stop` | Disables monitoring |

```json
{"requests": [{"requestId": "...", "url": "https://api.example.com/data", "method": "GET", "status": 200, "resourceType": "Fetch", "timing": {...}, "requestHeaders": {...}, "responseHeaders": {...}, "responseBody": "..."}], "count": 1}
```

---

## Event subscription — `event` command

```bash
remote-chrome event subscribe --event-types <csv> [--timeout <sec>]
remote-chrome event poll [--clear]
remote-chrome event clear
remote-chrome event unsubscribe
```

| Action | Options |
|--------|---------|
| `subscribe` | `--event-types` comma-separated (e.g., `Runtime.consoleAPICalled,Page.loadEventFired`); supports wildcards `Runtime.*`; `--timeout` max seconds (0=indefinite, default 300) |
| `poll` | `--clear` = read and truncate |
| `clear` | Truncate without reading |
| `unsubscribe` | Stop daemon |

**Full details**: [Events Reference](events.md)

```json
// subscribe
{"started": true, "pid": 12345, "events_file": "/tmp/remote-chrome-events-9223.jsonl", "subscribed_types": ["Runtime.consoleAPICalled", "Page.loadEventFired"], "timeout": 300, "requested": ["Runtime.consoleAPICalled", "Page.loadEventFired"]}

// poll
{"events": [{"timestamp": 1718500001.234, "method": "Runtime.consoleAPICalled", "params": {...}}], "count": 1, "events_file": "/tmp/remote-chrome-events-9223.jsonl"}

// unsubscribe
{"stopped": true, "events_file": "/tmp/remote-chrome-events-9223.jsonl"}
```

---

## Error codes (JSON stderr)

| Code | HTTP | Meaning |
|------|------|---------|
| `chrome_not_running` | 3 | CDP unreachable |
| `tab_not_found` | 4 | No matching tab |
| `element_not_found` | 5 | Selector no match |
| `navigation_timeout` | 6 | Wait-for-selector/title/load timeout |
| `auth_timeout` | 7 | Auth cookie didn't appear |
| `cdp_timeout` | 8 | CDP response timeout (eval Promise) |
| `remote_chrome_error` | 1 | Other CDP/client errors |

```json
{"error": "element_not_found", "message": "No element matching '#missing' at URL https://example.com/ (readyState=complete)"}
```

---

## See also

- [Events Reference](events.md) — CDP event types, wildcards, daemon lifecycle
- [SPA Patterns](spa-patterns.md) — Robust SPA handling workflows
- [Troubleshooting](troubleshooting.md) — Symptom → Cause → Fix table