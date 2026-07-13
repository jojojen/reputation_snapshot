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

```bat
scripts\run_all_tests.bat
```
