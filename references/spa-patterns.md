# SPA Handling Patterns

> **Navigation**: [Back to index](../SKILL.md) • [API Reference](api.md) • [Events](events.md) • [Troubleshooting](troubleshooting.md)

---

## The problem

Modern SPAs (X/Twitter, Reddit, React/Vue apps, e-commerce) have a **render phase after `document.readyState === 'complete'`**. The initial HTML is a shell; content loads via JS and renders later.

Standard `navigate` waits for `readyState === 'complete'` — **too early for SPAs**.

---

## Solution 1: `--wait-for-selector` (most reliable)

Wait for a content-bearing element to appear in DOM.

```bash
# X/Twitter - wait for tweet articles
uv run remote-chrome navigate "https://x.com/" --wait-for-selector "article[data-testid='tweet']"

# Reddit - wait for post listings
uv run remote-chrome navigate "https://reddit.com/r/programming" --wait-for-selector "shreddit-post"

# Generic - wait for main content container
uv run remote-chrome navigate "https://app.example.com" --wait-for-selector "main, [role=main], #content, .content"
```

**How it works**: Polls `document.querySelector(selector)` every 300ms until found or timeout.

---

## Solution 2: `--wait-for-title` (when title changes on route)

```bash
# X/Twitter home timeline
uv run remote-chrome navigate "https://x.com/home" --wait-for-title "Home"

# React Router app with title per route
uv run remote-chrome navigate "https://app.example.com/dashboard" --wait-for-title "Dashboard"
```

**How it works**: Polls `document.title` against regex every 300ms.

---

## Solution 3: `wait-for-navigation` (after user action)

Use when you **don't control the navigation** (user clicked, form submitted, SPA route change).

```bash
# Click a link that triggers SPA route change
uv run remote-chrome click "a[href='/dashboard']"
uv run remote-chrome wait-for-navigation --url-contains "/dashboard" --timeout 30

# Form submit
uv run remote-chrome click "#submit-btn"
uv run remote-chrome wait-for-navigation --url-contains "/success" --timeout 30
```

**How it works**: Establishes baseline `location.href` via `Runtime.evaluate`, then polls until URL changes or contains substring. **Uses real-time JS baseline, not HTTP `/json` tab.url** (which lags for SPAs).

---

## Solution 4: Async eval polling (DOM stability)

For "wait until content stops changing" — e.g., infinite scroll, virtual lists, lazy images.

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

**Why this works**: Runs entirely in-browser, no CLI round-trip latency between polls. Default `awaitPromise=true` means the async IIFE resolves before returning.

**Adapt for your selector**:
```js
const n = document.querySelectorAll('your-selector').length;
// or
const n = document.querySelectorAll('[data-testid="item"]').length;
```

---

## Scrolling to trigger lazy-render / virtual lists

### Use `--method=wheel` (default) — REQUIRED for virtual lists

```bash
uv run remote-chrome scroll --dy 1500 --wait-ms 500
```

**Why**: Dispatches real `Input.dispatchMouseEvent(mouseWheel)` at viewport center. Virtual lists (X, Reddit, TanStack Virtual) listen for **wheel events**, not just scroll position. `window.scrollBy` (`--method=js`) **won't trigger** them.

### Scroll element instead of window

```bash
# Virtual list inside a container
uv run remote-chrome scroll --selector ".virtual-list" --dy 1000 --method=js --wait-ms 300
```

---

## Combining patterns: robust SPA workflow

```bash
# 1. Navigate + wait for shell
uv run remote-chrome navigate "https://x.com/home" --wait-for-title "Home"

# 2. Wait for first batch of content
uv run remote-chrome eval "(async () => {
  for (let i = 0; i < 20; i++) {
    if (document.querySelectorAll('article').length > 0) return {ready: true};
    await new Promise(r => setTimeout(r, 200));
  }
  return {ready: false};
})()"

# 3. Scroll to trigger more (wheel method!)
uv run remote-chrome scroll --dy 2000 --wait-ms 800

# 4. Poll for DOM stability (new tweets settled)
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

# 5. Now extract / screenshot
uv run remote-chrome eval "Array.from(document.querySelectorAll('article')).map(a => a.innerText).join('|||')"
uv run remote-chrome screenshot --full-page --format png
```

---

## Pattern selection guide

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Known content selector exists | `--wait-for-selector` | Most reliable, fails fast if selector wrong |
| Title changes on route | `--wait-for-title` | Simple, no selector needed |
| User clicks / form submits | `wait-for-navigation` | Doesn't require knowing target URL upfront |
| Infinite scroll / virtual list | Async eval polling | Runs in-browser, no latency, detects "settled" |
| Trigger lazy content | `scroll --method=wheel` | Only wheel events trigger IntersectionObserver |

---

## Common SPA selectors cheat sheet

| Site | Content selector | Title pattern |
|------|------------------|---------------|
| X/Twitter | `article[data-testid='tweet']` | `/Home/` |
| Reddit (new) | `shreddit-post` | `/r\/\w+/` |
| Reddit (old) | `.thing.link` | `/reddit/` |
| GitHub | `.js-repo-root`, `#readme` | `/GitHub/` |
| LinkedIn | `.feed-shared-update-v2` | `/LinkedIn/` |
| YouTube | `ytd-rich-item-renderer` | `/YouTube/` |
| Generic React | `[data-testid]`, `.MuiContainer-root` | — |
| Generic Vue | `.v-application`, `#app > *` | — |

---

## Timeout guidelines

| Operation | Recommended timeout |
|-----------|---------------------|
| `--wait-for-selector` | 15-30s (default 15) |
| `--wait-for-title` | 15-30s |
| `wait-for-navigation` | 30-60s (default 300) |
| Async eval polling | 30-60s (via `--timeout-ms` on `eval`) |
| Scroll + wait | `--wait-ms 500-1000` per scroll |

---

## Debugging "element not found" on SPA

```bash
# 1. Screenshot immediately after navigate (see actual state)
uv run remote-chrome navigate "https://spa.example.com" --wait-for-selector "body"
uv run remote-chrome screenshot --full-page --format jpeg --quality 60

# 2. Check readyState + URL via eval
uv run remote-chrome eval "JSON.stringify({rs: document.readyState, url: location.href, title: document.title})"

# 3. Dump all visible text to understand structure
uv run remote-chrome eval "document.body.innerText.slice(0, 2000)"
```

---

## See also

- [API Reference → navigate](api.md#navigate)
- [API Reference → wait-for-navigation](api.md#wait-for-navigation)
- [API Reference → eval](api.md#eval)
- [API Reference → scroll](api.md#scroll)
- [Events](events.md) — subscribe to `DOM.childNodeInserted` for mutation-driven waits