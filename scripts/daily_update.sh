#!/bin/bash
# ═══════════════════════════════════════════════════════
# Wolf Pack Dashboard — 每日自動更新腳本
# 放在 Mac Mini 上，爬蟲跑完後自動執行
#
# 功能：
#   1. 執行 signal engine 產出 JSON
#   2. git add + commit + push 到 GitHub
#   3. GitHub Pages 自動更新
#
# 用法：
#   chmod +x daily_update.sh
#   ./daily_update.sh
# ═══════════════════════════════════════════════════════

set -e

# ── 路徑設定 ──
REPO_DIR="$HOME/wolf-pack-dashboard"
SCRIPTS_DIR="$REPO_DIR/scripts"
LOG_DIR="$HOME/FinanceData/logs"
LOG_FILE="$LOG_DIR/dashboard_update.log"

# 確保 log 目錄存在
mkdir -p "$LOG_DIR"

# 紀錄函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "═══════════════════════════════════════"
log "🐺 Wolf Pack Dashboard 每日更新開始"
log "═══════════════════════════════════════"

# ── Step 1: 產生 JSON 數據 ──
log "📊 Step 1: 執行 generate_dashboard_data.py..."
cd "$SCRIPTS_DIR"
python3 generate_dashboard_data.py >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "❌ JSON 生成失敗！"
    exit 1
fi
log "✅ JSON 生成完成"

# ── Step 2: Git 提交並推送 ──
log "📤 Step 2: Git commit & push..."
cd "$REPO_DIR"

# 檢查是否有變更
if git diff --quiet data/ 2>/dev/null; then
    log "ℹ️ 數據無變更，跳過提交"
else
    TODAY=$(date '+%Y-%m-%d')
    git add data/dashboard.json data/etf_pages.json
    git commit -m "📊 Daily update: $TODAY" --quiet
    git push origin main --quiet

    if [ $? -eq 0 ]; then
        log "✅ Git push 成功"
    else
        log "❌ Git push 失敗！"
        exit 1
    fi
fi

log "🐺 每日更新完成！"
log ""
