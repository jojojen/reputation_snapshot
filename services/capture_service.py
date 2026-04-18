from __future__ import annotations

import uuid
from typing import Any

from services.storage_service import save_raw_html, save_screenshot, save_visible_text
from utils.db_utils import now_jst_iso
from utils.hash_utils import sha256_bytes, sha256_text
from utils.url_utils import build_mercari_reviews_url, normalize_mercari_url


def capture_profile(profile_url: str) -> dict[str, Any]:
    normalized_url = normalize_mercari_url(profile_url)
    reviews_url = build_mercari_reviews_url(normalized_url)
    capture_id = f"cap_{uuid.uuid4().hex[:12]}"
    captured_at = now_jst_iso()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed. Run scripts\\setup_env.bat first.") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(locale="ja-JP", viewport={"width": 1440, "height": 2200})
            page = context.new_page()
            primary_capture = _capture_page(page, normalized_url, take_screenshot=True)
            review_capture = _capture_optional_review_page(context, reviews_url)
            context.close()
            browser.close()
    except Exception as exc:
        raise RuntimeError(f"Failed to capture profile: {exc}") from exc

    raw_html_path = save_raw_html(capture_id, primary_capture["raw_html"])
    visible_text_path = save_visible_text(capture_id, primary_capture["visible_text"])
    screenshot_path = save_screenshot(capture_id, primary_capture["screenshot_bytes"])

    return {
        "capture_id": capture_id,
        "raw_html": primary_capture["raw_html"],
        "visible_text": primary_capture["visible_text"],
        "raw_html_path": raw_html_path,
        "visible_text_path": visible_text_path,
        "screenshot_path": screenshot_path,
        "raw_html_sha256": sha256_text(primary_capture["raw_html"]),
        "visible_text_sha256": sha256_text(primary_capture["visible_text"]),
        "screenshot_sha256": sha256_bytes(primary_capture["screenshot_bytes"]),
        "http_status": primary_capture["http_status"],
        "captured_at": captured_at,
        "review_url": reviews_url if review_capture.get("http_status") == 200 else None,
        "review_raw_html": review_capture.get("raw_html"),
        "review_visible_text": review_capture.get("visible_text"),
        "review_http_status": review_capture.get("http_status"),
    }


def _capture_page(page: Any, url: str, take_screenshot: bool = False) -> dict[str, Any]:
    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("body", timeout=15000)
    page.wait_for_timeout(3000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass

    raw_html = page.content()
    visible_text = page.evaluate("() => document.body ? document.body.innerText : ''")
    screenshot_bytes = page.screenshot(full_page=True, type="png") if take_screenshot else None

    return {
        "url": url,
        "raw_html": raw_html,
        "visible_text": visible_text,
        "screenshot_bytes": screenshot_bytes,
        "http_status": response.status if response else 200,
    }


def _capture_optional_review_page(context: Any, reviews_url: str) -> dict[str, Any]:
    review_page = context.new_page()
    try:
        capture = _capture_page(review_page, reviews_url, take_screenshot=False)
        if capture["http_status"] >= 400:
            return {"http_status": capture["http_status"]}
        return capture
    except Exception:
        return {"http_status": None}
    finally:
        review_page.close()
