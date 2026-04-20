#!/bin/sh
set -e

# ── 把需要持久化的目錄全部移到 /data/ volume ──────────────────
# 目的：container 重建後 DB、金鑰、capture 檔案都不會消失
# /data/ 是 Fly.io persistent volume 的掛載點

# 金鑰 (非常重要：金鑰消失等於所有 proof 簽章全失效)
mkdir -p /data/keys
if [ ! -L /app/keys ]; then
    # 若 /app/keys 已有預設金鑰 (本機開發用途)，搬過去
    if [ -d /app/keys ] && [ "$(ls -A /app/keys)" ]; then
        cp -n /app/keys/* /data/keys/ 2>/dev/null || true
    fi
    rm -rf /app/keys
    ln -s /data/keys /app/keys
fi

# Capture 檔案 (HTML / screenshot / text)
mkdir -p /data/captures/html /data/captures/text /data/captures/screenshots
if [ ! -L /app/captures ]; then
    rm -rf /app/captures
    ln -s /data/captures /app/captures
fi

# ── 初始化 DB schema + 金鑰 ────────────────────────────────────
python - <<'EOF'
from utils.db_utils import ensure_runtime_directories, init_db
from services.signing_service import ensure_keypair
ensure_runtime_directories()
init_db()
ensure_keypair()
EOF

# ── 啟動方式：有 Litestream 設定就包 replicate；沒有就直接跑 ───
if [ -n "$LITESTREAM_ACCESS_KEY_ID" ]; then
    echo "[litestream] Restoring DB from R2 snapshot (if exists)..."
    litestream restore -if-replica-exists -config /app/litestream.yml /data/app.db || true
    echo "[litestream] Starting — DB writes will stream to R2"
    exec litestream replicate -config /app/litestream.yml \
        -exec "gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app"
else
    echo "[warn] No LITESTREAM_ACCESS_KEY_ID — running without R2 backup"
    exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
fi
