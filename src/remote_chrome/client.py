"""Core CDP client for remote-chrome-skill.

Architecture:
  WSL -> Windows-host IP:{port} -> netsh portproxy -> 127.0.0.1:9222 -> Chrome CDP

CDP routing rule:
  Browser-level methods (Target.*, Browser.*) -> /devtools/browser WS (from /json/version)
  Page-level methods (Page.*, Runtime.*, Network.*, Input.*) -> /devtools/page/<id> WS (from /json tab list)
"""

import asyncio
import json
import logging
import re
import shlex
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

import websockets

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class Tab:
    id: str
    url: str
    title: str
    type: str
    ws_url: str

    @classmethod
    def from_cdp(cls, d: dict) -> "Tab":
        return cls(
            id=d["id"],
            url=d.get("url", ""),
            title=d.get("title", ""),
            type=d.get("type", "page"),
            ws_url=d.get("webSocketDebuggerUrl", ""),
        )


@dataclass
class Cookie:
    name: str
    value: str
    domain: str
    path: str
    secure: bool
    http_only: bool
    same_site: str = ""

    @classmethod
    def from_cdp(cls, d: dict) -> "Cookie":
        return cls(
            name=d["name"],
            value=d.get("value", ""),
            domain=d.get("domain", ""),
            path=d.get("path", ""),
            secure=d.get("secure", False),
            http_only=d.get("httpOnly", False),
            same_site=d.get("sameSite", ""),
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RemoteChromeError(Exception):
    """Base error for the client."""


class ChromeNotRunningError(RemoteChromeError):
    """Chrome CDP endpoint is unreachable."""


class TabNotFoundError(RemoteChromeError):
    """No matching tab found."""


class ElementNotFoundError(RemoteChromeError):
    """CSS selector did not match any element."""


class NavigationTimeoutError(RemoteChromeError):
    """Page navigation or selector/title wait did not complete within the timeout."""


class AuthTimeoutError(RemoteChromeError):
    """Authentication cookie did not appear within the timeout."""


class CdpTimeoutError(RemoteChromeError):
    """CDP response (e.g. Runtime.evaluate awaiting a Promise) did not return in time."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class RemoteChrome:
    """Async client for Chrome DevTools Protocol over WebSocket."""

    def __init__(self, host: str = "172.25.112.1", port: int = 9223):
        self.host = host
        self.port = port
        self._http_base = f"http://{host}:{port}"
        self._browser_ws_url: str | None = None
        self._cmd_id: int = 0
        self._target_id: str | None = None
        self._chrome_process: subprocess.Popen | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Clean up resources on context exit."""
        await self.cleanup()

    async def cleanup(self) -> None:
        """Ensure all resources are properly released.
        
        This method:
        - Closes any tracked Chrome process started via this instance
        - Clears cached WebSocket URLs to force reconnection
        
        Safe to call multiple times.
        """
        if self._chrome_process is not None:
            try:
                self._chrome_process.terminate()
                try:
                    self._chrome_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._chrome_process.kill()
                    self._chrome_process.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                pass
            finally:
                self._chrome_process = None
        
        self._browser_ws_url = None

    # -- Internals ---------------------------------------------------------

    def _http_get(self, path: str) -> Any:
        url = f"{self._http_base}{path}"
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                return json.load(r)
        except (urllib.error.URLError, ConnectionRefusedError, OSError) as exc:
            raise ChromeNotRunningError(
                f"Cannot connect to Chrome CDP at {url}. "
                "Make sure Chrome is running with --remote-debugging-port=9222 "
                "and portproxy/firewall are configured."
            ) from exc

    def _ensure_browser_ws(self) -> str:
        if self._browser_ws_url is None:
            ver = self._http_get("/json/version")
            self._browser_ws_url = ver.get("webSocketDebuggerUrl", "")
            if not self._browser_ws_url:
                raise ChromeNotRunningError("No browser WS URL in /json/version")
        return self._browser_ws_url

    async def _cdp_send_browser(
        self, method: str, params: dict | None = None, *, timeout: float = 30.0
    ) -> dict:
        ws_url = self._ensure_browser_ws()
        self._cmd_id += 1
        cmd_id = self._cmd_id
        ws = None
        try:
            ws = await websockets.connect(ws_url, max_size=10 * 1024 * 1024)
            payload: dict[str, Any] = {"id": cmd_id, "method": method}
            if params:
                payload["params"] = params
            await ws.send(json.dumps(payload))
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError as exc:
                    raise CdpTimeoutError(
                        f"CDP response timeout after {timeout}s "
                        f"(method={method})"
                    ) from exc
                resp = json.loads(raw)
                if resp.get("id") == cmd_id:
                    err = resp.get("error")
                    if err:
                        raise RemoteChromeError(
                            f"CDP error: {err.get('message', err)} (method={method})"
                        )
                    return resp.get("result", {})
        finally:
            if ws is not None:
                await ws.close()

    async def _cdp_send_on_tab(
        self, tab: Tab, method: str, params: dict | None = None,
        *, timeout: float = 30.0,
    ) -> dict:
        """
        Send a page-level CDP command on a fresh per-call WebSocket.

        A 30s default recv timeout prevents hanging when an awaited Promise
        never resolves (e.g. an async eval that polls an element that never
        appears).
        """
        if not tab.ws_url:
            raise TabNotFoundError(
                f"Tab {tab.id} has no webSocketDebuggerUrl. "
                "It may be a chrome:// internal tab without CDP."
            )
        self._cmd_id += 1
        cmd_id = self._cmd_id
        ws = None
        try:
            ws = await websockets.connect(
                tab.ws_url, max_size=10 * 1024 * 1024
            )
            payload: dict[str, Any] = {"id": cmd_id, "method": method}
            if params:
                payload["params"] = params
            await ws.send(json.dumps(payload))
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError as exc:
                    raise CdpTimeoutError(
                        f"CDP response timeout after {timeout}s "
                        f"(method={method}, tab={tab.id[:8]}...)"
                    ) from exc
                resp = json.loads(raw)
                if resp.get("id") == cmd_id:
                    err = resp.get("error")
                    if err:
                        raise RemoteChromeError(
                            f"CDP error: {err.get('message', err)} (method={method})"
                        )
                    return resp.get("result", {})
        finally:
            if ws is not None:
                await ws.close()

    async def _eval_on_tab(
        self, tab: Tab, expression: str,
        *, await_promise: bool = False, timeout: float = 30.0,
    ) -> Any:
        """Low-level eval that returns the raw CDP result wrapper."""
        resp = await self._cdp_send_on_tab(
            tab, "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
            timeout=timeout,
        )
        return resp.get("result", {})

    async def _page_context(self, tab: Tab) -> dict:
        """Retrieve current URL + readyState for diagnostics. Best-effort."""
        try:
            raw = await self._eval_on_tab(
                tab,
                "JSON.stringify({url: location.href, rs: document.readyState})",
                timeout=5.0,
            )
            val = raw.get("value", "{}")
            return json.loads(val) if isinstance(val, str) else {}
        except RemoteChromeError:
            return {}

    # -- Chrome lifecycle --------------------------------------------------

    async def is_running(self) -> bool:
        try:
            self._http_get("/json/version")
            return True
        except ChromeNotRunningError:
            return False

    def start_chrome(self) -> None:
        ps_cmd = (
            "Start-Process -FilePath 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' "
            "-ArgumentList @('--remote-debugging-port=9222',"
            "'--user-data-dir=C:\\temp\\chrome-debug-profile')"
        )
        cmd = [
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "-NoProfile",
            "-Command",
            ps_cmd,
        ]
        logger.info("Starting Chrome via PowerShell: %s", shlex.join(cmd))
        subprocess.run(cmd, capture_output=True, timeout=15)

    def kill_chrome(self) -> None:
        """Kill ONLY the Chrome debug instance (--remote-debugging-port=9222)."""
        ps_cmd = (
            'Get-CimInstance Win32_Process '
            '-Filter "Name = \'chrome.exe\' AND CommandLine like '
            '\'%%remote-debugging-port=9222%%\'" '
            "| ForEach-Object { Stop-Process $_.ProcessId -Force }"
        )
        cmd = [
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "-NoProfile",
            "-Command",
            ps_cmd,
        ]
        logger.info("Killing debug Chrome via PowerShell (selective)")
        subprocess.run(cmd, capture_output=True, timeout=15)

    async def wait_for_ready(
        self, timeout: float = 30, poll_interval: float = 1.0
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.is_running():
                return True
            await asyncio.sleep(poll_interval)
        return False

    # -- Tab operations ----------------------------------------------------

    async def list_tabs(self) -> list[Tab]:
        raw = self._http_get("/json")
        return [Tab.from_cdp(t) for t in raw if t.get("type") == "page"]

    async def list_tabs_all(self) -> list[Tab]:
        raw = self._http_get("/json")
        return [Tab.from_cdp(t) for t in raw]

    async def activate_tab(
        self,
        url_substring: str | None = None,
        *,
        index: int | None = None,
    ) -> Tab:
        """Activate a tab by URL/title substring or zero-based *index*."""
        tabs = await self.list_tabs()

        if index is not None:
            if index < 0 or index >= len(tabs):
                raise TabNotFoundError(
                    f"Invalid tab index {index}; have {len(tabs)} tabs."
                )
            tab = tabs[index]
        else:
            if not url_substring:
                raise TabNotFoundError(
                    "Either url_substring or index must be provided."
                )
            matches = [t for t in tabs if url_substring in t.url]
            if not matches:
                matches = [t for t in tabs if url_substring in t.title]
            if not matches:
                raise TabNotFoundError(
                    f"No tab contains {url_substring!r} in URL or title. "
                    f"Available: {list(enumerate(t.url[:60] for t in tabs))}"
                )
            tab = matches[0]

        await self._cdp_send_browser("Target.activateTarget", {"targetId": tab.id})
        self._target_id = tab.id
        return tab

    async def navigate(
        self,
        url: str,
        wait: bool = True,
        timeout: float = 15,
        *,
        wait_for_selector: str | None = None,
        wait_for_title: str | None = None,
    ) -> dict:
        """Navigate to *url*. Optionally wait for readyState, selector, title.

        *wait_for_title* is a regex matched against document.title.
        """
        tab = await self._resolve_tab()
        result = await self._cdp_send_on_tab(tab, "Page.navigate", {"url": url})
        if wait:
            await self._wait_for_load(tab, timeout)
            if wait_for_selector:
                await self._wait_for_selector(tab, wait_for_selector, timeout)
            if wait_for_title:
                await self._wait_for_title_regex(tab, wait_for_title, timeout)
        return result

    async def _wait_for_load(self, tab: Tab, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        val = ""
        while time.monotonic() < deadline:
            resp = await self._cdp_send_on_tab(
                tab, "Runtime.evaluate",
                {"expression": "document.readyState", "returnByValue": True},
            )
            val = resp.get("result", {}).get("value", "")
            if val == "complete":
                return
            await asyncio.sleep(0.3)
        raise NavigationTimeoutError(
            f"Page did not finish loading within {timeout}s. "
            f"Last readyState: {val}"
        )

    async def _wait_for_selector(
        self, tab: Tab, selector: str, timeout: float
    ) -> None:
        sel = json.dumps(selector)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = await self._cdp_send_on_tab(
                tab, "Runtime.evaluate",
                {
                    "expression": f"!!document.querySelector({sel})",
                    "returnByValue": True,
                },
            )
            if resp.get("result", {}).get("value") is True:
                return
            await asyncio.sleep(0.3)
        raise NavigationTimeoutError(
            f"Selector {selector!r} did not appear within {timeout}s"
        )

    async def _wait_for_title_regex(
        self, tab: Tab, pattern: str, timeout: float
    ) -> None:
        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout
        title = ""
        while time.monotonic() < deadline:
            resp = await self._cdp_send_on_tab(
                tab, "Runtime.evaluate",
                {
                    "expression": "document.title",
                    "returnByValue": True,
                },
            )
            title = resp.get("result", {}).get("value", "")
            if compiled.search(title):
                return
            await asyncio.sleep(0.3)
        raise NavigationTimeoutError(
            f"Title did not match {pattern!r} within {timeout}s. "
            f"Last title: {title!r}"
        )

    async def _resolve_tab(self) -> Tab:
        tabs = await self.list_tabs()
        if not tabs:
            raise TabNotFoundError("No page tabs open in Chrome.")
        if self._target_id:
            for t in tabs:
                if t.id == self._target_id:
                    return t
        tab = tabs[0]
        self._target_id = tab.id
        return tab

    # -- Page interaction --------------------------------------------------

    async def click(self, selector: str) -> dict:
        tab = await self._resolve_tab()
        js_sel = json.dumps(selector)
        js = (
            "(function(){"
            "  var e = document.querySelector(" + js_sel + ");"
            "  if (!e) return JSON.stringify({error: 'not found'});"
            "  var r = e.getBoundingClientRect();"
            "  return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});"
            "})()"
        )
        rect_resp = await self._cdp_send_on_tab(
            tab, "Runtime.evaluate",
            {"expression": js, "returnByValue": True},
        )
        rect_val = rect_resp.get("result", {}).get("value", "{}")
        rect = json.loads(rect_val) if isinstance(rect_val, str) else {}
        if rect.get("error"):
            ctx = await self._page_context(tab)
            raise ElementNotFoundError(
                f"No element matching {selector!r} at URL {ctx.get('url','?')} "
                f"(readyState={ctx.get('rs','?')})"
            )

        x, y = rect["x"], rect["y"]
        for evt in ["mousePressed", "mouseReleased"]:
            await self._cdp_send_on_tab(
                tab, "Input.dispatchMouseEvent",
                {"type": evt, "x": x, "y": y, "button": "left", "clickCount": 1},
            )
        return {"x": x, "y": y, "selector": selector}

    async def type_text(self, selector: str, text: str) -> dict:
        tab = await self._resolve_tab()
        js_sel = json.dumps(selector)
        focus_js = (
            "(function(){"
            "  var e = document.querySelector(" + js_sel + ");"
            "  if (!e) return 'not found';"
            "  e.focus();"
            "  return e === document.activeElement ? 'ok' : 'focus failed';"
            "})()"
        )
        focus_resp = await self._cdp_send_on_tab(
            tab, "Runtime.evaluate",
            {"expression": focus_js, "returnByValue": True},
        )
        if focus_resp.get("result", {}).get("value") == "not found":
            ctx = await self._page_context(tab)
            raise ElementNotFoundError(
                f"No element matching {selector!r} (focus for type) "
                f"at URL {ctx.get('url','?')} (readyState={ctx.get('rs','?')})"
            )

        await self._cdp_send_on_tab(tab, "Input.insertText", {"text": text})

        verify_js = (
            "(function(){"
            "  var e = document.querySelector(" + js_sel + ");"
            "  return e ? e.value : null;"
            "})()"
        )
        verify = await self._cdp_send_on_tab(
            tab, "Runtime.evaluate",
            {"expression": verify_js, "returnByValue": True},
        )
        return {
            "selector": selector,
            "text_length": len(text),
            "input_value": verify.get("result", {}).get("value", ""),
        }

    async def scroll(
        self,
        dx: int = 0,
        dy: int = 500,
        selector: str | None = None,
        *,
        method: str = "wheel",
        wait_ms: int = 0,
    ) -> dict:
        """
        Scroll page or element.

        *method*:
          'wheel' (default): real CDP Input.dispatchMouseEvent mouseWheel.
            Best for SPAs with virtual lists -- triggers real wheel events
            that the page's IntersectionObserver / scroll listeners can see.
          'js': call window.scrollBy / element.scrollBy from JS. Fast but
            bypasses real input pipeline -- won't trigger wheel listeners.

        *wait_ms*: pause after scrolling so async renders can settle.
        *selector*: scroll a specific element instead of window.
          (only 'js' method applies to element scroll)
        """
        tab = await self._resolve_tab()

        if method == "wheel":
            if selector:
                # Scroll an element by dispatch wheel over its center.
                js_sel = json.dumps(selector)
                rect_js = (
                    "(function(){"
                    "  var e = document.querySelector(" + js_sel + ");"
                    "  if (!e) return JSON.stringify({error: 'not found'});"
                    "  var r = e.getBoundingClientRect();"
                    "  return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});"
                    "})()"
                )
                rect_resp = await self._cdp_send_on_tab(
                    tab, "Runtime.evaluate",
                    {"expression": rect_js, "returnByValue": True},
                )
                rect_val = rect_resp.get("result", {}).get("value", "{}")
                rect = json.loads(rect_val) if isinstance(rect_val, str) else {}
                if rect.get("error"):
                    ctx = await self._page_context(tab)
                    raise ElementNotFoundError(
                        f"Scroll target {selector!r} not found "
                        f"at URL {ctx.get('url','?')} (readyState={ctx.get('rs','?')})"
                    )
                cx, cy = rect["x"], rect["y"]
            else:
                # Scroll the window: wheel at viewport center.
                vp_resp = await self._cdp_send_on_tab(
                    tab, "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify({w: innerWidth, h: innerHeight})",
                        "returnByValue": True,
                    },
                )
                vp_val = vp_resp.get("result", {}).get("value", "{}")
                vp = json.loads(vp_val) if isinstance(vp_val, str) else {}
                cx = vp.get("w", 1024) / 2
                cy = vp.get("h", 768) / 2

            await self._cdp_send_on_tab(
                tab, "Input.dispatchMouseEvent",
                {
                    "type": "mouseWheel",
                    "x": cx,
                    "y": cy,
                    "deltaX": dx,
                    "deltaY": dy,
                },
            )
        elif method == "js":
            if selector:
                js_sel = json.dumps(selector)
                expr = (
                    "(function(){"
                    "  var e = document.querySelector(" + js_sel + ");"
                    "  if (!e) return JSON.stringify({error: 'not found'});"
                    "  e.scrollBy({left: " + str(dx) + ", top: " + str(dy) + ", behavior: 'instant'});"
                    "  return JSON.stringify({scrollTop: e.scrollTop, scrollLeft: e.scrollLeft});"
                    "})()"
                )
            else:
                expr = (
                    "window.scrollBy({left: " + str(dx) + ", top: " + str(dy) + ", behavior: 'instant'}); "
                    "JSON.stringify({scrollX: window.scrollX, scrollY: window.scrollY})"
                )
            resp = await self._cdp_send_on_tab(
                tab, "Runtime.evaluate",
                {"expression": expr, "returnByValue": True},
            )
            val = resp.get("result", {}).get("value", "{}")
            result = json.loads(val) if isinstance(val, str) else val
            if isinstance(result, dict) and result.get("error"):
                ctx = await self._page_context(tab)
                raise ElementNotFoundError(
                    f"Scroll failed at URL {ctx.get('url','?')}: {result['error']}"
                )
        else:
            raise RemoteChromeError(f"Unknown scroll method: {method!r}")

        if wait_ms > 0:
            await asyncio.sleep(wait_ms / 1000.0)

        # Always read final viewport scrollY for confirmation.
        final_resp = await self._cdp_send_on_tab(
            tab, "Runtime.evaluate",
            {
                "expression": "JSON.stringify({scrollX: window.scrollX, scrollY: window.scrollY})",
                "returnByValue": True,
            },
        )
        final_val = final_resp.get("result", {}).get("value", "{}")
        return json.loads(final_val) if isinstance(final_val, str) else {}

    # -- Data extraction ---------------------------------------------------

    async def eval_js(
        self,
        expression: str,
        *,
        await_promise: bool = True,
        timeout: float = 30.0,
    ) -> Any:
        """
        Evaluate JS. By default awaits the result Promise (BROKEN before fix).

        *await_promise=True* is required to actually receive the result of
        an async IIFE: `(async () => ...)()`. With await_promise=False you
        get `{}` for any Promise return.

        *timeout* protects against never-resolving Promises. Raise
        CdpTimeoutError if exceeded.
        """
        tab = await self._resolve_tab()
        raw = await self._eval_on_tab(
            tab, expression, await_promise=await_promise, timeout=timeout,
        )
        if raw.get("type") == "undefined" or raw.get("subtype") == "null":
            return None
        return raw.get("value")

    async def get_cookies(self, urls: list[str] | None = None) -> list[Cookie]:
        """Get cookies. If *urls* is None, returns ALL cookies in browser jar."""
        tab = await self._resolve_tab()
        params = {"urls": urls} if urls else {}
        result = await self._cdp_send_on_tab(
            tab, "Network.getCookies", params or None
        )
        raw = result.get("cookies", [])
        return [Cookie.from_cdp(c) for c in raw]

    async def get_cookies_for_domain(self, domain: str) -> list[Cookie]:
        return await self.get_cookies([
            f"https://{domain}", f"http://{domain}",
            f"https://www.{domain}", f"http://www.{domain}",
        ])

    async def get_cookies_for_current_page(self) -> list[Cookie]:
        """Cookies for the current page's origin URL.

        Better default than get_cookies(): avoids returning every cookie in
        the browser jar when the user just wants the current page's cookies.
        """
        tab = await self._resolve_tab()
        raw = await self._eval_on_tab(
            tab, "location.href", await_promise=False, timeout=5.0,
        )
        href = raw.get("value") or ""
        if not href.startswith(("http://", "https://")):
            # chrome:// pages have no cookies; returning [] is correct.
            return []
        return await self.get_cookies(urls=[href])

    # Chrome does NOT expose the download directory over CDP (no
    # Browser.getDownloadPath exists). The value lives in the user profile's
    # `Preferences` JSON under `download.default_directory`. This skill drives a
    # fixed debug profile (see start_chrome), so we read that profile's
    # Preferences. We try PowerShell on the native Windows path first, then fall
    # back to the WSL /mnt/c mount. When the key is absent Chrome uses its OS
    # default Downloads folder.

    DEBUG_PROFILE_DIR = "C:\\temp\\chrome-debug-profile"

    def get_download_dir(self) -> dict[str, Any]:
        """Read the debug profile's configured download directory.

        Returns a dict with keys:
          found   : bool  -- True if a custom directory is configured
          path    : str   -- the directory (custom, or OS default hint if not)
          source  : str   -- how the path was resolved
          profile : str   -- the profile directory that was inspected
        """
        profile = self.DEBUG_PROFILE_DIR
        pref_path = f"{profile}\\Default\\Preferences"

        raw = self._read_profile_preferences(pref_path)
        if raw is None:
            return {
                "found": False,
                "path": "",
                "source": "unreadable",
                "profile": profile,
                "note": "Could not read Preferences file (Chrome not started, or cross-fs access blocked).",
            }

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                "found": False,
                "path": "",
                "source": "parse_error",
                "profile": profile,
                "note": f"Preferences file is not valid JSON: {exc}",
            }

        ddir = (
            data.get("download", {}).get("default_directory")
            or data.get("savefile", {}).get("default_directory")
            or data.get("download", {}).get("directory_upgrade")
        )
        if ddir:
            return {
                "found": True,
                "path": ddir,
                "source": "profile_preferences",
                "profile": profile,
            }

        return {
            "found": False,
            "path": "",
            "source": "chrome_default",
            "profile": profile,
            "note": "No custom download directory set; Chrome uses the OS default Downloads folder.",
        }

    def _read_profile_preferences(self, pref_path: str) -> str | None:
        """Read the Preferences file via PowerShell (Windows path) with a WSL /mnt/c fallback."""
        ps_cmd = f"Get-Content -Raw -Path '{pref_path}'"
        cmd = [
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "-NoProfile",
            "-Command",
            ps_cmd,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except (OSError, subprocess.SubprocessError):
            pass

        wsl_path = pref_path.replace("C:\\", "/mnt/c/").replace("\\", "/")
        try:
            with open(wsl_path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    async def get_localstorage(self) -> dict[str, str]:
        value = await self.eval_js(
            "JSON.stringify("
            "  window.localStorage "
            "    ? Object.entries(localStorage).reduce((a,[k,v]) => (a[k]=v,a), {}) "
            "    : {}"
            ")"
        )
        if isinstance(value, str):
            return json.loads(value)
        return {}

    # -- Wait operations ---------------------------------------------------

    async def wait_for_navigation(
        self,
        url_contains: str | None = None,
        timeout: float = 300,
        poll_interval: float = 1.0,
    ) -> dict:
        """Poll location.href until URL matches.

        Establishes baseline via Runtime.evaluate (not HTTP /json) so the
        function works even if the tab already navigated before this call.
        """
        tab = await self._resolve_tab()

        baseline_resp = await self._cdp_send_on_tab(
            tab, "Runtime.evaluate",
            {
                "expression": "JSON.stringify({url: location.href, title: document.title})",
                "returnByValue": True,
            },
        )
        baseline_val = baseline_resp.get("result", {}).get("value", "{}")
        baseline = json.loads(baseline_val) if isinstance(baseline_val, str) else {}
        start_url = baseline.get("url", "")

        deadline = time.monotonic() + timeout
        current_url = start_url

        while time.monotonic() < deadline:
            resp = await self._cdp_send_on_tab(
                tab, "Runtime.evaluate",
                {
                    "expression": "JSON.stringify({url: location.href, title: document.title})",
                    "returnByValue": True,
                },
            )
            val = resp.get("result", {}).get("value", "{}")
            state = json.loads(val) if isinstance(val, str) else {}
            current_url = state.get("url", "")

            if url_contains:
                if url_contains in current_url:
                    return {"url": current_url, "title": state.get("title", "")}
            else:
                if (current_url and current_url != start_url
                        and current_url != "about:blank"):
                    return {"url": current_url, "title": state.get("title", "")}

            await asyncio.sleep(poll_interval)

        raise NavigationTimeoutError(
            f"Navigation wait timed out after {timeout}s. "
            f"url_contains={url_contains!r}. Last URL: {current_url}"
        )

    async def wait_for_auth(
        self,
        cookie_name: str = "SID",
        cookie_domain: str = ".google.com",
        timeout: float = 300,
        poll_interval: float = 1.0,
    ) -> dict:
        """Poll Network.getCookies until *cookie_name* on *cookie_domain* appears."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            cookies = await self.get_cookies()
            for c in cookies:
                if c.name == cookie_name and c.domain == cookie_domain and c.value:
                    return {
                        "cookie_name": cookie_name,
                        "cookie_domain": cookie_domain,
                        "found": True,
                    }
            await asyncio.sleep(poll_interval)

        raise AuthTimeoutError(
            f"Auth cookie {cookie_name!r} on domain {cookie_domain!r} "
            f"did not appear within {timeout}s."
        )

