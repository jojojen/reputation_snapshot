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

測試：

```bat
scripts\run_all_tests.bat
```
