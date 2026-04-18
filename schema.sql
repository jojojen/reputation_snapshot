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
