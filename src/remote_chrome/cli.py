"""CLI entry point for remote-chrome-skill.

All subcommands output JSON on stdout for easy agent/LLM parsing.
Human-readable errors go to stderr.
"""

import argparse
import asyncio
import json
import sys
from typing import Any

from remote_chrome.client import (
    RemoteChrome,
    RemoteChromeError,
    TabNotFoundError,
    ElementNotFoundError,
    NavigationTimeoutError,
    AuthTimeoutError,
    ChromeNotRunningError,
    CdpTimeoutError,
    NetworkRequest,
)


def _output_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))


def _detect_host() -> str:
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
    except OSError:
        pass
    return "172.25.112.1"


async def _cmd_status(rc, args) -> dict:
    running = await rc.is_running()
    out = {"running": running, "host": rc.host, "port": rc.port}
    if running:
        try:
            import urllib.request
            ver_url = f"http://{rc.host}:{rc.port}/json/version"
            with urllib.request.urlopen(ver_url, timeout=8) as r:
                ver = json.load(r)
            out["browser"] = ver.get("Browser", "")
            out["protocol_version"] = ver.get("Protocol-Version", "")
            tabs = await rc.list_tabs()
            out["tab_count"] = len(tabs)
        except Exception as exc:
            out["warning"] = str(exc)
    return out


async def _cmd_list_tabs(rc, args) -> dict:
    tabs = await rc.list_tabs()
    return {
        "tabs": [
            {"index": i, "id": t.id, "url": t.url, "title": t.title, "type": t.type}
            for i, t in enumerate(tabs)
        ]
    }


async def _cmd_activate(rc, args) -> dict:
    if args.index is not None:
        tab = await rc.activate_tab(index=args.index)
    else:
        tab = await rc.activate_tab(args.url_substring)
    return {"activated": {"id": tab.id, "url": tab.url, "title": tab.title}}


async def _cmd_navigate(rc, args) -> dict:
    result = await rc.navigate(
        args.url,
        wait=not args.no_wait,
        timeout=args.timeout,
        wait_for_selector=args.wait_for_selector,
        wait_for_title=args.wait_for_title,
    )
    return {"nav": result, "url": args.url}


async def _cmd_click(rc, args) -> dict:
    return await rc.click(args.selector)


async def _cmd_type(rc, args) -> dict:
    return await rc.type_text(args.selector, args.text)


async def _cmd_scroll(rc, args) -> dict:
    return await rc.scroll(
        dx=args.dx,
        dy=args.dy,
        selector=args.selector,
        method=args.method,
        wait_ms=args.wait_ms,
    )


async def _cmd_eval(rc, args) -> dict:
    value = await rc.eval_js(
        args.expression,
        await_promise=not args.no_await,
        timeout=(args.timeout_ms / 1000.0) if args.timeout_ms else 30.0,
    )
    return {"value": value}


async def _cmd_cookies(rc, args) -> dict:
    if args.domain:
        cookies = await rc.get_cookies_for_domain(args.domain)
    elif args.url:
        cookies = await rc.get_cookies([args.url])
    elif args.all:
        cookies = await rc.get_cookies()
    else:
        cookies = await rc.get_cookies_for_current_page()
    return {
        "cookies": [
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "secure": c.secure,
                "http_only": c.http_only,
                "same_site": c.same_site,
            }
            for c in cookies
        ]
    }


async def _cmd_localstorage(rc, args) -> dict:
    ls = await rc.get_localstorage()
    return {"entries": ls, "count": len(ls)}


async def _cmd_screenshot(rc, args) -> dict:
    import base64
    data = await rc.screenshot(
        fmt=args.format,
        quality=args.quality if args.format == "jpeg" else None,
        full_page=args.full_page,
    )
    return {
        "format": args.format,
        "full_page": args.full_page,
        "size_bytes": len(data),
        "data_base64": base64.b64encode(data).decode("ascii"),
    }


async def _cmd_get_download_dir(rc, args) -> dict:
    return rc.get_download_dir()


async def _cmd_wait_nav(rc, args) -> dict:
    return await rc.wait_for_navigation(
        url_contains=args.url_contains,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )


async def _cmd_wait_auth(rc, args) -> dict:
    return await rc.wait_for_auth(
        cookie_name=args.cookie_name,
        cookie_domain=args.cookie_domain,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )


async def _cmd_start_chrome(rc, args) -> dict:
    rc.start_chrome()
    ready = await rc.wait_for_ready(timeout=args.timeout)
    return {"started": True, "ready": ready, "host": rc.host, "port": rc.port}


async def _cmd_kill_chrome(rc, args) -> dict:
    rc.kill_chrome()
    return {"killed": True}


async def _cmd_bootstrap(rc, args) -> dict:
    from remote_chrome.bootstrap import generate_bootstrap
    return generate_bootstrap()


async def _cmd_network_monitor(rc, args) -> dict:
    """Start or stop network monitoring and retrieve requests."""
    if args.action == "start":
        await rc.start_network_monitoring(
            url_filter=args.url_filter,
            resource_types=args.resource_types.split(",") if args.resource_types else None,
        )
        return {"action": "start", "url_filter": args.url_filter, "resource_types": args.resource_types}
    elif args.action == "stop":
        await rc.stop_network_monitoring()
        return {"action": "stop"}
    elif args.action == "get":
        requests = await rc.get_network_requests()
        return {"requests": [req.to_dict() for req in requests], "count": len(requests)}
    else:
        return {"error": f"Unknown action: {args.action}"}


HANDLERS = {
    "status": _cmd_status,
    "list-tabs": _cmd_list_tabs,
    "activate": _cmd_activate,
    "navigate": _cmd_navigate,
    "click": _cmd_click,
    "type": _cmd_type,
    "scroll": _cmd_scroll,
    "eval": _cmd_eval,
    "cookies": _cmd_cookies,
    "localstorage": _cmd_localstorage,
    "screenshot": _cmd_screenshot,
    "get-download-dir": _cmd_get_download_dir,
    "wait-for-navigation": _cmd_wait_nav,
    "wait-for-auth": _cmd_wait_auth,
    "start-chrome": _cmd_start_chrome,
    "kill-chrome": _cmd_kill_chrome,
    "bootstrap": _cmd_bootstrap,
    "network-monitor": _cmd_network_monitor,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="remote-chrome",
        description=(
            "Control a Chrome debug instance running on Windows from WSL "
            "via the Chrome DevTools Protocol."
        ),
    )
    p.add_argument("--host", default=None, help="Chrome CDP host IP (default: auto-detect)")
    p.add_argument("--port", type=int, default=9223, help="Chrome CDP port (default: 9223)")

    sub = p.add_subparsers(dest="cmd", required=True, metavar="<command>")

    sub.add_parser("status", help="Check Chrome CDP health")
    sub.add_parser("list-tabs", help="List all open page tabs (with 0-based index)")
    sub.add_parser("bootstrap", help="Print Windows one-time setup commands")

    p_activate = sub.add_parser("activate", help="Activate a tab by URL/title substring or --index N")
    p_activate.add_argument("url_substring", nargs="?", default=None,
                            help="Substring to match in tab URL/title (omit if using --index)")
    p_activate.add_argument("--index", type=int, default=None,
                            help="Activate tab by 0-based index from list-tabs output")

    p_nav = sub.add_parser("navigate", help="Navigate current tab to a URL")
    p_nav.add_argument("url")
    p_nav.add_argument("--no-wait", action="store_true",
                       help="Return immediately after Page.navigate")
    p_nav.add_argument("--timeout", type=float, default=15,
                       help="Wait-for-load/selector/title timeout in seconds")
    p_nav.add_argument("--wait-for-selector", default=None,
                       help="Poll until a CSS selector matches (useful for SPAs where readyState lies)")
    p_nav.add_argument("--wait-for-title", default=None,
                       help="Poll until document.title matches this regex (useful for SPAs)")

    p_click = sub.add_parser("click", help="Click an element by CSS selector")
    p_click.add_argument("selector")

    p_type = sub.add_parser("type", help="Type text into an input by CSS selector")
    p_type.add_argument("selector")
    p_type.add_argument("text")

    p_scroll = sub.add_parser("scroll", help="Scroll the page or an element")
    p_scroll.add_argument("--dx", type=int, default=0)
    p_scroll.add_argument("--dy", type=int, default=500)
    p_scroll.add_argument("--selector", default=None,
                          help="Scroll an element instead of window")
    p_scroll.add_argument("--method", choices=["wheel", "js"], default="wheel",
                          help="wheel (default) = real CDP mouseWheel, triggers SPA lazy load; "
                               "js = window.scrollBy, faster but bypasses input pipeline")
    p_scroll.add_argument("--wait-ms", type=int, default=200,
                          help="Pause after scroll so async renders settle (default 200ms)")

    p_eval = sub.add_parser("eval", help="Evaluate a JS expression on the current page")
    p_eval.add_argument("expression")
    p_eval.add_argument("--no-await", action="store_true",
                       help="Disable awaitPromise (default awaits; async IIFEs work)")
    p_eval.add_argument("--timeout-ms", type=int, default=None,
                        help="Receive timeout for the CDP response in milliseconds (default 30000)")

    p_cookies = sub.add_parser("cookies", help="Read cookies")
    p_cookies.add_argument("--domain", default=None,
                           help="Filter by domain (e.g. google.com)")
    p_cookies.add_argument("--url", default=None,
                           help="Filter by exact URL")
    p_cookies.add_argument("--all", action="store_true",
                           help="Return ALL cookies in the browser jar (default: only current page origin)")

    sub.add_parser("localstorage", help="Read localStorage for current page origin")

    p_screenshot = sub.add_parser("screenshot", help="Capture a screenshot of the current page")
    p_screenshot.add_argument("--format", choices=["png", "jpeg"], default="png",
                              help="Image format (default: png)")
    p_screenshot.add_argument("--quality", type=int, default=None,
                              help="JPEG quality 0-100 (only used with --format jpeg)")
    p_screenshot.add_argument("--full-page", action="store_true",
                              help="Capture the entire scrollable page, not just viewport")

    sub.add_parser(
        "get-download-dir",
        help="Read the debug profile's configured download directory (from profile Preferences)",
    )

    p_waitnav = sub.add_parser("wait-for-navigation", help="Wait until URL changes or contains a substring")
    p_waitnav.add_argument("--url-contains", default=None)
    p_waitnav.add_argument("--timeout", type=float, default=300)
    p_waitnav.add_argument("--poll-interval", type=float, default=1.0)

    p_waitauth = sub.add_parser("wait-for-auth", help="Wait until an auth cookie appears in the cookie store")
    p_waitauth.add_argument("--cookie-name", default="SID")
    p_waitauth.add_argument("--cookie-domain", default=".google.com")
    p_waitauth.add_argument("--timeout", type=float, default=300)
    p_waitauth.add_argument("--poll-interval", type=float, default=1.0)

    p_start = sub.add_parser("start-chrome", help="Launch Chrome with debug port from WSL")
    p_start.add_argument("--timeout", type=float, default=30, help="Wait-for-ready timeout")

    sub.add_parser("kill-chrome",
                   help="Kill ONLY the debug Chrome instance (selective via --remote-debugging-port=9222 in command line)")

    p_network = sub.add_parser("network-monitor", help="Monitor network requests (start/stop/get)")
    p_network.add_argument("action", choices=["start", "stop", "get"],
                          help="Action: start monitoring, stop monitoring, or get captured requests")
    p_network.add_argument("--url-filter", default=None,
                          help="Filter URLs by substring (only for 'start' action)")
    p_network.add_argument("--resource-types", default=None,
                          help="Comma-separated resource types to monitor, e.g., 'XHR,Fetch,Document' (only for 'start')")

    return p


def main() -> int:
    args = build_parser().parse_args()

    host = args.host or _detect_host()
    rc = RemoteChrome(host=host, port=args.port)

    handler = HANDLERS.get(args.cmd)
    if not handler:
        print(json.dumps({"error": f"Unknown command: {args.cmd}"}), file=sys.stderr)
        return 2

    try:
        result = asyncio.run(handler(rc, args))
        _output_json(result)
        return 0
    except ChromeNotRunningError as exc:
        print(json.dumps({"error": "chrome_not_running", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 3
    except TabNotFoundError as exc:
        print(json.dumps({"error": "tab_not_found", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 4
    except ElementNotFoundError as exc:
        print(json.dumps({"error": "element_not_found", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 5
    except NavigationTimeoutError as exc:
        print(json.dumps({"error": "navigation_timeout", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 6
    except AuthTimeoutError as exc:
        print(json.dumps({"error": "auth_timeout", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 7
    except CdpTimeoutError as exc:
        print(json.dumps({"error": "cdp_timeout", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 8
    except RemoteChromeError as exc:
        print(json.dumps({"error": "remote_chrome_error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

