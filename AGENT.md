# AGENT.md — remote-chrome-skill

Guidance for AI coding agents (e.g. Pi) working in this repository.

## What this project is

`remote-chrome-skill` controls a **real Chrome browser running on Windows** from
**WSL/Linux** over the Chrome DevTools Protocol (CDP). It ships as an AI-agent
skill (OpenCode/Pi) with a CLI (`remote-chrome`) backed by an async Python CDP
client. Every subcommand emits JSON on stdout so agents can parse results
reliably; human-facing errors go to stderr.

- Repo: src layout, `src/remote_chrome/`
- Language: Python **>=3.10**
- Runtime deps: `websockets>=13`
- Dev deps: `mypy>=2.3.0` (for type checking)

User/agent-facing docs: `SKILL.md` (entry point), `README.md`, and the
progressive-disclosure `references/` (`api.md`, `architecture.md`, `events.md`,
`security.md`, `spa-patterns.md`, `troubleshooting.md`).

## Architecture in one paragraph

```
WSL -> Windows-host IP:9223 -> netsh portproxy -> 127.0.0.1:9222 -> Chrome CDP
```

**CDP routing rule (important when editing `client.py`):**
- Browser-level methods (`Target.*`, `Browser.*`) → the `/devtools/browser`
  WebSocket (discovered via `/json/version`).
- Page-level methods (`Page.*`, `Runtime.*`, `Network.*`, `Input.*`) → a
  `/devtools/page/<id>` WebSocket (from the `/json` tab list).

Each page-level call opens a **fresh per-call WebSocket** with a 30s default
`recv` timeout so an awaited Promise that never resolves cannot hang the client.

## Repository layout

| Path | Role |
|------|------|
| `src/remote_chrome/client.py` | Async CDP client (`RemoteChrome`). Core logic. **Must stay fully type-annotated.** |
| `src/remote_chrome/cli.py` | `argparse` CLI. Each subcommand is a `_cmd_*` coroutine returning a JSON-serializable dict. |
| `src/remote_chrome/events.py` | CDP event subscription: a background daemon subprocess writes events as JSONL; poll/unsubscribe read it. |
| `src/remote_chrome/bootstrap.py` | Generates the one-time Windows PowerShell setup script (no execution on Windows). |
| `tests/test_smoke.py` | Smoke tests (mock mode by default; live mode optional). |
| `pyproject.toml` | Packaging + `[tool.mypy]` config. |
| `SKILL.md`, `README.md`, `references/` | Documentation (not code). |

## Common commands

Set up (creates `.venv`):
```bash
uv sync
```

Run the CLI (every command returns JSON on stdout):
```bash
uv run remote-chrome status
uv run remote-chrome navigate "https://example.com" --wait-for-selector "body"
uv run remote-chrome screenshot --format png
# or, without uv:
.venv/bin/python -m remote_chrome.cli <command> ...
```

Run tests (mock mode is the default and needs no Chrome):
```bash
uv run pytest tests/test_smoke.py -v
# live mode against a real Chrome debug instance:
REMOTE_CHROME_TEST_MODE=live uv run pytest tests/test_smoke.py -v
```

Type check (this must stay green — see conventions):
```bash
uv run mypy src/remote_chrome/client.py src/remote_chrome/cli.py
# or across the whole package:
uv run mypy src/remote_chrome
```

## Code conventions

### Typing (enforced by `mypy`)
`pyproject.toml` defines a strict-ish `[tool.mypy]` profile:
`disallow_untyped_defs`, `disallow_incomplete_defs`, `disallow_any_generics`,
`no_implicit_optional`, `check_untyped_defs`, `warn_unused_ignores`.

- **`client.py` and `cli.py` must be fully annotated** — no bare `dict`/`list`/
  `tuple`/`set` generics (write `dict[str, Any]`, `list[Tab]`, etc.), and every
  function needs a return type.
- `cli.py` command handlers follow the established shape:
  `async def _cmd_x(rc: RemoteChrome, args: argparse.Namespace) -> dict[str, Any]`.
  The `CommandHandler` type alias and the `HANDLERS: dict[str, CommandHandler]`
  registry codify this.
- `events.py` and `bootstrap.py` are intentionally **excluded** from the strict
  generic check via a `[[tool.mypy.overrides]]` block (`disallow_any_generics =
  false`). Do not tighten those without explicitly expanding scope.
- Prefer `from __future__ import annotations` (already present in `client.py`/
  `cli.py`) so forward references and `X | None` syntax work on 3.10.

### Adding a new CLI command
1. Add the `argparse` subparser in `build_parser()`.
2. Add an async handler `async def _cmd_<name>(rc: RemoteChrome, args: argparse.Namespace) -> dict[str, Any]:`.
3. Register it in the `HANDLERS` dict.
4. Return a JSON-serializable dict (the CLI prints it with `_output_json`).
5. Keep behavior changes testable; prefer adding a mock-mode test in `tests/test_smoke.py`.

### Error handling
Raise the specific `RemoteChromeError` subclasses (`ChromeNotRunningError`,
`TabNotFoundError`, `ElementNotFoundError`, `NavigationTimeoutError`,
`AuthTimeoutError`, `CdpTimeoutError`). The CLI maps each to a distinct
JSON `error` code and exit status in `main()`. Do not let raw tracebacks reach
stdout (they would break agent JSON parsing).

## Things to watch
- `client.py::_network_url_filter` / `_network_resource_types` are instance
  attributes initialized in `__init__` (typed `str | None` / `set[str] | None`).
- `events.py` spawns a detached subprocess (`start_new_session=True`); it writes
  PID/JSONL under `/tmp/remote-chrome-events-<port>.*`.
- Windows/PowerShell paths and `C:\temp\chrome-debug-profile` are constants
  (`CHROME_EXE`, `DEBUG_PROFILE_DIR`); the debug profile's download dir is read
  from its `Preferences` JSON, not over CDP.
- Security posture: no password automation, cookie redaction, selective Chrome
  kill (only the `--remote-debugging-port=9222` instance). See `references/security.md`.
