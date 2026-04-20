from __future__ import annotations

from typing import Any


_DIFF_FIELDS = [
    "subject.display_name",
    "subject.verified_badge",
    "metrics.total_reviews",
    "metrics.positive_reviews",
    "metrics.negative_reviews",
    "metrics.listing_count",
    "metrics.followers_count",
    "metrics.following_count",
    "quality.overall.rate",
]


def build_timeline(proofs: list[dict[str, Any]], current_proof_id: str) -> list[dict[str, Any]]:
    """Build timeline node list oldest-first, each node includes diff vs previous."""
    nodes = []
    for i, proof in enumerate(proofs):
        quality = proof.get("quality") or {}
        overall = quality.get("overall") or {}
        node: dict[str, Any] = {
            "proof_id": proof.get("proof_id", ""),
            "captured_at": proof.get("captured_at", ""),
            "quality_rate": overall.get("rate"),
            "entry_count": quality.get("entry_count"),
            "total_reviews": proof.get("metrics", {}).get("total_reviews"),
            "status": proof.get("status", "active"),
            "is_current": proof.get("proof_id") == current_proof_id,
            "diff_from_prev": None if i == 0 else compute_proof_diff(proofs[i - 1], proof),
        }
        nodes.append(node)
    return nodes


def compute_proof_diff(old_proof: dict[str, Any], new_proof: dict[str, Any]) -> dict[str, Any]:
    """Return {"changes": [...], "has_changes": bool}."""
    changes = []
    for path in _DIFF_FIELDS:
        old_val = _get_nested(old_proof, path)
        new_val = _get_nested(new_proof, path)
        if old_val == new_val:
            continue
        change: dict[str, Any] = {
            "field": path,
            "old": old_val,
            "new": new_val,
            "delta": None,
            "delta_pct": None,
        }
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            change["delta"] = round(new_val - old_val, 1)
            if old_val and old_val != 0:
                change["delta_pct"] = round((new_val - old_val) / old_val * 100, 1)
        changes.append(change)
    return {"changes": changes, "has_changes": bool(changes)}


def _get_nested(d: dict, path: str) -> Any:
    val: Any = d
    for part in path.split("."):
        if not isinstance(val, dict):
            return None
        val = val.get(part)
    return val
