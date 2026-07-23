# Security Constraints

> **Navigation**: [Back to index](../SKILL.md) • [API Reference](api.md) • [Events](events.md) • [Troubleshooting](troubleshooting.md)

---

## Hard rules for agents

These are **non-negotiable**. Violations can leak credentials, corrupt user profiles, or enable malicious automation.

---

### 1. Never automate authentication

| ❌ Forbidden | ✅ Required |
|--------------|-------------|
| `type` password/2FA into login forms | Human types credentials in real Chrome window |
| `eval` to fill credentials via `input.value = ...` | Use `wait-for-auth` to detect login completion |
| Extract session cookies for reuse | Read cookies **only for current origin** (default) |

**Why**: The debug profile is separate from user's main profile. Automating login defeats the isolation boundary and stores credentials in skill-accessible memory.

**Correct flow**:
```bash
# 1. Navigate to login (SPA-aware)
uv run remote-chrome navigate "https://accounts.google.com/" --wait-for-selector "input[type=email]"

# 2. Human types credentials in the visible Chrome window

# 3. Wait for auth cookie (default: SID on .google.com)
uv run remote-chrome wait-for-auth --cookie-name SID --cookie-domain .google.com --timeout 300

# 4. Read cookies for current page only (safe default)
uv run remote-chrome cookies
# Or explicit domain if needed
uv run remote-chrome cookies --domain google.com
```

---

### 2. Redact sensitive cookie values

| ❌ Forbidden | ✅ Required |
|--------------|-------------|
| Output full cookie JSON with values in chat/logs | Summarize: `{"count": 12, "names": ["SID", "HSID", "SSID"]}` |
| Store cookie values in skill-accessible files | If value must be transmitted: `value=<REDACTED>` |

```bash
# Safe: count + names only
uv run remote-chrome cookies | jq '{count: .cookies|length, names: .cookies|map(.name)}'

# Unsafe: full values
uv run remote-chrome cookies  # <-- never paste this output to chat
```

---

### 3. `kill-chrome` is selective but use sparingly

```bash
# Only kills processes with --remote-debugging-port=9222 in command line
uv run remote-chrome kill-chrome
```

**Guarantees**:
- Your main browsing Chrome (no debug port) **never** killed
- Only the debug profile instance (`C:\temp\chrome-debug-profile`) affected

**Still**: Debug profile tabs may have unsaved work. Use when stuck, not routinely.

---

### 4. `eval` restrictions

| ❌ Forbidden | ✅ Allowed |
|--------------|------------|
| Inject untrusted code from user input/external source | Read-only DOM queries, data extraction |
| Call `fetch` to exfiltrate data | Async polling for DOM stability |
| Modify page state (click, navigate, form submit) via `eval` | `JSON.stringify({url: location.href, title: document.title})` |
| Access `localStorage`/`sessionStorage` of other origins | `localStorage` of **current origin only** (enforced by browser) |

**Default `eval` is read-friendly**: `awaitPromise=true` enables async patterns, but browser same-origin policy still applies.

---

### 5. Debug profile isolation (by design)

| Property | Value |
|----------|-------|
| Profile directory | `C:\temp\chrome-debug-profile` (fixed) |
| User data dir | **Never** override via `--user-data-dir` |
| Login state | **Not shared** with user's main Chrome |
| Extensions | None by default (clean profile) |

**Agent must not** attempt to point `start-chrome` at user's real profile. This would:
1. Corrupt the real profile (two Chrome instances same dir)
2. Expose all user cookies/extensions/history to automation

---

### 6. Network access scope

| Scope | Description |
|-------|-------------|
| CDP port | `9222` on Windows → proxied to `9223` on WSL host |
| Firewall | Only inbound TCP 9223 from WSL subnet (via bootstrap) |
| Chrome bindings | `127.0.0.1:9222` only (no external exposure) |

**Never** modify `netsh portproxy` to bind `0.0.0.0:9222` directly — exposes CDP to LAN.

---

### 7. File system access

| Path | Access | Notes |
|------|--------|-------|
| `C:\temp\chrome-debug-profile\Default\Preferences` | Read-only (download dir) | `get-download-dir` only |
| `/tmp/remote-chrome-events-*.jsonl` | Write (event daemon) | Auto-cleaned on daemon stop |
| Skill directory | Read (scripts, references) | No write by CLI |

**No arbitrary file read/write** via CLI. `eval` cannot escape browser sandbox.

---

## Security checklist for skill updates

When adding features, verify:

- [ ] No new CLI command writes secrets to stdout/stderr
- [ ] No `eval` enhancement bypasses same-origin policy
- [ ] No command accepts raw code from untrusted input
- [ ] Cookie/output redaction preserved
- [ ] `kill-chrome` selector unchanged (port 9222 only)
- [ ] Windows bootstrap doesn't widen firewall/portproxy
- [ ] Documentation updated with security implications

---

## Threat model summary

| Asset | Threat | Mitigation |
|-------|--------|------------|
| User's main Chrome profile | Corruption via shared `--user-data-dir` | Fixed debug profile path; no override |
| Auth cookies/session tokens | Leakage via skill output | Default origin-only cookies; redaction |
| Credentials | Automated entry | Human-only login flow; `wait-for-auth` |
| CDP endpoint | LAN exposure | Portproxy 9223→9222; firewall restricts to WSL subnet |
| Arbitrary code exec | `eval` with untrusted input | Same-origin policy; no file/OS access from JS |
| User data | Profile pollution | Debug profile isolated at `C:\temp\chrome-debug-profile` |

---

## Reporting security issues

Email: **security@v587d.example.com** (or GitHub Security Advisory)

Do **not** file public issues for:
- Cookie/session leakage
- Profile corruption vectors
- CDP exposure misconfiguration
- `eval` sandbox escapes