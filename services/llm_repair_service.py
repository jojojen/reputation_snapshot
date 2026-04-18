from __future__ import annotations


def repair_parse(raw_html: str, visible_text: str) -> dict[str, str | int | None]:
    return {
        "display_name": None,
        "total_reviews": None,
        "listing_count": None,
        "followers_count": None,
        "following_count": None,
    }
