#!/usr/bin/env bash
# 每日 23:00 自動備份到 GitHub
cd ~/ai-factory

# 讀取 GitHub Token 和 Repo（用於 HTTPS 認證）
TOKEN=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('GITHUB_TOKEN',''))" 2>/dev/null)
REPO=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('GITHUB_REPO',''))" 2>/dev/null)

[ -z "$TOKEN" ] && echo "$(date): No GITHUB_TOKEN, skip backup" >> logs/backup.log && exit 0
[ -z "$REPO" ] && echo "$(date): No GITHUB_REPO, skip backup" >> logs/backup.log && exit 0

# 設定帶 token 的 remote URL（每次設定，避免 token 過期後殘留舊設定）
git remote set-url origin "https://${TOKEN}@github.com/${REPO}.git"

TITLE=$(grep "文章標題" logs/daily.log 2>/dev/null | tail -1 | cut -d: -f2 | xargs)
MSG="Auto backup: $(date +%Y-%m-%d)${TITLE:+ [$TITLE]}"

git add -A

if git diff --cached --quiet; then
    echo "$(date): Nothing to commit" >> logs/backup.log
    exit 0
fi

git commit -m "$MSG"
git push origin master >> logs/backup.log 2>&1 && echo "$(date): Push OK" >> logs/backup.log || echo "$(date): Push failed" >> logs/error.log
