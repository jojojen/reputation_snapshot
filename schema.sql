CREATE TABLE IF NOT EXISTS captures (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    source_platform TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    verified_badge INTEGER,
    total_reviews INTEGER,
    positive_reviews INTEGER,
    negative_reviews INTEGER,
    listing_count INTEGER,
    followers_count INTEGER,
    following_count INTEGER,
    bio_excerpt TEXT,
    sample_items_json TEXT NOT NULL,
    raw_html_path TEXT NOT NULL,
    raw_html_sha256 TEXT NOT NULL,
    visible_text_path TEXT NOT NULL,
    visible_text_sha256 TEXT NOT NULL,
    screenshot_path TEXT NOT NULL,
    screenshot_sha256 TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    extractor_strategy TEXT NOT NULL,
    llm_repair_applied INTEGER NOT NULL DEFAULT 0,
    completeness_status TEXT NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proofs (
    id TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL,
    proof_payload_json TEXT NOT NULL,
    proof_sha256 TEXT NOT NULL,
    signature TEXT NOT NULL,
    kid TEXT NOT NULL,
    status TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    published_at TEXT NOT NULL,
    revoked_at TEXT,
    revocation_reason TEXT,
    FOREIGN KEY (capture_id) REFERENCES captures(id)
);

CREATE TABLE IF NOT EXISTS parser_runs (
    id TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    extractor_strategy TEXT NOT NULL,
    success INTEGER NOT NULL,
    missing_fields_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_entries (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    capture_id TEXT NOT NULL,
    role TEXT NOT NULL,
    rating TEXT NOT NULL,
    body_excerpt TEXT,
    entry_order INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    FOREIGN KEY (capture_id) REFERENCES captures(id),
    UNIQUE (source_url, content_hash)
);

CREATE TABLE IF NOT EXISTS query_events (
    id               TEXT PRIMARY KEY,
    query_url        TEXT NOT NULL,
    query_kind       TEXT,
    profile_url      TEXT,
    display_name     TEXT,
    result           TEXT NOT NULL,
    proof_id         TEXT,
    capture_id       TEXT,
    primary_category TEXT,
    ip_address       TEXT,
    queried_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qe_queried_at  ON query_events(queried_at DESC);
CREATE INDEX IF NOT EXISTS idx_qe_profile_url ON query_events(profile_url);
CREATE INDEX IF NOT EXISTS idx_qe_category    ON query_events(primary_category);
