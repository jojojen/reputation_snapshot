"""
Inserts 5 fake snapshots of a demo seller for testing the timeline UI.

Usage:
    python seed_demo.py          # insert demo data
    python seed_demo.py --reset  # delete existing demo data, then re-insert
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

# ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.proof_service import build_proof
from services.storage_service import insert_capture, insert_proof, insert_review_entries
from utils.db_utils import ensure_runtime_directories, get_db_connection, init_db, project_path

DEMO_SOURCE_URL = "https://jp.mercari.com/user/profile/u_demo_test_seller"

SNAPSHOTS = [
    {
        "capture_id": "cap_demo_001",
        "captured_at": "2025-09-15T10:00:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": False,
        "total_reviews": 89,
        "positive_reviews": 87,
        "negative_reviews": 2,
        "listing_count": 42,
        "followers_count": 98,
        "following_count": 65,
        "bio_excerpt": "フリマ初心者です。丁寧な梱包を心がけています。",
        "sample_items": ["ノートPC", "キーボード", "マウス", "USBハブ"],
        "review_entries": [
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な発送でした。商品も説明通りで満足です。", "entry_order": 1},
            {"role": "buyer", "rating": "positive", "body_excerpt": "丁寧な対応をしていただきました。", "entry_order": 2},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が丁寧で良かったです。", "entry_order": 3},
            {"role": "seller", "rating": "negative", "body_excerpt": "発送が遅かった。連絡も少なかったです。", "entry_order": 4},
            {"role": "seller", "rating": "positive", "body_excerpt": "またよろしくお願いします。", "entry_order": 5},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い取引でした。", "entry_order": 6},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の状態も良く、すぐ届きました。", "entry_order": 7},
            {"role": "seller", "rating": "positive", "body_excerpt": "ありがとうございました。", "entry_order": 8},
        ],
    },
    {
        "capture_id": "cap_demo_002",
        "captured_at": "2025-11-20T14:30:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": True,
        "total_reviews": 256,
        "positive_reviews": 251,
        "negative_reviews": 5,
        "listing_count": 71,
        "followers_count": 195,
        "following_count": 78,
        "bio_excerpt": "フリマ初心者です。丁寧な梱包を心がけています。",
        "sample_items": ["ノートPC", "キーボード", "マウス", "USBハブ", "モバイルバッテリー"],
        "review_entries": [
            {"role": "seller", "rating": "positive", "body_excerpt": "品質も良くすぐ届きました！またお願いしたいです。", "entry_order": 1},
            {"role": "seller", "rating": "positive", "body_excerpt": "とても丁寧な梱包でした。", "entry_order": 2},
            {"role": "buyer", "rating": "positive", "body_excerpt": "購入してすぐ発送してもらいました。", "entry_order": 3},
            {"role": "seller", "rating": "positive", "body_excerpt": "説明通りの商品でした。", "entry_order": 4},
            {"role": "seller", "rating": "negative", "body_excerpt": "思ってたより状態が悪かった。", "entry_order": 5},
            {"role": "buyer", "rating": "positive", "body_excerpt": "問題なく取引できました。", "entry_order": 6},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な対応ありがとうございます。", "entry_order": 7},
            {"role": "seller", "rating": "positive", "body_excerpt": "また機会があればよろしくお願いします。", "entry_order": 8},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い方でした。", "entry_order": 9},
            {"role": "seller", "rating": "positive", "body_excerpt": "ありがとうございました。", "entry_order": 10},
        ],
    },
    {
        "capture_id": "cap_demo_003",
        "captured_at": "2026-01-10T09:15:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": True,
        "total_reviews": 412,
        "positive_reviews": 405,
        "negative_reviews": 7,
        "listing_count": 93,
        "followers_count": 288,
        "following_count": 90,
        "bio_excerpt": "フリマ初心者です。丁寧な梱包を心がけています。",
        "sample_items": ["ノートPC", "キーボード", "マウス", "USBハブ", "モバイルバッテリー", "ゲームソフト"],
        "review_entries": [
            {"role": "buyer", "rating": "positive", "body_excerpt": "新年の取引もスムーズでした。ありがとうございます。", "entry_order": 1},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が丁寧で状態も良かったです。", "entry_order": 2},
            {"role": "seller", "rating": "positive", "body_excerpt": "スムーズな取引でした。", "entry_order": 3},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品状態も良く満足です。", "entry_order": 4},
            {"role": "buyer", "rating": "positive", "body_excerpt": "また利用したいです。", "entry_order": 5},
            {"role": "seller", "rating": "negative", "body_excerpt": "梱包が雑でした。", "entry_order": 6},
            {"role": "seller", "rating": "positive", "body_excerpt": "対応が早くて助かりました。", "entry_order": 7},
            {"role": "buyer", "rating": "positive", "body_excerpt": "迅速な対応をいただきました。", "entry_order": 8},
            {"role": "seller", "rating": "positive", "body_excerpt": "ありがとうございました！", "entry_order": 9},
            {"role": "seller", "rating": "positive", "body_excerpt": "説明通りの商品でした。", "entry_order": 10},
            {"role": "seller", "rating": "positive", "body_excerpt": "また取引できれば幸いです。", "entry_order": 11},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い商品でした。", "entry_order": 12},
        ],
    },
    {
        "capture_id": "cap_demo_004",
        "captured_at": "2026-03-28T11:00:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": True,
        "total_reviews": 531,
        "positive_reviews": 519,
        "negative_reviews": 12,
        "listing_count": 82,
        "followers_count": 274,
        "following_count": 94,
        "bio_excerpt": "フリマ初心者です。丁寧な梱包を心がけています。",
        "sample_items": ["ノートPC", "キーボード", "マウス", "ゲームソフト", "フィギュア"],
        "review_entries": [
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包完璧でした。また購入したいです。", "entry_order": 1},
            {"role": "seller", "rating": "negative", "body_excerpt": "思ったより傷がありました。説明不足では？", "entry_order": 2},
            {"role": "seller", "rating": "positive", "body_excerpt": "すぐ届きました。ありがとうございます。", "entry_order": 3},
            {"role": "buyer", "rating": "positive", "body_excerpt": "丁寧な梱包でした。", "entry_order": 4},
            {"role": "seller", "rating": "positive", "body_excerpt": "良い商品でした。", "entry_order": 5},
            {"role": "seller", "rating": "negative", "body_excerpt": "発送が予定より2日遅れた。", "entry_order": 6},
            {"role": "seller", "rating": "positive", "body_excerpt": "問題なく取引できました。", "entry_order": 7},
            {"role": "buyer", "rating": "positive", "body_excerpt": "スムーズな取引でした。", "entry_order": 8},
            {"role": "seller", "rating": "positive", "body_excerpt": "またよろしくお願いします。", "entry_order": 9},
            {"role": "seller", "rating": "positive", "body_excerpt": "ありがとうございました。", "entry_order": 10},
            {"role": "seller", "rating": "positive", "body_excerpt": "丁寧な対応でした。", "entry_order": 11},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い取引でした。", "entry_order": 12},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の説明通りでした。", "entry_order": 13},
        ],
    },
    {
        "capture_id": "cap_demo_005",
        "captured_at": "2026-04-05T16:45:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": True,
        "total_reviews": 618,
        "positive_reviews": 543,
        "negative_reviews": 75,
        "listing_count": 4,
        "followers_count": 185,
        "following_count": 97,
        "bio_excerpt": "フリマ初心者です。丁寧な梱包を心がけています。",
        "sample_items": ["フィギュア", "アニメグッズ"],
        "review_entries": [
            {"role": "seller", "rating": "negative", "body_excerpt": "商品が届いたが説明と全然違う。返金対応もしてもらえなかった。", "entry_order": 1},
            {"role": "seller", "rating": "negative", "body_excerpt": "発送がとても遅かった。連絡も取れず困りました。", "entry_order": 2},
            {"role": "seller", "rating": "negative", "body_excerpt": "写真と実物が違いすぎます。", "entry_order": 3},
            {"role": "seller", "rating": "positive", "body_excerpt": "問題なく届きました。", "entry_order": 4},
            {"role": "seller", "rating": "negative", "body_excerpt": "梱包がひどく中身が傷ついていた。", "entry_order": 5},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い方でした。", "entry_order": 6},
            {"role": "seller", "rating": "negative", "body_excerpt": "全く別の商品が届いた。最悪でした。", "entry_order": 7},
            {"role": "seller", "rating": "positive", "body_excerpt": "早めに届きました。", "entry_order": 8},
            {"role": "seller", "rating": "negative", "body_excerpt": "返答が遅すぎる。", "entry_order": 9},
            {"role": "seller", "rating": "negative", "body_excerpt": "説明に偽りあり。二度と利用しません。", "entry_order": 10},
            {"role": "seller", "rating": "positive", "body_excerpt": "ありがとうございました。", "entry_order": 11},
            {"role": "seller", "rating": "negative", "body_excerpt": "評価通りの商品ではなかった。", "entry_order": 12},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包も丁寧でした。", "entry_order": 13},
            {"role": "buyer", "rating": "positive", "body_excerpt": "取引ありがとうございます。", "entry_order": 14},
            {"role": "seller", "rating": "negative", "body_excerpt": "雑な梱包で商品が破損していた。", "entry_order": 15},
        ],
    },
]


def _fake_sha256(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _create_stub_files(capture_id: str) -> tuple[str, str, str]:
    html_path = project_path("captures", "html", f"{capture_id}.html")
    text_path = project_path("captures", "text", f"{capture_id}.txt")
    shot_path = project_path("captures", "screenshots", f"{capture_id}.png")
    html_path.write_text(f"<!-- demo stub {capture_id} -->", encoding="utf-8")
    text_path.write_text(f"demo stub {capture_id}", encoding="utf-8")
    shot_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header stub
    return str(html_path), str(text_path), str(shot_path)


def _delete_demo_data() -> None:
    with get_db_connection() as conn:
        cap_ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM captures WHERE source_url = ?", (DEMO_SOURCE_URL,)
            ).fetchall()
        ]
        if cap_ids:
            placeholders = ",".join("?" * len(cap_ids))
            conn.execute(f"DELETE FROM review_entries WHERE source_url = ?", (DEMO_SOURCE_URL,))
            conn.execute(f"DELETE FROM proofs WHERE capture_id IN ({placeholders})", cap_ids)
            conn.execute(f"DELETE FROM captures WHERE id IN ({placeholders})", cap_ids)
            conn.commit()
            print(f"Deleted {len(cap_ids)} existing demo captures.")


def _already_seeded() -> bool:
    with get_db_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM captures WHERE source_url = ?", (DEMO_SOURCE_URL,)
        ).fetchone()[0]
    return count > 0


def main() -> None:
    reset = "--reset" in sys.argv
    ensure_runtime_directories()
    init_db()

    if _already_seeded():
        if reset:
            _delete_demo_data()
        else:
            print("Demo data already present. Use --reset to recreate.")
            _print_url()
            return

    print(f"Seeding {len(SNAPSHOTS)} demo snapshots...")

    last_proof_id = None
    for snap in SNAPSHOTS:
        cid = snap["capture_id"]
        html_path, text_path, shot_path = _create_stub_files(cid)
        review_entries = snap.get("review_entries") or []

        capture_data = {
            "capture_id": cid,
            "raw_html_path": html_path,
            "raw_html_sha256": _fake_sha256(f"{cid}_html"),
            "visible_text_path": text_path,
            "visible_text_sha256": _fake_sha256(f"{cid}_text"),
            "screenshot_path": shot_path,
            "screenshot_sha256": _fake_sha256(f"{cid}_shot"),
            "captured_at": snap["captured_at"],
        }

        parsed_data = {
            "display_name": snap["display_name"],
            "avatar_url": snap["avatar_url"],
            "verified_badge": snap["verified_badge"],
            "total_reviews": snap["total_reviews"],
            "positive_reviews": snap["positive_reviews"],
            "negative_reviews": snap["negative_reviews"],
            "listing_count": snap["listing_count"],
            "followers_count": snap["followers_count"],
            "following_count": snap["following_count"],
            "bio_excerpt": snap["bio_excerpt"],
            "sample_items": snap["sample_items"],
            "parser_version": "demo_seed_v2",
            "extractor_strategy": "demo",
            "llm_repair_applied": False,
            "completeness_status": "complete",
        }

        capture_record = {
            "id": cid,
            "source_url": DEMO_SOURCE_URL,
            "source_platform": "mercari_jp",
            **{k: snap.get(k) for k in (
                "display_name", "avatar_url", "verified_badge",
                "total_reviews", "positive_reviews", "negative_reviews",
                "listing_count", "followers_count", "following_count", "bio_excerpt",
            )},
            "sample_items": snap["sample_items"],
            "raw_html_path": html_path,
            "raw_html_sha256": capture_data["raw_html_sha256"],
            "visible_text_path": text_path,
            "visible_text_sha256": capture_data["visible_text_sha256"],
            "screenshot_path": shot_path,
            "screenshot_sha256": capture_data["screenshot_sha256"],
            "parser_version": "demo_seed_v2",
            "extractor_strategy": "demo",
            "llm_repair_applied": False,
            "completeness_status": "complete",
            "captured_at": snap["captured_at"],
        }
        insert_capture(capture_record)

        insert_review_entries(cid, DEMO_SOURCE_URL, review_entries, snap["captured_at"])

        bundle = build_proof(
            DEMO_SOURCE_URL,
            capture_data,
            parsed_data,
            review_entries=review_entries,
            expires_in_days=3650,
        )
        insert_proof({
            "id": bundle["proof_id"],
            "capture_id": cid,
            "proof_payload_json": __import__("utils.json_utils", fromlist=["pretty_json"]).pretty_json(bundle["proof_payload"]),
            "proof_sha256": bundle["proof_sha256"],
            "signature": bundle["signature"],
            "kid": bundle["kid"],
            "status": bundle["status"],
            "expires_at": bundle["expires_at"],
            "published_at": bundle["published_at"],
        })
        last_proof_id = bundle["proof_id"]
        quality = bundle["proof_payload"].get("quality") or {}
        overall = quality.get("overall") or {}
        rate = overall.get("rate")
        entry_count = quality.get("entry_count", 0)
        print(f"  [OK] {snap['captured_at'][:10]}  reviews={snap['total_reviews']}  listing={snap['listing_count']}  quality={rate}% ({entry_count} entries)  proof_id={bundle['proof_id']}")

    print("\nDone.")
    _print_url(last_proof_id)


def _print_url(proof_id: str | None = None) -> None:
    if proof_id:
        print(f"\nOpen the latest snapshot:\n  http://127.0.0.1:5000/p/{proof_id}\n")
    else:
        print(f"\nSeller URL:  {DEMO_SOURCE_URL}\n")


if __name__ == "__main__":
    main()
