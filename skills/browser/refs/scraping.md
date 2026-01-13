# Data Scraping Guide

For large datasets (followers, posts, search results), **intercept and replay network requests** rather than scrolling and parsing the DOM. This is faster, more reliable, and handles pagination automatically.

## Why Not Scroll?

Scrolling is slow, unreliable, and wastes time. APIs return structured data with pagination built in. Always prefer API replay.

## Start Small, Then Scale

**Don't try to automate everything at once.** Work incrementally:

1. **Capture one request** - verify you're intercepting the right endpoint
2. **Inspect one response** - understand the schema before writing extraction code
3. **Extract a few items** - make sure your parsing logic works
4. **Then scale up** - add pagination loop only after the basics work

This prevents wasting time debugging a complex script when the issue is a simple path like `data.user.timeline` vs `data.user.result.timeline`.

## Step-by-Step Workflow

### 1. Capture Request Details

Intercept requests to find API endpoints and headers:

```bash
cd skills/browser && uv run python <<'EOF'
from client import BrowserClient
import json

client = BrowserClient()
page = client.get_playwright_page("main")

captured = []
def on_request(request):
    url = request.url
    if "/api/" in url or "/graphql/" in url:
        captured.append({
            "url": url,
            "method": request.method,
            "headers": dict(request.headers),
        })
        print(f"Captured: {url[:80]}...")

page.on("request", on_request)
page.goto("https://example.com/profile")
page.wait_for_timeout(3000)

with open("tmp/request-details.json", "w") as f:
    json.dump(captured, f, indent=2)
print(f"Saved {len(captured)} requests")
EOF
```

### 2. Capture Response to Understand Schema

Save a response to inspect the data structure:

```bash
cd skills/browser && uv run python <<'EOF'
from client import BrowserClient
import json

client = BrowserClient()
page = client.get_playwright_page("main")

def on_response(response):
    url = response.url
    if "api/posts" in url or "graphql" in url:
        try:
            data = response.json()
            with open("tmp/api-response.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"Captured response from: {url[:60]}...")
        except:
            pass

page.on("response", on_response)
page.reload()
page.wait_for_timeout(3000)
EOF
```

Then analyze the structure to find:

- Where the data array lives (e.g., `data.posts`, `data.items`)
- Where pagination cursors are (e.g., `next_cursor`, `has_more`)
- What fields you need to extract

### 3. Replay API with Pagination

Once you understand the schema, replay requests directly:

```bash
cd skills/browser && uv run python <<'EOF'
from client import BrowserClient
import json
import time

client = BrowserClient()
page = client.get_playwright_page("main")

# Load captured headers
with open("tmp/request-details.json") as f:
    headers = json.load(f)[0]["headers"]

results = {}  # Use dict for deduplication
cursor = None
base_url = "https://example.com/api/posts"

while True:
    # Build URL with pagination
    url = f"{base_url}?limit=20"
    if cursor:
        url += f"&cursor={cursor}"

    # Fetch in browser context (inherits cookies)
    data = page.evaluate("""
        async (params) => {
            const res = await fetch(params.url, { headers: params.headers });
            return res.json();
        }
    """, {"url": url, "headers": headers})

    # Extract items (deduplicate by id)
    items = data.get("posts", [])
    for item in items:
        if item.get("id") and item["id"] not in results:
            results[item["id"]] = item
    print(f"Fetched {len(items)} items, total: {len(results)}")

    # Check for more pages
    cursor = data.get("next_cursor")
    if not cursor or not items:
        break

    time.sleep(0.5)  # Rate limiting

# Save results
with open("results.json", "w") as f:
    json.dump(list(results.values()), f, indent=2)
print(f"Saved {len(results)} items")
EOF
```

## Key Patterns

| Pattern | Description |
|---------|-------------|
| `page.on("request")` | Capture outgoing request URL + headers |
| `page.on("response")` | Capture response data to understand schema |
| `page.evaluate(fetch)` | Replay requests in browser context (inherits auth) |
| `dict` for deduplication | APIs often return overlapping data across pages |
| Cursor-based pagination | Look for `cursor`, `next_token`, `offset` in responses |

## Tips

- **Rate limiting**: Add 500ms+ delays between requests to avoid blocks
- **Stop conditions**: Check for empty results, missing cursor, or reaching a date/ID/count threshold
- **Auth cookies**: Using `page.evaluate` + `fetch()` inherits the browser's cookies
- **GraphQL APIs**: URL params often include `variables` and `features` JSON objects - capture and reuse them
