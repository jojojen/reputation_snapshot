from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from services.capture_service import capture_profile, resolve_profile_reference
from services.parser_mercari import parse_profile, parse_review_entries
from services.proof_service import build_proof
from services.verify_service import verify_proof


RUN_LIVE_CAPTURE_TESTS = os.environ.get("RUN_LIVE_CAPTURE_TESTS", "1") != "0"
DEFAULT_LIVE_URLS = [
    "https://jp.mercari.com/user/profile/492792377",
    "https://jp.mercari.com/user/profile/839104844",
    "https://jp.mercari.com/user/profile/839104844",
]
LIVE_URLS = [url.strip() for url in os.environ.get("MERCARI_LIVE_TEST_URLS", ",".join(DEFAULT_LIVE_URLS)).split(",") if url.strip()]
LIVE_ITEM_URLS = json.loads((Path(__file__).resolve().parent / "live_item_urls.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(
    not RUN_LIVE_CAPTURE_TESTS,
    reason="Set RUN_LIVE_CAPTURE_TESTS=0 to disable live Playwright capture tests.",
)


@pytest.mark.parametrize("profile_url", LIVE_URLS[:3])
def test_live_capture_smoke(profile_url: str) -> None:
    capture = capture_profile(profile_url)

    assert capture["http_status"] == 200
    assert capture["raw_html"]
    assert capture["visible_text"]
    assert capture["raw_html_sha256"]
    assert capture["visible_text_sha256"]
    assert capture["screenshot_sha256"]

    parsed = parse_profile(
        capture["raw_html"],
        capture["visible_text"],
        review_raw_html=capture.get("review_raw_html"),
        review_visible_text=capture.get("review_visible_text"),
    )
    review_entries = parse_review_entries(
        capture.get("review_raw_html"),
        capture.get("review_visible_text"),
        capture.get("review_bad_visible_text"),
        review_buyer_visible_text=capture.get("review_buyer_visible_text"),
        review_buyer_bad_visible_text=capture.get("review_buyer_bad_visible_text"),
    )
    assert parsed["display_name"] is not None or parsed["total_reviews"] is not None
    if profile_url.endswith("/492792377"):
        assert parsed["positive_reviews"] is not None
        assert parsed["negative_reviews"] is not None
        assert parsed["total_reviews"] is not None
        assert parsed["total_reviews"] >= parsed["positive_reviews"] + parsed["negative_reviews"]
        assert review_entries

    proof_bundle = build_proof(profile_url, capture, parsed, review_entries=review_entries)
    verify_result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])

    assert verify_result["valid"] is True


@pytest.mark.parametrize("item_url", LIVE_ITEM_URLS[:5])
def test_live_item_url_generates_review_quality(item_url: str) -> None:
    resolution = resolve_profile_reference(item_url)
    assert resolution["query_kind"] == "item"
    assert resolution["profile_url"]

    capture = capture_profile(resolution["profile_url"])
    review_entries = parse_review_entries(
        capture.get("review_raw_html"),
        capture.get("review_visible_text"),
        capture.get("review_bad_visible_text"),
        review_buyer_visible_text=capture.get("review_buyer_visible_text"),
        review_buyer_bad_visible_text=capture.get("review_buyer_bad_visible_text"),
    )
    parsed = parse_profile(
        capture["raw_html"],
        capture["visible_text"],
        review_raw_html=capture.get("review_raw_html"),
        review_visible_text=capture.get("review_visible_text"),
        item_raw_html=resolution.get("item_raw_html"),
        item_visible_text=resolution.get("item_visible_text"),
        item_total_reviews=resolution.get("seller_total_reviews"),
    )
    if parsed.get("display_name") is None and resolution.get("display_name"):
        parsed["display_name"] = resolution["display_name"]

    proof_bundle = build_proof(resolution["profile_url"], capture, parsed, review_entries=review_entries)
    proof = proof_bundle["proof_payload"]
    verify_result = verify_proof(proof, proof_bundle["signature"])

    assert verify_result["valid"] is True
    assert parsed["display_name"] is not None
    assert parsed["total_reviews"] is not None
    assert parsed["positive_reviews"] is not None
    assert parsed["negative_reviews"] is not None
    assert review_entries
    assert proof["quality"] is not None
    assert proof["quality"]["entry_count"] > 0
    assert proof["quality"]["as_seller"] or proof["quality"]["as_buyer"]
