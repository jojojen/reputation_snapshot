from __future__ import annotations

from pathlib import Path

from services.parser_mercari import parse_profile
from services.proof_service import build_proof
from services.storage_service import insert_capture, insert_proof, revoke_proof
from services.verify_service import verify_proof
from utils.hash_utils import sha256_text
from utils.json_utils import pretty_json


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _fixture_text(fixture_name: str, extension: str) -> str:
    return (FIXTURE_DIR / f"{fixture_name}.{extension}").read_text(encoding="utf-8")


def _build_fixture_bundle(fixture_name: str = "fixture_high") -> tuple[str, str, dict, dict]:
    raw_html = _fixture_text(fixture_name, "html")
    visible_text = _fixture_text(fixture_name, "txt")
    parsed = parse_profile(raw_html, visible_text)
    capture_data = {
        "capture_id": "cap_fixture",
        "captured_at": "2026-04-18T09:00:00+09:00",
        "raw_html_sha256": sha256_text(raw_html),
        "visible_text_sha256": sha256_text(visible_text),
        "screenshot_sha256": sha256_text("fixture_screenshot"),
        "raw_html_path": str(FIXTURE_DIR / f"{fixture_name}.html"),
        "visible_text_path": str(FIXTURE_DIR / f"{fixture_name}.txt"),
        "screenshot_path": str(FIXTURE_DIR / f"{fixture_name}.png"),
    }
    return raw_html, visible_text, parsed, capture_data


def test_build_and_verify_roundtrip() -> None:
    _, _, parsed, capture_data = _build_fixture_bundle("fixture_high")
    proof_bundle = build_proof("https://jp.mercari.com/user/profile/verify01", capture_data, parsed)

    result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])

    assert result == {"valid": True, "reason": None, "status": "active"}


def test_verify_detects_expired_proof() -> None:
    _, _, parsed, capture_data = _build_fixture_bundle("fixture_low")
    proof_bundle = build_proof("https://jp.mercari.com/user/profile/verify02", capture_data, parsed, expires_in_days=-1)

    result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])

    assert result["valid"] is False
    assert result["status"] == "expired"


def test_verify_detects_revoked_proof() -> None:
    raw_html, visible_text, parsed, capture_data = _build_fixture_bundle("fixture_medium")
    insert_capture(
        {
            "id": capture_data["capture_id"],
            "source_url": "https://jp.mercari.com/user/profile/verify03",
            "source_platform": "mercari_jp",
            "display_name": parsed.get("display_name"),
            "avatar_url": parsed.get("avatar_url"),
            "verified_badge": parsed.get("verified_badge"),
            "total_reviews": parsed.get("total_reviews"),
            "positive_reviews": parsed.get("positive_reviews"),
            "negative_reviews": parsed.get("negative_reviews"),
            "listing_count": parsed.get("listing_count"),
            "followers_count": parsed.get("followers_count"),
            "following_count": parsed.get("following_count"),
            "bio_excerpt": parsed.get("bio_excerpt"),
            "sample_items": parsed.get("sample_items"),
            "raw_html_path": capture_data["raw_html_path"],
            "raw_html_sha256": sha256_text(raw_html),
            "visible_text_path": capture_data["visible_text_path"],
            "visible_text_sha256": sha256_text(visible_text),
            "screenshot_path": capture_data["screenshot_path"],
            "screenshot_sha256": capture_data["screenshot_sha256"],
            "parser_version": parsed["parser_version"],
            "extractor_strategy": parsed["extractor_strategy"],
            "llm_repair_applied": parsed["llm_repair_applied"],
            "completeness_status": parsed["completeness_status"],
            "captured_at": capture_data["captured_at"],
        }
    )

    proof_bundle = build_proof("https://jp.mercari.com/user/profile/verify03", capture_data, parsed)
    insert_proof(
        {
            "id": proof_bundle["proof_id"],
            "capture_id": capture_data["capture_id"],
            "proof_payload_json": pretty_json(proof_bundle["proof_payload"]),
            "proof_sha256": proof_bundle["proof_sha256"],
            "signature": proof_bundle["signature"],
            "kid": proof_bundle["kid"],
            "status": proof_bundle["status"],
            "expires_at": proof_bundle["expires_at"],
            "published_at": proof_bundle["published_at"],
        }
    )

    revoke_proof(proof_bundle["proof_id"], "test_revoke")
    result = verify_proof(proof_bundle["proof_payload"], proof_bundle["signature"])

    assert result["valid"] is False
    assert result["status"] == "revoked"
