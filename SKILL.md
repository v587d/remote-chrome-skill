---
name: remote-chrome-skill
description: "Control a Windows Chrome debug instance from WSL Ubuntu via the Chrome DevTools Protocol (CDP). Use for real browser automation: navigate, click, type, scroll, screenshot, read cookies/localStorage, monitor network, subscribe to CDP events. Triggers: 'remote-chrome', 'windows chrome', 'control chrome from wsl', 'chrome debug', 'browser automation via cdp', 'CDP', 'DevTools Protocol', 'take screenshot', 'capture page'."
license: MIT
compatibility: opencode
metadata:
  audience: developers
  platform: wsl
  requires: chrome-windows
  version: "0.1.0"
---

# remote-chrome-skill

Control a real Chrome browser running on Windows from WSL Ubuntu (or any Linux that can reach Chrome via CDP).

## What this skill does

Exposes a CLI (`remote-chrome`) backed by an async Python CDP client. Every subcommand outputs JSON for reliable agent parsing. Covers:

- **Tab management** — create/close/switch/list tabs
- **Navigation** — with SPA-aware `--wait-for-selector` / `--wait-for-title`
- **Interaction** — click, type, scroll (real `mouseWheel` by default)
- **Evaluation** — arbitrary JS including async/await
- **Data extraction** — cookies (origin-scoped by default), localStorage
- **Screenshots** — PNG/JPEG, viewport or full-page
- **Network monitoring** — filter by URL/resource-type, retrieve request/response details
- **CDP event subscription** — listen to `Runtime.*`, `Page.*`, `Network.*`, `DOM.*`, `Log.*` events via background daemon + JSONL polling
- **Wait helpers** — `wait-for-navigation`, `wait-for-auth`
- **Chrome lifecycle** — `start-chrome`, `kill-chrome` (selective), `bootstrap` (Windows setup), `get-download-dir`

## Quick start (1 minute)

```bash
# 1. Install
git clone https://github.com/v587d/remote-chrome-skill
cd remote-chrome-skill && uv sync

# 2. One-time Windows setup (run in Admin PowerShell on Windows)
uv run remote-chrome bootstrap   # copy printed script to Windows Admin PowerShell

# 3. Start Chrome debug instance
uv run remote-chrome start-chrome

# 4. Navigate & interact
uv run remote-chrome navigate "https://example.com" --wait-for-selector "body"
uv run remote-chrome click "#btn"
uv run remote-chrome screenshot --format png
```

## Command index

| Category | Commands |
|----------|----------|
| **Status & tabs** | `status`, `list-tabs`, `tab-new`, `tab-close`, `tab-switch`, `activate` |
| **Navigation** | `navigate`, `wait-for-navigation` |
| **Interaction** | `click`, `type`, `scroll`, `eval` |
| **Data** | `cookies`, `localstorage`, `get-download-dir` |
| **Visual** | `screenshot` |
| **Network** | `network-monitor` (start/stop/get) |
| **Events** | `event` (subscribe/unsubscribe/poll/clear) |
| **Auth** | `wait-for-auth` |
| **Chrome lifecycle** | `start-chrome`, `kill-chrome`, `bootstrap` |

**Full command reference →** [references/api.md](references/api.md)

## Key capabilities

- **SPA-ready** — `--wait-for-selector` / `--wait-for-title` / async eval polling → [SPA patterns](references/spa-patterns.md)
- **Event-driven** — subscribe to console logs, network, DOM mutations, page lifecycle → [Event subscription](references/events.md)
- **Secure by default** — no password automation, cookie redaction, selective kill → [Security constraints](references/security.md)

## Troubleshooting

Common issues and fixes → [references/troubleshooting.md](references/troubleshooting.md)

## Architecture

WSL → Windows host IP:9223 → netsh portproxy → 127.0.0.1:9222 → Chrome CDP

Details: [references/architecture.md](references/architecture.md) (installation, Windows bootstrap, login flow, auto-detection, quick-reference scenarios)

## License

MIT — see `LICENSE`.