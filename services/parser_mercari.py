from __future__ import annotations

import re
from html import unescape
from typing import Any

from services.llm_repair_service import repair_parse
from utils.db_utils import get_settings


REQUIRED_FIELDS = (
    "display_name",
    "total_reviews",
    "listing_count",
    "followers_count",
    "following_count",
)

TOTAL_REVIEW_LABELS = ("件のレビュー",)
POSITIVE_REVIEW_LABELS = ("良かった", "良い")
NEGATIVE_REVIEW_LABELS = ("残念だった", "悪い")
LISTING_LABELS = ("出品数",)
FOLLOWER_LABELS = ("フォロワー",)
FOLLOWING_LABELS = ("フォロー中",)
VERIFIED_LABELS = ("本人確認済",)

NOISE_TOKENS = (
    "コンテンツにスキップ",
    "ログイン",
    "会員登録",
    "出品",
    "日本語",
    "販売中のみ表示",
    "もっとみる",
    "もっと見る",
    "出品者レベル",
    "フォロー",
    "フォロワー",
    "フォロー中",
    "出品数",
    "評価一覧",
    "評価",
    "件のレビュー",
    "本人確認済",
)


def parse_profile(
    raw_html: str,
    visible_text: str,
    review_raw_html: str | None = None,
    review_visible_text: str | None = None,
    item_raw_html: str | None = None,
    item_visible_text: str | None = None,
    item_total_reviews: int | None = None,
) -> dict[str, Any]:
    lines = _extract_lines(visible_text)
    display_name = _extract_display_name(raw_html, lines, review_raw_html, review_visible_text)
    metric_sources = _build_metric_sources(
        raw_html,
        visible_text,
        review_raw_html,
        review_visible_text,
        item_raw_html,
        item_visible_text,
    )

    parsed: dict[str, Any] = {
        "display_name": display_name,
        "avatar_url": _extract_avatar_url(raw_html),
        "verified_badge": _extract_verified_badge(raw_html, visible_text),
        "total_reviews": _extract_total_reviews(metric_sources, lines, display_name),
        "positive_reviews": _extract_metric_value(metric_sources, POSITIVE_REVIEW_LABELS, allow_label_first=True),
        "negative_reviews": _extract_metric_value(metric_sources, NEGATIVE_REVIEW_LABELS, allow_label_first=True),
        "listing_count": _extract_metric_value(metric_sources, LISTING_LABELS, allow_label_first=False),
        "followers_count": _extract_metric_value(metric_sources, FOLLOWER_LABELS, allow_label_first=False),
        "following_count": _extract_metric_value(metric_sources, FOLLOWING_LABELS, allow_label_first=False),
        "bio_excerpt": None,
        "sample_items": [],
        "parser_version": get_settings().parser_version,
        "extractor_strategy": _build_extractor_strategy(review_raw_html, review_visible_text, item_raw_html, item_visible_text),
        "llm_repair_applied": 0,
        "completeness_status": "partial",
    }

    if item_total_reviews is not None and (parsed["total_reviews"] is None or parsed["total_reviews"] < item_total_reviews):
        parsed["total_reviews"] = item_total_reviews

    if parsed["total_reviews"] is None and parsed["positive_reviews"] is not None and parsed["negative_reviews"] is not None:
        parsed["total_reviews"] = parsed["positive_reviews"] + parsed["negative_reviews"]

    parsed["bio_excerpt"] = _extract_bio_excerpt(lines, parsed["display_name"])
    parsed["sample_items"] = _extract_sample_items(raw_html, lines, parsed["display_name"], parsed["bio_excerpt"])

    missing_required = [field for field in REQUIRED_FIELDS if parsed.get(field) is None]
    if missing_required:
        repaired = repair_parse(raw_html, visible_text)
        for field in missing_required:
            repaired_value = repaired.get(field)
            if repaired_value is not None:
                parsed[field] = repaired_value
                parsed["llm_repair_applied"] = 1

    parsed["completeness_status"] = "full" if all(parsed.get(field) is not None for field in REQUIRED_FIELDS) else "partial"
    return parsed


def _extract_lines(visible_text: str) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in visible_text.splitlines():
        line = _normalize_space(raw_line)
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def _build_metric_sources(
    raw_html: str,
    visible_text: str,
    review_raw_html: str | None,
    review_visible_text: str | None,
    item_raw_html: str | None,
    item_visible_text: str | None,
) -> tuple[str, ...]:
    sources = [_normalize_space(visible_text), _clean_html_fragment(raw_html)]
    if review_visible_text:
        sources.append(_normalize_space(review_visible_text))
    if review_raw_html:
        sources.append(_clean_html_fragment(review_raw_html))
    if item_visible_text:
        sources.append(_normalize_space(item_visible_text))
    if item_raw_html:
        sources.append(_clean_html_fragment(item_raw_html))
    return tuple(source for source in sources if source)


def _extract_display_name(
    raw_html: str,
    lines: list[str],
    review_raw_html: str | None = None,
    review_visible_text: str | None = None,
) -> str | None:
    patterns = (
        r'data-testid="mer-profile-heading".*?<h1[^>]*>(.*?)</h1>',
        r'data-testid="mer-avatar"[^>]*>.*?<img[^>]+alt="([^"]+)"',
        r'<img[^>]+src="https://static\.mercdn\.net/thumb/members/[^"]+"[^>]+alt="([^"]+)"',
        r"<h1[^>]*>(.*?)</h1>",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_html, re.IGNORECASE | re.DOTALL)
        if match:
            candidate = _clean_html_fragment(match.group(1))
            if _looks_like_display_name(candidate):
                return candidate

    title_match = re.search(r"<title>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title_text = _clean_html_fragment(title_match.group(1))
        for separator in (" - メルカリ",):
            if separator in title_text:
                title_candidate = title_text.split(separator, 1)[0].strip()
                if _looks_like_display_name(title_candidate):
                    return title_candidate

    for line in lines[:10]:
        if _looks_like_display_name(line):
            return line

    if review_visible_text:
        for line in _extract_lines(review_visible_text)[:10]:
            if _looks_like_display_name(line):
                return line

    if review_raw_html:
        review_title_match = re.search(r"<title>(.*?)</title>", review_raw_html, re.IGNORECASE | re.DOTALL)
        if review_title_match:
            review_title = _clean_html_fragment(review_title_match.group(1))
            if " - メルカリ" in review_title:
                review_title_candidate = review_title.split(" - メルカリ", 1)[0].strip()
                if _looks_like_display_name(review_title_candidate):
                    return review_title_candidate
    return None


def _extract_avatar_url(raw_html: str) -> str | None:
    patterns = (
        r'<img[^>]+src="(https://static\.mercdn\.net/thumb/members/[^"]+)"[^>]+alt="[^"]+"',
        r'<picture><img[^>]+src="(https://static\.mercdn\.net/thumb/members/[^"]+)"',
        r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
        r'<meta[^>]+name="twitter:image"[^>]+content="([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, raw_html, re.IGNORECASE)
        if match:
            return unescape(match.group(1))
    return None


def _extract_verified_badge(raw_html: str, visible_text: str) -> bool | None:
    text = f"{raw_html}\n{visible_text}"
    if any(token in text for token in VERIFIED_LABELS):
        return True
    return None


def _extract_total_reviews(metric_sources: tuple[str, ...], lines: list[str], display_name: str | None) -> int | None:
    total_reviews = _extract_metric_from_patterns(
        metric_sources,
        (
            r"([\d,]+)\s*件のレビュー",
            r"件のレビュー\s*[\(:：]?\s*([\d,]+)",
            r"評価(?!一覧)\s*[\(:：]?\s*([\d,]+)",
            r"([\d,]+)\s*評価(?!一覧)",
        ),
    )
    if total_reviews is not None:
        return total_reviews
    return _extract_total_reviews_from_lines(lines, display_name)


def _extract_metric_value(metric_sources: tuple[str, ...], labels: tuple[str, ...], allow_label_first: bool) -> int | None:
    patterns: list[str] = []
    for label in labels:
        escaped_label = re.escape(label)
        patterns.append(rf"([\d,]+)\s*{escaped_label}")
        if allow_label_first:
            patterns.append(rf"{escaped_label}\s*[\(:：]?\s*([\d,]+)")
    return _extract_metric_from_patterns(metric_sources, tuple(patterns))


def _extract_metric_from_patterns(metric_sources: tuple[str, ...], patterns: tuple[str, ...]) -> int | None:
    for haystack in metric_sources:
        for pattern in patterns:
            match = re.search(pattern, haystack)
            if match:
                return int(match.group(1).replace(",", ""))
    return None


def _extract_total_reviews_from_lines(lines: list[str], display_name: str | None) -> int | None:
    if display_name and display_name in lines:
        display_index = lines.index(display_name)
        nearby_lines = lines[display_index + 1 : display_index + 6]
    else:
        nearby_lines = lines[:8]

    candidate = _find_review_count_line(nearby_lines)
    if candidate is not None:
        return candidate

    for index, line in enumerate(lines[:-1]):
        if re.fullmatch(r"[\d,]+", line) and _looks_like_review_context(lines[index + 1]):
            return int(line.replace(",", ""))

    return None


def _find_review_count_line(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if re.fullmatch(r"[\d,]+", line):
            context_window = " ".join(lines[max(index - 1, 0) : min(index + 3, len(lines))])
            if _looks_like_review_context(context_window):
                return int(line.replace(",", ""))

        combined_match = re.fullmatch(r"(.+?)\s+([\d,]+)", line)
        if combined_match and _looks_like_display_name(combined_match.group(1).strip()):
            return int(combined_match.group(2).replace(",", ""))
    return None


def _looks_like_review_context(value: str) -> bool:
    return any(token in value for token in ("本人確認済", "出品者レベル", "評価", "件のレビュー"))


def _extract_bio_excerpt(lines: list[str], display_name: str | None) -> str | None:
    candidates: list[str] = []
    for line in lines:
        if line == display_name or len(line) < 8 or len(line) > 280:
            continue
        if _contains_metric_label(line):
            continue
        if any(token in line for token in NOISE_TOKENS):
            continue
        if re.fullmatch(r"[\d,\s]+", line):
            continue
        candidates.append(line)

    if not candidates:
        return None

    excerpt = " ".join(candidates[:2]).strip()
    return excerpt[:280] if excerpt else None


def _extract_sample_items(raw_html: str, lines: list[str], display_name: str | None, bio_excerpt: str | None) -> list[str]:
    html_items = _extract_sample_items_from_html(raw_html)
    if html_items:
        return html_items[:10]

    items: list[str] = []
    for line in lines:
        if line == display_name or line == bio_excerpt:
            continue
        if len(line) < 3 or len(line) > 120:
            continue
        if _contains_metric_label(line):
            continue
        if any(token in line for token in NOISE_TOKENS):
            continue
        if re.fullmatch(r"[\d,\s]+", line):
            continue
        if line not in items:
            items.append(line)
        if len(items) == 10:
            break
    return items


def _extract_sample_items_from_html(raw_html: str) -> list[str]:
    patterns = (
        r'data-testid="thumbnail-item-name"[^>]*>(.*?)</span>',
        r"<li[^>]*>(.*?)</li>",
        r'<span[^>]+class="itemName[^"]*"[^>]*>(.*?)</span>',
    )
    items: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, raw_html, re.IGNORECASE | re.DOTALL):
            candidate = _clean_html_fragment(match.group(1))
            if not _is_probable_item_name(candidate):
                continue
            if candidate not in items:
                items.append(candidate)
            if len(items) == 10:
                return items
    return items


def _build_extractor_strategy(
    review_raw_html: str | None,
    review_visible_text: str | None,
    item_raw_html: str | None,
    item_visible_text: str | None,
) -> str:
    strategy_parts = ["dom_text_regex"]
    if review_raw_html or review_visible_text:
        strategy_parts.append("review_page")
    if item_raw_html or item_visible_text:
        strategy_parts.append("item_page")
    return "+".join(strategy_parts)


def _contains_metric_label(value: str) -> bool:
    metric_labels = (
        TOTAL_REVIEW_LABELS
        + POSITIVE_REVIEW_LABELS
        + NEGATIVE_REVIEW_LABELS
        + LISTING_LABELS
        + FOLLOWER_LABELS
        + FOLLOWING_LABELS
        + VERIFIED_LABELS
    )
    return any(label in value for label in metric_labels)


def _clean_html_fragment(fragment: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", fragment)
    return _normalize_space(unescape(without_tags))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_display_name(value: str) -> bool:
    if not value or len(value) > 50:
        return False
    if value.startswith("http"):
        return False
    if re.fullmatch(r"[\d,\s]+", value):
        return False
    if _contains_metric_label(value):
        return False
    return True


def _is_probable_item_name(value: str) -> bool:
    if not value or len(value) > 120:
        return False
    if _contains_metric_label(value):
        return False
    if re.fullmatch(r"[\d,\s]+", value):
        return False
    return True
