from __future__ import annotations

from pathlib import Path

import app as app_module

from utils.hash_utils import sha256_text


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _fixture_text(fixture_name: str, extension: str) -> str:
    return (FIXTURE_DIR / f"{fixture_name}.{extension}").read_text(encoding="utf-8")


def test_index_route(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert b"Mercari Reputation Snapshot" in response.data


def test_capture_route_creates_proof_and_verify_roundtrip(client, monkeypatch) -> None:
    raw_html = _fixture_text("fixture_high", "html")
    visible_text = _fixture_text("fixture_high", "txt")

    def fake_capture_profile(profile_url: str) -> dict[str, str | int]:
        return {
            "capture_id": "cap_api_001",
            "raw_html": raw_html,
            "visible_text": visible_text,
            "raw_html_path": str(FIXTURE_DIR / "fixture_high.html"),
            "visible_text_path": str(FIXTURE_DIR / "fixture_high.txt"),
            "screenshot_path": str(FIXTURE_DIR / "fixture_high.png"),
            "raw_html_sha256": sha256_text(raw_html),
            "visible_text_sha256": sha256_text(visible_text),
            "screenshot_sha256": sha256_text("fixture_high.png"),
            "http_status": 200,
            "captured_at": "2026-04-18T09:00:00+09:00",
        }

    monkeypatch.setattr(app_module, "capture_profile", fake_capture_profile)

    capture_response = client.post(
        "/api/captures",
        json={
            "profile_url": "https://jp.mercari.com/user/profile/555555555",
            "expires_in_days": 30,
        },
    )

    assert capture_response.status_code == 200
    capture_payload = capture_response.get_json()
    assert capture_payload["capture_id"] == "cap_api_001"
    assert capture_payload["proof_url"].startswith("/p/")

    proof_response = client.get(f"/api/proofs/{capture_payload['proof_id']}")
    assert proof_response.status_code == 200
    proof_document = proof_response.get_json()
    assert proof_document["subject"]["display_name"] == "青空商店"

    proof_page_response = client.get(capture_payload["proof_url"])
    assert proof_page_response.status_code == 200
    assert b"Mercari JP" in proof_page_response.data

    verify_response = client.post("/api/verify", json={"proof": proof_document})
    assert verify_response.status_code == 200
    assert verify_response.get_json()["valid"] is True


def test_revoke_route_updates_proof_status(client, monkeypatch) -> None:
    raw_html = _fixture_text("fixture_medium", "html")
    visible_text = _fixture_text("fixture_medium", "txt")

    def fake_capture_profile(profile_url: str) -> dict[str, str | int]:
        return {
            "capture_id": "cap_api_002",
            "raw_html": raw_html,
            "visible_text": visible_text,
            "raw_html_path": str(FIXTURE_DIR / "fixture_medium.html"),
            "visible_text_path": str(FIXTURE_DIR / "fixture_medium.txt"),
            "screenshot_path": str(FIXTURE_DIR / "fixture_medium.png"),
            "raw_html_sha256": sha256_text(raw_html),
            "visible_text_sha256": sha256_text(visible_text),
            "screenshot_sha256": sha256_text("fixture_medium.png"),
            "http_status": 200,
            "captured_at": "2026-04-18T09:00:00+09:00",
        }

    monkeypatch.setattr(app_module, "capture_profile", fake_capture_profile)

    capture_response = client.post(
        "/api/captures",
        json={
            "profile_url": "https://jp.mercari.com/user/profile/666666666",
            "expires_in_days": 30,
        },
    )
    proof_id = capture_response.get_json()["proof_id"]

    revoke_response = client.post(f"/api/proofs/{proof_id}/revoke", json={"reason": "policy_test"})
    assert revoke_response.status_code == 200
    assert revoke_response.get_json()["status"] == "revoked"

    proof_response = client.get(f"/api/proofs/{proof_id}")
    assert proof_response.status_code == 200
    assert proof_response.get_json()["status"] == "revoked"
