from __future__ import annotations

import re
import uuid
from html import unescape
from typing import Any

from services.storage_service import save_raw_html, save_screenshot, save_visible_text
from utils.db_utils import now_jst_iso
from utils.hash_utils import sha256_bytes, sha256_text
from utils.url_utils import (
    MERCARI_ITEM_URL_ERROR,
    build_absolute_mercari_url,
    build_mercari_reviews_url,
    mercari_url_kind,
    normalize_mercari_profile_url,
    normalize_mercari_url,
)


def capture_profile(profile_url: str) -> dict[str, Any]:
    normalized_url = normalize_mercari_profile_url(profile_url)
    reviews_url = build_mercari_reviews_url(normalized_url)
    capture_id = f"cap_{uuid.uuid4().hex[:12]}"
    captured_at = now_jst_iso()

    try:
        with _mercari_browser_context() as context:
            page = context.new_page()
            primary_capture = _capture_page(page, normalized_url, take_screenshot=True)
            review_capture = _capture_optional_review_page(context, reviews_url)
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
        "review_bad_visible_text": review_capture.get("bad_visible_text"),
        "review_http_status": review_capture.get("http_status"),
    }


def resolve_profile_reference(query_url: str) -> dict[str, Any]:
    normalized_url = normalize_mercari_url(query_url)
    query_kind = mercari_url_kind(normalized_url)

    if query_kind == "profile":
        return {
            "query_url": normalized_url,
            "query_kind": query_kind,
            "profile_url": normalized_url,
            "item_url": None,
            "item_raw_html": None,
            "item_visible_text": None,
            "display_name": None,
            "seller_total_reviews": None,
        }

    if query_kind != "item":
        raise ValueError(MERCARI_ITEM_URL_ERROR)

    item_capture = capture_lookup_page(normalized_url)
    seller_context = extract_item_seller_context(item_capture["raw_html"], item_capture["visible_text"])
    if not seller_context.get("profile_url"):
        raise RuntimeError("Unable to extract seller profile from the Mercari item page.")

    return {
        "query_url": normalized_url,
        "query_kind": query_kind,
        "profile_url": seller_context["profile_url"],
        "item_url": normalized_url,
        "item_raw_html": item_capture["raw_html"],
        "item_visible_text": item_capture["visible_text"],
        "display_name": seller_context.get("display_name"),
        "seller_total_reviews": seller_context.get("seller_total_reviews"),
    }


def capture_lookup_page(query_url: str) -> dict[str, Any]:
    normalized_url = normalize_mercari_url(query_url)
    try:
        with _mercari_browser_context() as context:
            page = context.new_page()
            capture = _capture_page(page, normalized_url, take_screenshot=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to inspect Mercari page: {exc}") from exc
    return capture


def extract_item_seller_context(raw_html: str, visible_text: str) -> dict[str, Any]:
    context: dict[str, Any] = {
        "profile_url": None,
        "display_name": None,
        "seller_total_reviews": None,
    }

    anchor_match = re.search(
        r'<a[^>]+href="(?P<href>/user/profile/[^"]+)"[^>]*?(?:data-location="item_details:seller_info"|aria-label="[^"]*件のレビュー)[^>]*?(?:aria-label="(?P<label>[^"]+)")?[^>]*>',
        raw_html,
        re.IGNORECASE | re.DOTALL,
    )
    if anchor_match:
        context["profile_url"] = build_absolute_mercari_url(unescape(anchor_match.group("href")))
        label = unescape(anchor_match.group("label") or "")
        if label:
            label_context = _parse_item_seller_label(label)
            context.update({key: value for key, value in label_context.items() if value is not None})

    line_context = _extract_item_seller_from_lines(visible_text)
    for key, value in line_context.items():
        if context.get(key) is None and value is not None:
            context[key] = value

    if context["profile_url"] is None:
        href_match = re.search(r'href="(/user/profile/[^"]+)"', raw_html, re.IGNORECASE)
        if href_match:
            context["profile_url"] = build_absolute_mercari_url(unescape(href_match.group(1)))

    return context


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
        good_html = capture["raw_html"]
        good_text = capture["visible_text"]
        # Also capture the bad (残念だった) tab by clicking it
        bad_text = ""
        try:
            bad_btn = review_page.query_selector('[aria-controls="bad"]')
            if bad_btn:
                bad_btn.click()
                review_page.wait_for_timeout(2000)
                bad_text = review_page.evaluate("() => document.body ? document.body.innerText : ''")
        except Exception:
            pass
        return {
            "raw_html": good_html,
            "visible_text": good_text,
            "bad_visible_text": bad_text,
            "http_status": capture["http_status"],
        }
    except Exception:
        return {"http_status": None}
    finally:
        review_page.close()


def _parse_item_seller_label(label: str) -> dict[str, Any]:
    parts = [part.strip() for part in label.split(",") if part.strip()]
    display_name = parts[0] if parts else None
    total_reviews = None
    total_match = re.search(r"([\d,]+)\s*件のレビュー", label)
    if total_match:
        total_reviews = int(total_match.group(1).replace(",", ""))
    return {
        "display_name": display_name or None,
        "seller_total_reviews": total_reviews,
    }


def _extract_item_seller_from_lines(visible_text: str) -> dict[str, Any]:
    lines = _extract_lines(visible_text)
    try:
        seller_index = lines.index("出品者")
    except ValueError:
        seller_index = -1

    seller_window = lines[seller_index + 1 : seller_index + 6] if seller_index >= 0 else lines[:12]
    display_name = None
    total_reviews = None

    for line in seller_window:
        combined_match = re.fullmatch(r"(.+?)\s+([\d,]+)", line)
        if combined_match and display_name is None:
            display_name = combined_match.group(1).strip()
            total_reviews = int(combined_match.group(2).replace(",", ""))
            break

    if display_name is None:
        for line in seller_window:
            if _looks_like_seller_name(line):
                display_name = line
                break

    if total_reviews is None:
        for line in seller_window:
            if re.fullmatch(r"[\d,]+", line):
                total_reviews = int(line.replace(",", ""))
                break

    return {
        "display_name": display_name,
        "seller_total_reviews": total_reviews,
    }


def _extract_lines(visible_text: str) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in visible_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def _looks_like_seller_name(line: str) -> bool:
    if not line or line in {"本人確認済", "フォロー", "コメント"}:
        return False
    if re.search(r"(税込|送料|分前|出品者レベル|レビュー|出品数|フォロワー|フォロー中)", line):
        return False
    if re.fullmatch(r"[\d,]+", line):
        return False
    return True


def _mercari_browser_context():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed. Run scripts\\setup_env.bat first.") from exc

    class _BrowserContextManager:
        def __enter__(self):
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.context = self.browser.new_context(locale="ja-JP", viewport={"width": 1440, "height": 2200})
            return self.context

        def __exit__(self, exc_type, exc, tb):
            self.context.close()
            self.browser.close()
            self.playwright.stop()

    return _BrowserContextManager()
