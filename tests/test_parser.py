from __future__ import annotations

from pathlib import Path

import pytest

from services.parser_mercari import parse_profile
from services.proof_service import build_proof
from services.verify_service import verify_proof
from utils.hash_utils import sha256_text
from utils.json_utils import load_json


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TEST_CASES = load_json(Path(__file__).resolve().parent / "test_cases.json")


def _fixture_text(fixture_name: str, extension: str) -> str:
    return (FIXTURE_DIR / f"{fixture_name}.{extension}").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", TEST_CASES, ids=[case["name"] for case in TEST_CASES])
def test_parser_cases(case: dict) -> None:
    raw_html = _fixture_text(case["fixture"], "html")
    visible_text = _fixture_text(case["fixture"], "txt")
    parsed = parse_profile(raw_html, visible_text)
    expect = case["expect"]

    assert (parsed["display_name"] is not None) is expect["has_display_name"]
    assert (parsed["total_reviews"] is not None) is expect["has_total_reviews"]
    assert (parsed["listing_count"] is not None) is expect["has_listing_count"]
    assert (parsed["followers_count"] is not None) is expect["has_followers_count"]
    assert (parsed["following_count"] is not None) is expect["has_following_count"]

    capture_data = {
        "captured_at": "2026-04-18T09:00:00+09:00",
        "raw_html_sha256": sha256_text(raw_html),
        "visible_text_sha256": sha256_text(visible_text),
        "screenshot_sha256": sha256_text(case["fixture"]),
    }
    proof_bundle = build_proof(case["url"], capture_data, parsed)
    score_value = proof_bundle["proof_payload"]["score"]["value"]

    assert expect["proof_should_generate"] is True
    assert expect["min_score"] <= score_value <= expect["max_score"]

    verify_result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])
    assert verify_result["valid"] is True

    expected_status = "full" if all(expect[f"has_{field}"] for field in ("display_name", "total_reviews", "listing_count", "followers_count", "following_count")) else "partial"
    assert parsed["completeness_status"] == expected_status


def test_parser_uses_reviews_page_for_review_breakdown() -> None:
    raw_html = _fixture_text("fixture_review_bridge_profile", "html")
    visible_text = _fixture_text("fixture_review_bridge_profile", "txt")
    review_visible_text = _fixture_text("fixture_review_bridge_reviews", "txt")

    parsed = parse_profile(raw_html, visible_text, review_visible_text=review_visible_text)

    assert parsed["display_name"] == "山本商店"
    assert parsed["positive_reviews"] == 96
    assert parsed["negative_reviews"] == 4
    assert parsed["total_reviews"] == 100
    assert parsed["sample_items"][:3] == ["ゲッコウガsar", "ゼクロム ex ポケモンカード 230HP", "ナンジャモ SAR"]
    assert parsed["extractor_strategy"] == "dom_text_regex+review_page"
