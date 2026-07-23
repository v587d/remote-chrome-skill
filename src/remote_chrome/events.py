"""CDP Event subscription and polling.

This module provides event-driven monitoring of Chrome DevTools Protocol 
events. It supports persistent event listeners that run as background 
daemon processes, writing events to a file for later retrieval.

Architecture:
  CLI "event subscribe" spawns a daemon subprocess that:
    1. Connects to Chrome CDP via WebSocket (page-level WS)
    2. Enables the required CDP domains for the subscribed events
    3. Listens for matching events and writes them as JSONL to a temp file
    4. Exits on SIGTERM/SIGINT or after a configurable timeout

  CLI "event poll" reads the JSONL file; "event unsubscribe" kills the daemon.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event type -> (CDP domain, enable method) mapping
# ---------------------------------------------------------------------------

EVENT_DOMAIN_MAP: dict[str, tuple[str, str]] = {
    # Runtime domain
    "Runtime.consoleAPICalled":       ("Runtime", "Runtime.enable"),
    "Runtime.exceptionThrown":        ("Runtime", "Runtime.enable"),
    "Runtime.executionContextCreated": ("Runtime", "Runtime.enable"),
    "Runtime.executionContextDestroyed": ("Runtime", "Runtime.enable"),
    "Runtime.executionContextsCleared": ("Runtime", "Runtime.enable"),
    "Runtime.inspectRequested":       ("Runtime", "Runtime.enable"),
    # Page domain
    "Page.loadEventFired":            ("Page", "Page.enable"),
    "Page.domContentEventFired":      ("Page", "Page.enable"),
    "Page.frameNavigated":            ("Page", "Page.enable"),
    "Page.frameStartedLoading":       ("Page", "Page.enable"),
    "Page.frameStoppedLoading":       ("Page", "Page.enable"),
    "Page.javascriptDialogOpening":   ("Page", "Page.enable"),
    "Page.windowOpen":                ("Page", "Page.enable"),
    "Page.lifecycleEvent":            ("Page", "Page.enable"),
    # DOM domain
    "DOM.attributeModified":          ("DOM", "DOM.enable"),
    "DOM.attributeRemoved":           ("DOM", "DOM.enable"),
    "DOM.childNodeInserted":          ("DOM", "DOM.enable"),
    "DOM.childNodeRemoved":           ("DOM", "DOM.enable"),
    "DOM.characterDataModified":      ("DOM", "DOM.enable"),
    "DOM.documentUpdated":            ("DOM", "DOM.enable"),
    "DOM.setChildNodes":              ("DOM", "DOM.enable"),
    # Network domain
    "Network.requestWillBeSent":      ("Network", "Network.enable"),
    "Network.responseReceived":       ("Network", "Network.enable"),
    "Network.loadingFinished":        ("Network", "Network.enable"),
    "Network.loadingFailed":          ("Network", "Network.enable"),
    "Network.requestServedFromCache": ("Network", "Network.enable"),
    "Network.webSocketCreated":       ("Network", "Network.enable"),
    # Log domain
    "Log.entryAdded":                 ("Log", "Log.enable"),
    # Overlay domain
    "Overlay.inspectNodeRequested":   ("Overlay", "Overlay.enable"),
}


def get_unique_domains(event_types: list[str]) -> set[str]:
    """Determine which CDP domains need to be enabled for given event types."""
    domains: set[str] = set()
    for et in event_types:
        if et in EVENT_DOMAIN_MAP:
            domains.add(EVENT_DOMAIN_MAP[et][1])  # the enable method
        else:
            # Wildcard: enable all domains that start with the prefix
            prefix = et.replace(".*", ".")
            for event_name, (_, enable_method) in EVENT_DOMAIN_MAP.items():
                if event_name.startswith(prefix):
                    domains.add(enable_method)
    return domains


# ---------------------------------------------------------------------------
# File paths for daemon state
# ---------------------------------------------------------------------------

def _events_file(port: int) -> str:
    return f"/tmp/remote-chrome-events-{port}.jsonl"


def _pid_file(port: int) -> str:
    return f"/tmp/remote-chrome-events-{port}.pid"


# ---------------------------------------------------------------------------
# Event daemon (runs as a subprocess)
# ---------------------------------------------------------------------------

async def _run_event_daemon(
    host: str,
    port: int,
    tab_ws_url: str,
    event_types: list[str],
    timeout: float,
) -> None:
    """Core daemon logic: connect to CDP, enable domains, collect events.

    Writes each event as a JSON line to the events file.
    This function is designed to run in a subprocess spawned by 
    `event subscribe`.
    """
    events_path = _events_file(port)
    pid_path = _pid_file(port)

    # Write PID file
    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))

    logger.info(
        "Event daemon PID %d started: host=%s port=%s types=%s timeout=%s",
        os.getpid(), host, port, event_types, timeout,
    )

    try:
        import websockets
    except ImportError:
        logger.error("websockets not installed; cannot run event daemon")
        return

    # Determine which domains to enable
    enable_methods = get_unique_domains(event_types)
    logger.info("Will enable domains: %s", enable_methods)

    deadline = time.monotonic() + timeout if timeout > 0 else float("inf")

    try:
        async with websockets.connect(tab_ws_url, max_size=10 * 1024 * 1024) as ws:
            cmd_id = 0

            # Enable each required domain
            for method in enable_methods:
                cmd_id += 1
                await ws.send(json.dumps({"id": cmd_id, "method": method}))
                # Read back the enable response
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    resp = json.loads(raw)
                    if resp.get("id") == cmd_id:
                        err = resp.get("error")
                        if err:
                            logger.warning(
                                "Failed to enable domain via %s: %s",
                                method, err.get("message", err),
                            )
                        else:
                            logger.info("Enabled domain: %s", method)
                        break

            logger.info("Daemon ready, listening for events...")

            # Main event loop: read events and write to file
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        ws.recv(),
                        timeout=1.0,  # short poll so we can check deadline
                    )
                except asyncio.TimeoutError:
                    continue

                msg = json.loads(raw)

                # Skip CDP command responses (have an "id" field)
                if "id" in msg:
                    continue

                # This is an event message: {"method": "...", "params": {...}}
                method = msg.get("method", "")

                # Check if this event matches any subscribed type
                matched = False
                for et in event_types:
                    if et == method:
                        matched = True
                        break
                    if et.endswith(".*"):
                        prefix = et[:-2]  # strip .*
                        if method.startswith(prefix):
                            matched = True
                            break

                if not matched:
                    continue

                # Write event to file
                event_record = {
                    "timestamp": time.time(),
                    "method": method,
                    "params": msg.get("params", {}),
                }
                try:
                    with open(events_path, "a") as f:
                        f.write(json.dumps(event_record, default=str) + "\n")
                except OSError as exc:
                    logger.error("Failed to write event: %s", exc)

    except asyncio.CancelledError:
        logger.info("Daemon cancelled")
    except Exception as exc:
        logger.error("Daemon error: %s", exc)
    finally:
        # Clean up PID file
        try:
            os.remove(pid_path)
        except OSError:
            pass
        logger.info("Event daemon PID %d exiting", os.getpid())


# ---------------------------------------------------------------------------
# Client-side management (called from RemoteChrome)
# ---------------------------------------------------------------------------

def start_event_daemon(
    host: str,
    port: int,
    tab_ws_url: str,
    event_types: list[str],
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Spawn the event daemon as a background subprocess.

    Args:
        host: Chrome CDP host IP
        port: Chrome CDP port
        tab_ws_url: WebSocket URL for the target tab
        event_types: List of CDP event method names to subscribe to
        timeout: Maximum seconds to listen (0 = no timeout / indefinite)

    Returns:
        Dict with daemon status and PID.
    """
    events_path = _events_file(port)
    pid_path = _pid_file(port)

    # Kill any existing daemon for this port
    _kill_daemon(port)

    # Truncate old events file
    with open(events_path, "w") as f:
        pass

    # Determine the project root (parent of this module's package)
    # src/remote_chrome/events.py -> src/ -> project root
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    src_dir = os.path.join(project_root, "src")

    # Build a robust daemon launcher script
    daemon_code = (
        "import sys, os, json, asyncio\n"
        + f"sys.path.insert(0, {json.dumps(src_dir)})\n"
        + "from remote_chrome.events import _run_event_daemon\n"
        + f"params = json.loads({json.dumps(json.dumps({
            'host': host,
            'port': port,
            'tab_ws_url': tab_ws_url,
            'event_types': event_types,
            'timeout': timeout,
        }))})\n"
        + "asyncio.run(_run_event_daemon(**params))"
    )

    cmd = [sys.executable, "-c", daemon_code]

    logger.info("Starting event daemon from project root: %s", project_root)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # detach from parent
        )
    except OSError as exc:
        return {
            "started": False,
            "error": f"Failed to spawn daemon: {exc}",
            "pid": None,
        }

    # Wait briefly for PID file to appear
    for _ in range(20):
        if os.path.exists(pid_path):
            try:
                with open(pid_path) as f:
                    daemon_pid = int(f.read().strip())
                return {
                    "started": True,
                    "pid": daemon_pid,
                    "events_file": events_path,
                    "subscribed_types": event_types,
                    "timeout": timeout,
                }
            except (ValueError, OSError):
                pass
        time.sleep(0.1)

    # PID file didn't appear; daemon may have failed
    proc.poll()
    if proc.returncode is not None:
        return {
            "started": False,
            "error": f"Daemon exited immediately with code {proc.returncode}",
            "pid": None,
        }

    return {
        "started": True,
        "pid": proc.pid,
        "events_file": events_path,
        "subscribed_types": event_types,
        "timeout": timeout,
        "warning": "PID file not found; daemon may not be fully initialized",
    }


def _kill_daemon(port: int) -> bool:
    """Kill any running event daemon for the given port.

    Returns True if a daemon was found and killed.
    """
    pid_path = _pid_file(port)

    # Try PID file first
    if os.path.exists(pid_path):
        try:
            with open(pid_path) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.2)
            # Force kill if still alive
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            return True
        except (ValueError, OSError):
            pass

    return False


def stop_event_daemon(port: int) -> dict[str, Any]:
    """Stop the event daemon and clean up.

    Returns status dict.
    """
    killed = _kill_daemon(port)

    # Clean up PID file
    pid_path = _pid_file(port)
    try:
        os.remove(pid_path)
    except OSError:
        pass

    return {
        "stopped": killed,
        "events_file": _events_file(port),
    }


def poll_events(port: int, clear: bool = False) -> dict[str, Any]:
    """Read accumulated events from the daemon's output file.

    Args:
        port: Chrome CDP port
        clear: If True, truncate the events file after reading

    Returns:
        Dict with events list and count.
    """
    events_path = _events_file(port)
    events: list[dict] = []

    if os.path.exists(events_path):
        try:
            with open(events_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except OSError as exc:
            return {"events": [], "count": 0, "error": str(exc)}

    if clear:
        try:
            with open(events_path, "w") as f:
                pass
        except OSError:
            pass

    return {
        "events": events,
        "count": len(events),
        "events_file": events_path,
    }


def clear_events(port: int) -> dict[str, Any]:
    """Truncate the events file without reading it.

    Returns status dict.
    """
    events_path = _events_file(port)
    try:
        with open(events_path, "w") as f:
            pass
        return {"cleared": True, "events_file": events_path}
    except OSError as exc:
        return {"cleared": False, "events_file": events_path, "error": str(exc)}


def is_daemon_running(port: int) -> bool:
    """Check if the event daemon is alive."""
    pid_path = _pid_file(port)
    if not os.path.exists(pid_path):
        return False
    try:
        with open(pid_path) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # test if process exists
        return True
    except (ValueError, OSError):
        return False
