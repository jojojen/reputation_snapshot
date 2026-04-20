from __future__ import annotations

import base64
import uuid
from typing import Any

from flask import Flask, jsonify, make_response, redirect, render_template, request

from services.capture_service import capture_profile, capture_lookup_page, resolve_profile_reference, extract_item_seller_context
from services.parser_mercari import REQUIRED_FIELDS, parse_profile, parse_review_entries
from services.proof_service import build_proof
from services.analysis_service import build_timeline
from services.storage_service import (
    claim_next_capture_job,
    complete_capture_job,
    create_capture_job,
    fail_capture_job,
    find_latest_reusable_proof_by_source_url,
    get_admin_stats,
    get_capture_by_id,
    get_capture_job,
    get_latest_review_entry_hash,
    get_proof,
    get_proof_document,
    get_proofs_by_source_url,
    insert_capture,
    insert_parser_run,
    insert_proof,
    insert_query_event,
    insert_review_entries,
    revoke_proof,
    save_raw_html,
    save_screenshot,
    save_visible_text,
)
from services.verify_service import verify_proof
from utils.db_utils import ensure_runtime_directories, get_settings, init_db, now_jst_iso
from utils.hash_utils import sha256_bytes, sha256_text
from utils.i18n import detect_lang, get_translations
from utils.json_utils import pretty_json
from utils.profile_view_utils import build_proof_view, infer_primary_categories
from utils.url_utils import MERCARI_URL_ERROR, build_mercari_reviews_url, is_valid_mercari_url, is_valid_mercari_profile_url, normalize_mercari_profile_url


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    settings = get_settings()
    app = Flask(__name__)
    app.config.update(
        APP_HOST=settings.app_host,
        APP_PORT=settings.app_port,
        DEFAULT_EXPIRES_DAYS=settings.default_expires_days,
        ADMIN_TOKEN=settings.admin_token,
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    ensure_runtime_directories()
    init_db()

    @app.get("/lang/<code>")
    def set_lang(code: str) -> Any:
        referrer = request.referrer or "/"
        resp = make_response(redirect(referrer))
        if code in ("en", "zh", "ja"):
            resp.set_cookie("lang", code, max_age=60 * 60 * 24 * 365)
        return resp

    @app.get("/")
    def index() -> str:
        lang = detect_lang(request)
        t = get_translations(lang)
        demo_url = "https://jp.mercari.com/user/profile/u_demo_test_seller" if settings.env == "local" else ""
        return render_template("index.html", t=t, lang=lang, demo_url=demo_url)

    @app.post("/api/captures")
    def create_capture() -> tuple[Any, int] | Any:
        payload = request.get_json(silent=True) or {}
        query_url = _extract_query_url(payload)

        if not is_valid_mercari_url(query_url):
            return jsonify({"error": MERCARI_URL_ERROR}), 400

        # Quick reuse check (no Playwright needed)
        try:
            from utils.url_utils import normalize_mercari_url, mercari_url_kind
            normalized = normalize_mercari_url(query_url)
            if mercari_url_kind(normalized) == "profile":
                profile_url_check = normalized
                reusable = find_latest_reusable_proof_by_source_url(profile_url_check)
                if reusable is not None:
                    reviews_url = build_mercari_reviews_url(profile_url_check)
                    if not _has_new_reviews(profile_url_check, reviews_url):
                        return jsonify({
                            "proof_id": reusable["proof_id"],
                            "proof_url": f"/p/{reusable['proof_id']}",
                            "reused": True,
                        })
        except Exception:
            pass

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        create_capture_job(job_id, query_url)
        return jsonify({"job_id": job_id, "status": "pending"})

    @app.get("/api/jobs/<job_id>")
    def get_job_status(job_id: str) -> tuple[Any, int] | Any:
        job = get_capture_job(job_id)
        if job is None:
            return jsonify({"error": "Job not found"}), 404
        resp: dict[str, Any] = {"job_id": job_id, "status": job["status"]}
        if job["status"] == "done":
            resp["proof_url"] = f"/p/{job['proof_id']}"
        elif job["status"] == "failed":
            resp["error"] = job.get("error", "Unknown error")
        return jsonify(resp)

    @app.get("/api/jobs/claim")
    def claim_job() -> tuple[Any, int] | Any:
        token = request.args.get("token") or request.headers.get("X-Admin-Token")
        if token != app.config["ADMIN_TOKEN"]:
            return jsonify({"error": "Unauthorized"}), 401
        job = claim_next_capture_job()
        if job is None:
            return jsonify({"job": None})
        return jsonify({"job": {"job_id": job["id"], "query_url": job["query_url"]}})

    @app.post("/api/jobs/<job_id>/result")
    def submit_job_result(job_id: str) -> tuple[Any, int] | Any:
        token = request.args.get("token") or request.headers.get("X-Admin-Token")
        if token != app.config["ADMIN_TOKEN"]:
            return jsonify({"error": "Unauthorized"}), 401

        job = get_capture_job(job_id)
        if job is None:
            return jsonify({"error": "Job not found"}), 404

        payload = request.get_json(silent=True) or {}
        if payload.get("error"):
            fail_capture_job(job_id, payload["error"])
            return jsonify({"status": "failed"})

        profile_url_raw = (payload.get("profile_url") or "").strip()
        if not is_valid_mercari_profile_url(profile_url_raw):
            fail_capture_job(job_id, "Invalid profile_url in result")
            return jsonify({"error": "Invalid profile_url"}), 400
        profile_url = normalize_mercari_profile_url(profile_url_raw)

        expires_in_days = _parse_expires_in_days(None, app.config["DEFAULT_EXPIRES_DAYS"])

        try:
            capture_id = f"cap_{uuid.uuid4().hex[:12]}"
            captured_at = now_jst_iso()
            raw_html = payload.get("profile_html", "")
            visible_text = payload.get("profile_text", "")
            screenshot_b64 = payload.get("screenshot_base64")
            screenshot_bytes = base64.b64decode(screenshot_b64) if screenshot_b64 else None

            capture_data = {
                "capture_id": capture_id,
                "raw_html": raw_html,
                "visible_text": visible_text,
                "raw_html_path": save_raw_html(capture_id, raw_html),
                "visible_text_path": save_visible_text(capture_id, visible_text),
                "screenshot_path": save_screenshot(capture_id, screenshot_bytes),
                "raw_html_sha256": sha256_text(raw_html),
                "visible_text_sha256": sha256_text(visible_text),
                "screenshot_sha256": sha256_bytes(screenshot_bytes) if screenshot_bytes else None,
                "http_status": 200,
                "captured_at": captured_at,
                "review_url": payload.get("reviews_url"),
                "review_raw_html": payload.get("reviews_html"),
                "review_visible_text": payload.get("reviews_text"),
                "review_bad_visible_text": payload.get("reviews_bad_text"),
                "review_http_status": 200 if payload.get("reviews_html") else None,
            }
            resolution = {
                "query_url": job["query_url"],
                "query_kind": payload.get("query_kind", "profile"),
                "profile_url": profile_url,
                "item_raw_html": payload.get("item_html"),
                "item_visible_text": payload.get("item_text"),
                "seller_total_reviews": payload.get("seller_total_reviews"),
                "display_name": payload.get("display_name"),
            }
            review_entries = parse_review_entries(
                capture_data.get("review_raw_html"),
                capture_data.get("review_visible_text"),
                capture_data.get("review_bad_visible_text"),
            )
            parsed_data = parse_profile(
                raw_html, visible_text,
                review_raw_html=capture_data.get("review_raw_html"),
                review_visible_text=capture_data.get("review_visible_text"),
                item_raw_html=resolution.get("item_raw_html"),
                item_visible_text=resolution.get("item_visible_text"),
                item_total_reviews=resolution.get("seller_total_reviews"),
            )
            if parsed_data.get("display_name") is None and resolution.get("display_name"):
                parsed_data["display_name"] = resolution["display_name"]

            insert_capture(_build_capture_record(profile_url, capture_data, parsed_data))
            insert_review_entries(capture_id, profile_url, review_entries, captured_at)
            missing_fields = [f for f in REQUIRED_FIELDS if parsed_data.get(f) is None]
            insert_parser_run(capture_id, parsed_data["parser_version"],
                              parsed_data["extractor_strategy"], not missing_fields, missing_fields)
            proof_bundle = build_proof(profile_url, capture_data, parsed_data,
                                       review_entries=review_entries, expires_in_days=expires_in_days)
            insert_proof({
                "id": proof_bundle["proof_id"], "capture_id": capture_id,
                "proof_payload_json": pretty_json(proof_bundle["proof_payload"]),
                "proof_sha256": proof_bundle["proof_sha256"], "signature": proof_bundle["signature"],
                "kid": proof_bundle["kid"], "status": proof_bundle["status"],
                "expires_at": proof_bundle["expires_at"], "published_at": proof_bundle["published_at"],
            })
            complete_capture_job(job_id, proof_bundle["proof_id"], capture_id)
        except Exception as exc:
            fail_capture_job(job_id, str(exc))
            return jsonify({"error": str(exc)}), 500

        _record_query_event(request, job["query_url"], resolution, parsed_data,
                            "new_capture", proof_bundle["proof_id"], capture_id)
        return jsonify({"status": "done", "proof_url": f"/p/{proof_bundle['proof_id']}"})

    @app.post("/api/raw-capture")
    def raw_capture() -> tuple[Any, int] | Any:
        """Accept pre-scraped HTML from the local capture script (residential IP).
        Auth: api_key must match ADMIN_TOKEN."""
        payload = request.get_json(silent=True) or {}
        if payload.get("api_key") != app.config["ADMIN_TOKEN"]:
            return jsonify({"error": "Unauthorized"}), 401

        profile_url_raw = (payload.get("profile_url") or "").strip()
        if not is_valid_mercari_profile_url(profile_url_raw):
            return jsonify({"error": "Invalid profile_url"}), 400
        profile_url = normalize_mercari_profile_url(profile_url_raw)

        expires_in_days = _parse_expires_in_days(
            payload.get("expires_in_days"), app.config["DEFAULT_EXPIRES_DAYS"]
        )

        try:
            reusable_proof = find_latest_reusable_proof_by_source_url(profile_url)
            reviews_url = build_mercari_reviews_url(profile_url)
            if reusable_proof is not None:
                if not _has_new_reviews(profile_url, reviews_url):
                    return jsonify({
                        "capture_id": reusable_proof["capture_id"],
                        "proof_id": reusable_proof["proof_id"],
                        "proof_url": f"/p/{reusable_proof['proof_id']}",
                        "profile_url": profile_url,
                        "reused": True,
                    })

            capture_id = f"cap_{uuid.uuid4().hex[:12]}"
            captured_at = now_jst_iso()
            raw_html = payload.get("profile_html", "")
            visible_text = payload.get("profile_text", "")
            screenshot_b64 = payload.get("screenshot_base64")
            screenshot_bytes = base64.b64decode(screenshot_b64) if screenshot_b64 else None

            capture_data = {
                "capture_id": capture_id,
                "raw_html": raw_html,
                "visible_text": visible_text,
                "raw_html_path": save_raw_html(capture_id, raw_html),
                "visible_text_path": save_visible_text(capture_id, visible_text),
                "screenshot_path": save_screenshot(capture_id, screenshot_bytes),
                "raw_html_sha256": sha256_text(raw_html),
                "visible_text_sha256": sha256_text(visible_text),
                "screenshot_sha256": sha256_bytes(screenshot_bytes) if screenshot_bytes else None,
                "http_status": 200,
                "captured_at": captured_at,
                "review_url": payload.get("reviews_url"),
                "review_raw_html": payload.get("reviews_html"),
                "review_visible_text": payload.get("reviews_text"),
                "review_bad_visible_text": payload.get("reviews_bad_text"),
                "review_http_status": 200 if payload.get("reviews_html") else None,
            }

            resolution = {
                "query_url": payload.get("query_url") or profile_url,
                "query_kind": payload.get("query_kind", "profile"),
                "profile_url": profile_url,
                "item_raw_html": payload.get("item_html"),
                "item_visible_text": payload.get("item_text"),
                "seller_total_reviews": payload.get("seller_total_reviews"),
                "display_name": payload.get("display_name"),
            }

            review_entries = parse_review_entries(
                capture_data.get("review_raw_html"),
                capture_data.get("review_visible_text"),
                capture_data.get("review_bad_visible_text"),
            )
            parsed_data = parse_profile(
                capture_data["raw_html"],
                capture_data["visible_text"],
                review_raw_html=capture_data.get("review_raw_html"),
                review_visible_text=capture_data.get("review_visible_text"),
                item_raw_html=resolution.get("item_raw_html"),
                item_visible_text=resolution.get("item_visible_text"),
                item_total_reviews=resolution.get("seller_total_reviews"),
            )
            if parsed_data.get("display_name") is None and resolution.get("display_name"):
                parsed_data["display_name"] = resolution["display_name"]

            insert_capture(_build_capture_record(profile_url, capture_data, parsed_data))
            insert_review_entries(capture_id, profile_url, review_entries, captured_at)
            missing_fields = [f for f in REQUIRED_FIELDS if parsed_data.get(f) is None]
            insert_parser_run(
                capture_id,
                parsed_data["parser_version"],
                parsed_data["extractor_strategy"],
                not missing_fields,
                missing_fields,
            )
            proof_bundle = build_proof(
                profile_url, capture_data, parsed_data,
                review_entries=review_entries,
                expires_in_days=expires_in_days,
            )
            insert_proof({
                "id": proof_bundle["proof_id"],
                "capture_id": capture_id,
                "proof_payload_json": pretty_json(proof_bundle["proof_payload"]),
                "proof_sha256": proof_bundle["proof_sha256"],
                "signature": proof_bundle["signature"],
                "kid": proof_bundle["kid"],
                "status": proof_bundle["status"],
                "expires_at": proof_bundle["expires_at"],
                "published_at": proof_bundle["published_at"],
            })
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

        _record_query_event(
            request, resolution["query_url"], resolution, parsed_data,
            "new_capture", proof_bundle["proof_id"], capture_id,
        )
        return jsonify({
            "capture_id": capture_id,
            "proof_id": proof_bundle["proof_id"],
            "proof_url": f"/p/{proof_bundle['proof_id']}",
            "profile_url": profile_url,
            "reused": False,
        })

    @app.get("/api/proofs/<proof_id>")
    def get_proof_json(proof_id: str) -> tuple[Any, int] | Any:
        document = get_proof_document(proof_id)
        if document is None:
            return jsonify({"error": "Proof not found."}), 404
        return jsonify(document)

    @app.post("/api/verify")
    def verify() -> Any:
        payload = request.get_json(silent=True) or {}
        proof_input = payload.get("proof")
        signature = payload.get("signature")
        proof_payload, resolved_signature = _normalize_verify_input(proof_input, signature)
        result = verify_proof(proof_payload, resolved_signature)
        return jsonify(result)

    @app.post("/api/proofs/<proof_id>/revoke")
    def revoke(proof_id: str) -> tuple[Any, int] | Any:
        if get_proof(proof_id) is None:
            return jsonify({"error": "Proof not found."}), 404

        payload = request.get_json(silent=True) or {}
        reason = payload.get("reason", "revoked_by_operator")
        revoke_proof(proof_id, reason)
        return jsonify({"proof_id": proof_id, "status": "revoked", "reason": reason})

    @app.get("/admin")
    def admin_dashboard() -> Any:
        token = request.args.get("token") or request.cookies.get("admin_token")
        if not token or token != app.config["ADMIN_TOKEN"]:
            return "Unauthorized", 401
        stats = get_admin_stats()
        max_cat = max((c["total"] for c in stats["top_categories"]), default=1)
        max_kw = max((k["count"] for k in stats["top_keywords"]), default=1)
        resp = make_response(render_template("admin.html", stats=stats, max_cat=max_cat, max_kw=max_kw))
        if request.args.get("token") == app.config["ADMIN_TOKEN"]:
            resp.set_cookie("admin_token", token, max_age=86400, httponly=True, samesite="Lax")
        return resp

    @app.get("/p/<proof_id>")
    def proof_page(proof_id: str) -> tuple[str, int] | str:
        document = get_proof_document(proof_id)
        if document is None:
            lang = detect_lang(request)
            t = get_translations(lang)
            return render_template("partial.html", proof=None, missing_fields=["proof_not_found"], t=t, lang=lang), 404

        missing_fields = _missing_required_fields(document)
        template_name = "partial.html" if document.get("status") == "partial" else "proof.html"
        proof_view = build_proof_view(document)
        lang = detect_lang(request)
        t = get_translations(lang)

        source_url = document.get("source_url", "")
        all_proofs = get_proofs_by_source_url(source_url) if source_url else [document]
        timeline = build_timeline(all_proofs, proof_id)
        _format_timeline_nodes(timeline, t)

        return render_template(
            template_name,
            proof=document,
            proof_view=proof_view,
            missing_fields=missing_fields,
            proof_json=pretty_json(document),
            t=t,
            lang=lang,
            timeline=timeline,
        )

    return app


def _get_client_ip(req: Any) -> str:
    forwarded = req.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = req.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return req.remote_addr or ""


def _capture_to_parsed_signals(capture: dict[str, Any] | None) -> dict[str, Any]:
    if not capture:
        return {}
    import json as _json
    try:
        sample_items = _json.loads(capture.get("sample_items_json") or "[]")
    except Exception:
        sample_items = []
    return {
        "display_name": capture.get("display_name"),
        "sample_items": sample_items,
        "bio_excerpt": capture.get("bio_excerpt"),
    }


def _record_query_event(
    req: Any,
    query_url: str,
    resolution: dict[str, Any],
    parsed_data: dict[str, Any],
    result: str,
    proof_id: str | None,
    capture_id: str | None,
) -> None:
    try:
        sample_items = [str(i) for i in (parsed_data.get("sample_items") or [])]
        categories = infer_primary_categories(sample_items, parsed_data.get("bio_excerpt"))
        insert_query_event({
            "query_url": query_url,
            "query_kind": resolution.get("query_kind"),
            "profile_url": resolution.get("profile_url"),
            "display_name": parsed_data.get("display_name") or resolution.get("display_name"),
            "result": result,
            "proof_id": proof_id,
            "capture_id": capture_id,
            "primary_category": categories[0] if categories else None,
            "ip_address": _get_client_ip(req),
        })
    except Exception:
        pass


def _has_new_reviews(source_url: str, reviews_url: str) -> bool:
    """Returns True if the latest live review differs from what is stored in the DB."""
    stored_hash = get_latest_review_entry_hash(source_url)
    if stored_hash is None:
        # No review entries stored yet — force re-capture.
        return True
    try:
        capture = capture_lookup_page(reviews_url)
        entries = parse_review_entries(capture.get("raw_html"), capture.get("visible_text"))
        if not entries:
            return False
        first = entries[0]
        body = first.get("body_excerpt") or ""
        live_hash = sha256_text(f"{first['role']}|{first['rating']}|{body}")
        return live_hash != stored_hash
    except Exception:
        return False


def _extract_query_url(payload: dict[str, Any]) -> str:
    return str(
        payload.get("query_url")
        or payload.get("item_url")
        or payload.get("profile_url")
        or ""
    ).strip()


def _parse_expires_in_days(raw_value: Any, default_value: int) -> int:
    try:
        return int(raw_value or default_value)
    except (TypeError, ValueError):
        return int(default_value)


def _build_capture_record(source_url: str, capture_data: dict[str, Any], parsed_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": capture_data["capture_id"],
        "source_url": source_url,
        "source_platform": "mercari_jp",
        "display_name": parsed_data.get("display_name"),
        "avatar_url": parsed_data.get("avatar_url"),
        "verified_badge": parsed_data.get("verified_badge"),
        "total_reviews": parsed_data.get("total_reviews"),
        "positive_reviews": parsed_data.get("positive_reviews"),
        "negative_reviews": parsed_data.get("negative_reviews"),
        "listing_count": parsed_data.get("listing_count"),
        "followers_count": parsed_data.get("followers_count"),
        "following_count": parsed_data.get("following_count"),
        "bio_excerpt": parsed_data.get("bio_excerpt"),
        "sample_items": parsed_data.get("sample_items", []),
        "raw_html_path": capture_data["raw_html_path"],
        "raw_html_sha256": capture_data["raw_html_sha256"],
        "visible_text_path": capture_data["visible_text_path"],
        "visible_text_sha256": capture_data["visible_text_sha256"],
        "screenshot_path": capture_data["screenshot_path"],
        "screenshot_sha256": capture_data["screenshot_sha256"],
        "parser_version": parsed_data["parser_version"],
        "extractor_strategy": parsed_data["extractor_strategy"],
        "llm_repair_applied": parsed_data["llm_repair_applied"],
        "completeness_status": parsed_data["completeness_status"],
        "captured_at": capture_data["captured_at"],
    }


def _normalize_verify_input(proof_input: Any, signature: Any) -> tuple[dict[str, Any], str]:
    proof = dict(proof_input or {})
    resolved_signature = signature or proof.pop("signature", None)
    proof.pop("kid", None)
    proof.pop("proof_sha256", None)
    proof.pop("revoked_at", None)
    proof.pop("revocation_reason", None)
    if not resolved_signature:
        resolved_signature = ""
    return proof, str(resolved_signature)


def _format_timeline_nodes(timeline: list[dict[str, Any]], t: dict[str, str]) -> None:
    field_labels: dict[str, str] = {
        "metrics.total_reviews": t.get("total_reviews", "reviews"),
        "metrics.positive_reviews": t.get("positive", "positive"),
        "metrics.negative_reviews": t.get("negative", "negative"),
        "metrics.listing_count": t.get("listings", "listings"),
        "metrics.followers_count": t.get("followers", "followers"),
        "metrics.following_count": t.get("following", "following"),
        "quality.overall.rate": t.get("quality_overall", "quality"),
        "subject.display_name": t.get("display_name_label", "Name"),
        "subject.verified_badge": t.get("badge_label", "Badge"),
    }
    for node in timeline:
        captured_at = node.get("captured_at", "")
        node["display_date"] = captured_at[:10] if len(captured_at) >= 10 else captured_at

        diff = node.get("diff_from_prev")
        summaries: list[str] = []
        if diff and diff.get("changes"):
            for change in diff["changes"]:
                field = change["field"]
                label = field_labels.get(field, field.split(".")[-1])
                delta = change.get("delta")
                old_val = change.get("old")
                new_val = change.get("new")
                if delta is not None:
                    prefix = "+" if delta > 0 else ""
                    summaries.append(f"{prefix}{delta} {label}")
                elif old_val is not None and new_val is not None:
                    summaries.append(f"{label}: {old_val}\u2192{new_val}")
        node["change_summary"] = summaries


def _missing_required_fields(document: dict[str, Any]) -> list[str]:
    subject = document.get("subject", {})
    metrics = document.get("metrics", {})
    values = {
        "display_name": subject.get("display_name"),
        "total_reviews": metrics.get("total_reviews"),
        "listing_count": metrics.get("listing_count"),
        "followers_count": metrics.get("followers_count"),
        "following_count": metrics.get("following_count"),
    }
    return [field for field, value in values.items() if value is None]


app = create_app()


if __name__ == "__main__":
    app.run(host=app.config["APP_HOST"], port=app.config["APP_PORT"], debug=False)
