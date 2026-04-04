#!/usr/bin/env bash
# deploy.sh
# 用途：VPS 部署腳本（只在 Zeabur VPS 上執行）
# 執行：bash ~/ai-factory/deploy.sh

set -euo pipefail

echo "=== AI 無人工廠 VPS 部署 ==="
echo "時間：$(date)"

# 1. 更新程式碼
git pull origin main

# 2. 設定 hook 執行權限
chmod +x .claude/hooks/*.sh
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
echo "設定 cron 排程（兩條）..."

# 設定兩條 cron
(
  crontab -l 2>/dev/null | grep -v 'ai-factory/run.sh' | grep -v 'feedback-collector'
  echo "0  9 * * * /bin/bash ~/ai-factory/run.sh >> ~/ai-factory/logs/cron.log 2>&1"
  echo "10 9 * * * cd ~/ai-factory && claude -p '呼叫 feedback-collector agent 收集昨日發文數據' --allowedTools 'Read,Write,Bash,Agent,WebFetch' --permission-mode acceptEdits --max-turns 20 >> ~/ai-factory/logs/feedback.log 2>&1"
) | crontab -

echo "Cron 排程已設定："
crontab -l
