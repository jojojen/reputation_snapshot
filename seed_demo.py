"""
Inserts 3 fake snapshots of a demo seller for testing the timeline UI.

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
    # ── Snapshot 1: 2026-01-01 ─── total 200, recent 100 reviews: 80 good / 20 bad
    #    early records = 200 - 80 - 20 = 100 (older transactions outside rating window)
    {
        "capture_id": "cap_demo_001",
        "captured_at": "2026-01-01T10:00:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": True,
        "total_reviews": 200,
        "positive_reviews": 80,
        "negative_reviews": 20,
        "listing_count": 35,
        "followers_count": 120,
        "following_count": 40,
        "bio_excerpt": "ポケモンカードやゲーム関連商品を中心に出品しています。丁寧な梱包を心がけています。",
        "sample_items": ["ポケモンカード", "トレーディングカード", "ゲームソフト", "フィギュア"],
        "review_entries": [
            # 90 good (seller role: 75, buyer role: 15)
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な発送で、商品も説明通りでした。また利用します。", "entry_order": 1},
            {"role": "seller", "rating": "positive", "body_excerpt": "丁寧な梱包でした。商品の状態も良く満足です。", "entry_order": 2},
            {"role": "seller", "rating": "positive", "body_excerpt": "とても良い取引でした。信頼できる出品者さんです。", "entry_order": 3},
            {"role": "seller", "rating": "positive", "body_excerpt": "素早い対応でした。問題なく届きました。ありがとうございます。", "entry_order": 4},
            {"role": "buyer", "rating": "positive", "body_excerpt": "とても良いお買い物ができました。ありがとうございます。", "entry_order": 5},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の状態が写真通りで安心しました。", "entry_order": 6},
            {"role": "seller", "rating": "positive", "body_excerpt": "発送が早く、梱包も丁寧でした。また購入したいです。", "entry_order": 7},
            {"role": "seller", "rating": "positive", "body_excerpt": "想像以上に良い状態でした。対応も丁寧でした。", "entry_order": 8},
            {"role": "seller", "rating": "positive", "body_excerpt": "スムーズな取引ができました。おすすめの出品者さんです。", "entry_order": 9},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が完璧でした。商品も期待通りです。", "entry_order": 10},
            {"role": "buyer", "rating": "positive", "body_excerpt": "すぐに発送していただきました。助かりました。", "entry_order": 11},
            {"role": "seller", "rating": "positive", "body_excerpt": "対応が親切で、発送も早かったです。", "entry_order": 12},
            {"role": "seller", "rating": "positive", "body_excerpt": "説明通りの商品で満足しています。ありがとうございました。", "entry_order": 13},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速に発送していただきました。良い取引でした。", "entry_order": 14},
            {"role": "seller", "rating": "positive", "body_excerpt": "質問にも素早く回答してもらいました。安心して購入できます。", "entry_order": 15},
            {"role": "buyer", "rating": "positive", "body_excerpt": "丁寧な取引をしていただきました。良い方です。", "entry_order": 16},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が丁寧で、商品に傷もありませんでした。", "entry_order": 17},
            {"role": "seller", "rating": "positive", "body_excerpt": "初めて利用しましたが、とても良かったです。", "entry_order": 18},
            {"role": "seller", "rating": "positive", "body_excerpt": "綺麗な状態で届きました。また機会があれば利用します。", "entry_order": 19},
            {"role": "seller", "rating": "positive", "body_excerpt": "スムーズな取引でした。また購入させていただきます。", "entry_order": 20},
            {"role": "buyer", "rating": "positive", "body_excerpt": "素早い対応に感謝します。また取引したいです。", "entry_order": 21},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品説明が正確で、写真通りでした。信頼できます。", "entry_order": 22},
            {"role": "seller", "rating": "positive", "body_excerpt": "すぐに届きました。梱包も問題ありませんでした。", "entry_order": 23},
            {"role": "seller", "rating": "positive", "body_excerpt": "状態の良い商品をありがとうございました。", "entry_order": 24},
            {"role": "seller", "rating": "positive", "body_excerpt": "発送が早くて助かりました。また購入します。", "entry_order": 25},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い商品をありがとうございました。また機会があれば。", "entry_order": 26},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の状態が良く、対応も丁寧でした。", "entry_order": 27},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包がしっかりしていて安心しました。", "entry_order": 28},
            {"role": "seller", "rating": "positive", "body_excerpt": "写真通りの商品で満足しました。ありがとうございます。", "entry_order": 29},
            {"role": "seller", "rating": "positive", "body_excerpt": "対応が迅速で信頼できる出品者さんです。", "entry_order": 30},
            {"role": "buyer", "rating": "positive", "body_excerpt": "丁寧な取引をしていただき、ありがとうございました。", "entry_order": 31},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品が綺麗な状態で届き、とても満足です。", "entry_order": 32},
            {"role": "seller", "rating": "positive", "body_excerpt": "説明以上の状態でした。また購入したいと思います。", "entry_order": 33},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な取引ありがとうございました。おすすめです。", "entry_order": 34},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包も丁寧で、商品も説明通りでした。", "entry_order": 35},
            {"role": "buyer", "rating": "positive", "body_excerpt": "とても親切な対応でした。安心して取引できました。", "entry_order": 36},
            {"role": "seller", "rating": "positive", "body_excerpt": "発送が早く、商品状態も良かったです。", "entry_order": 37},
            {"role": "seller", "rating": "positive", "body_excerpt": "信頼できる出品者さんです。また利用します。", "entry_order": 38},
            {"role": "seller", "rating": "positive", "body_excerpt": "丁寧なメッセージ対応でした。良い取引でした。", "entry_order": 39},
            {"role": "seller", "rating": "positive", "body_excerpt": "スムーズな取引ができ、商品も満足です。", "entry_order": 40},
            {"role": "buyer", "rating": "positive", "body_excerpt": "素早い発送でした。また購入させていただきます。", "entry_order": 41},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の品質が高く、梱包も丁寧でした。", "entry_order": 42},
            {"role": "seller", "rating": "positive", "body_excerpt": "また機会があればよろしくお願いします。", "entry_order": 43},
            {"role": "seller", "rating": "positive", "body_excerpt": "想定通りの商品が届きました。ありがとうございます。", "entry_order": 44},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包がとても丁寧でした。商品も良い状態でした。", "entry_order": 45},
            {"role": "buyer", "rating": "positive", "body_excerpt": "問題なく取引できました。ありがとうございました。", "entry_order": 46},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な対応と梱包に感謝します。また利用します。", "entry_order": 47},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品が写真通りで、発送も早かったです。", "entry_order": 48},
            {"role": "seller", "rating": "positive", "body_excerpt": "対応が親切で安心して購入できました。", "entry_order": 49},
            {"role": "seller", "rating": "positive", "body_excerpt": "良い商品をありがとうございました。また購入します。", "entry_order": 50},
            {"role": "buyer", "rating": "positive", "body_excerpt": "迅速な取引でした。また機会があれば利用したいです。", "entry_order": 51},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が完璧で商品も綺麗でした。おすすめです。", "entry_order": 52},
            {"role": "seller", "rating": "positive", "body_excerpt": "質問への対応が迅速でした。信頼できます。", "entry_order": 53},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の状態が良く、とても満足しています。", "entry_order": 54},
            {"role": "seller", "rating": "positive", "body_excerpt": "発送が非常に早かったです。また購入したいです。", "entry_order": 55},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い取引ができました。ありがとうございます。", "entry_order": 56},
            {"role": "seller", "rating": "positive", "body_excerpt": "丁寧な梱包と迅速な発送でした。また利用します。", "entry_order": 57},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品説明が正確で、安心して購入できました。", "entry_order": 58},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が丁寧で、商品に問題はありませんでした。", "entry_order": 59},
            {"role": "seller", "rating": "positive", "body_excerpt": "スムーズな取引でした。また購入したいと思います。", "entry_order": 60},
            {"role": "buyer", "rating": "positive", "body_excerpt": "とても親切な対応でした。また利用したいです。", "entry_order": 61},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品が説明以上の状態で届きました。満足です。", "entry_order": 62},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な対応に感謝します。良い取引でした。", "entry_order": 63},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包がしっかりしていました。商品も良い状態です。", "entry_order": 64},
            {"role": "seller", "rating": "positive", "body_excerpt": "対応が迅速で梱包も丁寧でした。おすすめです。", "entry_order": 65},
            {"role": "buyer", "rating": "positive", "body_excerpt": "スムーズな取引をありがとうございました。", "entry_order": 66},
            {"role": "seller", "rating": "positive", "body_excerpt": "写真通りの商品が届きました。また利用します。", "entry_order": 67},
            {"role": "seller", "rating": "positive", "body_excerpt": "発送が早く梱包も完璧でした。", "entry_order": 68},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の品質が高く、大満足です。ありがとうございます。", "entry_order": 69},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な発送と丁寧な梱包でした。また購入します。", "entry_order": 70},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い商品でした。また機会があれば購入したいです。", "entry_order": 71},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品が説明通りで、対応も親切でした。", "entry_order": 72},
            {"role": "seller", "rating": "positive", "body_excerpt": "問題なく届きました。また利用させていただきます。", "entry_order": 73},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が丁寧で商品も綺麗でした。満足しています。", "entry_order": 74},
            {"role": "seller", "rating": "positive", "body_excerpt": "素晴らしい取引でした。また購入したいです。", "entry_order": 75},
            {"role": "buyer", "rating": "positive", "body_excerpt": "丁寧な対応と迅速な発送に感謝します。", "entry_order": 76},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品の状態が良く説明通りでした。信頼できます。", "entry_order": 77},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が完璧で安心して受け取れました。", "entry_order": 78},
            {"role": "seller", "rating": "positive", "body_excerpt": "対応が丁寧で、また利用したいと思います。", "entry_order": 79},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な対応と発送でした。おすすめの出品者です。", "entry_order": 80},
            # 20 bad
            {"role": "seller", "rating": "negative", "body_excerpt": "発送が予定より遅かった。連絡も少なかったです。", "entry_order": 81},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品の状態が説明より悪かったです。少し残念でした。", "entry_order": 82},
            {"role": "seller", "rating": "negative", "body_excerpt": "梱包が少し雑で、商品の角が凹んでいました。", "entry_order": 83},
            {"role": "seller", "rating": "negative", "body_excerpt": "発送通知が遅く、心配しました。商品は届きましたが。", "entry_order": 84},
            {"role": "seller", "rating": "negative", "body_excerpt": "写真と実物で色味が異なっていました。説明に追記を。", "entry_order": 85},
            {"role": "seller", "rating": "negative", "body_excerpt": "質問への返答に時間がかかりました。改善を期待します。", "entry_order": 86},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品の細かい傷の記載がなかったです。残念でした。", "entry_order": 87},
            {"role": "seller", "rating": "negative", "body_excerpt": "梱包材が薄く、商品が少し動いた跡がありました。", "entry_order": 88},
            {"role": "seller", "rating": "negative", "body_excerpt": "発送が数日遅れました。一言連絡が欲しかったです。", "entry_order": 89},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品説明と実物で多少差異がありました。注意してください。", "entry_order": 90},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品の細かい傷の記載がなかったです。残念でした。", "entry_order": 91},
            {"role": "seller", "rating": "negative", "body_excerpt": "梱包材が薄く、商品が少し動いた跡がありました。", "entry_order": 92},
            {"role": "seller", "rating": "negative", "body_excerpt": "発送が数日遅れました。一言連絡が欲しかったです。", "entry_order": 93},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品説明と実物で多少差異がありました。注意してください。", "entry_order": 94},
            {"role": "seller", "rating": "negative", "body_excerpt": "梱包が雑でした。商品は無事でしたが改善してほしいです。", "entry_order": 95},
            {"role": "seller", "rating": "negative", "body_excerpt": "発送が思ったより遅かった。追跡番号の連絡が遅かったです。", "entry_order": 96},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品の汚れが写真では分かりませんでした。説明不足です。", "entry_order": 97},
            {"role": "seller", "rating": "negative", "body_excerpt": "返信が少し遅かったです。急いでいたので困りました。", "entry_order": 98},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品の付属品が説明と違いました。確認不足だと思います。", "entry_order": 99},
            {"role": "seller", "rating": "negative", "body_excerpt": "説明文をもっと詳しく書いてほしかったです。", "entry_order": 100},
        ],
    },
    # ── Snapshot 2: 2026-02-01 ─── total 210 (+10 new: 8 good / 2 bad)
    #    early records = 210 - 88 - 22 = 100
    {
        "capture_id": "cap_demo_002",
        "captured_at": "2026-02-01T10:00:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": True,
        "total_reviews": 210,
        "positive_reviews": 88,
        "negative_reviews": 22,
        "listing_count": 38,
        "followers_count": 135,
        "following_count": 42,
        "bio_excerpt": "ポケモンカードやゲーム関連商品を中心に出品しています。丁寧な梱包を心がけています。",
        "sample_items": ["ポケモンカード", "トレーディングカード", "ゲームソフト", "フィギュア", "アニメグッズ"],
        "review_entries": [
            # 8 good (new reviews added since last snapshot)
            {"role": "seller", "rating": "positive", "body_excerpt": "また購入しました。今回も迅速な対応でした。", "entry_order": 1},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包がしっかりしていて安心して受け取れました。", "entry_order": 2},
            {"role": "seller", "rating": "positive", "body_excerpt": "説明通りの商品が届きました。ありがとうございます。", "entry_order": 3},
            {"role": "seller", "rating": "positive", "body_excerpt": "とてもスムーズな取引でした。満足しています。", "entry_order": 4},
            {"role": "buyer", "rating": "positive", "body_excerpt": "良い商品をありがとうございました。また購入したいです。", "entry_order": 5},
            {"role": "seller", "rating": "positive", "body_excerpt": "発送が早く、商品も綺麗でした。また利用します。", "entry_order": 6},
            {"role": "seller", "rating": "positive", "body_excerpt": "丁寧な対応に感謝します。また利用したいです。", "entry_order": 7},
            {"role": "seller", "rating": "positive", "body_excerpt": "問題なく取引できました。信頼できる方です。", "entry_order": 8},
            # 2 bad
            {"role": "seller", "rating": "negative", "body_excerpt": "今回は発送が少し遅れました。連絡はありましたが残念。", "entry_order": 9},
            {"role": "seller", "rating": "negative", "body_excerpt": "商品に細かい傷がありました。説明に記載がなかったです。", "entry_order": 10},
        ],
    },
    # ── Snapshot 3: 2026-03-01 ─── total 230 (+20 new: 19 good / 1 bad)
    #    early records = 230 - 107 - 23 = 100
    {
        "capture_id": "cap_demo_003",
        "captured_at": "2026-03-01T10:00:00+09:00",
        "display_name": "テスト商人Demo",
        "avatar_url": None,
        "verified_badge": True,
        "total_reviews": 230,
        "positive_reviews": 107,
        "negative_reviews": 23,
        "listing_count": 44,
        "followers_count": 158,
        "following_count": 45,
        "bio_excerpt": "ポケモンカードやゲーム関連商品を中心に出品しています。丁寧な梱包を心がけています。",
        "sample_items": ["ポケモンカード", "トレーディングカード", "フィギュア", "アニメグッズ", "ゲームソフト", "漫画"],
        "review_entries": [
            # 19 good (new reviews added since last snapshot)
            {"role": "seller", "rating": "positive", "body_excerpt": "春の取引もスムーズでした。また購入します。", "entry_order": 1},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な発送に感謝します。商品も満足です。", "entry_order": 2},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包が丁寧で商品が傷つかず届きました。", "entry_order": 3},
            {"role": "seller", "rating": "positive", "body_excerpt": "説明以上に良い状態でした。お得な買い物でした。", "entry_order": 4},
            {"role": "buyer", "rating": "positive", "body_excerpt": "対応が親切で安心して取引できました。", "entry_order": 5},
            {"role": "seller", "rating": "positive", "body_excerpt": "素早い発送で、商品も写真通りでした。", "entry_order": 6},
            {"role": "seller", "rating": "positive", "body_excerpt": "信頼できる出品者さんです。また利用します。", "entry_order": 7},
            {"role": "seller", "rating": "positive", "body_excerpt": "梱包も丁寧で、商品の状態も良かったです。", "entry_order": 8},
            {"role": "seller", "rating": "positive", "body_excerpt": "スムーズな取引ありがとうございました。", "entry_order": 9},
            {"role": "buyer", "rating": "positive", "body_excerpt": "問題なく届きました。また購入したいです。", "entry_order": 10},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品説明が正確でした。安心して購入できます。", "entry_order": 11},
            {"role": "seller", "rating": "positive", "body_excerpt": "とても親切な対応でした。また利用させていただきます。", "entry_order": 12},
            {"role": "seller", "rating": "positive", "body_excerpt": "発送が早く助かりました。商品も満足です。", "entry_order": 13},
            {"role": "seller", "rating": "positive", "body_excerpt": "良い状態で届きました。ありがとうございます。", "entry_order": 14},
            {"role": "buyer", "rating": "positive", "body_excerpt": "梱包がしっかりしていました。また購入します。", "entry_order": 15},
            {"role": "seller", "rating": "positive", "body_excerpt": "対応が迅速で安心しました。おすすめです。", "entry_order": 16},
            {"role": "seller", "rating": "positive", "body_excerpt": "商品が綺麗な状態で届き満足しています。", "entry_order": 17},
            {"role": "seller", "rating": "positive", "body_excerpt": "また機会があればぜひ購入したいと思います。", "entry_order": 18},
            {"role": "seller", "rating": "positive", "body_excerpt": "迅速な対応と丁寧な梱包でした。ありがとうございました。", "entry_order": 19},
            # 1 bad
            {"role": "seller", "rating": "negative", "body_excerpt": "商品の色が写真と少し異なっていました。説明に追記があると良いです。", "entry_order": 20},
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
