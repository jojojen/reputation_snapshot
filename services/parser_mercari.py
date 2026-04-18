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

NOISE_TOKENS = (
    "コンテンツにスキップ",
    "ログイン",
    "会員登録",
    "販売中のみ表示",
    "もっとみる",
    "もっと見る",
    "出品者レベル",
    "本人確認済",
    "フォロー",
    "プロフィール",
    "フォロワー",
    "フォロー中",
    "出品数",
    "商品",
    "評価一覧",
    "シェア",
    "メニュー",
    "メルカリ",
    "安心への取り組み",
    "良かった",
    "残念だった",
)


def parse_profile(
    raw_html: str,
    visible_text: str,
    review_raw_html: str | None = None,
    review_visible_text: str | None = None,
) -> dict[str, Any]:
    lines = _extract_lines(visible_text)
    metric_sources = _build_metric_sources(raw_html, visible_text, review_raw_html, review_visible_text)
    parsed: dict[str, Any] = {
        "display_name": _extract_display_name(raw_html, lines, review_raw_html, review_visible_text),
        "avatar_url": _extract_avatar_url(raw_html),
        "verified_badge": _extract_verified_badge(raw_html, visible_text),
        "total_reviews": _extract_total_reviews(metric_sources),
        "positive_reviews": _extract_metric_from_sources(
            metric_sources,
            (
                r"良かった\s*[\(:：（]?\s*([\d,]+)\s*[\)）]?",
                r"([\d,]+)\s*良かった",
            ),
        ),
        "negative_reviews": _extract_metric_from_sources(
            metric_sources,
            (
                r"残念だった\s*[\(:：（]?\s*([\d,]+)\s*[\)）]?",
                r"([\d,]+)\s*残念だった",
            ),
        ),
        "listing_count": _extract_metric_from_sources(
            metric_sources,
            (
                r"([\d,]+)\s*出品数",
                r"出品数\s*[:：]?\s*([\d,]+)",
                r"([\d,]+)\s*商品",
                r"商品\s*[:：]?\s*([\d,]+)",
            ),
        ),
        "followers_count": _extract_metric_from_sources(
            metric_sources,
            (r"([\d,]+)\s*フォロワー", r"フォロワー\s*[:：]?\s*([\d,]+)"),
        ),
        "following_count": _extract_metric_from_sources(
            metric_sources,
            (r"([\d,]+)\s*フォロー中", r"フォロー中\s*[:：]?\s*([\d,]+)"),
        ),
        "bio_excerpt": None,
        "sample_items": [],
        "parser_version": get_settings().parser_version,
        "extractor_strategy": "dom_text_regex+review_page" if review_visible_text or review_raw_html else "dom_text_regex",
        "llm_repair_applied": 0,
        "completeness_status": "partial",
    }

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
) -> tuple[str, ...]:
    sources = [_normalize_space(visible_text), _clean_html_fragment(raw_html)]
    if review_visible_text:
        sources.append(_normalize_space(review_visible_text))
    if review_raw_html:
        sources.append(_clean_html_fragment(review_raw_html))
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
        r'<div[^>]+role="img"[^>]+aria-label="([^"]+)"',
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
        if " - メルカリ" in title_text:
            title_candidate = title_text.split(" - メルカリ", 1)[0].strip()
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
        r'<img[^>]+src="([^"]+)"[^>]+alt="[^"]*(?:avatar|プロフィール|icon|アイコン)[^"]*"',
    )
    for pattern in patterns:
        match = re.search(pattern, raw_html, re.IGNORECASE)
        if match:
            return unescape(match.group(1))
    return None


def _extract_verified_badge(raw_html: str, visible_text: str) -> bool | None:
    text = f"{raw_html}\n{visible_text}"
    if re.search(r"本人確認済|メルカリ公認|公式バッジ|優良ショップ|本人確認バッジ", text):
        return True
    return None


def _extract_total_reviews(metric_sources: tuple[str, ...]) -> int | None:
    return _extract_metric_from_sources(
        metric_sources,
        (
            r"評価\s*[:：]?\s*([\d,]+)",
            r"([\d,]+)\s*件の評価",
            r"レビュー\s*[:：]?\s*([\d,]+)",
            r"評価一覧\s*[:：]?\s*([\d,]+)",
        ),
    )


def _extract_metric_from_sources(metric_sources: tuple[str, ...], patterns: tuple[str, ...]) -> int | None:
    for haystack in metric_sources:
        for pattern in patterns:
            match = re.search(pattern, haystack)
            if match:
                return int(match.group(1).replace(",", ""))
    return None


def _extract_bio_excerpt(lines: list[str], display_name: str | None) -> str | None:
    candidates: list[str] = []
    for line in lines:
        if line == display_name or len(line) < 8 or len(line) > 280:
            continue
        if any(token in line for token in NOISE_TOKENS):
            continue
        if re.search(r"[¥￥]\s*[\d,]+|[\d,]+\s*円", line):
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
        if any(token in line for token in NOISE_TOKENS):
            continue
        if re.search(r"[¥￥]\s*[\d,]+|[\d,]+\s*円", line):
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


def _clean_html_fragment(fragment: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", fragment)
    return _normalize_space(unescape(without_tags))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_display_name(value: str) -> bool:
    if not value or len(value) > 50:
        return False
    if any(token in value for token in NOISE_TOKENS):
        return False
    if re.fullmatch(r"[\d,\s]+", value):
        return False
    if value.startswith("http"):
        return False
    return True


def _is_probable_item_name(value: str) -> bool:
    if not value or len(value) > 120:
        return False
    if any(token in value for token in NOISE_TOKENS):
        return False
    if re.fullmatch(r"[\d,\s]+", value):
        return False
    return True
