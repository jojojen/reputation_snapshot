from __future__ import annotations

from datetime import datetime
from typing import Any

from services.signing_service import verify_signature
from services.storage_service import get_proof
from utils.db_utils import JST
from utils.json_utils import canonical_json


REQUIRED_TOP_LEVEL_KEYS = {
    "proof_id",
    "proof_version",
    "source_platform",
    "source_url",
    "captured_at",
    "expires_at",
    "subject",
    "metrics",
    "signals",
    "score",
    "evidence",
    "status",
}


def verify_proof(proof: dict[str, Any], signature: str) -> dict[str, Any]:
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(proof))
    if missing:
        return {"valid": False, "reason": f"missing fields: {', '.join(missing)}", "status": "invalid"}

    if not verify_signature(canonical_json(proof), signature):
        return {"valid": False, "reason": "invalid signature", "status": "invalid"}

    try:
        expires_at = datetime.fromisoformat(proof["expires_at"])
    except (TypeError, ValueError):
        return {"valid": False, "reason": "invalid expires_at", "status": "invalid"}

    if expires_at <= datetime.now(JST):
        return {"valid": False, "reason": "proof expired", "status": "expired"}

    stored_record = get_proof(proof["proof_id"])
    if stored_record and stored_record["status"] == "revoked":
        return {"valid": False, "reason": "proof revoked", "status": "revoked"}

    status = stored_record["status"] if stored_record else proof.get("status", "active")
    if status not in {"active", "partial", "expired", "revoked"}:
        return {"valid": False, "reason": "invalid status", "status": "invalid"}

    return {"valid": True, "reason": None, "status": status}
