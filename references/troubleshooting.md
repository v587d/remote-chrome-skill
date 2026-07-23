# Troubleshooting

> **Navigation**: [Back to index](../SKILL.md) • [API Reference](api.md) • [Events](events.md) • [SPA Patterns](spa-patterns.md) • [Security](security.md) • [Architecture](architecture.md)

---

## Quick diagnosis

| Symptom | Most likely cause | First try |
|---------|-------------------|-----------|
| `chrome_not_running` | Chrome not started or crashed | `start-chrome` |
| `tab_not_found` | No tab matches substring | `list-tabs` to see IDs |
| `element_not_found` | Page still loading / wrong selector | Add `--wait-for-selector` or screenshot |
| `navigation_timeout` | Page slow or SPA render not done | Increase `--timeout` / use SPA patterns |
| `auth_timeout` | User didn't login / wrong cookie name | Check login page, verify cookie name |
| `cdp_timeout` | Async eval Promise never resolves | Add `--timeout-ms` / fix selector |
| `daemon exited immediately` | No real page tab open | `navigate` to real URL first |
| Empty event poll | Wrong event name / no activity | Try `Runtime.*` wildcard |

---

## Full symptom → cause → fix table

### Chrome connection

| Symptom | Cause | Fix |
|---------|-------|-----|
| `status` → `chrome_not_running` | Chrome not launched | `uv run remote-chrome start-chrome` |
| `status` → `chrome_not_running` after reboot | Portproxy persisted but Chrome not relaunched | `start-chrome` or click "Chrome Debug" shortcut |
| `start-chrome` succeeds but `status` still fails | Firewall rule deleted / IP changed | Re-run bootstrap PowerShell as Admin |
| Connection refused on `navigate` | Chrome crashed after start | Check Windows Task Manager; `kill-chrome` then `start-chrome` |

### Tabs

| Symptom | Cause | Fix |
|---------|-------|-----|
| `tab_not_found` on `activate` | Substring doesn't match any tab | `list-tabs` to see exact URLs/titles |
| `tab_not_found` on `tab-switch` | Tab ID invalid or tab closed | `list-tabs` for current IDs |
| New tab opens but `navigate` fails | Tab is `chrome://newtab` (no CDP) | `tab-new --url "https://example.com"` |

### Navigation & waits

| Symptom | Cause | Fix |
|---------|-------|-----|
| `navigation_timeout` | Page >15s to load | `navigate --timeout 60` |
| `navigation_timeout` on `--wait-for-selector` | SPA renders after `readyState=complete` | Use `--wait-for-selector` with content selector (see [SPA Patterns](spa-patterns.md)) |
| `--wait-for-title` never matches | Title regex wrong | Test with `eval "document.title"` |
| `wait-for-navigation` times out | URL doesn't change or substring wrong | Verify with `eval "location.href"`; use broader substring |

### Element interaction

| Symptom | Cause | Fix |
|---------|-------|-----|
| `element_not_found` on `click` | Selector wrong or element not rendered | Screenshot to verify; add `--wait-for-selector` to prior `navigate` |
| `click` succeeds but nothing happens | Element not interactive (covered, disabled) | Check `disabled`, `pointer-events`, overlays via screenshot |
| `type` → `input_value` empty | Element not `<input>`/`<textarea>` or not focused | Verify selector targets correct element type |

### Scrolling

| Symptom | Cause | Fix |
|---------|-------|-----|
| Scroll doesn't trigger lazy load | Used `--method=js` | Use default `--method=wheel` (see [SPA Patterns](spa-patterns.md)) |
| Element scroll fails | `--method=js` required for element scroll | Use `--selector` with `--method=js` |
| Page jumps back after scroll | SPA virtual list re-renders | Increase `--wait-ms`; poll for DOM stability |

### Screenshots

| Symptom | Cause | Fix |
|---------|-------|-----|
| Blank/white screenshot | Page not rendered yet | Add `--wait-for-selector "body"` to `navigate` |
| Partial page (not full) | `--full-page` omitted | Add `--full-page` flag |
| Full-page distorted | Responsive layout breaks at large height | Use viewport screenshot (no `--full-page`) |

### Cookies & localStorage

| Symptom | Cause | Fix |
|---------|-------|-----|
| `cookies` returns empty | Default is **current page origin only** | Use `--all` for full jar or `--domain` for specific |
| `localstorage` empty | Wrong origin / page not loaded | Ensure `navigate` completed; check `eval "location.origin"` |

### Network monitoring

| Symptom | Cause | Fix |
|---------|-------|-----|
| `network-monitor get` → empty | Monitor not started / wrong tab | `start` before action; ensure same tab active |
| Missing request bodies | CDP doesn't capture by default | Use `get-request-details` (limited) or `event subscribe Network.*` |

### Event subscription

| Symptom | Cause | Fix |
|---------|-------|-----|
| `subscribe` → `daemon exited immediately` | No page tabs, or active tab is `chrome://` | `navigate` to real URL first |
| `poll` → empty but daemon running | Event name typo / no matching events | Check spelling; try `Runtime.*` |
| Events missing `params` | CDP domain not enabled | Verify event type in [Events Reference](events.md) |
| Daemon dies after navigation | Tab closed / navigated away | Re-subscribe after navigation |

### Auth

| Symptom | Cause | Fix |
|---------|-------|-----|
| `auth_timeout` | User didn't complete login | Increase `--timeout`; verify manual login works |
| `auth_timeout` on correct login | Wrong `--cookie-name` / `--cookie-domain` | Check DevTools Application → Cookies for exact name/domain |

### Download directory

| Symptom | Cause | Fix |
|---------|-------|-----|
| `get-download-dir` → `found: false, source: unreadable` | Chrome not started / profile missing | `start-chrome` first; check `C:\temp\chrome-debug-profile\Default\Preferences` exists |
| Returns Chrome default not custom | Preference not set in profile | Chrome → Settings → Downloads → Change → Save |

---

## Debug commands

```bash
# 1. Health check
uv run remote-chrome status

# 2. See all tabs
uv run remote-chrome list-tabs

# 3. Screenshot current state (always revealing)
uv run remote-chrome screenshot --full-page --format jpeg --quality 60

# 4. Dump page info
uv run remote-chrome eval "JSON.stringify({url: location.href, title: document.title, rs: document.readyState, origin: location.origin})"

# 5. Check active tab's WS URL
uv run remote-chrome eval "location.href"

# 6. Test CDP directly (bypass CLI)
# From Python:
# import websockets, json, asyncio
# asyncio.run(websockets.connect("ws://<host>:9223/devtools/page/<tab_id>"))
```

---

## Event subscription specific

| Issue | Diagnosis | Resolution |
|-------|-----------|------------|
| Daemon PID file exists but process dead | Daemon crashed | Check `/tmp/remote-chrome-events-<port>.jsonl` for last events; re-subscribe |
| High CPU from daemon | Subscribed to `Network.*` on heavy page | Narrow to specific events; use `network-monitor` instead |
| Events stop after `navigate` | New page = new WS; daemon on old WS | Re-subscribe after navigation |
| `poll --clear` returns same events twice | Forgot `--clear` | Use `--clear` to consume |

---

## Windows-side issues

| Issue | Check | Fix |
|-------|-------|-----|
| Portproxy not working | `netsh interface portproxy show all` | Re-run bootstrap |
| Firewall blocking | `netsh advfirewall firewall show rule name="WSL Chrome Debug"` | Re-run bootstrap as Admin |
| Chrome Debug shortcut fails | Target path wrong / profile dir missing | Verify `C:\Program Files\Google\Chrome\Application\chrome.exe` exists; profile dir exists |
| Multiple Chrome instances | `start-chrome` opens new window but debug port busy | `kill-chrome` first |

---

## Logs & artifacts

| Location | Content |
|----------|---------|
| `/tmp/remote-chrome-events-<port>.jsonl` | Event daemon JSONL output |
| `/tmp/remote-chrome-events-<port>.pid` | Daemon PID |
| `C:\temp\chrome-debug-profile\Default\Preferences` | Download dir, cookie settings |
| `C:\temp\chrome-debug-profile\Default\Cookies` | SQLite cookie jar (Chrome internal) |

---

## Getting help

1. Run diagnostic commands above
2. Capture `status`, `list-tabs`, screenshot
3. Note exact error code (`chrome_not_running`, etc.)
4. File issue with: OS, Chrome version, Python version, full command + output