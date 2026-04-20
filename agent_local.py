#!/usr/bin/env python3
"""
Local capture agent — keeps running on your PC, polls Fly.io for pending jobs,
does Playwright scraping locally (residential IP), and sends results back.

Usage:
    python agent_local.py

Required env vars (set once in PowerShell, or add to .env):
    ADMIN_TOKEN   — same as the server's ADMIN_TOKEN
    SERVER_URL    — defaults to https://reputation-snapshot.fly.dev
"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html import unescape
from urllib.parse import urlparse

SERVER_URL = os.getenv("SERVER_URL", "https://reputation-snapshot.fly.dev").rstrip("/")
API_KEY    = os.getenv("ADMIN_TOKEN", "")
POLL_SECS  = 5
MERCARI_HOST = "jp.mercari.com"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _post(path: str, body: dict) -> dict:
    url = f"{SERVER_URL}{path}?token={API_KEY}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def _get(path: str) -> dict:
    url = f"{SERVER_URL}{path}?token={API_KEY}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())


# ── Playwright helpers ────────────────────────────────────────────────────────

def _capture_page(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("body", timeout=15000)
    page.wait_for_timeout(2000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    return {
        "raw_html":     page.content(),
        "visible_text": page.evaluate("() => document.body ? document.body.innerText : ''"),
    }


def _find_profile_url(html: str) -> str | None:
    for pat in [r'href="(/user/profile/([A-Za-z0-9_-]+))"',
                r'["\x27](/user/profile/([A-Za-z0-9_-]+))["\x27]']:
        m = re.search(pat, html)
        if m:
            return f"https://{MERCARI_HOST}{unescape(m.group(1))}"
    return None


def _run_capture(query_url: str) -> dict:
    from playwright.sync_api import sync_playwright

    path = urlparse(query_url.strip()).path.rstrip("/")
    is_item = "/item/" in path

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage"],
        )
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
        query_kind = "profile"

        if is_item:
            pg = ctx.new_page()
            d = _capture_page(pg, f"https://{MERCARI_HOST}{path}")
            item_html, item_text = d["raw_html"], d["visible_text"]
            pg.close()
            query_kind = "item"
            profile_url = _find_profile_url(item_html)
            if not profile_url:
                raise RuntimeError("Could not find seller profile in item page.")
        else:
            profile_url = f"https://{MERCARI_HOST}{path}"

        # Profile page
        pg = ctx.new_page()
        pg.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_selector("body", timeout=15000)
        pg.wait_for_timeout(2000)
        try:
            pg.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        profile_html = pg.content()
        profile_text = pg.evaluate("() => document.body ? document.body.innerText : ''")
        screenshot_bytes = pg.screenshot(full_page=True, type="png")
        pg.close()

        # Reviews page
        profile_id   = profile_url.rstrip("/").split("/")[-1]
        reviews_url  = f"https://{MERCARI_HOST}/user/reviews/{profile_id}"
        reviews_html = reviews_text = reviews_bad_text = None
        try:
            rpg = ctx.new_page()
            rd = _capture_page(rpg, reviews_url)
            reviews_html, reviews_text = rd["raw_html"], rd["visible_text"]
            try:
                bad_btn = rpg.query_selector('[aria-controls="bad"]')
                if bad_btn:
                    bad_btn.click()
                    rpg.wait_for_timeout(2000)
                    reviews_bad_text = rpg.evaluate(
                        "() => document.body ? document.body.innerText : ''"
                    )
            except Exception:
                pass
            rpg.close()
        except Exception as e:
            print(f"  [warn] reviews capture skipped: {e}")

        ctx.close()
        browser.close()

    return {
        "query_kind":       query_kind,
        "profile_url":      profile_url,
        "profile_html":     profile_html,
        "profile_text":     profile_text,
        "screenshot_base64": base64.b64encode(screenshot_bytes).decode() if screenshot_bytes else None,
        "reviews_url":      reviews_url,
        "reviews_html":     reviews_html,
        "reviews_text":     reviews_text,
        "reviews_bad_text": reviews_bad_text,
        "item_html":        item_html,
        "item_text":        item_text,
    }


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    if not API_KEY:
        print("ERROR: Set ADMIN_TOKEN env var first.")
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright as _  # noqa
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    print(f"Agent running — polling {SERVER_URL} every {POLL_SECS}s  (Ctrl+C to stop)")

    while True:
        try:
            resp = _get("/api/jobs/claim")
            job = resp.get("job")

            if job is None:
                time.sleep(POLL_SECS)
                continue

            job_id    = job["job_id"]
            query_url = job["query_url"]
            print(f"[job {job_id}] {query_url}")

            try:
                result = _run_capture(query_url)
                out = _post(f"/api/jobs/{job_id}/result", result)
                print(f"[job {job_id}] done → {SERVER_URL}{out.get('proof_url','')}")
            except Exception as exc:
                print(f"[job {job_id}] FAILED: {exc}")
                try:
                    _post(f"/api/jobs/{job_id}/result", {"error": str(exc)})
                except Exception:
                    pass

        except KeyboardInterrupt:
            print("\nAgent stopped.")
            break
        except Exception as e:
            print(f"[poll error] {e}")
            time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()
