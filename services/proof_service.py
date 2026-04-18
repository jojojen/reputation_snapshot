from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from services.signing_service import KEY_ID, sign_proof
from utils.db_utils import now_jst_iso
from utils.hash_utils import sha256_text
from utils.json_utils import canonical_json
from utils.score_utils import calculate_score
from utils.url_utils import normalize_mercari_profile_url


PROOF_VERSION = "v0.1"
SOURCE_PLATFORM = "mercari_jp"


def build_proof(
    source_url: str,
    capture_data: dict[str, Any],
    parsed_data: dict[str, Any],
    expires_in_days: int = 30,
) -> dict[str, Any]:
    proof_id = f"proof_{uuid.uuid4().hex[:12]}"
    normalized_url = normalize_mercari_profile_url(source_url)
    captured_at = capture_data.get("captured_at") or now_jst_iso()
    expires_at = _calculate_expiry(captured_at, expires_in_days)
    score = calculate_score(
        parsed_data.get("total_reviews"),
        parsed_data.get("listing_count"),
        parsed_data.get("verified_badge"),
    )

    payload = {
        "proof_id": proof_id,
        "proof_version": PROOF_VERSION,
        "source_platform": SOURCE_PLATFORM,
        "source_url": normalized_url,
        "captured_at": captured_at,
        "expires_at": expires_at,
        "assurance": {"level": "public_snapshot"},
        "subject": {
            "display_name": parsed_data.get("display_name"),
            "avatar_url": parsed_data.get("avatar_url"),
            "verified_badge": parsed_data.get("verified_badge"),
        },
        "metrics": {
            "total_reviews": parsed_data.get("total_reviews"),
            "positive_reviews": parsed_data.get("positive_reviews"),
            "negative_reviews": parsed_data.get("negative_reviews"),
            "listing_count": parsed_data.get("listing_count"),
            "followers_count": parsed_data.get("followers_count"),
            "following_count": parsed_data.get("following_count"),
        },
        "signals": {
            "bio_excerpt": parsed_data.get("bio_excerpt"),
            "sample_items": list(parsed_data.get("sample_items", []))[:10],
        },
        "score": score,
        "evidence": {
            "parser_version": parsed_data.get("parser_version"),
            "extractor_strategy": parsed_data.get("extractor_strategy"),
            "raw_html_sha256": capture_data.get("raw_html_sha256"),
            "visible_text_sha256": capture_data.get("visible_text_sha256"),
            "screenshot_sha256": capture_data.get("screenshot_sha256"),
        },
        "status": "partial" if parsed_data.get("completeness_status") == "partial" else "active",
    }

    canonical_payload = canonical_json(payload)
    proof_sha256 = sha256_text(canonical_payload)
    signature = sign_proof(canonical_payload)
    published_at = now_jst_iso()

    return {
        "proof_id": proof_id,
        "proof_payload": payload,
        "proof_sha256": proof_sha256,
        "signature": signature,
        "kid": KEY_ID,
        "published_at": published_at,
        "expires_at": expires_at,
        "status": payload["status"],
        "proof_document": {**payload, "proof_sha256": proof_sha256, "signature": signature, "kid": KEY_ID},
    }


def _calculate_expiry(captured_at: str, expires_in_days: int) -> str:
    captured_at_dt = datetime.fromisoformat(captured_at)
    return (captured_at_dt + timedelta(days=expires_in_days)).replace(microsecond=0).isoformat()
