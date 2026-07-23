# CDP Event Subscription — Deep Dive

> **Navigation**: [Back to index](../SKILL.md) • [API Reference](api.md) • [SPA Patterns](spa-patterns.md) • [Troubleshooting](troubleshooting.md)

---

## How it works

```
uv run remote-chrome event subscribe --event-types "Runtime.*" --timeout 300
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Spawns background daemon (subprocess, detached session)    │
│  1. Connects to page WebSocket (from active tab)            │
│  2. Enables required CDP domains (Runtime.enable, etc.)     │
│  3. Listens for events matching your types                  │
│  4. Writes JSONL to /tmp/remote-chrome-events-<port>.jsonl  │
│  5. Exits on timeout or SIGTERM (unsubscribe)               │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
uv run remote-chrome event poll [--clear]   # Read (and optionally clear) events
```

---

## Supported event types (with wildcard expansion)

### Runtime
| Event | Description | Key params |
|-------|-------------|------------|
| `Runtime.consoleAPICalled` | `console.log/error/warn/info/debug/trace` | `type`, `args[]`, `executionContextId`, `timestamp` |
| `Runtime.exceptionThrown` | Uncaught JS exception | `exceptionDetails` (text, line, column, stackTrace) |
| `Runtime.executionContextCreated` | New context (iframe, worker) | `context` (id, origin, name) |
| `Runtime.executionContextDestroyed` | Context destroyed | `executionContextId` |
| `Runtime.executionContextsCleared` | All contexts cleared | — |
| `Runtime.inspectRequested` | DevTools "Inspect" | `objectId`, `hints` |

### Page
| Event | Description | Key params |
|-------|-------------|------------|
| `Page.loadEventFired` | `window.onload` fired | `timestamp` |
| `Page.domContentEventFired` | `DOMContentLoaded` | `timestamp` |
| `Page.frameNavigated` | Frame navigation (SPA routes!) | `frame` (id, url, name, parentId) |
| `Page.frameStartedLoading` | Frame started loading | `frameId` |
| `Page.frameStoppedLoading` | Frame stopped loading | `frameId` |
| `Page.javascriptDialogOpening` | `alert/confirm/prompt` | `type`, `message`, `defaultPrompt` |
| `Page.windowOpen` | `window.open()` | `url`, `windowName`, `windowFeatures` |
| `Page.lifecycleEvent` | Page lifecycle | `frameId`, `loaderId`, `name` (init, ready, etc.) |

### Network
| Event | Description | Key params |
|-------|-------------|------------|
| `Network.requestWillBeSent` | Request about to send | `request` (url, method, headers), `frameId`, `initiator` |
| `Network.responseReceived` | Response headers received | `response` (url, status, headers, mimeType), `frameId` |
| `Network.loadingFinished` | Body fully received | `requestId`, `encodedDataLength` |
| `Network.loadingFailed` | Load failed | `requestId`, `errorText`, `canceled` |
| `Network.requestServedFromCache` | Served from cache | `requestId` |
| `Network.webSocketCreated` | WebSocket handshake | `requestId`, `url` |

### DOM
| Event | Description | Key params |
|-------|-------------|------------|
| `DOM.attributeModified` | Element attribute changed | `nodeId`, `name`, `value` |
| `DOM.attributeRemoved` | Attribute removed | `nodeId`, `name` |
| `DOM.childNodeInserted` | Node inserted | `parentNodeId`, `previousNodeId`, `node` |
| `DOM.childNodeRemoved` | Node removed | `parentNodeId`, `nodeId` |
| `DOM.characterDataModified` | Text node changed | `nodeId`, `characterData` |
| `DOM.documentUpdated` | Document updated | — |
| `DOM.setChildNodes` | Children replaced | `parentNodeId`, `nodes[]` |

### Log
| Event | Description | Key params |
|-------|-------------|------------|
| `Log.entryAdded` | Console/violation entry | `entry` (source, level, text, url, lineNumber) |

### Overlay
| Event | Description | Key params |
|-------|-------------|------------|
| `Overlay.inspectNodeRequested` | DevTools inspect | `nodeId`, `backendNodeId` |

---

## Wildcard syntax

```bash
# All Runtime events
--event-types "Runtime.*"

# All Network events
--event-types "Network.*"

# Multiple wildcards
--event-types "Runtime.*,Page.*,Network.requestWillBeSent"

# Mix specific + wildcard
--event-types "Runtime.consoleAPICalled,Runtime.exceptionThrown,Network.*"
```

**Expansion happens at subscribe time** — daemon enables only the domains needed for matched events.

---

## Event output format (JSONL)

Each line in `/tmp/remote-chrome-events-<port>.jsonl`:

```json
{
  "timestamp": 1718500001.234567,
  "method": "Runtime.consoleAPICalled",
  "params": {
    "type": "error",
    "args": [
      {"type": "string", "value": "Failed to fetch"},
      {"type": "object", "value": {"message": "NetworkError"}}
    ],
    "executionContextId": 1,
    "timestamp": 1718500001234.56
  }
}
```

```json
{
  "timestamp": 1718500002.111,
  "method": "Network.requestWillBeSent",
  "params": {
    "requestId": "abc123",
    "frameId": "frame1",
    "request": {
      "url": "https://api.example.com/users",
      "method": "GET",
      "headers": {"Authorization": "Bearer ..."}
    },
    "initiator": {"type": "script", "stackTrace": {...}}
  }
}
```

```json
{
  "timestamp": 1718500003.999,
  "method": "Page.frameNavigated",
  "params": {
    "frame": {
      "id": "frame1",
      "loaderId": "loader456",
      "url": "https://spa.example.com/dashboard",
      "name": "",
      "parentId": "frame0"
    }
  }
}
```

---

## Common patterns

### 1. Debug console errors
```bash
uv run remote-chrome event subscribe --event-types "Runtime.consoleAPICalled,Runtime.exceptionThrown" --timeout 300
# ... navigate, interact ...
uv run remote-chrome event poll --clear
# Filter for type:"error" or exceptionThrown
uv run remote-chrome event unsubscribe
```

### 2. Track SPA navigation (no full reload)
```bash
uv run remote-chrome event subscribe --event-types "Page.frameNavigated" --timeout 600
# ... click SPA links ...
uv run remote-chrome event poll --clear
# Each frameNavigated = route change
uv run remote-chrome event unsubscribe
```

### 3. Monitor API calls
```bash
uv run remote-chrome event subscribe --event-types "Network.requestWillBeSent,Network.responseReceived" --timeout 300
# ... click search button ...
uv run remote-chrome event poll --clear
# Match request/response by requestId
uv run remote-chrome event unsubscribe
```

### 4. Detect DOM mutations
```bash
uv run remote-chrome event subscribe --event-types "DOM.childNodeInserted,DOM.attributeModified" --timeout 300
# ... click "Load more" ...
uv run remote-chrome event poll --clear
# Watch for inserted nodes / attribute changes
uv run remote-chrome event unsubscribe
```

### 5. Catch all "something happened" for debugging
```bash
uv run remote-chrome event subscribe --event-types "Runtime.*,Page.*,Network.*" --timeout 600
# ... complex flow ...
uv run remote-chrome event poll --clear
# Large dump — filter programmatically
uv run remote-chrome event unsubscribe
```

---

## Daemon lifecycle

| State | Trigger |
|-------|---------|
| **Starting** | `event subscribe` → spawns subprocess, writes PID file |
| **Running** | WebSocket open, domains enabled, filtering events |
| **Auto-stop** | `--timeout` seconds elapsed (default 300; 0 = no timeout) |
| **Manual stop** | `event unsubscribe` → SIGTERM → SIGKILL if needed |
| **Crash** | PID file missing on poll → `daemon exited immediately` |

**Per-port singleton**: Only one daemon per Chrome debug port. New `subscribe` kills old daemon automatically.

---

## Polling strategies

| Strategy | Command | Use when |
|----------|---------|----------|
| **Consume** | `event poll --clear` | Process events once, don't re-read |
| **Peek** | `event poll` | Check what happened, keep for later |
| **Clear only** | `event clear` | Reset buffer without reading |

**Recommendation**: Use `--clear` in automation loops to avoid duplicate processing.

---

## Programmatic filtering (jq examples)

```bash
# Only console errors
uv run remote-chrome event poll --clear | jq 'select(.method=="Runtime.consoleAPICalled" and .params.type=="error")'

# Only failed network requests
uv run remote-chrome event poll --clear | jq 'select(.method=="Network.loadingFailed")'

# Only frame navigations (SPA routes)
uv run remote-chrome event poll --clear | jq 'select(.method=="Page.frameNavigated") | .params.frame.url'

# Exception stack traces
uv run remote-chrome event poll --clear | jq 'select(.method=="Runtime.exceptionThrown") | .params.exceptionDetails.stackTrace'
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `daemon exited immediately` | No page tabs open, or active tab is `chrome://` | `navigate` to real page first |
| `poll` returns empty but daemon running | Events don't match subscribed types | Check spelling; try `Runtime.*` |
| `subscribe` warns "Unknown event type" | Typo in event name | See table above; wildcards: `Runtime.*` |
| Events missing `params` | CDP domain not enabled | Ensure event type matches enabled domain |
| Daemon dies before timeout | Tab closed / navigated to internal page | Re-subscribe after navigation |

---

## Limits

- **File-based**: Events written to `/tmp/remote-chrome-events-<port>.jsonl` — survives agent restarts but not reboots
- **No real-time push**: Polling only; for streaming, use `event poll --clear` in a loop
- **One daemon per port**: Multiple skills sharing port will conflict
- **Timeout max**: Practical limit ~1 hour (daemon memory grows with event buffer)

---

## See also

- [API Reference](api.md) — `event` command syntax
- [SPA Patterns](spa-patterns.md) — Using events for SPA route tracking
- [Troubleshooting](troubleshooting.md) — Event-related issues