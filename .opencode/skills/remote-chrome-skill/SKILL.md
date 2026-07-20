---
name: remote-chrome-skill
description: "Control a Windows Chrome debug instance from WSL Ubuntu via the Chrome DevTools Protocol (CDP). Use this skill when the user asks to operate a real Chrome browser running on Windows - open URLs, click buttons, type into inputs, scroll, read cookies/localStorage, wait for user login to complete, or automate any browser interaction that requires a real browser profile. Triggers: 'remote-chrome', 'windows chrome', 'control chrome from wsl', 'use my chrome', 'chrome debug', 'browser cookie scraping', 'browser automation via cdp', 'CDP', 'DevTools Protocol'."
license: MIT
compatibility: opencode
metadata:
  audience: developers
  platform: wsl
  requires: chrome-windows
---

# remote-chrome-skill

Control a real Chrome browser running on Windows from WSL Ubuntu (or any Linux that can reach Chrome via CDP).

## What this skill does

It exposes a CLI (`remote-chrome`) backed by an async Python CDP client. Each subcommand outputs JSON so an agent can parse results reliably. It covers:

- Listing and activating tabs (by URL substring **or** 0-based index)
- Navigating to URLs — supports `--wait-for-selector` / `--wait-for-title` for SPAs where `readyState` lies
- Clicking elements by CSS selector (real CDP mouse events; error messages include `url` + `readyState` for diagnostics)
- Typing text into inputs via `Input.insertText`
- Scrolling — **default `--method=wheel`** dispatches real CDP `mouseWheel` events (triggers SPA virtualization / IntersectionObserver lazy-load). Use `--method=js` for the simpler `window.scrollBy` path. `--wait-ms N` pauses so async renders settle
- Evaluating **arbitrary JS including async/await** (default `awaitPromise=true`; pass `--no-await` to opt out). Set `--timeout-ms` to override the 30s default recv timeout
- Reading **cookies scoped to the current page origin by default** (use `--all` for the full browser cookie jar, `--domain X` for an explicit domain)
- Reading `localStorage` for the current origin
- `wait-for-navigation` (polls `location.href` against the real-time baseline, not the HTTP `/json` tab.url)
- `wait-for-auth` (polls `Network.getCookies` until a named auth cookie appears)
- `start-chrome` (launch Chrome with debug port from WSL — no desktop click needed)
- `kill-chrome` (selectively kill ONLY the debug Chrome instance, never the user's browsing Chrome)
- `bootstrap` (print the one-time Windows setup PowerShell commands)
- `get-download-dir` (read the debug profile's configured download directory from its `Preferences` file — CDP does not expose this directly)

## Installation

From WSL Ubuntu:

```bash
git clone https://github.com/<owner>/remote-chrome-skill
cd remote-chrome-skill
uv sync                      # creates .venv with websockets dependency
```

Optionally install the CLI on PATH:

```bash
uv pip install -e .          # exposes `remote-chrome` on PATH
```

Or just use `uv run remote-chrome <command>` from the project root.

## Windows one-time setup (run ONCE on the Windows host)

From an Administrator PowerShell window on Windows, run the script:

```powershell
# From WSL, get the script content:
#   uv run remote-chrome bootstrap
# Copy the printed `powershell_script` field to a Windows PowerShell (Admin) window.
```

Or copy `scripts/windows-bootstrap.ps1` to Windows and run it as Administrator.

It configures:
1. `netsh portproxy` 9223 -> 9222 (Chrome binds 127.0.0.1; this exposes it to WSL)
2. Firewall rule allowing inbound TCP 9223
3. `C:\temp\chrome-debug-profile` directory
4. Desktop shortcut "Chrome Debug" (one-click launcher)

The setup persists across reboots.

## Daily usage flow

```bash
# 1. (Optional) If Chrome is not running, start it from WSL
uv run remote-chrome start-chrome

# 2. Navigate somewhere
uv run remote-chrome navigate "https://example.com"

# 3. Interact with the page
uv run remote-chrome click "#submit-button"
uv run remote-chrome type "#username-input" "alice"
uv run remote-chrome scroll --dy 500            # default method=wheel --wait-ms=200

# 4. Read data
uv run remote-chrome cookies                    # current page only (use --all for full jar)
uv run remote-chrome localstorage
uv run remote-chrome eval "JSON.stringify({url: location.href, title: document.title})"

# 5. Inspect the debug profile's download directory
uv run remote-chrome get-download-dir           # reads C:\temp\chrome-debug-profile\Default\Preferences
```

## Handling SPAs (X, Reddit, modern e-commerce)

These sites have a separate render step AFTER `document.readyState==='complete'`. Use **either** of these waits:

```bash
# Option A: wait for a CSS selector to appear (most reliable)
uv run remote-chrome navigate "https://x.com/" --wait-for-selector "article"

# Option B: wait until document.title starts with something specific
uv run remote-chrome navigate "https://x.com/home" --wait-for-title "Home"

# Option C: don't navigate, just wait after the user clicked something
uv run remote-chrome wait-for-navigation --url-contains "/home" --timeout 30
```

### Scrolling to trigger lazy-render / virtual lists

The default `--method=wheel` dispatches real `Input.dispatchMouseEvent(mouseWheel)` at the viewport center. **This is required** for sites with virtualization (X, Reddit) which look at `wheel` events, not just scroll position, before rendering more rows. Don't switch to `--method=js` unless you understand the trade-off.

```bash
uv run remote-chrome scroll --dy 1500 --wait-ms 500    # wheel scroll, then wait for new articles
```

### Async eval to poll for DOM stability

Because `eval` awaits Promises by default, you can park a polling expression in one call instead of looping CLI invocations:

```bash
uv run remote-chrome eval "(async () => {
  let prev = -1, stable = 0;
  for (let i = 0; i < 30; i++) {
    const n = document.querySelectorAll('article').length;
    if (n === prev && n > 0) { stable++; if (stable >= 4) return {stabilized: true, count: n}; }
    else { stable = 0; }
    prev = n;
    await new Promise(r => setTimeout(r, 200));
  }
  return {stabilized: false, last_count: prev};
})()"
```

This avoids CLI call latency between polls and is the natural pattern for "wait until new tweets settle".

## Login flow (the user types credentials themselves, NOT the agent)

This skill deliberately does NOT automate password entry. The flow is:

```bash
# 1. Navigate to the login page (note: use --wait-for-selector if it's a SPA)
uv run remote-chrome navigate "https://accounts.google.com/" --wait-for-selector "input[type=email]"

# 2. Tell the user to type their email/password/2FA in the real Chrome window

# 3. Wait until auth cookie appears (default waits for SID on .google.com,
#    pass --cookie-name / --cookie-domain for other sites)
uv run remote-chrome wait-for-auth --cookie-name SID --cookie-domain .google.com --timeout 300

# 4. Read the auth cookies for use elsewhere.
#    cookies without args = cookies for current page origin (safe default).
uv run remote-chrome cookies --domain google.com     # explicit domain filter still works
```

## Security constraints (HARD RULES for the agent)

The agent using this skill MUST follow:

1. **Never use `type` to enter passwords or 2FA codes.** Authentication flows are intentional manual user actions. The skill provides `wait-for-auth` precisely so the agent does not have to handle credentials.

2. **Do not paste sensitive cookies into chat/logs.** When reading cookies for diagnostic purposes, summarize counts and names rather than dumping values. If a value must be transmitted, redact it (`value=<REDACTED>`).

3. **`kill-chrome` kills ONLY the debug Chrome instance** (filtered by `--remote-debugging-port=9222` in its command line). Your non-debug browsing Chrome is NOT affected. Still, use sparingly — the debug profile's tabs might have unsaved work.

4. **Limit `eval` to read-only or spec-fulfilled actions.** Do not call `eval` with code injected from untrusted sources.

5. **The debug Chrome profile is separate from the user's main Chrome profile.** Websites are NOT logged in by default in the debug profile — the user must log in there manually once per site. This is by design (avoids perturbing the user's main browser state).

6. **`start-chrome` only launches with the fixed debug profile** at `C:\temp\chrome-debug-profile`. The agent must not override the `--user-data-dir` flag to point at the user's main Chrome profile, as that would corrupt their profile when both instances run simultaneously.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `uv run remote-chrome status` returns `chrome_not_running` | Chrome not launched or crashed | Run `uv run remote-chrome start-chrome` |
| Connection refused after reboot | Windows portproxy persisted, but Chrome was not relaunched | Run `start-chrome` or double-click the desktop shortcut |
| `chrome_not_running` even after `start-chrome` | Firewall rule deleted, or IP changed | Re-run the bootstrap PowerShell script as Administrator |
| `tab_not_found` | No tab matches the URL substring | Run `uv run remote-chrome list-tabs` to see available tabs |
| `element_not_found` | CSS selector did not match | The page may still be loading; pass `--timeout` to `navigate` or add explicit waits |
| `navigation_timeout` | Page took >15s to load | Run `navigate --timeout 60` |

## Auto-detection of Windows host IP

When `--host` is not given, the CLI reads `/etc/resolv.conf` for the `nameserver` entry, which on WSL2 is typically the Windows host IP (e.g. `172.x.x.1`). If your WSL is configured differently, pass `--host <windows-ip>` explicitly.

## Architecture

```
WSL (this skill) --HTTP/WS--> 172.x.x.1:9223 --netsh portproxy--> 127.0.0.1:9222 --WS--> Chrome (--remote-debugging-port=9222)
```

Chrome's CDP only binds `127.0.0.1`. The `netsh portproxy` rule forwards traffic from the Windows host's external interface (reachable from WSL) to the loopback CDP port, and a firewall rule lets WSL subnet traffic through.

## License

MIT — see `LICENSE`.

