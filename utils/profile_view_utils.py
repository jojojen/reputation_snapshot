from __future__ import annotations

import re
from typing import Any


PLATFORM_LABELS = {
    "mercari_jp": "Mercari JP",
}

STATUS_META = {
    "active": {"label": "Active Snapshot", "tone": "good", "description": "Core public signals were captured successfully."},
    "partial": {"label": "Partial Snapshot", "tone": "warn", "description": "Some core public signals are missing, but the proof is still signed."},
    "revoked": {"label": "Revoked", "tone": "danger", "description": "This proof has been revoked and should not be relied on."},
    "expired": {"label": "Expired", "tone": "muted", "description": "This proof has passed its validity window."},
}

CATEGORY_RULES = (
    ("Trading Cards", ("ポケモンカード", "ポケカ", "遊戯王", "トレカ", "sar", "sr ", " sr", "chr", "ur ", " ur", "psa", "promo", "vmax", "vstar", "gx", "ex ")),
    ("Collectibles", ("限定", "フィギュア", "サイン", "レトロ", "コレクション", "collector", "vintage")),
    ("Fashion", ("ジャケット", "シャツ", "バッグ", "財布", "デニム", "scarf", "wallet", "tote", "coat", "hoodie", "dress")),
    ("Books & Media", ("本", "雑誌", "コミック", "漫画", "book", "novel", "dvd", "cd", "blu-ray")),
    ("Home & Living", ("食器", "マグ", "家具", "lamp", "mug", "kitchen", "notebook", "ceramic")),
    ("Beauty", ("コスメ", "美容", "香水", "skincare", "makeup")),
    ("Electronics", ("iphone", "ipad", "camera", "pc", "sony", "nintendo", "switch", "headphone", "apple watch")),
    ("Kids & Baby", ("ベビー", "子ども", "kids", "baby", "nursery")),
    ("Sports & Outdoor", ("ゴルフ", "camp", "camping", "outdoor", "スポーツ", "釣り")),
)


def build_proof_view(proof: dict[str, Any]) -> dict[str, Any]:
    subject = proof.get("subject", {})
    metrics = proof.get("metrics", {})
    signals = proof.get("signals", {})
    status = proof.get("status", "active")
    status_meta = STATUS_META.get(status, STATUS_META["active"])
    sample_items = [str(item).strip() for item in signals.get("sample_items", []) if str(item).strip()]
    total_reviews = metrics.get("total_reviews")
    positive_reviews = metrics.get("positive_reviews")
    negative_reviews = metrics.get("negative_reviews")
    positive_ratio, negative_ratio, no_record_ratio, no_record_count, rated_total, rated_positive_pct = _review_ratios(
        total_reviews, positive_reviews, negative_reviews
    )

    return {
        "platform_label": PLATFORM_LABELS.get(proof.get("source_platform"), proof.get("source_platform", "Unknown Platform")),
        "status_label": status_meta["label"],
        "status_tone": status_meta["tone"],
        "status_description": status_meta["description"],
        "review_breakdown_available": positive_reviews is not None or negative_reviews is not None,
        "positive_reviews": positive_reviews,
        "negative_reviews": negative_reviews,
        "positive_ratio": positive_ratio,
        "negative_ratio": negative_ratio,
        "no_record_ratio": no_record_ratio,
        "no_record_count": no_record_count,
        "rated_total": rated_total,
        "rated_positive_pct": rated_positive_pct,
        "primary_categories": infer_primary_categories(sample_items, signals.get("bio_excerpt")),
        "sample_items": sample_items[:8],
        "seller_initial": _seller_initial(subject.get("display_name")),
        "score_headline": _score_headline(proof.get("score", {}).get("grade")),
    }


def infer_primary_categories(sample_items: list[str], bio_excerpt: str | None) -> list[str]:
    text = " ".join(sample_items + ([bio_excerpt] if bio_excerpt else []))
    normalized = text.lower()
    categories: list[str] = []

    for label, keywords in CATEGORY_RULES:
        if any(keyword.lower() in normalized for keyword in keywords):
            categories.append(label)

    if categories:
        return categories[:4]

    if sample_items:
        return ["Mixed Inventory"]
    return ["Category Unknown"]


def _review_ratios(
    total_reviews: int | None,
    positive_reviews: int | None,
    negative_reviews: int | None,
) -> tuple:
    if positive_reviews is None and negative_reviews is None:
        return None, None, None, None, None, None

    pos = positive_reviews or 0
    neg = negative_reviews or 0
    rated_total = pos + neg

    review_total = total_reviews if total_reviews is not None else rated_total
    if not review_total:
        return None, None, None, None, None, None

    no_record_count = max(0, review_total - rated_total)
    positive_ratio = round(pos / review_total * 100)
    negative_ratio = round(neg / review_total * 100)
    no_record_ratio = 100 - positive_ratio - negative_ratio
    rated_positive_pct = round(pos / rated_total * 100) if rated_total else None

    return positive_ratio, negative_ratio, no_record_ratio, no_record_count, rated_total, rated_positive_pct


def _seller_initial(display_name: str | None) -> str:
    if not display_name:
        return "?"
    stripped = re.sub(r"\s+", "", display_name)
    return stripped[:1].upper()


def _score_headline(grade: Any) -> str:
    grade_map = {
        "A": "Outstanding public track record",
        "B": "Strong public track record",
        "C": "Moderate public track record",
        "D": "Thin public track record",
    }
    return grade_map.get(str(grade), "Public signal strength")
