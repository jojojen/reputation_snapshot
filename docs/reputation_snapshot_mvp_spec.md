# Mercari Reputation Snapshot MVP
## 可直接落地開發的完整規格文件（無框架前端、Python 單體、可拆成 `.py` 與 `.bat`）

---

## 0. 文件目的

這份文件不是簡介，也不是概念說明。

這份文件的目的只有一個：

> **讓你或 Codex 可以依照本文件，直接把系統拆成 Python 程式檔與 Windows `.bat` 執行檔，逐步完成 MVP。**

因此本文件會直接定義：

- 專案目錄結構
- 每個檔案要做什麼
- 每個 Python 模組要有哪些函式
- 每個 API 要收什麼、回什麼
- 每個資料表要有哪些欄位
- 每個 `.bat` 要執行哪些命令
- 每個測試要驗證什麼
- parser 壞掉時要怎麼修

這份文件**不提供完整代碼**，但它的粒度會細到足以直接寫成代碼。

---

## 1. MVP 最終目標

系統要完成這件事：

1. 使用者輸入一個 Mercari 公開賣家頁 URL
2. 系統抓取頁面
3. 系統抽取公開信譽欄位
4. 系統保存證據（HTML、可見文字、截圖、hash）
5. 系統生成 proof JSON
6. 系統對 proof JSON 做 Ed25519 簽章
7. 系統產生一個 proof 頁面
8. 系統提供 verify API 驗證 proof 與 signature

---

## 2. 這版刻意不做的東西

以下全部不做：

- 區塊鏈
- DID / VC / NFT
- 多平台同步
- OAuth / 登入系統
- 後台權限系統
- Docker
- 雲端排程器
- 大規模爬站
- 帳號所有權強驗證
- 自動 OCR 主流程
- 前端框架（React / Vue）
- 先寫完整 AI agent

---

## 3. 技術選型

### 後端
- Python 3.12
- Flask
- SQLite
- Playwright（Python）
- PyNaCl（Ed25519）
- 標準庫：`json`, `hashlib`, `sqlite3`, `uuid`, `datetime`, `os`, `pathlib`, `re`

### 前端
- HTML
- CSS
- 原生 JavaScript
- Flask Jinja 模板

### 作業系統
- Windows 為主
- 文件中會提供 `.bat` 腳本規格

---

## 4. 產品定義

本系統產生的 proof 代表的是：

> 在某一時間點，某一個公開 Mercari 賣家頁面上，可觀察到的一組公開資料，被系統擷取、封存、計算 hash、整理成 proof，並以伺服器私鑰簽章。

它**不代表**：

- 你已證明這個人一定是帳號主人
- Mercari 官方授權了你這份證明
- 這個帳號的未來狀態不會改變
- 這份 proof 是永久有效

對外用語固定使用：

**第三方公開資料信譽快照**

---



---

## 4.1 信任模型（Trust Model）

本系統不提供「身份驗證」或「帳號控制權證明」。

本系統提供的是：

> 對某一公開頁面，在某一時間點的「可驗證資料快照」。

驗證方可以確認：
- 該資料確實由本系統擷取
- 資料在生成後未被竄改（透過簽章）
- 該資料對應到某個公開 URL

但無法確認：
- 提供 proof 的人是否為該帳號持有者
- 該帳號是否未被轉讓或共用
- 該資料是否仍為最新狀態

因此本 proof 屬於：

**Weak Attestation（弱證明）**

---

## 4.2 使用限制聲明

本系統生成的 proof：

不得用於：
- 金融信用評分
- 放貸決策
- 法律責任判定
- 身份認證用途

本系統僅適用於：
- 二手交易平台參考
- 社群信譽展示
- 非關鍵風險場景

任何依賴本 proof 作出重大決策的行為，應由使用方自行承擔風險。

---

## 4.3 MVP 範圍鎖定

本專案當前版本（v0.x）僅實作：

- 單一來源（Mercari）
- 公開資料擷取
- 靜態快照生成
- 基本簽章驗證

明確不包含：

- 跨平台身份整合
- 帳號所有權驗證
- 即時資料同步
- 去識別化處理
- 信用分數標準化
- 反詐騙系統

任何上述功能，需列為後續版本（v1+）討論，不得在 MVP 階段實作。

---

## 32.1 資料可信度等級（Assurance Level）

每份 proof 應標記其可信度等級：

- level: "public_snapshot"

定義：
- 僅基於公開資料
- 未驗證帳號控制權
- 未驗證資料真實性（僅驗證未被竄改）

未來可擴展：
- "ownership_verified"
- "platform_attested"

## 5. 專案目錄結構（必須照這個拆）

```text
mercari-proof/
├─ app.py
├─ requirements.txt
├─ schema.sql
├─ README.md
├─ .env
├─ instance/
│  └─ app.db
├─ keys/
│  ├─ ed25519_private_key.pem
│  └─ ed25519_public_key.pem
├─ captures/
│  ├─ html/
│  ├─ text/
│  └─ screenshots/
├─ templates/
│  ├─ index.html
│  ├─ proof.html
│  └─ partial.html
├─ static/
│  ├─ style.css
│  └─ app.js
├─ services/
│  ├─ capture_service.py
│  ├─ parser_mercari.py
│  ├─ proof_service.py
│  ├─ signing_service.py
│  ├─ verify_service.py
│  ├─ storage_service.py
│  └─ llm_repair_service.py
├─ utils/
│  ├─ hash_utils.py
│  ├─ json_utils.py
│  ├─ score_utils.py
│  ├─ db_utils.py
│  └─ url_utils.py
├─ tests/
│  ├─ test_cases.json
│  ├─ fixtures/
│  ├─ test_parser.py
│  ├─ test_live_capture.py
│  └─ test_verify.py
└─ scripts/
   ├─ setup_env.bat
   ├─ init_db.bat
   ├─ run_app.bat
   ├─ run_capture_test.bat
   ├─ run_all_tests.bat
   ├─ generate_keys.bat
   └─ freeze_fixtures.bat
```

---

## 6. 各檔案責任定義

這一節非常重要。

### `app.py`
用途：
- Flask 主程式
- 定義所有 HTTP 路由
- 呼叫 service 層
- 不直接放 parser 細節
- 不直接放簽章算法細節

### `schema.sql`
用途：
- 初始化 SQLite 資料表
- 不做 migration 系統，MVP 直接初始化即可

### `services/capture_service.py`
用途：
- 用 Playwright 開頁
- 抓 raw HTML
- 抓 visible text
- 截圖
- 回傳原始擷取結果

### `services/parser_mercari.py`
用途：
- 將 raw HTML / visible text 解析成結構化欄位
- 只負責解析，不負責存檔、不負責簽章

### `services/proof_service.py`
用途：
- 組合 proof payload
- 呼叫 score
- 呼叫 hash
- 呼叫 signing
- 回傳最終 proof JSON

### `services/signing_service.py`
用途：
- 載入私鑰 / 公鑰
- 產生 signature
- 驗證 signature

### `services/verify_service.py`
用途：
- 驗證輸入 proof 是否有效
- 驗證 signature
- 驗證 proof 是否被撤銷 / 是否過期

### `services/storage_service.py`
用途：
- 統一處理 DB 存取
- 統一處理 HTML / 截圖 / 文字檔案保存

### `services/llm_repair_service.py`
用途：
- parser 抽取失敗時的補救
- 非主流程必要
- 可以先 stub

### `utils/hash_utils.py`
用途：
- SHA-256 計算
- 檔案與字串 hash

### `utils/json_utils.py`
用途：
- canonical JSON
- JSON dump / load 統一設定

### `utils/score_utils.py`
用途：
- score 計算
- grade 計算

### `utils/db_utils.py`
用途：
- 建立 DB connection
- query helper

### `utils/url_utils.py`
用途：
- Mercari URL 驗證
- URL 正規化

---

## 7. 必要資料表設計

### 7.1 captures

```sql
CREATE TABLE captures (
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
```

### 7.2 proofs

```sql
CREATE TABLE proofs (
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
```

### 7.3 parser_runs（可選，但建議做）
用途：
- 記錄 parser 成功率
- 方便未來查 UI 改版

```sql
CREATE TABLE parser_runs (
    id TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    extractor_strategy TEXT NOT NULL,
    success INTEGER NOT NULL,
    missing_fields_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

---

## 8. 欄位定義與型別規格

### 8.1 必抓欄位
這些欄位若抽不到，proof 仍可產出，但會標記 partial。

- `display_name: str | None`
- `total_reviews: int | None`
- `listing_count: int | None`
- `followers_count: int | None`
- `following_count: int | None`

### 8.2 選抓欄位
- `avatar_url: str | None`
- `verified_badge: bool | None`
- `positive_reviews: int | None`
- `negative_reviews: int | None`
- `bio_excerpt: str | None`
- `sample_items: list[str]`

### 8.3 證據欄位
- `raw_html_path: str`
- `visible_text_path: str`
- `screenshot_path: str`
- `raw_html_sha256: str`
- `visible_text_sha256: str`
- `screenshot_sha256: str`

### 8.4 proof 狀態
- `active`
- `revoked`
- `expired`
- `partial`

---

## 9. Proof JSON 完整規格

```json
{
  "proof_id": "proof_xxx",
  "proof_version": "v0.1",
  "source_platform": "mercari_jp",
  "source_url": "https://jp.mercari.com/user/profile/123456789",
  "captured_at": "2026-04-18T09:00:00+09:00",
  "expires_at": "2026-05-18T09:00:00+09:00",
  "subject": {
    "display_name": "seller_name",
    "avatar_url": null,
    "verified_badge": null
  },
  "metrics": {
    "total_reviews": 104,
    "positive_reviews": null,
    "negative_reviews": null,
    "listing_count": 81,
    "followers_count": 3,
    "following_count": 27
  },
  "signals": {
    "bio_excerpt": "......",
    "sample_items": ["item1", "item2", "item3"]
  },
  "score": {
    "value": 59,
    "grade": "C",
    "label": "public_signal_strength_v0"
  },
  "evidence": {
    "parser_version": "mercari_parser_v0",
    "extractor_strategy": "dom_text_regex",
    "raw_html_sha256": "......",
    "visible_text_sha256": "......",
    "screenshot_sha256": "......"
  },
  "status": "active",
  "signature": "base64url..."
}
```

---

## 10. score 計算規格

這個分數只是「公開訊號強度」，不是信用評分。

### 10.1 公式

```text
review_factor  = min(log10(total_reviews + 1) / log10(2001), 1)
listing_factor = min(listing_count, 100) / 100
badge_factor   = 1 if verified_badge else 0

score = round(70 * review_factor + 20 * listing_factor + 10 * badge_factor)
```

### 10.2 grade
- `A >= 80`
- `B >= 60`
- `C >= 40`
- `D < 40`

### 10.3 缺值規則
若某欄位為 `None`：
- `total_reviews is None` → `review_factor = 0`
- `listing_count is None` → `listing_factor = 0`
- `verified_badge is None` → `badge_factor = 0`

---

## 11. URL 驗證規格

`utils/url_utils.py` 必須提供以下函式：

### `is_valid_mercari_profile_url(url: str) -> bool`
功能：
- 檢查是否為 Mercari 個人頁 URL
- 只接受 `https://jp.mercari.com/user/profile/...`

### `normalize_mercari_url(url: str) -> str`
功能：
- 移除 tracking query
- 移除多餘參數
- 只保留 profile 主網址

---

## 12. Capture Service 規格

`services/capture_service.py` 必須實作：

### `capture_profile(profile_url: str) -> dict`
輸入：
- Mercari profile URL

輸出：
```python
{
    "raw_html": "...",
    "visible_text": "...",
    "screenshot_path": "captures/screenshots/xxx.png",
    "raw_html_sha256": "...",
    "visible_text_sha256": "...",
    "screenshot_sha256": "...",
    "http_status": 200,
    "captured_at": "..."
}
```

### 必做流程
1. 開啟 Chromium
2. 進入 URL
3. 等待頁面穩定
4. 取得 `page.content()`
5. 取得 `body.innerText`
6. 截 full-page screenshot
7. 存到 `captures/`
8. 計算 hash
9. 回傳結果

### 失敗處理
若頁面打不開：
- 丟出可讀錯誤
- 不要靜默失敗

---

## 13. Parser 規格

`services/parser_mercari.py` 必須實作：

### `parse_profile(raw_html: str, visible_text: str) -> dict`

輸出格式：

```python
{
    "display_name": str | None,
    "avatar_url": str | None,
    "verified_badge": bool | None,
    "total_reviews": int | None,
    "positive_reviews": int | None,
    "negative_reviews": int | None,
    "listing_count": int | None,
    "followers_count": int | None,
    "following_count": int | None,
    "bio_excerpt": str | None,
    "sample_items": list[str],
    "parser_version": "mercari_parser_v0",
    "extractor_strategy": "dom_text_regex",
    "llm_repair_applied": 0,
    "completeness_status": "full" | "partial"
}
```

### 13.1 解析策略順序
1. DOM selector
2. visible text regex
3. optional LLM repair
4. 回傳 partial

### 13.2 主要欄位抽取策略

#### display_name
- 優先找 `h1`
- 若沒有，從最上方主要文字區域抓

#### total_reviews
- 優先找 review 相關 anchor 旁的數字
- 若無法穩定找到，用 visible text regex 補

#### listing_count
regex:
```text
(\d+)\s*出品数
```

#### followers_count
regex:
```text
(\d+)\s*フォロワー
```

#### following_count
regex:
```text
(\d+)\s*フォロー中
```

#### bio_excerpt
- 從主要資料區塊切出最多 280 字

#### sample_items
- 抓商品列表前 5~10 個標題

---

## 14. LLM repair 規格（可 stub）

`services/llm_repair_service.py`

### 目的
當 parser 抽不到主要欄位時，用地端模型幫忙猜候選規則。

### MVP 要求
先做成 stub 即可：

### `repair_parse(raw_html: str, visible_text: str) -> dict`
回傳：
```python
{
    "display_name": None,
    "total_reviews": None,
    "listing_count": None,
    "followers_count": None,
    "following_count": None
}
```

之後若要接 Ollama：
- 只在 parser 抽不到主要欄位時呼叫
- 不要放在主流程必經路徑

---

## 15. Signing Service 規格

`services/signing_service.py`

### 必須實作函式

#### `load_private_key()`
- 從 `keys/ed25519_private_key.pem` 載入

#### `load_public_key()`
- 從 `keys/ed25519_public_key.pem` 載入

#### `sign_proof(canonical_json: str) -> str`
- 輸入 canonical JSON 字串
- 輸出 base64url signature

#### `verify_signature(canonical_json: str, signature: str) -> bool`
- 驗證 signature 是否有效

---

## 16. Proof Service 規格

`services/proof_service.py`

### 必須實作函式

#### `build_proof(source_url: str, capture_data: dict, parsed_data: dict, expires_in_days: int = 30) -> dict`

功能：
1. 整合 capture data + parsed data
2. 計算 score
3. 組 proof payload
4. canonical JSON
5. hash
6. sign
7. 回傳最終 proof dict

### 回傳格式
```python
{
    "proof_id": "...",
    "proof_payload": {...},
    "proof_sha256": "...",
    "signature": "..."
}
```

---

## 17. Verify Service 規格

`services/verify_service.py`

### 必須實作函式

#### `verify_proof(proof: dict, signature: str) -> dict`

回傳：
```python
{
    "valid": True,
    "reason": None,
    "status": "active"
}
```

驗證步驟：
1. proof 結構是否完整
2. signature 是否有效
3. proof 是否過期
4. proof 是否已撤銷

---

## 18. Storage Service 規格

`services/storage_service.py`

### 必須實作函式

#### `save_raw_html(capture_id: str, raw_html: str) -> str`
回傳 HTML 檔案路徑

#### `save_visible_text(capture_id: str, visible_text: str) -> str`
回傳文字檔路徑

#### `save_screenshot(capture_id: str, screenshot_bytes: bytes) -> str`
回傳圖片路徑

#### `insert_capture(data: dict) -> None`
寫入 captures table

#### `insert_proof(data: dict) -> None`
寫入 proofs table

#### `get_proof(proof_id: str) -> dict | None`
查詢 proof

#### `revoke_proof(proof_id: str, reason: str) -> None`
更新 proof 狀態

---

## 19. Flask 路由完整規格

### `GET /`
用途：
- 顯示首頁表單

### `POST /api/captures`
用途：
- 建立 capture
- 直接同步執行也可以，MVP 不一定要 queue

Request:
```json
{
  "profile_url": "https://jp.mercari.com/user/profile/123456789",
  "expires_in_days": 30
}
```

Response:
```json
{
  "capture_id": "cap_xxx",
  "proof_id": "proof_xxx",
  "proof_url": "/p/proof_xxx"
}
```

### `GET /api/proofs/<proof_id>`
用途：
- 回傳 proof JSON

### `POST /api/verify`
用途：
- 驗章

Request:
```json
{
  "proof": { "...": "..." },
  "signature": "..."
}
```

Response:
```json
{
  "valid": true,
  "status": "active"
}
```

### `POST /api/proofs/<proof_id>/revoke`
用途：
- 撤銷 proof

### `GET /p/<proof_id>`
用途：
- 顯示公開 proof 頁面

---

## 20. HTML 頁面規格

### `templates/index.html`
必須包含：
- URL 輸入框
- 送出按鈕
- 結果區塊
- fetch `/api/captures`

### `templates/proof.html`
必須顯示：
- source_url
- display_name
- total_reviews
- listing_count
- followers_count
- following_count
- score
- grade
- proof_sha256
- signature
- status
- captured_at
- expires_at

### `templates/partial.html`
用途：
- 若 parser 不完整時顯示 warning
- 顯示哪些欄位缺失

---

## 21. static/app.js 規格

必須做的事：

1. 監聽首頁表單 submit
2. 送 POST `/api/captures`
3. 顯示結果
4. 若成功，顯示 proof link
5. 若失敗，顯示錯誤訊息

---

## 22. static/style.css 規格

只要最小樣式：
- 內容置中
- input / button / result block 可讀
- proof page 欄位有區塊感

不需要 UI framework。

---

## 23. Windows `.bat` 檔規格

這一節是重點，因為你說要細到能直接拆成 `.bat`。

### 23.1 `scripts/setup_env.bat`
用途：
- 建立虛擬環境
- 安裝套件
- 安裝 Playwright Chromium

內容流程：
1. `python -m venv .venv`
2. `call .venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. `playwright install chromium`

### 23.2 `scripts/init_db.bat`
用途：
- 初始化 SQLite DB

內容流程：
1. 若 `instance` 不存在則建立
2. 執行 `sqlite3 instance\app.db < schema.sql`

### 23.3 `scripts/run_app.bat`
用途：
- 啟動 Flask app

內容流程：
1. `call .venv\Scripts\activate`
2. `python app.py`

### 23.4 `scripts/generate_keys.bat`
用途：
- 執行 Python 腳本產生 Ed25519 金鑰
- 寫入 `keys/`

內容流程：
1. `call .venv\Scripts\activate`
2. `python scripts\generate_keys.py`

### 23.5 `scripts/run_capture_test.bat`
用途：
- 執行 live capture smoke test

內容流程：
1. `call .venv\Scripts\activate`
2. `python -m pytest tests/test_live_capture.py -s`

### 23.6 `scripts/run_all_tests.bat`
用途：
- 跑所有測試

內容流程：
1. `call .venv\Scripts\activate`
2. `python -m pytest tests -s`

### 23.7 `scripts/freeze_fixtures.bat`
用途：
- 用 live capture 結果更新 fixtures

內容流程：
1. `call .venv\Scripts\activate`
2. `python scripts/freeze_fixtures.py`

---

## 24. 你還需要的 Python 腳本規格

除了 service 檔，你還要這些腳本。

### `scripts/generate_keys.py`
功能：
- 生成 Ed25519 key pair
- 寫出 private/public PEM

### `scripts/freeze_fixtures.py`
功能：
- 讀 `tests/test_cases.json`
- 逐筆抓取頁面
- 存 `raw_html` 到 `tests/fixtures/`
- 存 `visible_text` 到 `tests/fixtures/`

---

## 25. requirements.txt 規格

至少包含：

```text
Flask==3.1.0
playwright==1.52.0
PyNaCl==1.5.0
pytest==8.3.5
```

---

## 26. .env 規格

`.env` 至少要有：

```env
APP_HOST=127.0.0.1
APP_PORT=5000
DB_PATH=instance/app.db
DEFAULT_EXPIRES_DAYS=30
PARSER_VERSION=mercari_parser_v0
```

---

## 27. 20 筆案例與測試規劃

這一節不能拿掉。

### 27.1 用途
這 20 筆不是展示用，是 regression test。

### 27.2 分類
- 高評價賣家 5 筆
- 中等賣家 5 筆
- 低評價賣家 5 筆
- 邊界案例 5 筆

### 27.3 `tests/test_cases.json` 格式

```json
[
  {
    "name": "case_01",
    "category": "high",
    "url": "https://jp.mercari.com/user/profile/EXAMPLE1",
    "notes": "high volume seller",
    "expect": {
      "has_display_name": true,
      "has_total_reviews": true,
      "has_listing_count": true,
      "has_followers_count": true,
      "has_following_count": true,
      "proof_should_generate": true,
      "min_score": 0,
      "max_score": 100
    }
  }
]
```

### 27.4 每筆要檢查的項目
- display_name 有值
- total_reviews 有值
- listing_count 有值
- followers_count 有值
- following_count 有值
- raw_html_sha256 有值
- visible_text_sha256 有值
- screenshot_sha256 有值
- proof 可以生成
- verify = true

### 27.5 壞掉判定規則
- 壞 1~2 筆：先查個案
- 壞 3~4 筆：查 parser
- 壞 >= 5 筆：視為 parser 壞掉

---

## 28. 測試檔規格

### `tests/test_parser.py`
功能：
- 讀 fixtures
- 驗證 parser 解析結果

### `tests/test_live_capture.py`
功能：
- 實際抓 3 筆 live case
- 驗證 capture 基本可用

### `tests/test_verify.py`
功能：
- 驗證 build proof + verify proof

---

## 29. 開發順序（照這個做）

### 第 1 階段：骨架
1. 建目錄
2. 建 `requirements.txt`
3. 建 `schema.sql`
4. 建 `app.py`
5. 建 `scripts/setup_env.bat`
6. 建 `scripts/init_db.bat`

### 第 2 階段：擷取
1. 實作 `capture_service.py`
2. 實作 `storage_service.py`
3. 可以把 HTML / text / screenshot 存下來

### 第 3 階段：解析
1. 實作 `parser_mercari.py`
2. 抓出主要欄位

### 第 4 階段：proof
1. 實作 `hash_utils.py`
2. 實作 `score_utils.py`
3. 實作 `signing_service.py`
4. 實作 `proof_service.py`

### 第 5 階段：頁面與 API
1. 做首頁
2. 做 proof page
3. 做 verify API
4. 做 revoke API

### 第 6 階段：測試
1. 建 `test_cases.json`
2. 建 fixtures
3. 跑 parser test
4. 跑 live smoke test
5. 跑 verify test

---

## 30. 最小驗收標準

做到以下就算 MVP 完成：

1. `setup_env.bat` 能成功建立環境
2. `init_db.bat` 能成功建立 DB
3. `run_app.bat` 能成功啟動 Flask
4. 首頁可輸入 Mercari URL
5. `/api/captures` 能建立 proof
6. proof page 可顯示資料
7. `/api/verify` 能回 `valid=true`
8. 20 筆案例至少 18 筆可產出完整或 partial proof
9. parser 壞掉時系統不崩潰

---

## 31. partial proof 規格

若主要欄位缺失：

- 仍可產出 proof
- `status = partial`
- `completeness_status = partial`
- 頁面要顯示：
  - 哪些欄位缺
  - 這是一份不完整 proof

### 主要欄位定義
- display_name
- total_reviews
- listing_count
- followers_count
- following_count

---

## 32. Parser 壞掉時的維護流程

當 Mercari UI 改版時，工程流程固定如下：

1. 跑 `run_all_tests.bat`
2. 看哪些 fixture 掛掉
3. 看哪些 live case 掛掉
4. 修 `parser_mercari.py`
5. 若需要，補 visible text regex
6. 若還抓不到，暫時標 partial
7. 更新 `PARSER_VERSION`
8. 重新 freeze fixtures

---

## 33. LLM repair 未來升級規格

先留接口，不急著做。

將來可升級成：

- 本地模型：Ollama
- 只在 parser 失敗時啟動
- 輸入：HTML fragment + visible text
- 輸出：候選 selector / regex JSON
- 人工確認後寫回 parser

MVP 階段只要求：
- `llm_repair_service.py` 有 stub
- parser 能呼叫但不依賴它成功

---

## 34. 這份文件可以直接拆成哪些實作任務

你可以把這份文件直接拆成以下工作項：

### Task 1
建立專案目錄與 `.bat`

### Task 2
完成 DB 初始化

### Task 3
完成 capture service

### Task 4
完成 parser

### Task 5
完成 hash / score / sign

### Task 6
完成 proof service

### Task 7
完成 Flask API

### Task 8
完成 HTML 頁面

### Task 9
完成 test_cases.json 與 fixtures

### Task 10
完成 pytest 測試

---

## 35. 一句話總結

你要做的不是一個抽象的跨平台信譽系統。

你要做的是：

> **一個可以用 Python + Flask + Playwright 生成 Mercari 公開信譽快照、輸出 proof JSON、可驗章、可測試、可用 `.bat` 一鍵跑起來的 MVP。**

只要照這份文件拆檔與實作，就可以直接進入寫代碼階段。
