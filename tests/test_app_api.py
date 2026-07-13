from __future__ import annotations

import base64
from datetime import datetime, timedelta

import app as app_module

from services.proof_service import build_proof
from services.storage_service import (
    claim_next_capture_job,
    create_capture_job,
    get_capture_job,
    insert_capture,
    insert_proof,
    insert_review_entries,
)
from utils.db_utils import JST
from utils.hash_utils import sha256_text
from utils.json_utils import pretty_json

# build_proof expires proofs older than 30 days; a hardcoded absolute date
# here would age out and flip this test from "reuse valid proof" to "proof
# expired" once real time passed the window (same class of bug as 8e7f998).
RECENT_CAPTURED_AT = (datetime.now(JST) - timedelta(days=1)).replace(microsecond=0).isoformat()


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
    assert proof_document["review_entries"][0]["role"] == "seller"
    assert proof_document["review_entries"][0]["rating"] == "positive"
    assert proof_document["review_entries"][1]["rating"] == "positive"


def test_capture_route_reuses_existing_profile_snapshot(client, monkeypatch) -> None:
    def fail_if_live_check_runs(source_url: str, reviews_url: str) -> bool:
        raise AssertionError("quick profile reuse must not block on live Mercari review checks")

    monkeypatch.setattr(app_module, "_has_new_reviews", fail_if_live_check_runs)
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
        "captured_at": RECENT_CAPTURED_AT,
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

    capture_response = client.post("/api/captures", json={"query_url": PROFILE_URL})

    assert capture_response.status_code == 200
    capture_payload = capture_response.get_json()
    assert capture_payload["proof_id"] == proof_bundle["proof_id"]
    assert capture_payload["proof_url"] == f"/p/{proof_bundle['proof_id']}"
    assert capture_payload["reused"] is True
    proof_document = client.get(f"/api/proofs/{proof_bundle['proof_id']}").get_json()
    assert proof_document["review_entries"][0]["body_excerpt"] == "ありがとうございました"


def test_revoke_route_updates_proof_status(client) -> None:
    capture_payload = _submit_capture_job(client, PROFILE_URL)
    proof_id = capture_payload["proof_id"]

    revoke_response = client.post(f"/api/proofs/{proof_id}/revoke", json={"reason": "policy_test"})
    assert revoke_response.status_code == 200
    assert revoke_response.get_json()["status"] == "revoked"

    proof_response = client.get(f"/api/proofs/{proof_id}")
    assert proof_response.status_code == 200
    assert proof_response.get_json()["status"] == "revoked"


# ── Stale-job reclaim ────────────────────────────────────────────────────────


def test_claim_reclaims_stale_processing_job() -> None:
    from datetime import datetime, timedelta, timezone
    from utils.db_utils import get_db_connection

    # Insert a job that was claimed 10 minutes ago (older than the 8-min lease).
    stale_claimed_at = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    create_capture_job("job_stale", "https://jp.mercari.com/user/profile/stale_seller")
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE capture_jobs SET status = 'processing', claimed_at = ? WHERE id = ?",
            (stale_claimed_at, "job_stale"),
        )
        conn.commit()

    # Insert a newer pending job so we can confirm the stale one gets re-queued first.
    create_capture_job("job_new", "https://jp.mercari.com/user/profile/new_seller")

    # Claiming should reclaim the stale job (oldest created_at = stale) and return it.
    claimed = claim_next_capture_job()
    assert claimed is not None
    assert claimed["id"] == "job_stale"
    assert get_capture_job("job_stale")["status"] == "processing"
    assert get_capture_job("job_new")["status"] == "pending"


def test_claim_does_not_reclaim_fresh_processing_job() -> None:
    from utils.db_utils import get_db_connection

    create_capture_job("job_fresh", "https://jp.mercari.com/user/profile/fresh_seller")
    # Mark as processing with a claimed_at of NOW (within the 8-min lease).
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE capture_jobs SET status = 'processing', claimed_at = datetime('now') WHERE id = ?",
            ("job_fresh",),
        )
        conn.commit()

    # Nothing pending → claim returns None; fresh job remains processing.
    result = claim_next_capture_job()
    assert result is None
    assert get_capture_job("job_fresh")["status"] == "processing"


def test_json_responses_carry_envelope_version(client) -> None:
    """Every JSON object response is stamped with the transport envelope
    version (aka_no_claw#77 D2.4), independent of the signed proof payload."""
    capture_payload = _submit_capture_job(client)
    assert capture_payload["envelope_version"] == app_module.ENVELOPE_VERSION

    proof_response = client.get(f"/api/proofs/{capture_payload['proof_id']}")
    proof_document = proof_response.get_json()
    assert proof_document["envelope_version"] == app_module.ENVELOPE_VERSION

    # The envelope field is transport-only: a client that round-trips the
    # fetched document into /api/verify must still get a valid signature.
    verify_response = client.post("/api/verify", json={"proof": proof_document})
    assert verify_response.status_code == 200
    verify_payload = verify_response.get_json()
    assert verify_payload["valid"] is True
    assert verify_payload["envelope_version"] == app_module.ENVELOPE_VERSION


def test_error_responses_carry_envelope_version(client) -> None:
    response = client.post("/api/captures", json={"query_url": "https://example.com/nope"})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["envelope_version"] == app_module.ENVELOPE_VERSION
