#!/usr/bin/env -S uv run --script --python 3.12
# /// script
# requires-python = "==3.12.*"
# dependencies = [
#     "playwright>=1.49.0",
#     "requests>=2.31.0",
# ]
# ///

"""
Browser automation client for Max.

Connects to the Browser Server's session-scoped API.
Requires MAX_SESSION_ID environment variable.

Usage:
    uv run client.py list
    uv run client.py create <name> [url]
    uv run client.py goto <name> <url>
    uv run client.py screenshot <name> [output_path]
    uv run client.py click <name> <selector>
    uv run client.py fill <name> <selector> <text>
    uv run client.py hover <name> <selector>
    uv run client.py keyboard <name> <key>
    uv run client.py evaluate <name> <script>
    uv run client.py text <name> <selector>
    uv run client.py snapshot <name>
    uv run client.py select-ref <name> <ref> <action> [value]
    uv run client.py wait-selector <name> <selector>
    uv run client.py wait-url <name> <url_pattern>
    uv run client.py wait-load <name>
    uv run client.py close <name>
    uv run client.py info <name>
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from playwright.sync_api import Browser, ElementHandle, Page, sync_playwright

SERVER_URL = "http://localhost:9222"
HTTP_TIMEOUT = 10  # seconds


def _load_snapshot_script() -> str:
    """Load the ARIA snapshot script from file."""
    script_path = Path(__file__).parent / "snapshot.js"
    return script_path.read_text(encoding="utf-8")


# ARIA Snapshot script - loaded from snapshot.js
SNAPSHOT_SCRIPT = _load_snapshot_script()


@dataclass
class PageInfo:
    """Page information"""

    name: str
    target_id: str
    ws_endpoint: str
    title: str
    url: str


@dataclass
class WaitForPageLoadResult:
    """Result of waiting for page load"""

    success: bool
    ready_state: str
    pending_requests: int
    wait_time_ms: int
    timed_out: bool


class BrowserClient:
    """Session-scoped browser client for Max."""

    def __init__(self, session_id: Optional[str] = None):
        """Initialize client with session ID from env or parameter."""
        self.session_id = session_id or os.environ.get("MAX_SESSION_ID")
        if not self.session_id:
            raise RuntimeError(
                "MAX_SESSION_ID environment variable is required.\n"
                "Make sure you're running this from within Max."
            )

        self.base_url = f"{SERVER_URL}/sessions/{self.session_id}"
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._browser_ws_endpoint: Optional[str] = None
        self._page_cache: dict[str, Page] = {}

    def _check_server(self) -> bool:
        """Check if browser server is running."""
        try:
            resp = requests.get(SERVER_URL, timeout=2)
            return resp.ok
        except requests.RequestException:
            return False

    def _ensure_browser_connected(self) -> Browser:
        """Ensure we have a browser connection, connecting if necessary."""
        if self._browser and self._browser.is_connected():
            return self._browser

        # Get browser-level wsEndpoint from server root
        resp = requests.get(SERVER_URL, timeout=5)
        if not resp.ok:
            raise RuntimeError(f"Failed to get server info: {resp.status_code}")

        server_info = resp.json()
        ws_endpoint = server_info.get("wsEndpoint")
        if not ws_endpoint:
            raise RuntimeError("Server did not return wsEndpoint")

        # Start playwright if needed
        if not self._playwright:
            self._playwright = sync_playwright().start()

        # Connect to browser
        self._browser = self._playwright.chromium.connect_over_cdp(ws_endpoint)
        self._browser_ws_endpoint = ws_endpoint
        return self._browser

    def _find_page_by_target_id(
        self, browser: Browser, target_id: str
    ) -> Optional[Page]:
        """Find a page by its CDP targetId."""
        for context in browser.contexts:
            for page in context.pages:
                try:
                    # Create CDP session to get target info
                    cdp_session = context.new_cdp_session(page)
                    try:
                        result = cdp_session.send("Target.getTargetInfo")
                        page_target_id = result.get("targetInfo", {}).get("targetId")
                        if page_target_id == target_id:
                            return page
                    finally:
                        try:
                            cdp_session.detach()
                        except Exception:
                            pass  # Ignore detach errors
                except Exception as e:
                    # Ignore errors for closed pages
                    msg = str(e)
                    if "Target closed" not in msg and "Session closed" not in msg:
                        print(
                            f"Warning: Error checking page target: {msg}",
                            file=sys.stderr,
                        )
        return None

    def list_pages(self) -> list[PageInfo]:
        """List all pages in current session"""
        resp = requests.get(f"{self.base_url}/pages")
        if not resp.ok:
            if resp.status_code == 404:
                return []  # Session doesn't exist yet
            raise RuntimeError(f"Failed to list pages: {resp.status_code}")

        data = resp.json()
        return [
            PageInfo(
                name=p["name"],
                target_id=p["targetId"],
                ws_endpoint=p["wsEndpoint"],
                title=p.get("title", ""),
                url=p.get("url", ""),
            )
            for p in data.get("pages", [])
        ]

    def create_page(self, name: str, url: Optional[str] = None) -> PageInfo:
        """Create a new page for current session"""
        payload = {"name": name}
        if url:
            payload["url"] = url

        resp = requests.post(
            f"{self.base_url}/pages",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if not resp.ok:
            error = resp.json().get("error", f"HTTP {resp.status_code}")
            raise RuntimeError(f"Failed to create page: {error}")

        data = resp.json()
        return PageInfo(
            name=data["name"],
            target_id=data["targetId"],
            ws_endpoint=data["wsEndpoint"],
            title="",
            url=data.get("url", ""),
        )

    def get_page_info(self, name: str) -> PageInfo:
        """Get page details"""
        resp = requests.get(f"{self.base_url}/pages/{name}")
        if not resp.ok:
            raise RuntimeError(f"Page '{name}' not found")

        data = resp.json()
        return PageInfo(
            name=data["name"],
            target_id=data["targetId"],
            ws_endpoint=data["wsEndpoint"],
            title=data.get("title", ""),
            url=data.get("url", ""),
        )

    def close_page(self, name: str) -> bool:
        """Close a page"""
        resp = requests.delete(f"{self.base_url}/pages/{name}")

        # Clear from cache
        if name in self._page_cache:
            del self._page_cache[name]

        return resp.ok

    def get_playwright_page(self, name: str) -> Page:
        """Get Playwright Page object"""
        # Check cache first
        if name in self._page_cache:
            cached = self._page_cache[name]
            if not cached.is_closed():
                return cached
            # Remove stale cache entry
            del self._page_cache[name]

        # Get page info (contains targetId)
        page_info = self.get_page_info(name)

        # Connect to browser (reuses existing connection)
        browser = self._ensure_browser_connected()

        # Find page by targetId
        page = self._find_page_by_target_id(browser, page_info.target_id)
        if not page:
            # Debug: list available pages
            all_pages = []
            for ctx in browser.contexts:
                for p in ctx.pages:
                    all_pages.append(p.url[:50] if p.url else "(blank)")
            raise RuntimeError(
                f"Page '{name}' (targetId={page_info.target_id}) not found in browser.\n"
                f"Available pages: {all_pages}"
            )

        self._page_cache[name] = page
        return page

    def get_or_create_page(self, name: str, url: Optional[str] = None) -> Page:
        """Get or create page (idempotent operation)"""
        try:
            return self.get_playwright_page(name)
        except RuntimeError:
            # Page doesn't exist, create it
            self.create_page(name, url)
            return self.get_playwright_page(name)

    def disconnect(self):
        """Disconnect all connections"""
        self._page_cache.clear()
        self._browser = None
        self._browser_ws_endpoint = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    # === New Features ===

    def get_ai_snapshot(self, name: str) -> str:
        """Get AI-friendly ARIA snapshot for a page.
        Returns YAML format with refs like [ref=e1], [ref=e2].
        """
        page = self.get_playwright_page(name)

        # Inject snapshot script and call getAISnapshot
        snapshot = page.evaluate(f"""() => {{
            {SNAPSHOT_SCRIPT}
            return window.__devBrowser_getAISnapshot();
        }}""")

        return snapshot

    def select_snapshot_ref(self, name: str, ref: str) -> ElementHandle:
        """Get an element handle by its ref from the last getAISnapshot call."""
        page = self.get_playwright_page(name)

        element_handle = page.evaluate_handle(
            """(refId) => {
            const refs = window.__devBrowserRefs;
            if (!refs) {
                throw new Error("No snapshot refs found. Call getAISnapshot first.");
            }
            const element = refs[refId];
            if (!element) {
                throw new Error('Ref "' + refId + '" not found. Available refs: ' + Object.keys(refs).join(", "));
            }
            return element;
        }""",
            ref,
        )

        element = element_handle.as_element()
        if not element:
            raise RuntimeError(f"Ref '{ref}' did not resolve to an element")

        return element

    def wait_for_page_load(
        self,
        name: str,
        timeout: int = 10000,
        poll_interval: int = 50,
        minimum_wait: int = 100,
        wait_for_network_idle: bool = True,
    ) -> WaitForPageLoadResult:
        """Wait for a page to finish loading using document.readyState and performance API."""
        page = self.get_playwright_page(name)

        start_time = time.time() * 1000  # ms
        last_state = None

        # Wait minimum time first
        if minimum_wait > 0:
            time.sleep(minimum_wait / 1000)

        # Poll until ready or timeout
        while (time.time() * 1000 - start_time) < timeout:
            try:
                last_state = page.evaluate("""() => {
                    const perf = performance;
                    const doc = document;
                    const now = perf.now();
                    const resources = perf.getEntriesByType("resource");
                    const pending = [];

                    const adPatterns = [
                        "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
                        "google-analytics.com", "facebook.net", "connect.facebook.net",
                        "analytics", "ads", "tracking", "pixel", "hotjar.com", "clarity.ms",
                        "mixpanel.com", "segment.com", "newrelic.com", "nr-data.net",
                        "/tracker/", "/collector/", "/beacon/", "/telemetry/", "/log/",
                        "/events/", "/track.", "/metrics/"
                    ];

                    const nonCriticalTypes = ["img", "image", "icon", "font"];

                    for (const entry of resources) {
                        if (entry.responseEnd === 0) {
                            const url = entry.name;
                            const isAd = adPatterns.some(pattern => url.includes(pattern));
                            if (isAd) continue;
                            if (url.startsWith("data:") || url.length > 500) continue;

                            const loadingDuration = now - entry.startTime;
                            if (loadingDuration > 10000) continue;

                            const resourceType = entry.initiatorType || "unknown";
                            if (nonCriticalTypes.includes(resourceType) && loadingDuration > 3000) continue;

                            const isImageUrl = /\\.(jpg|jpeg|png|gif|webp|svg|ico)(\\?|$)/i.test(url);
                            if (isImageUrl && loadingDuration > 3000) continue;

                            pending.push({
                                url: url,
                                loadingDurationMs: Math.round(loadingDuration),
                                resourceType: resourceType
                            });
                        }
                    }

                    return {
                        documentReadyState: doc.readyState,
                        documentLoading: doc.readyState !== "complete",
                        pendingRequests: pending
                    };
                }""")

                document_ready = last_state["documentReadyState"] == "complete"
                network_idle = (
                    not wait_for_network_idle or len(last_state["pendingRequests"]) == 0
                )

                if document_ready and network_idle:
                    return WaitForPageLoadResult(
                        success=True,
                        ready_state=last_state["documentReadyState"],
                        pending_requests=len(last_state["pendingRequests"]),
                        wait_time_ms=int(time.time() * 1000 - start_time),
                        timed_out=False,
                    )
            except Exception:
                # Page may be navigating, continue polling
                pass

            time.sleep(poll_interval / 1000)

        # Timeout reached
        return WaitForPageLoadResult(
            success=False,
            ready_state=last_state["documentReadyState"] if last_state else "unknown",
            pending_requests=len(last_state["pendingRequests"]) if last_state else 0,
            wait_time_ms=int(time.time() * 1000 - start_time),
            timed_out=True,
        )


# === CLI Commands ===


def cmd_list(client: BrowserClient, args):
    """List all pages in current session."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        print("Please make sure Max is open.")
        return 1

    pages = client.list_pages()
    if not pages:
        print("No pages in current session.")
        return 0

    print(f"Pages in session ({len(pages)}):")
    for p in pages:
        print(f"  - {p.name}: {p.title or p.url or '(empty)'}")
    return 0


def cmd_create(client: BrowserClient, args):
    """Create a new page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page_info = client.create_page(args.name, args.url)
        print(f"Created page: {page_info.name}")
        print(f"  targetId: {page_info.target_id}")
        if args.url:
            print(f"  url: {args.url}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1


def cmd_goto(client: BrowserClient, args):
    """Navigate a page to URL."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_or_create_page(args.name, args.url)
        if page.url != args.url:
            page.goto(args.url)
        print(f"Navigated to: {args.url}")
        print(f"Title: {page.title()}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_screenshot(client: BrowserClient, args):
    """Take a screenshot of a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        output_path = args.output or f"{args.name}.png"
        page.screenshot(path=output_path)
        print(f"Screenshot saved to: {output_path}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_click(client: BrowserClient, args):
    """Click an element on a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.click(args.selector)
        print(f"Clicked: {args.selector}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_fill(client: BrowserClient, args):
    """Fill an input element with text."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.fill(args.selector, args.text)
        print(f"Filled '{args.selector}' with: {args.text}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_hover(client: BrowserClient, args):
    """Hover over an element."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.hover(args.selector)
        print(f"Hovered: {args.selector}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_keyboard(client: BrowserClient, args):
    """Press a keyboard key."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.keyboard.press(args.key)
        print(f"Pressed key: {args.key}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_evaluate(client: BrowserClient, args):
    """Execute JavaScript on a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        result = page.evaluate(args.script)
        print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_text(client: BrowserClient, args):
    """Get text content of an element."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        text = page.text_content(args.selector)
        print(text or "(empty)")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_snapshot(client: BrowserClient, args):
    """Get AI snapshot of a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        snapshot = client.get_ai_snapshot(args.name)
        print(snapshot)
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_select_ref(client: BrowserClient, args):
    """Select element by ref and perform action."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        element = client.select_snapshot_ref(args.name, args.ref)
        action = args.action.lower()

        if action == "click":
            element.click()
            print(f"Clicked element ref: {args.ref}")
        elif action == "fill":
            if not args.value:
                print("Error: fill action requires a value")
                return 1
            element.fill(args.value)
            print(f"Filled element ref: {args.ref}")
        elif action == "hover":
            element.hover()
            print(f"Hovered element ref: {args.ref}")
        elif action == "text":
            text = element.text_content()
            print(text or "(empty)")
        else:
            print(
                f"Error: Unknown action '{action}'. Supported: click, fill, hover, text"
            )
            return 1

        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_wait_selector(client: BrowserClient, args):
    """Wait for a selector to appear."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        timeout = args.timeout or 30000
        page.wait_for_selector(args.selector, timeout=timeout)
        print(f"Selector found: {args.selector}")
        return 0
    except Exception as e:
        print(f"Error: Timeout waiting for selector '{args.selector}': {e}")
        return 1
    finally:
        client.disconnect()


def cmd_wait_url(client: BrowserClient, args):
    """Wait for URL to match pattern."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        timeout = args.timeout or 30000
        page.wait_for_url(args.url_pattern, timeout=timeout)
        print(f"URL matched: {page.url}")
        return 0
    except Exception as e:
        print(f"Error: Timeout waiting for URL '{args.url_pattern}': {e}")
        return 1
    finally:
        client.disconnect()


def cmd_wait_load(client: BrowserClient, args):
    """Wait for page to fully load."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        timeout = args.timeout or 10000
        result = client.wait_for_page_load(args.name, timeout=timeout)

        if result.success:
            print("Page loaded successfully")
            print(f"  Ready state: {result.ready_state}")
            print(f"  Wait time: {result.wait_time_ms}ms")
        else:
            print("Page load timed out")
            print(f"  Ready state: {result.ready_state}")
            print(f"  Pending requests: {result.pending_requests}")
            print(f"  Wait time: {result.wait_time_ms}ms")
            return 1

        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_close(client: BrowserClient, args):
    """Close a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    if client.close_page(args.name):
        print(f"Closed page: {args.name}")
        return 0
    else:
        print(f"Error: Page '{args.name}' not found")
        return 1


def cmd_info(client: BrowserClient, args):
    """Get page information."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        info = client.get_page_info(args.name)
        print(f"Page: {info.name}")
        print(f"  Title: {info.title}")
        print(f"  URL: {info.url}")
        print(f"  Target ID: {info.target_id}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Browser automation client for Max")
    parser.add_argument(
        "--session-id",
        help="Session ID (defaults to MAX_SESSION_ID env var)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list
    subparsers.add_parser("list", help="List all pages in current session")

    # create
    p_create = subparsers.add_parser("create", help="Create a new page")
    p_create.add_argument("name", help="Page name")
    p_create.add_argument("url", nargs="?", help="Initial URL")

    # goto
    p_goto = subparsers.add_parser("goto", help="Navigate a page to URL")
    p_goto.add_argument("name", help="Page name")
    p_goto.add_argument("url", help="URL to navigate to")

    # screenshot
    p_screenshot = subparsers.add_parser("screenshot", help="Take a screenshot")
    p_screenshot.add_argument("name", help="Page name")
    p_screenshot.add_argument("output", nargs="?", help="Output file path")

    # click
    p_click = subparsers.add_parser("click", help="Click an element")
    p_click.add_argument("name", help="Page name")
    p_click.add_argument("selector", help="CSS selector")

    # fill
    p_fill = subparsers.add_parser("fill", help="Fill an input element")
    p_fill.add_argument("name", help="Page name")
    p_fill.add_argument("selector", help="CSS selector")
    p_fill.add_argument("text", help="Text to fill")

    # hover
    p_hover = subparsers.add_parser("hover", help="Hover over an element")
    p_hover.add_argument("name", help="Page name")
    p_hover.add_argument("selector", help="CSS selector")

    # keyboard
    p_keyboard = subparsers.add_parser("keyboard", help="Press a keyboard key")
    p_keyboard.add_argument("name", help="Page name")
    p_keyboard.add_argument("key", help="Key to press (e.g., Enter, Tab, Escape)")

    # evaluate
    p_evaluate = subparsers.add_parser("evaluate", help="Execute JavaScript")
    p_evaluate.add_argument("name", help="Page name")
    p_evaluate.add_argument("script", help="JavaScript code to execute")

    # text
    p_text = subparsers.add_parser("text", help="Get text content of element")
    p_text.add_argument("name", help="Page name")
    p_text.add_argument("selector", help="CSS selector")

    # snapshot
    p_snapshot = subparsers.add_parser("snapshot", help="Get AI snapshot (ARIA tree)")
    p_snapshot.add_argument("name", help="Page name")

    # select-ref
    p_select_ref = subparsers.add_parser(
        "select-ref", help="Select element by ref and perform action"
    )
    p_select_ref.add_argument("name", help="Page name")
    p_select_ref.add_argument("ref", help="Element ref (e.g., e1, e2)")
    p_select_ref.add_argument("action", help="Action: click, fill, hover, text")
    p_select_ref.add_argument("value", nargs="?", help="Value for fill action")

    # wait-selector
    p_wait_selector = subparsers.add_parser("wait-selector", help="Wait for selector")
    p_wait_selector.add_argument("name", help="Page name")
    p_wait_selector.add_argument("selector", help="CSS selector")
    p_wait_selector.add_argument(
        "--timeout", type=int, help="Timeout in ms (default: 30000)"
    )

    # wait-url
    p_wait_url = subparsers.add_parser("wait-url", help="Wait for URL to match")
    p_wait_url.add_argument("name", help="Page name")
    p_wait_url.add_argument("url_pattern", help="URL pattern (string or regex)")
    p_wait_url.add_argument(
        "--timeout", type=int, help="Timeout in ms (default: 30000)"
    )

    # wait-load
    p_wait_load = subparsers.add_parser("wait-load", help="Wait for page to fully load")
    p_wait_load.add_argument("name", help="Page name")
    p_wait_load.add_argument(
        "--timeout", type=int, help="Timeout in ms (default: 10000)"
    )

    # close
    p_close = subparsers.add_parser("close", help="Close a page")
    p_close.add_argument("name", help="Page name")

    # info
    p_info = subparsers.add_parser("info", help="Get page information")
    p_info.add_argument("name", help="Page name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        client = BrowserClient(args.session_id)
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    commands = {
        "list": cmd_list,
        "create": cmd_create,
        "goto": cmd_goto,
        "screenshot": cmd_screenshot,
        "click": cmd_click,
        "fill": cmd_fill,
        "hover": cmd_hover,
        "keyboard": cmd_keyboard,
        "evaluate": cmd_evaluate,
        "text": cmd_text,
        "snapshot": cmd_snapshot,
        "select-ref": cmd_select_ref,
        "wait-selector": cmd_wait_selector,
        "wait-url": cmd_wait_url,
        "wait-load": cmd_wait_load,
        "close": cmd_close,
        "info": cmd_info,
    }

    return commands[args.command](client, args)


if __name__ == "__main__":
    sys.exit(main())
