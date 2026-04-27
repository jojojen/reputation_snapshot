from __future__ import annotations

import base64

import app as app_module

from services.proof_service import build_proof
from services.storage_service import insert_capture, insert_proof, insert_review_entries
from utils.hash_utils import sha256_text
from utils.json_utils import pretty_json


PROFILE_RAW_HTML = """
<section data-testid="profile-info">
  <div data-testid="mer-avatar">
    <img src="https://static.mercdn.net/thumb/members/webp/492792377.jpg" alt="山本商店">
  </div>
  <div data-testid="mer-profile-heading">
    <h1>山本商店</h1>
  </div>
  <span data-testid="thumbnail-item-name">ポケモンカード sar</span>
</section>
"""

PROFILE_VISIBLE_TEXT = "\n".join(
    [
        "山本商店",
        "本人確認済",
        "759 出品数",
        "39 フォロワー",
        "0 フォロー中",
    ]
)

REVIEW_VISIBLE_TEXT = "\n".join(
    [
        "評価一覧",
        "良かった (96)",
        "残念だった (4)",
        "購入者",
        "ありがとうございました",
        "2026/04",
        "出品者",
        "良い商品でした",
        "2026/04",
    ]
)

ITEM_RAW_HTML = """
<a href="/user/profile/492792377" data-location="item_details:seller_info"
   aria-label="山本商店, 961件のレビュー, 5段階評価中4.5, 本人確認済">
  山本商店 961
</a>
"""

ITEM_VISIBLE_TEXT = "\n".join(["出品者", "山本商店", "961", "本人確認済"])

ITEM_URL = "https://jp.mercari.com/item/m74005892833"
PROFILE_URL = "https://jp.mercari.com/user/profile/492792377"


def _submit_capture_job(client, query_url: str = ITEM_URL, include_reviews: bool = True) -> dict:
    create_response = client.post("/api/captures", json={"query_url": query_url})
    assert create_response.status_code == 200
    create_payload = create_response.get_json()
    assert create_payload["status"] == "pending"
    job_id = create_payload["job_id"]

    token = client.application.config["ADMIN_TOKEN"]
    payload = {
        "query_kind": "item" if query_url == ITEM_URL else "profile",
        "profile_url": PROFILE_URL,
        "profile_html": PROFILE_RAW_HTML,
        "profile_text": PROFILE_VISIBLE_TEXT,
        "screenshot_base64": base64.b64encode(b"fake-png").decode(),
        "reviews_url": "https://jp.mercari.com/user/reviews/492792377",
        "reviews_html": "" if include_reviews else None,
        "reviews_text": REVIEW_VISIBLE_TEXT if include_reviews else None,
        "reviews_bad_text": "",
        "item_html": ITEM_RAW_HTML if query_url == ITEM_URL else None,
        "item_text": ITEM_VISIBLE_TEXT if query_url == ITEM_URL else None,
        "seller_total_reviews": 961,
        "display_name": "山本商店",
    }
    result_response = client.post(
        f"/api/jobs/{job_id}/result?token={token}",
        json=payload,
    )
    assert result_response.status_code == 200
    assert result_response.get_json()["status"] == "done"

    job_response = client.get(f"/api/jobs/{job_id}")
    assert job_response.status_code == 200
    job_payload = job_response.get_json()
    assert job_payload["status"] == "done"
    job_payload["proof_id"] = job_payload["proof_url"].rsplit("/", 1)[-1]
    return job_payload


def test_index_route(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert b"Mercari Reputation Snapshot" in response.data


def test_capture_job_result_creates_proof_and_verify_roundtrip(client) -> None:
    capture_payload = _submit_capture_job(client)

    proof_response = client.get(f"/api/proofs/{capture_payload['proof_id']}")
    assert proof_response.status_code == 200
    proof_document = proof_response.get_json()
    assert proof_document["subject"]["display_name"] == "山本商店"
    assert proof_document["metrics"]["total_reviews"] == 961
    assert proof_document["metrics"]["positive_reviews"] == 96
    assert proof_document["metrics"]["negative_reviews"] == 4
    assert proof_document["quality"]["entry_count"] == 2
    assert proof_document["quality"]["as_seller"]["positive"] == 1
    assert proof_document["quality"]["as_buyer"]["positive"] == 1

    proof_page_response = client.get(capture_payload["proof_url"])
    assert proof_page_response.status_code == 200
    assert b"Mercari JP" in proof_page_response.data

    verify_response = client.post("/api/verify", json={"proof": proof_document})
    assert verify_response.status_code == 200
    assert verify_response.get_json()["valid"] is True


def test_capture_job_result_fetches_reviews_when_agent_payload_omits_them(client, monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "capture_lookup_page",
        lambda url: {"raw_html": "<html>reviews</html>", "visible_text": REVIEW_VISIBLE_TEXT, "http_status": 200},
    )

    capture_payload = _submit_capture_job(client, include_reviews=False)
    proof_document = client.get(f"/api/proofs/{capture_payload['proof_id']}").get_json()

    assert proof_document["metrics"]["positive_reviews"] == 96
    assert proof_document["metrics"]["negative_reviews"] == 4
    assert proof_document["quality"]["entry_count"] == 2


def test_capture_route_reuses_existing_profile_snapshot(client, monkeypatch) -> None:
    capture_id = "cap_existing_001"
    parsed_data = {
        "display_name": "山本商店",
        "avatar_url": "https://static.mercdn.net/thumb/members/webp/492792377.jpg",
        "verified_badge": True,
        "total_reviews": 961,
        "positive_reviews": 96,
        "negative_reviews": 4,
        "listing_count": 759,
        "followers_count": 39,
        "following_count": 0,
        "bio_excerpt": "ポケモンカード中心の出品です。",
        "sample_items": ["ポケモンカード sar"],
        "parser_version": "mercari_parser_v0",
        "extractor_strategy": "dom_text_regex+review_page+item_page",
        "llm_repair_applied": 0,
        "completeness_status": "full",
    }
    capture_data = {
        "capture_id": capture_id,
        "captured_at": "2026-04-18T09:00:00+09:00",
        "raw_html_sha256": sha256_text(PROFILE_RAW_HTML),
        "visible_text_sha256": sha256_text(PROFILE_VISIBLE_TEXT),
        "screenshot_sha256": sha256_text("profile_existing.png"),
        "raw_html_path": "tests/fixtures/profile_existing.html",
        "visible_text_path": "tests/fixtures/profile_existing.txt",
        "screenshot_path": "tests/fixtures/profile_existing.png",
    }

    insert_capture(
        {
            "id": capture_id,
            "source_url": PROFILE_URL,
            "source_platform": "mercari_jp",
            "display_name": parsed_data["display_name"],
            "avatar_url": parsed_data["avatar_url"],
            "verified_badge": parsed_data["verified_badge"],
            "total_reviews": parsed_data["total_reviews"],
            "positive_reviews": parsed_data["positive_reviews"],
            "negative_reviews": parsed_data["negative_reviews"],
            "listing_count": parsed_data["listing_count"],
            "followers_count": parsed_data["followers_count"],
            "following_count": parsed_data["following_count"],
            "bio_excerpt": parsed_data["bio_excerpt"],
            "sample_items": parsed_data["sample_items"],
            "raw_html_path": capture_data["raw_html_path"],
            "raw_html_sha256": capture_data["raw_html_sha256"],
            "visible_text_path": capture_data["visible_text_path"],
            "visible_text_sha256": capture_data["visible_text_sha256"],
            "screenshot_path": capture_data["screenshot_path"],
            "screenshot_sha256": capture_data["screenshot_sha256"],
            "parser_version": parsed_data["parser_version"],
            "extractor_strategy": parsed_data["extractor_strategy"],
            "llm_repair_applied": parsed_data["llm_repair_applied"],
            "completeness_status": parsed_data["completeness_status"],
            "captured_at": capture_data["captured_at"],
        }
    )

    fake_review_entries = [
        {"role": "seller", "rating": "positive", "body_excerpt": "ありがとうございました", "entry_order": 1},
        {"role": "buyer", "rating": "positive", "body_excerpt": "良い商品でした", "entry_order": 2},
    ]
    insert_review_entries(capture_id, PROFILE_URL, fake_review_entries, capture_data["captured_at"])
    proof_bundle = build_proof(PROFILE_URL, capture_data, parsed_data, review_entries=fake_review_entries)
    insert_proof(
        {
            "id": proof_bundle["proof_id"],
            "capture_id": capture_id,
            "proof_payload_json": pretty_json(proof_bundle["proof_payload"]),
            "proof_sha256": proof_bundle["proof_sha256"],
            "signature": proof_bundle["signature"],
            "kid": proof_bundle["kid"],
            "status": proof_bundle["status"],
            "expires_at": proof_bundle["expires_at"],
            "published_at": proof_bundle["published_at"],
        }
    )

    monkeypatch.setattr(
        app_module,
        "capture_lookup_page",
        lambda url: {"raw_html": "", "visible_text": "購入者\nありがとうございました\n2026/04"},
    )

    capture_response = client.post("/api/captures", json={"query_url": PROFILE_URL})

    assert capture_response.status_code == 200
    capture_payload = capture_response.get_json()
    assert capture_payload["proof_id"] == proof_bundle["proof_id"]
    assert capture_payload["proof_url"] == f"/p/{proof_bundle['proof_id']}"
    assert capture_payload["reused"] is True


def test_revoke_route_updates_proof_status(client) -> None:
    capture_payload = _submit_capture_job(client, PROFILE_URL)
    proof_id = capture_payload["proof_id"]

    revoke_response = client.post(f"/api/proofs/{proof_id}/revoke", json={"reason": "policy_test"})
    assert revoke_response.status_code == 200
    assert revoke_response.get_json()["status"] == "revoked"

    proof_response = client.get(f"/api/proofs/{proof_id}")
    assert proof_response.status_code == 200
    assert proof_response.get_json()["status"] == "revoked"
