#!/usr/bin/env bash
# set-gemini-key.sh
# 安全輸入並儲存 Gemini API key，測試連線
# 用法：bash set-gemini-key.sh

cd ~/ai-factory 2>/dev/null || { echo "❌ 找不到 ~/ai-factory"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Gemini API Key 設定工具                  ║"
echo "║  模型：gemma-3-27b-it（每日 1500 次免費）  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 檢查現有 key
EXISTING=$(python3 -c "
import json,pathlib
try:
  s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text())
  k=s.get('env',{}).get('GEMINI_API_KEY','')
  print(k[:12]+'...' if k else '')
except: print('')
" 2>/dev/null)

if [ -n "$EXISTING" ]; then
  echo "目前已設定的 key：$EXISTING"
  echo "是否要更換？[y/N]"
  read -r -t 10 REPLACE
  [ "$REPLACE" != "y" ] && [ "$REPLACE" != "Y" ] && echo "保留現有 key。" && exit 0
fi

echo "請輸入 Gemini API key（從 https://aistudio.google.com/apikey 取得）："
read -rs GEMINI_KEY
echo ""

if [ -z "$GEMINI_KEY" ]; then
  echo "❌ 未輸入 key，取消。"
  exit 1
fi

# 儲存到 settings.json
python3 -c "
import json,pathlib
f=pathlib.Path.home()/'.claude/settings.json'
s=json.loads(f.read_text())
s.setdefault('env',{})['GEMINI_API_KEY']='$GEMINI_KEY'
f.write_text(json.dumps(s,indent=2))
print('✅ 已儲存到 ~/.claude/settings.json')
" 2>/dev/null || echo "⚠️  settings.json 寫入失敗"

# 備份到 .env
grep -v "^GEMINI_API_KEY=" .env 2>/dev/null > .env.tmp && mv .env.tmp .env 2>/dev/null || true
echo "GEMINI_API_KEY=$GEMINI_KEY" >> .env
echo "✅ 已備份到 ~/ai-factory/.env"

# 測試連線
echo ""
echo "測試 Gemini 連線..."
TEST_RESULT=$(curl -s --max-time 15 \
  "https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key=${GEMINI_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Reply with exactly: GEMINI_OK"}]}],"generationConfig":{"maxOutputTokens":20}}' \
  | python3 -c "
import json,sys
try:
  d=json.load(sys.stdin)
  if 'error' in d:
    print('ERROR:', d['error'].get('message','unknown'))
  else:
    print(d['candidates'][0]['content']['parts'][0]['text'].strip())
except Exception as e:
  print('PARSE_ERROR:', e)
" 2>/dev/null)

if echo "$TEST_RESULT" | grep -qi "GEMINI_OK\|ok"; then
  echo "✅ Gemini 連線成功！回應：$TEST_RESULT"
elif echo "$TEST_RESULT" | grep -qi "ERROR"; then
  echo "❌ Gemini 連線失敗：$TEST_RESULT"
  echo "   請確認 key 正確且有啟用 Gemini API"
else
  echo "⚠️  回應異常：$TEST_RESULT"
fi

echo ""
echo "設定完成。之後壓力測試遇到 MiniMax 超限時會自動切換 Gemini。"
