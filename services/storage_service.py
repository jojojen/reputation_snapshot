from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from utils.db_utils import ensure_runtime_directories, get_db_connection, now_jst_iso, project_path
from utils.json_utils import pretty_json


def save_raw_html(capture_id: str, raw_html: str) -> str:
    ensure_runtime_directories()
    path = project_path("captures", "html", f"{capture_id}.html")
    path.write_text(raw_html, encoding="utf-8")
    return str(path)


def save_visible_text(capture_id: str, visible_text: str) -> str:
    ensure_runtime_directories()
    path = project_path("captures", "text", f"{capture_id}.txt")
    path.write_text(visible_text, encoding="utf-8")
    return str(path)


def save_screenshot(capture_id: str, screenshot_bytes: bytes) -> str:
    ensure_runtime_directories()
    path = project_path("captures", "screenshots", f"{capture_id}.png")
    path.write_bytes(screenshot_bytes)
    return str(path)


def insert_capture(data: dict[str, Any]) -> None:
    sample_items = data.get("sample_items_json")
    if sample_items is None:
        sample_items = json.dumps(data.get("sample_items", []), ensure_ascii=False)

    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO captures (
                id, source_url, source_platform, display_name, avatar_url, verified_badge,
                total_reviews, positive_reviews, negative_reviews, listing_count,
                followers_count, following_count, bio_excerpt, sample_items_json,
                raw_html_path, raw_html_sha256, visible_text_path, visible_text_sha256,
                screenshot_path, screenshot_sha256, parser_version, extractor_strategy,
                llm_repair_applied, completeness_status, captured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["source_url"],
                data["source_platform"],
                data.get("display_name"),
                data.get("avatar_url"),
                _bool_to_db(data.get("verified_badge")),
                data.get("total_reviews"),
                data.get("positive_reviews"),
                data.get("negative_reviews"),
                data.get("listing_count"),
                data.get("followers_count"),
                data.get("following_count"),
                data.get("bio_excerpt"),
                sample_items,
                data["raw_html_path"],
                data["raw_html_sha256"],
                data["visible_text_path"],
                data["visible_text_sha256"],
                data["screenshot_path"],
                data["screenshot_sha256"],
                data["parser_version"],
                data["extractor_strategy"],
                int(data.get("llm_repair_applied", 0)),
                data["completeness_status"],
                data["captured_at"],
            ),
        )
        connection.commit()


def insert_proof(data: dict[str, Any]) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO proofs (
                id, capture_id, proof_payload_json, proof_sha256, signature, kid,
                status, expires_at, published_at, revoked_at, revocation_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["capture_id"],
                data["proof_payload_json"],
                data["proof_sha256"],
                data["signature"],
                data["kid"],
                data["status"],
                data["expires_at"],
                data["published_at"],
                data.get("revoked_at"),
                data.get("revocation_reason"),
            ),
        )
        connection.commit()


def insert_parser_run(
    capture_id: str,
    parser_version: str,
    extractor_strategy: str,
    success: bool,
    missing_fields: list[str],
) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO parser_runs (
                id, capture_id, parser_version, extractor_strategy, success,
                missing_fields_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"prun_{uuid.uuid4().hex[:12]}",
                capture_id,
                parser_version,
                extractor_strategy,
                int(success),
                json.dumps(missing_fields, ensure_ascii=False),
                now_jst_iso(),
            ),
        )
        connection.commit()


def get_proof(proof_id: str) -> dict[str, Any] | None:
    with get_db_connection() as connection:
        row = connection.execute("SELECT * FROM proofs WHERE id = ?", (proof_id,)).fetchone()
    return dict(row) if row else None


def get_proof_document(proof_id: str) -> dict[str, Any] | None:
    row = get_proof(proof_id)
    if row is None:
        return None

    payload = json.loads(row["proof_payload_json"])
    payload["proof_sha256"] = row["proof_sha256"]
    payload["signature"] = row["signature"]
    payload["kid"] = row["kid"]
    payload["status"] = row["status"]
    if row.get("revoked_at"):
        payload["revoked_at"] = row["revoked_at"]
    if row.get("revocation_reason"):
        payload["revocation_reason"] = row["revocation_reason"]
    return payload


def revoke_proof(proof_id: str, reason: str) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            UPDATE proofs
            SET status = ?, revoked_at = ?, revocation_reason = ?
            WHERE id = ?
            """,
            ("revoked", now_jst_iso(), reason, proof_id),
        )
        connection.commit()


def dump_proof_document(path: str | Path, proof_document: dict[str, Any]) -> None:
    Path(path).write_text(pretty_json(proof_document), encoding="utf-8")


def _bool_to_db(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(bool(value))
