#!/usr/bin/env bash
# telegram-notify.sh
# 用法：bash telegram-notify.sh "訊息內容"
# 成功：輸出 "OK"；失敗：輸出具體錯誤原因

MSG="${1:-}"
[ -z "$MSG" ] && { echo "SKIP: 訊息為空"; exit 0; }

TOKEN=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_BOT_TOKEN',''))" 2>/dev/null)
CHAT=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_CHAT_ID',''))" 2>/dev/null)

# 明確檢查是否設定
if [ -z "$TOKEN" ] || [ "$TOKEN" = "你的Bot_Token" ]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN 未設定或仍是預設值"
  echo "請執行：python3 -c \"import json,pathlib; f=pathlib.Path.home()/'.claude/settings.json'; s=json.loads(f.read_text()); s.setdefault('env',{})['TELEGRAM_BOT_TOKEN']='實際token'; f.write_text(json.dumps(s,indent=2))\""
  exit 1
fi

if [ -z "$CHAT" ] || [ "$CHAT" = "你的Chat_ID" ]; then
  echo "ERROR: TELEGRAM_CHAT_ID 未設定或仍是預設值"
  echo "請對 bot 發一則訊息後執行：curl -s \"https://api.telegram.org/bot\${TOKEN}/getUpdates\" | python3 -c \"import json,sys; u=json.load(sys.stdin)['result']; print(u[-1]['message']['chat']['id'] if u else '無更新，請先對 bot 發一則訊息')\""
  exit 1
fi

MSG_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$MSG")

RESP=$(curl -s -w "\n%{http_code}" -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\":\"${CHAT}\",\"text\":${MSG_JSON},\"parse_mode\":\"HTML\"}")

HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -1)

if [ "$HTTP_CODE" = "200" ]; then
  OK=$(echo "$BODY" | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK' if d.get('ok') else 'FAIL: '+str(d))" 2>/dev/null)
  echo "$OK"
else
  echo "ERROR: HTTP $HTTP_CODE"
  echo "$BODY" | python3 -c "import json,sys; d=json.load(sys.stdin); print('Telegram 說：'+d.get('description','未知錯誤'))" 2>/dev/null || echo "$BODY"
  exit 1
fi
