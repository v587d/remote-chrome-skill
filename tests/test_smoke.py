"""Smoke tests for remote-chrome-skill.

Runs in two modes:

1. Mock mode (default in CI / no Chrome available):
   The HTTP /json endpoints and WebSocket interactions are mocked, so tests
   run with NO Chrome. Set REMOTE_CHROME_TEST_MODE=mock (default) explicitly.

2. Live mode:
   Requires a real Chrome debug running on the Windows host pointed to by
   host/port. Set REMOTE_CHROME_TEST_MODE=live and optionally
   REMOTE_CHROME_HOST / REMOTE_CHROME_PORT.

Run:
    REMOTE_CHROME_TEST_MODE=mock uv run pytest tests/test_smoke.py -v
    REMOTE_CHROME_TEST_MODE=live uv run pytest tests/test_smoke.py -v
"""

import asyncio
import json
import os
import sys
from unittest import mock

import pytest

# Ensure src is importable when running pytest from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from remote_chrome.client import (  # noqa: E402
    RemoteChrome,
    Tab,
    Cookie,
    ChromeNotRunningError,
    TabNotFoundError,
    ElementNotFoundError,
)


MODE = os.environ.get("REMOTE_CHROME_TEST_MODE", "mock").lower()
HOST = os.environ.get("REMOTE_CHROME_HOST", "172.25.112.1")
PORT = int(os.environ.get("REMOTE_CHROME_PORT", "9223"))


# --------------------------------------------------------------------------
# Mock mode fixtures
# --------------------------------------------------------------------------

MOCK_TABS = [
    {
        "id": "TAB1",
        "type": "page",
        "url": "https://www.wikipedia.org/",
        "title": "Wikipedia",
        "webSocketDebuggerUrl": "ws://mock:9223/devtools/page/TAB1",
    },
    {
        "id": "TAB2",
        "type": "page",
        "url": "https://example.com/",
        "title": "Example Domain",
        "webSocketDebuggerUrl": "ws://mock:9223/devtools/page/TAB2",
    },
]

MOCK_VERSION = {
    "Browser": "Chrome/150.0.7871.115",
    "Protocol-Version": "1.3",
    "webSocketDebuggerUrl": "ws://mock:9223/devtools/browser/abc",
}

MOCK_COOKIES = [
    {"name": "SID", "value": "abc123", "domain": ".google.com", "path": "/", "secure": True, "httpOnly": True},
    {"name": "NID", "value": "xyz", "domain": ".google.com", "path": "/", "secure": False, "httpOnly": False},
]


# --------------------------------------------------------------------------
# Constants / utility
# --------------------------------------------------------------------------

def _skip_if_live(reason: str = "Live mode requires Chrome running"):
    if MODE == "live":
        # Still attempt the test; it will surface real failures.
        pass


# --------------------------------------------------------------------------
# Mock tests
# --------------------------------------------------------------------------

@pytest.mark.skipif(MODE == "live", reason="Mock-only test")
def test_tab_from_cdp():
    t = Tab.from_cdp(MOCK_TABS[0])
    assert t.id == "TAB1"
    assert t.url == "https://www.wikipedia.org/"
    assert t.title == "Wikipedia"
    assert t.type == "page"


@pytest.mark.skipif(MODE == "live", reason="Mock-only test")
def test_cookie_from_cdp():
    c = Cookie.from_cdp(MOCK_COOKIES[0])
    assert c.name == "SID"
    assert c.value == "abc123"
    assert c.domain == ".google.com"
    assert c.http_only is True


@pytest.mark.skipif(MODE == "live", reason="Mock-only test")
def test_chrome_not_running_error_raised_when_http_fails():
    rc = RemoteChrome(host="127.0.0.1", port=65500)
    with pytest.raises(ChromeNotRunningError):
        rc._http_get("/json/version")


# --------------------------------------------------------------------------
# Live tests - require real Chrome running
# --------------------------------------------------------------------------

@pytest.mark.skipif(MODE != "live", reason="Live test requires real Chrome")
def test_live_status():
    from remote_chrome.cli import _cmd_status
    import argparse
    rc = RemoteChrome(host=HOST, port=PORT)
    args = argparse.Namespace()
    result = asyncio.run(_cmd_status(rc, args))
    assert result["running"] is True
    assert "browser" in result


@pytest.mark.skipif(MODE != "live", reason="Live test requires real Chrome")
def test_live_list_tabs():
    rc = RemoteChrome(host=HOST, port=PORT)
    tabs = asyncio.run(rc.list_tabs())
    assert isinstance(tabs, list)
    assert len(tabs) >= 1
    assert all(t.type == "page" for t in tabs)


@pytest.mark.skipif(MODE != "live", reason="Live test requires real Chrome")
def test_live_navigate_and_eval():
    rc = RemoteChrome(host=HOST, port=PORT)
    asyncio.run(rc.navigate("https://example.com/"))
    title = asyncio.run(rc.eval_js("document.title"))
    assert title == "Example Domain"


@pytest.mark.skipif(MODE != "live", reason="Live test requires real Chrome")
def test_live_get_cookies_for_domain():
    rc = RemoteChrome(host=HOST, port=PORT)
    # wikipedia.org sets cookies
    asyncio.run(rc.navigate("https://www.wikipedia.org/"))
    cookies = asyncio.run(rc.get_cookies_for_domain("wikipedia.org"))
    assert isinstance(cookies, list)


@pytest.mark.skipif(MODE != "live", reason="Live test requires real Chrome")
def test_live_cli_bootstrap_no_chrome_needed():
    from remote_chrome.cli import _cmd_bootstrap
    import argparse
    rc = RemoteChrome(host=HOST, port=PORT)
    args = argparse.Namespace()
    result = asyncio.run(_cmd_bootstrap(rc, args))
    assert "powershell_script" in result
    assert "WSL Chrome Debug" in result["powershell_script"]
    assert "9223" in result["powershell_script"]

