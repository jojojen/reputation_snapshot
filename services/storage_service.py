from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from utils.db_utils import ensure_runtime_directories, get_db_connection, now_jst_iso, project_path
from utils.hash_utils import sha256_text
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


def find_latest_reusable_proof_by_source_url(source_url: str) -> dict[str, Any] | None:
    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT
                p.id AS proof_id,
                p.capture_id AS capture_id,
                p.status AS proof_status,
                p.expires_at AS expires_at,
                p.published_at AS published_at,
                c.source_url AS source_url,
                c.display_name AS display_name,
                p.proof_payload_json AS proof_payload_json
            FROM proofs AS p
            INNER JOIN captures AS c ON c.id = p.capture_id
            WHERE c.source_url = ?
              AND p.revoked_at IS NULL
              AND p.status IN ('active', 'partial')
              AND p.expires_at > ?
            ORDER BY p.published_at DESC
            LIMIT 1
            """,
            (source_url, now_jst_iso()),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    try:
        result.pop("proof_payload_json", None)
    except Exception:
        pass
    return result


def insert_review_entries(
    capture_id: str,
    source_url: str,
    entries: list[dict[str, Any]],
    captured_at: str,
) -> None:
    if not entries:
        return
    with get_db_connection() as connection:
        for entry in entries:
            body = entry.get("body_excerpt") or ""
            content_hash = sha256_text(f"{entry['role']}|{entry['rating']}|{body}")
            connection.execute(
                """
                INSERT OR IGNORE INTO review_entries
                    (id, source_url, capture_id, role, rating, body_excerpt,
                     entry_order, content_hash, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"rev_{uuid.uuid4().hex[:12]}",
                    source_url,
                    capture_id,
                    entry["role"],
                    entry["rating"],
                    entry.get("body_excerpt"),
                    entry["entry_order"],
                    content_hash,
                    captured_at,
                ),
            )
        connection.commit()


def get_latest_review_entry_hash(source_url: str) -> str | None:
    """Returns content_hash of entry_order=1 from the most recent capture."""
    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT content_hash FROM review_entries
            WHERE source_url = ? AND entry_order = 1
            ORDER BY captured_at DESC
            LIMIT 1
            """,
            (source_url,),
        ).fetchone()
    return row[0] if row else None


def get_proofs_by_source_url(source_url: str) -> list[dict[str, Any]]:
    """Return all non-revoked proofs for a seller URL, oldest first, with payloads parsed."""
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT p.*
            FROM proofs AS p
            INNER JOIN captures AS c ON c.id = p.capture_id
            WHERE c.source_url = ?
              AND p.revoked_at IS NULL
              AND p.status IN ('active', 'partial')
            ORDER BY p.published_at ASC
            """,
            (source_url,),
        ).fetchall()

    result = []
    for row in rows:
        rec = dict(row)
        payload = json.loads(rec["proof_payload_json"])
        payload["proof_sha256"] = rec["proof_sha256"]
        payload["signature"] = rec["signature"]
        payload["kid"] = rec["kid"]
        payload["status"] = rec["status"]
        result.append(payload)
    return result


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


def get_capture_by_id(capture_id: str) -> dict[str, Any] | None:
    with get_db_connection() as connection:
        row = connection.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
    return dict(row) if row else None


def insert_query_event(data: dict[str, Any]) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO query_events
                (id, query_url, query_kind, profile_url, display_name, result,
                 proof_id, capture_id, primary_category, ip_address, queried_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"qe_{uuid.uuid4().hex[:12]}",
                data["query_url"],
                data.get("query_kind"),
                data.get("profile_url"),
                data.get("display_name"),
                data["result"],
                data.get("proof_id"),
                data.get("capture_id"),
                data.get("primary_category"),
                data.get("ip_address"),
                now_jst_iso(),
            ),
        )
        connection.commit()


def get_admin_stats() -> dict[str, Any]:
    week_ago = _days_ago(7)
    two_weeks_ago = _days_ago(14)

    with get_db_connection() as conn:
        summary = dict(
            conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(DISTINCT profile_url) AS unique_sellers,
                    SUM(CASE WHEN result = 'new_capture' THEN 1 ELSE 0 END) AS new_captures,
                    SUM(CASE WHEN result = 'reused'      THEN 1 ELSE 0 END) AS reused,
                    SUM(CASE WHEN queried_at >= ?         THEN 1 ELSE 0 END) AS last_7_days
                FROM query_events
                """,
                (week_ago,),
            ).fetchone()
            or {}
        )

        raw_categories = conn.execute(
            """
            SELECT primary_category,
                   COUNT(*) AS total,
                   SUM(CASE WHEN queried_at >= ? THEN 1 ELSE 0 END) AS this_week,
                   SUM(CASE WHEN queried_at >= ? AND queried_at < ? THEN 1 ELSE 0 END) AS last_week
            FROM query_events
            WHERE primary_category IS NOT NULL
            GROUP BY primary_category
            ORDER BY total DESC
            LIMIT 12
            """,
            (week_ago, two_weeks_ago, week_ago),
        ).fetchall()

        raw_sellers = conn.execute(
            """
            SELECT profile_url, display_name, primary_category,
                   COUNT(*) AS cnt, MAX(queried_at) AS last_queried
            FROM query_events
            WHERE profile_url IS NOT NULL
            GROUP BY profile_url
            ORDER BY cnt DESC
            LIMIT 15
            """,
        ).fetchall()

        raw_ip_cat = conn.execute(
            """
            SELECT ip_address, primary_category, COUNT(*) AS cnt
            FROM query_events
            WHERE ip_address IS NOT NULL AND ip_address != ''
              AND primary_category IS NOT NULL
            GROUP BY ip_address, primary_category
            ORDER BY cnt DESC
            LIMIT 300
            """,
        ).fetchall()

        raw_samples = conn.execute(
            """
            SELECT c.sample_items_json, COUNT(*) AS query_cnt
            FROM query_events qe
            JOIN captures c ON c.id = qe.capture_id
            WHERE qe.capture_id IS NOT NULL
            GROUP BY qe.capture_id
            """,
        ).fetchall()

        recent = conn.execute(
            """
            SELECT query_url, query_kind, display_name, primary_category,
                   result, ip_address, queried_at
            FROM query_events
            ORDER BY queried_at DESC
            LIMIT 50
            """,
        ).fetchall()

    # Week-over-week change per category
    top_categories = []
    for row in raw_categories:
        r = dict(row)
        lw = r.get("last_week") or 0
        tw = r.get("this_week") or 0
        r["wow_change"] = round((tw - lw) / lw * 100) if lw > 0 else None
        top_categories.append(r)

    # Keyword aggregation from sample_items
    keyword_counts: dict[str, int] = {}
    for row in raw_samples:
        try:
            items = json.loads(row["sample_items_json"] or "[]")
            for item in items:
                kw = str(item).strip()
                if kw:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + int(row["query_cnt"])
        except Exception:
            pass
    top_keywords = [
        {"keyword": k, "count": c}
        for k, c in sorted(keyword_counts.items(), key=lambda x: -x[1])[:20]
    ]

    # IP subnet aggregation (/24)
    subnet_data: dict[str, dict[str, Any]] = {}
    for row in raw_ip_cat:
        subnet = _ip_to_subnet(row["ip_address"])
        if subnet not in subnet_data:
            subnet_data[subnet] = {"total": 0, "categories": {}}
        subnet_data[subnet]["total"] += row["cnt"]
        cats = subnet_data[subnet]["categories"]
        cats[row["primary_category"]] = cats.get(row["primary_category"], 0) + row["cnt"]

    ip_analysis = []
    for subnet, data in sorted(subnet_data.items(), key=lambda x: -x[1]["total"])[:20]:
        top_cat = max(data["categories"].items(), key=lambda x: x[1])
        ip_analysis.append({
            "subnet": subnet,
            "total": data["total"],
            "top_category": top_cat[0],
            "categories": sorted(data["categories"].items(), key=lambda x: -x[1]),
        })

    return {
        "summary": summary,
        "top_categories": top_categories,
        "top_sellers": [dict(r) for r in raw_sellers],
        "top_keywords": top_keywords,
        "ip_analysis": ip_analysis,
        "recent_events": [dict(r) for r in recent],
    }


def _days_ago(n: int) -> str:
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    return (datetime.now(jst) - timedelta(days=n)).replace(microsecond=0).isoformat()


def _ip_to_subnet(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".x"
    return ip


def _bool_to_db(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(bool(value))
