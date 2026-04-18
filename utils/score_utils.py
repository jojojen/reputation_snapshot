from __future__ import annotations

import math


def calculate_score(
    total_reviews: int | None,
    listing_count: int | None,
    verified_badge: bool | None,
) -> dict[str, int | str]:
    review_factor = 0.0
    listing_factor = 0.0
    badge_factor = 0.0

    if total_reviews is not None and total_reviews >= 0:
        review_factor = min(math.log10(total_reviews + 1) / math.log10(2001), 1.0)
    if listing_count is not None and listing_count >= 0:
        listing_factor = min(listing_count, 100) / 100
    if verified_badge:
        badge_factor = 1.0

    score_value = round(70 * review_factor + 20 * listing_factor + 10 * badge_factor)
    return {
        "value": score_value,
        "grade": score_to_grade(score_value),
        "label": "public_signal_strength_v0",
    }


def score_to_grade(score_value: int) -> str:
    if score_value >= 80:
        return "A"
    if score_value >= 60:
        return "B"
    if score_value >= 40:
        return "C"
    return "D"
