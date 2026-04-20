#!/usr/bin/env python3
"""
Local capture script — runs Playwright on YOUR machine (residential IP).
Sends the captured data to the Fly.io server for proof generation.

Usage:
    python capture_local.py <mercari_url>
    python capture_local.py          # prompts for URL

Required env vars (set in .env or PowerShell):
    ADMIN_TOKEN   — same token as the server's ADMIN_TOKEN
    SERVER_URL    — defaults to https://reputation-snapshot.fly.dev
"""
import base64
import os
import re
import sys
import webbrowser
from html import unescape
from urllib.parse import urlparse

SERVER_URL = os.getenv("SERVER_URL", "https://reputation-snapshot.fly.dev").rstrip("/")
API_KEY = os.getenv("ADMIN_TOKEN", "")

MERCARI_HOST = "jp.mercari.com"


def _normalize_path(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed.path.rstrip("/")


def _capture_page(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("body", timeout=15000)
    page.wait_for_timeout(2000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    return {
        "raw_html": page.content(),
        "visible_text": page.evaluate("() => document.body ? document.body.innerText : ''"),
    }


def _find_profile_url_in_html(html: str) -> str | None:
    for pat in [
        r'href="(/user/profile/([A-Za-z0-9_-]+))"',
        r'["\x27](/user/profile/([A-Za-z0-9_-]+))["\x27]',
    ]:
        m = re.search(pat, html)
        if m:
            return f"https://{MERCARI_HOST}{unescape(m.group(1))}"
    return None


def main() -> None:
    query_url = (sys.argv[1] if len(sys.argv) > 1 else input("Mercari URL: ")).strip()

    if not API_KEY:
        print("ERROR: Set ADMIN_TOKEN env var (same value as server's ADMIN_TOKEN)")
        sys.exit(1)

    path = _normalize_path(query_url)
    is_item = "/item/" in path

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    print(f"[1/4] Starting browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="ja-JP",
            viewport={"width": 1440, "height": 2200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        item_html = item_text = None
        profile_url = None
        seller_total_reviews = None
        display_name = None
        query_kind = "profile"

        if is_item:
            print(f"[2/4] Capturing item page...")
            item_page = ctx.new_page()
            item_data = _capture_page(item_page, f"https://{MERCARI_HOST}{path}")
            item_html = item_data["raw_html"]
            item_text = item_data["visible_text"]
            item_page.close()
            query_kind = "item"

            profile_url = _find_profile_url_in_html(item_html)
            if not profile_url:
                print("ERROR: Could not find seller profile link in item page.")
                sys.exit(1)
            print(f"       Seller: {profile_url}")
        else:
            profile_url = f"https://{MERCARI_HOST}{path}"
            print(f"[2/4] Profile URL: {profile_url}")

        print(f"[3/4] Capturing profile page...")
        profile_page = ctx.new_page()
        profile_page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        profile_page.wait_for_selector("body", timeout=15000)
        profile_page.wait_for_timeout(2000)
        try:
            profile_page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        profile_html = profile_page.content()
        profile_text = profile_page.evaluate("() => document.body ? document.body.innerText : ''")
        screenshot_bytes = profile_page.screenshot(full_page=True, type="png")
        profile_page.close()

        profile_id = profile_url.rstrip("/").split("/")[-1]
        reviews_url = f"https://{MERCARI_HOST}/user/reviews/{profile_id}"
        reviews_html = reviews_text = reviews_bad_text = None

        try:
            reviews_page = ctx.new_page()
            r = _capture_page(reviews_page, reviews_url)
            reviews_html = r["raw_html"]
            reviews_text = r["visible_text"]
            try:
                bad_btn = reviews_page.query_selector('[aria-controls="bad"]')
                if bad_btn:
                    bad_btn.click()
                    reviews_page.wait_for_timeout(2000)
                    reviews_bad_text = reviews_page.evaluate(
                        "() => document.body ? document.body.innerText : ''"
                    )
            except Exception:
                pass
            reviews_page.close()
        except Exception as e:
            print(f"       Reviews capture failed (non-fatal): {e}")

        ctx.close()
        browser.close()

    print(f"[4/4] Sending to {SERVER_URL} ...")
    try:
        import urllib.request
        import json as _json

        payload = {
            "api_key": API_KEY,
            "query_url": query_url,
            "query_kind": query_kind,
            "profile_url": profile_url,
            "profile_html": profile_html,
            "profile_text": profile_text,
            "screenshot_base64": base64.b64encode(screenshot_bytes).decode() if screenshot_bytes else None,
            "reviews_url": reviews_url,
            "reviews_html": reviews_html,
            "reviews_text": reviews_text,
            "reviews_bad_text": reviews_bad_text,
            "item_html": item_html,
            "item_text": item_text,
            "seller_total_reviews": seller_total_reviews,
            "display_name": display_name,
        }
        body = _json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{SERVER_URL}/api/raw-capture",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = _json.loads(resp.read().decode())
    except Exception as e:
        print(f"ERROR sending to server: {e}")
        sys.exit(1)

    if "error" in data:
        print(f"ERROR from server: {data['error']}")
        sys.exit(1)

    proof_url = f"{SERVER_URL}{data['proof_url']}"
    reused = data.get("reused", False)
    print(f"\n{'[Reused existing proof]' if reused else '[New proof created]'}")
    print(f"Proof URL: {proof_url}")
    webbrowser.open(proof_url)


if __name__ == "__main__":
    main()
