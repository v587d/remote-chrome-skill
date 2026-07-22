# Loading remote-chrome-skill into pi Agent

## Quick Start

The skill is already in the correct format for OpenCode-compatible agents. To load it into pi Agent:

### Option 1: Symlink (Recommended)

```bash
# Assuming pi Agent looks for skills in ~/.pi-agent/skills/
mkdir -p ~/.pi-agent/skills/
ln -s /workspace/.opencode/skills/remote-chrome-skill ~/.pi-agent/skills/
```

### Option 2: Copy

```bash
cp -r /workspace/.opencode/skills/remote-chrome-skill ~/.pi-agent/skills/
```

### Option 3: Configure pi Agent

Add this to your pi Agent config file (e.g., `~/.pi-agent/config.yaml`):

```yaml
skills:
  - path: /workspace/.opencode/skills/remote-chrome-skill
    enabled: true
```

## Verification

After loading, test with:

```bash
# Ask pi Agent to use the skill
"Use remote-chrome to navigate to https://example.com and take a screenshot"
```

Or directly via CLI:

```bash
cd /workspace
uv run remote-chrome status
uv run remote-chrome screenshot --format png
```

## Skill Metadata

- **Name**: remote-chrome-skill
- **Version**: 0.1.0
- **Compatibility**: opencode, pi-agent (OpenCode-compatible)
- **Triggers**: remote-chrome, windows chrome, control chrome from wsl, use my chrome, chrome debug, CDP, DevTools Protocol
- **Platform**: WSL Ubuntu → Windows Chrome
- **Dependencies**: Python 3.10+, websockets>=13

## Available Commands

The skill exposes these CLI commands that pi Agent can invoke:

| Command | Description |
|---------|-------------|
| `status` | Check if Chrome is running and reachable |
| `list-tabs` | List all open tabs |
| `navigate <url>` | Navigate to URL (supports --wait-for-selector) |
| `click <selector>` | Click element by CSS selector |
| `type <selector> <text>` | Type text into input |
| `scroll` | Scroll page (default: wheel events for SPA support) |
| `eval <js>` | Execute JavaScript (async/await supported) |
| `cookies` | Read cookies (scoped to current origin by default) |
| `localstorage` | Read localStorage for current origin |
| `screenshot` | Capture screenshot (PNG/JPEG, --full-page supported) |
| `wait-for-navigation` | Wait for URL change |
| `wait-for-auth` | Wait for auth cookie to appear |
| `start-chrome` | Launch Chrome with debug port |
| `kill-chrome` | Close debug Chrome instance |
| `get-download-dir` | Get configured download directory |

## Security Reminders for pi Agent

When using this skill, pi Agent must follow these rules:

1. **Never automate password entry** - Use `wait-for-auth` instead
2. **Redact sensitive cookies** - Don't log full cookie values
3. **Read-only eval** - Don't execute untrusted JS
4. **Separate profile** - Debug profile is isolated from user's main Chrome

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Skill not loaded | Check pi Agent config for skills path |
| Connection refused | Run `remote-chrome start-chrome` first |
| Tab not found | Use `list-tabs` to see available tabs |
| Screenshot blank | Scroll first to load lazy content |

## Example pi Agent Prompts

```
"Navigate to GitHub, wait for the repository list to load, and take a screenshot"

"Open Twitter, scroll down 3 times to load more tweets, then read the localStorage"

"Go to my bank's login page, wait for me to log in manually, then extract the session cookie"

"Navigate to an e-commerce site, search for 'laptop', scroll to load more products, and capture a full-page screenshot"
```

## License

MIT - See LICENSE file
