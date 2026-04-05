#!/usr/bin/env bash
# 每5分鐘輪詢 Telegram updates，執行指令（只處理授權 chat ID 的訊息）
TOKEN=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_BOT_TOKEN',''))" 2>/dev/null)
CHAT_ID=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_CHAT_ID',''))" 2>/dev/null)

[ -z "$TOKEN" ] && exit 0

OFFSET_FILE=/tmp/tg_offset
OFFSET=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)
RESP=$(curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates?offset=${OFFSET}&timeout=5")

echo "$RESP" | python3 -c "
import json,sys,os,subprocess,pathlib
d=json.load(sys.stdin)
CHAT_ID='${CHAT_ID}'
BASE=os.path.expanduser('~/ai-factory')
NOTIFY=f'bash {BASE}/.claude/hooks/telegram-notify.sh'

for u in d.get('result',[]):
    uid=u['update_id']+1
    open('/tmp/tg_offset','w').write(str(uid))
    msg=u.get('message',{})

    # 安全驗證：只處理授權 chat ID 的訊息
    if str(msg.get('chat',{}).get('id','')) != CHAT_ID:
        continue

    txt=msg.get('text','')

    if txt=='/run':
        subprocess.Popen(['bash',f'{BASE}/run.sh'])
        os.system(f'{NOTIFY} \"🚀 run.sh 已啟動\"')

    elif txt=='/status':
        lines=''
        try:
            with open(f'{BASE}/logs/daily.log') as f:
                lines='\n'.join(f.readlines()[-5:]).strip()
        except: lines='(無 log)'
        os.system(f'{NOTIFY} \"{lines}\"')

    elif txt=='/stop':
        subprocess.run(['pkill','-f','run.sh'])
        os.system(f'{NOTIFY} \"⏹ run.sh 已停止\"')

    elif txt=='/report':
        rf=pathlib.Path(f'{BASE}/.team-memory/revenue-tracking.json')
        if rf.exists():
            r=json.loads(rf.read_text())
            cost=r.get('monthly_cost',200)
            rev=r.get('total_revenue',0)
            pl=rev-cost
            sign='+' if pl>=0 else ''
            pct=int(rev/cost*100) if cost else 0
            rpt=f'💰 本月收益報告\n總收益：\${rev}\n月成本：\${cost}\n損益：{sign}\${pl}\n達成率：{pct}%'
        else:
            rpt='revenue-tracking.json 不存在，尚未設定收益'
        os.system(f'{NOTIFY} \"{rpt}\"')

    elif txt.startswith('/approve '):
        pid=txt.split(' ',1)[1].strip()
        pathlib.Path('/tmp/tg_approved.txt').write_text(pid)
        os.system(f'{NOTIFY} \"✅ 已批准提案：{pid}，等待下次主流程執行\"')

" 2>/dev/null
