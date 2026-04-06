#!/usr/bin/env bash
# deploy.sh
# 用途：VPS 部署腳本（只在 Zeabur VPS 上執行）
# 執行：bash ~/ai-factory/deploy.sh

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "=== AI 無人工廠 VPS 部署 ==="
echo "時間：$(date)"

# 1. 更新程式碼（自動偵測當前 branch）
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "master")
git pull origin "$CURRENT_BRANCH" || git pull origin master || true

# 2. 設定 hook 執行權限
chmod +x .claude/hooks/*.sh
chmod +x "$BASE_DIR/auto-update-dashboard.sh"
echo "Hook 權限設定完成"

# 3. 確認 Python3 可用
python3 --version || { echo "ERROR: python3 未找到，請安裝"; exit 1; }

# 4. 確認 Claude Code CLI 可用
claude --version || { echo "ERROR: claude CLI 未找到，請安裝 Claude Code"; exit 1; }

# 5. 建立必要目錄
mkdir -p logs

# 6. 初始化 progress.json（如果不存在）
[ ! -f logs/progress.json ] && echo "[]" > logs/progress.json && echo "初始化 progress.json"

# 7. 測試 checkpoint
echo "測試 checkpoint..."
bash .claude/hooks/checkpoint.sh status

# 8. 驗證 CLAUDE.md 連結
echo "檢查 Payhip 連結..."
bash .claude/hooks/link-validation.sh || true

# 9. 初始化 topic-performance.json（如果不存在）
if [ ! -f logs/topic-performance.json ]; then
  cat > logs/topic-performance.json << 'JSON'
{
  "last_updated": "",
  "categories": {
    "A": {"avg_upvotes": 0, "avg_comments": 0, "count": 0, "trend": "unknown"},
    "B": {"avg_upvotes": 0, "avg_comments": 0, "count": 0, "trend": "unknown"},
    "C": {"avg_upvotes": 0, "avg_comments": 0, "count": 0, "trend": "unknown"},
    "D": {"avg_upvotes": 0, "avg_comments": 0, "count": 0, "trend": "unknown"}
  }
}
JSON
  echo "初始化 topic-performance.json"
fi

echo ""
echo "=== 部署完成 ==="
echo "設定 cron 排程..."

# 偵測 cron 實作（容器環境可能需要安裝）
if ! command -v crontab >/dev/null 2>&1; then
  echo "crontab 未找到，嘗試安裝 cron..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq cron
    service cron start 2>/dev/null || true
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache dcron
    crond 2>/dev/null || true
  else
    echo "WARN: 無法自動安裝 cron，請手動安裝後重新執行 deploy.sh"
    echo "Ubuntu/Debian: apt-get install -y cron && service cron start"
    echo "Alpine: apk add dcron && crond"
    echo ""
    echo "=== cron 未設定，其餘部署完成 ==="
    exit 0
  fi
fi

# 設定排程（先清掉舊版/重複項目，再重建必要任務）
(
  crontab -l 2>/dev/null \
    | grep -v 'run.sh >> .*logs/cron.log' \
    | grep -v "feedback-collector agent 收集昨日發文數據" \
    | grep -v 'auto-update-dashboard.sh >> .*logs/cron.log' || true
  echo "0  9 * * * /bin/bash $BASE_DIR/run.sh >> $BASE_DIR/logs/cron.log 2>&1"
  echo "10 9 * * * cd $BASE_DIR && claude -p '呼叫 feedback-collector agent 收集昨日發文數據' --allowedTools 'Read,Write,Bash,Agent,WebFetch' --permission-mode acceptEdits --max-turns 20 >> $BASE_DIR/logs/feedback.log 2>&1"
  echo "*/5 * * * * /bin/bash $BASE_DIR/auto-update-dashboard.sh >> $BASE_DIR/logs/cron.log 2>&1"
) | crontab -

echo "Cron 排程已設定："
crontab -l
