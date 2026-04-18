from __future__ import annotations

import re
from urllib.parse import urlparse


PROFILE_PATH_RE = re.compile(r"^/user/profile/([A-Za-z0-9_-]+)/?$")


def is_valid_mercari_profile_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme != "https" or parsed.netloc != "jp.mercari.com":
        return False

    return bool(PROFILE_PATH_RE.fullmatch(parsed.path))


def normalize_mercari_url(url: str) -> str:
    if not is_valid_mercari_profile_url(url):
        raise ValueError("Only https://jp.mercari.com/user/profile/... URLs are supported.")

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"https://jp.mercari.com{path}"


def extract_mercari_profile_id(url: str) -> str:
    normalized = normalize_mercari_url(url)
    match = PROFILE_PATH_RE.fullmatch(urlparse(normalized).path)
    if not match:
        raise ValueError("Unable to extract Mercari profile id.")
    return match.group(1)


def build_mercari_reviews_url(url: str) -> str:
    profile_id = extract_mercari_profile_id(url)
    return f"https://jp.mercari.com/user/reviews/{profile_id}"
