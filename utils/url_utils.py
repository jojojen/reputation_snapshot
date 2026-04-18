from __future__ import annotations

import re
from urllib.parse import urlparse


MERCARI_HOST = "jp.mercari.com"
MERCARI_URL_ERROR = "Only https://jp.mercari.com/user/profile/... or https://jp.mercari.com/item/... URLs are supported."
MERCARI_PROFILE_URL_ERROR = "Only https://jp.mercari.com/user/profile/... URLs are supported."
MERCARI_ITEM_URL_ERROR = "Only https://jp.mercari.com/item/... URLs are supported."

PROFILE_PATH_RE = re.compile(r"^/user/profile/([A-Za-z0-9_-]+)/?$")
REVIEWS_PATH_RE = re.compile(r"^/user/reviews/([A-Za-z0-9_-]+)/?$")
ITEM_PATH_RE = re.compile(r"^/item/([A-Za-z0-9_-]+)/?$")


def is_valid_mercari_url(url: str) -> bool:
    try:
        mercari_url_kind(url)
    except ValueError:
        return False
    return True


def is_valid_mercari_profile_url(url: str) -> bool:
    try:
        return mercari_url_kind(url) == "profile"
    except ValueError:
        return False


def is_valid_mercari_item_url(url: str) -> bool:
    try:
        return mercari_url_kind(url) == "item"
    except ValueError:
        return False


def normalize_mercari_url(url: str) -> str:
    parsed = _parse_mercari_url(url)
    path = parsed.path.rstrip("/")
    if not path:
        raise ValueError(MERCARI_URL_ERROR)

    if not _match_supported_path(path):
        raise ValueError(MERCARI_URL_ERROR)

    return f"https://{MERCARI_HOST}{path}"


def normalize_mercari_profile_url(url: str) -> str:
    normalized = normalize_mercari_url(url)
    if mercari_url_kind(normalized) != "profile":
        raise ValueError(MERCARI_PROFILE_URL_ERROR)
    return normalized


def normalize_mercari_item_url(url: str) -> str:
    normalized = normalize_mercari_url(url)
    if mercari_url_kind(normalized) != "item":
        raise ValueError(MERCARI_ITEM_URL_ERROR)
    return normalized


def mercari_url_kind(url: str) -> str:
    parsed = _parse_mercari_url(url)
    path = parsed.path.rstrip("/")
    if not path:
        raise ValueError(MERCARI_URL_ERROR)

    if PROFILE_PATH_RE.fullmatch(path):
        return "profile"
    if ITEM_PATH_RE.fullmatch(path):
        return "item"
    if REVIEWS_PATH_RE.fullmatch(path):
        return "reviews"
    raise ValueError(MERCARI_URL_ERROR)


def extract_mercari_profile_id(url: str) -> str:
    normalized = normalize_mercari_profile_url(url)
    match = PROFILE_PATH_RE.fullmatch(urlparse(normalized).path)
    if not match:
        raise ValueError("Unable to extract Mercari profile id.")
    return match.group(1)


def build_mercari_profile_url(profile_id: str) -> str:
    return f"https://{MERCARI_HOST}/user/profile/{profile_id}"


def build_mercari_reviews_url(url: str) -> str:
    profile_id = extract_mercari_profile_id(url)
    return f"https://{MERCARI_HOST}/user/reviews/{profile_id}"


def build_absolute_mercari_url(path_or_url: str) -> str:
    candidate = path_or_url.strip()
    if not candidate:
        raise ValueError(MERCARI_URL_ERROR)

    if candidate.startswith("http://") or candidate.startswith("https://"):
        return normalize_mercari_url(candidate)
    if candidate.startswith("/"):
        return normalize_mercari_url(f"https://{MERCARI_HOST}{candidate}")
    raise ValueError(MERCARI_URL_ERROR)


def _parse_mercari_url(url: str):
    try:
        parsed = urlparse(str(url).strip())
    except ValueError as exc:
        raise ValueError(MERCARI_URL_ERROR) from exc

    if parsed.scheme != "https" or parsed.netloc != MERCARI_HOST:
        raise ValueError(MERCARI_URL_ERROR)
    return parsed


def _match_supported_path(path: str) -> bool:
    return any(pattern.fullmatch(path) for pattern in (PROFILE_PATH_RE, REVIEWS_PATH_RE, ITEM_PATH_RE))
