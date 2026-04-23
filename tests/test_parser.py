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

    assert expect["proof_should_generate"] is True

    verify_result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])
    assert verify_result["valid"] is True

    expected_status = "full" if all(
        expect[f"has_{field}"] for field in ("display_name", "total_reviews", "listing_count", "followers_count", "following_count")
    ) else "partial"
    assert parsed["completeness_status"] == expected_status


def test_parser_prefers_profile_total_reviews_over_breakdown_sum() -> None:
    raw_html = """
    <section data-testid="profile-info">
      <div data-testid="mer-avatar">
        <img src="https://static.mercdn.net/thumb/members/webp/492792377.jpg" alt="山本商店">
      </div>
      <div data-testid="mer-profile-heading">
        <h1>山本商店</h1>
      </div>
      <span data-testid="thumbnail-item-name">ゲッコウガsar</span>
    </section>
    """
    visible_text = "\n".join(
        [
            "山本商店",
            "961",
            "本人確認済",
            "759 出品数",
            "39 フォロワー",
            "0 フォロー中",
        ]
    )
    review_visible_text = "\n".join(["山本商店", "良い (96)", "残念だった (4)"])

    parsed = parse_profile(raw_html, visible_text, review_visible_text=review_visible_text)

    assert parsed["display_name"] == "山本商店"
    assert parsed["positive_reviews"] == 96
    assert parsed["negative_reviews"] == 4
    assert parsed["total_reviews"] == 961
    assert parsed["sample_items"] == ["ゲッコウガsar"]
    assert parsed["extractor_strategy"] == "dom_text_regex+review_page"


def test_parser_uses_item_context_for_total_reviews() -> None:
    raw_html = """
    <section data-testid="profile-info">
      <div data-testid="mer-avatar">
        <img src="https://static.mercdn.net/thumb/members/webp/492792377.jpg" alt="山本商店">
      </div>
      <div data-testid="mer-profile-heading">
        <h1>山本商店</h1>
      </div>
    </section>
    """
    visible_text = "\n".join(["山本商店", "本人確認済", "759 出品数", "39 フォロワー", "0 フォロー中"])
    review_visible_text = "\n".join(["良い (96)", "残念だった (4)"])
    item_raw_html = """
    <a href="/user/profile/492792377" data-location="item_details:seller_info"
       aria-label="山本商店, 961件のレビュー, 5段階評価中4.5, 本人確認済">
      山本商店 961
    </a>
    """

    parsed = parse_profile(
        raw_html,
        visible_text,
        review_visible_text=review_visible_text,
        item_raw_html=item_raw_html,
        item_total_reviews=961,
    )

    assert parsed["display_name"] == "山本商店"
    assert parsed["positive_reviews"] == 96
    assert parsed["negative_reviews"] == 4
    assert parsed["total_reviews"] == 961
    assert parsed["extractor_strategy"] == "dom_text_regex+review_page+item_page"


def test_parser_supports_label_first_metric_layout() -> None:
    raw_html = """
    <section data-testid="profile-info">
      <div data-testid="mer-avatar">
        <img src="https://static.mercdn.net/thumb/members/webp/492792377.jpg" alt="賣家A">
      </div>
      <div data-testid="mer-profile-heading">
        <h1>賣家A</h1>
      </div>
    </section>
    """
    visible_text = "\n".join(
        [
            "賣家A",
            "評価 961",
            "出品数 759",
            "フォロワー 39",
            "フォロー中 0",
        ]
    )

    parsed = parse_profile(raw_html, visible_text)

    assert parsed["display_name"] == "賣家A"
    assert parsed["total_reviews"] == 961
    assert parsed["listing_count"] == 759
    assert parsed["followers_count"] == 39
    assert parsed["following_count"] == 0


def test_parser_rejects_company_page_noise_as_identity_or_items() -> None:
    raw_html = """
    <html>
      <head><title>メルカリについて 会社概要（運営会社）</title></head>
      <body>
        <h1>メルカリについて 会社概要（運営会社）</h1>
        <ul>
          <li>メルカリについて</li>
          <li>会社概要（運営会社）</li>
        </ul>
      </body>
    </html>
    """
    visible_text = "\n".join(
        [
            "メルカリについて 会社概要（運営会社）",
            "メルカリについて",
            "会社概要（運営会社）",
        ]
    )

    parsed = parse_profile(raw_html, visible_text)

    assert parsed["display_name"] is None
    assert parsed["sample_items"] == []
