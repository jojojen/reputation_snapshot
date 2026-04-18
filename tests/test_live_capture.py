from __future__ import annotations

import os

import pytest

from services.capture_service import capture_profile
from services.parser_mercari import parse_profile
from services.proof_service import build_proof
from services.verify_service import verify_proof


RUN_LIVE_CAPTURE_TESTS = os.environ.get("RUN_LIVE_CAPTURE_TESTS", "1") != "0"
DEFAULT_LIVE_URLS = [
    "https://jp.mercari.com/user/profile/492792377",
    "https://jp.mercari.com/user/profile/839104844",
    "https://jp.mercari.com/user/profile/839104844",
]
LIVE_URLS = [url.strip() for url in os.environ.get("MERCARI_LIVE_TEST_URLS", ",".join(DEFAULT_LIVE_URLS)).split(",") if url.strip()]

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
    assert parsed["display_name"] is not None or parsed["total_reviews"] is not None
    if profile_url.endswith("/492792377"):
        assert parsed["positive_reviews"] is not None
        assert parsed["negative_reviews"] is not None

    proof_bundle = build_proof(profile_url, capture, parsed)
    verify_result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])

    assert verify_result["valid"] is True
