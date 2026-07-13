# Mercari Reputation Snapshot MVP

Mercari 公開賣家頁信譽快照 MVP，使用 Python、Flask、SQLite、Playwright 與 Ed25519 簽章建立可驗證 proof。

## Quick Start

一鍵啟動（含環境設定、DB 初始化、金鑰產生）：

```bat
launchers\start.bat
```

不自動開瀏覽器：

```bat
launchers\start-no-browser.bat
```

或分步驟手動執行：

```bat
scripts\setup_env.bat
scripts\init_db.bat
scripts\generate_keys.bat
scripts\run_app.bat
```

## 測試

兩條測試路徑：

- **離線（預設）** — 決定性、不連網、快速。`pytest` 不帶任何旗標即為此模式：

  ```bash
  .venv/bin/python -m pytest -q
  ```

- **Live capture（需明確 opt-in）** — 真的透過 Playwright 打 Mercari 頁面，用於偵測來源版型漂移。需設定 `RUN_LIVE_CAPTURE_TESTS=1` 並用 `live_capture` marker 篩選：

  ```bash
  RUN_LIVE_CAPTURE_TESTS=1 .venv/bin/python -m pytest -q -m live_capture
  ```

  Windows 開發腳本 `scripts\run_all_tests.bat` / `scripts\run_capture_test.bat` 已內建此
  opt-in 旗標。CI 的 `tests` workflow 只跑離線路徑（`-m "not live_capture"`），live
  路徑不在 PR/push 上自動執行。

### Live capture 的界限（bounded execution）

Live batch 會真的打第三方頁面，因此整批受 `utils/live_capture_guard.RequestBudget`
約束：導覽次數與整體 wall-clock deadline 都有硬上限，且一遇到 429／rate-limit／bot
interstitial 就中止剩餘 batch（`should_abort_batch`）。每個 stage 會用
`log_live_event` 輸出一行結構化 JSON（只含 source URL、stage、elapsed、failure
class，不含頁面內容，可安全當 CI artifact）。這些界限本身由離線套件
`tests/test_live_capture_guard.py` 驗證。

可用環境變數調整（皆有保守預設值）：

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `LIVE_CAPTURE_MAX_PROFILES` | `3` | profile case 上限 |
| `LIVE_CAPTURE_MAX_ITEMS` | `5` | item-URL case 上限 |
| `LIVE_CAPTURE_MAX_REQUESTS` | `20` | 整批導覽次數硬上限 |
| `LIVE_CAPTURE_DEADLINE_SECONDS` | `300` | 整批 wall-clock deadline（秒） |
| `MERCARI_LIVE_TEST_URLS` | 內建兩個 profile | 逗號分隔的測試 profile URL |

### Live CI lane

`.github/workflows/live-capture.yml` 是唯一會驅動真實瀏覽器的 workflow，刻意不掛在
PR/push 上：只在 **手動 `workflow_dispatch`**（可覆寫 `max_requests` /
`deadline_seconds`）或 **每週排程 cron**（週一 03:00 UTC）執行。它用保守的 case 上限、
`concurrency` 序列化避免同時打 Mercari、`timeout-minutes` 作為 job 級硬天花板，並把
結構化 log 以 artifact 上傳。

```bat
scripts\run_all_tests.bat
```
