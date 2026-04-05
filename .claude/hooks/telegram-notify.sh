#!/usr/bin/env bash
# 發送 Telegram 通知
# 用法：bash telegram-notify.sh "訊息內容"
MSG="${1:-}"
[ -z "$MSG" ] && exit 0

TOKEN=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_BOT_TOKEN',''))" 2>/dev/null)
CHAT=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_CHAT_ID',''))" 2>/dev/null)

[ -z "$TOKEN" ] && exit 0
[ -z "$CHAT" ] && exit 0

# 用 JSON body 傳送，避免中文/換行/特殊字元造成 HTTP 格式錯誤
MSG_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$MSG")

curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\":\"${CHAT}\",\"text\":${MSG_JSON},\"parse_mode\":\"HTML\"}" > /dev/null
