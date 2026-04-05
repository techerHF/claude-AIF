#!/usr/bin/env bash
# telegram-listen.sh
# 每5分鐘輪詢 Telegram，執行老闆指令
# 只處理授權 chat ID 的訊息

TOKEN=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_BOT_TOKEN',''))" 2>/dev/null)
CHAT_ID=$(python3 -c "import json,pathlib; s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text()); print(s.get('env',{}).get('TELEGRAM_CHAT_ID',''))" 2>/dev/null)

[ -z "$TOKEN" ] && exit 0

OFFSET_FILE=/tmp/tg_offset
OFFSET=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)
RESP=$(curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates?offset=${OFFSET}&timeout=5")

echo "$RESP" | python3 -c "
import json,sys,os,subprocess,pathlib,datetime

d=json.load(sys.stdin)
CHAT_ID='${CHAT_ID}'
BASE=os.path.expanduser('~/ai-factory')
NOTIFY=f'bash {BASE}/.claude/hooks/telegram-notify.sh'

def notify(msg):
    os.system(f'{NOTIFY} \"{msg}\"')

for u in d.get('result',[]):
    uid=u['update_id']+1
    open('/tmp/tg_offset','w').write(str(uid))
    msg=u.get('message',{})

    # 安全驗證：只處理授權 chat ID
    if str(msg.get('chat',{}).get('id','')) != CHAT_ID:
        continue

    txt=msg.get('text','').strip()
    if not txt:
        continue

    # ── 系統指令 ──────────────────────────────────

    if txt == '/run':
        subprocess.Popen(['bash', f'{BASE}/run.sh'])
        notify('🚀 run.sh 已啟動，約10分鐘後完成')

    elif txt == '/stop':
        subprocess.run(['pkill','-f','run.sh'])
        notify('⏹ run.sh 已停止')

    elif txt == '/status':
        try:
            log_lines = open(f'{BASE}/logs/daily.log').readlines()[-5:]
            lines = ''.join(log_lines).strip()
        except:
            lines = '(無 log)'
        try:
            prog = json.loads(open(f'{BASE}/logs/progress.json').read())
            today = datetime.date.today().isoformat()
            done = [p for p in prog if p.get('date') == today]
            status = f'今日已完成 {len(done)} 篇' if done else '今日尚未執行'
        except:
            status = '尚無進度資料'
        notify(f'📊 {status}\n最新 log：{lines[:200]}')

    elif txt == '/report':
        try:
            rf = pathlib.Path(f'{BASE}/.team-memory/revenue-tracking.json')
            if rf.exists():
                r = json.loads(rf.read_text())
                cost = r.get('monthly_cost', 200)
                rev = r.get('total_revenue', 0)
                pl = rev - cost
                sign = '+' if pl >= 0 else ''
                pct = int(rev / cost * 100) if cost else 0
                rpt = f'💰 本月收益\n收益：\${rev}\n成本：\${cost}\n損益：{sign}\${pl}\n達成：{pct}%'
            else:
                rpt = '尚未設定收益追蹤'
        except Exception as e:
            rpt = f'讀取失敗：{e}'
        notify(rpt)

    elif txt == '/week':
        # 觸發週報
        subprocess.Popen(['bash', f'{BASE}/.claude/hooks/weekly-retrospective.sh'])
        notify('📋 週報產生中，約5分鐘後發送...')

    elif txt == '/proposals':
        try:
            content = open(f'{BASE}/.team-memory/proposals.md').read()
            # 找待審核區塊
            if '待審核' in content:
                lines = content.split('\n')
                pending = []
                in_section = False
                for l in lines:
                    if '待審核' in l and '##' in l:
                        in_section = True
                    elif '##' in l and in_section:
                        break
                    elif in_section and l.strip():
                        pending.append(l)
                summary = '\n'.join(pending[:10]) if pending else '目前沒有待審核提案'
            else:
                summary = '目前沒有提案'
        except:
            summary = '讀取 proposals.md 失敗'
        notify(f'💡 待審核提案：\n{summary}')

    elif txt.startswith('/approve '):
        pid = txt.split(' ', 1)[1].strip()
        # 寫入批准記錄
        pathlib.Path('/tmp/tg_approved.txt').write_text(pid)
        # 在 proposals.md 標記批准
        pf = pathlib.Path(f'{BASE}/.team-memory/proposals.md')
        if pf.exists():
            content = pf.read_text()
            content = content.replace(f'**狀態**：待審核', f'**狀態**：✅ 已批准（{datetime.date.today().isoformat()}）', 1)
            pf.write_text(content)
        notify(f'✅ 已批准提案：{pid}')

    elif txt.startswith('/reject '):
        parts = txt.split(' ', 2)
        pid = parts[1] if len(parts) > 1 else ''
        reason = parts[2] if len(parts) > 2 else '未說明原因'
        pf = pathlib.Path(f'{BASE}/.team-memory/proposals.md')
        if pf.exists():
            content = pf.read_text()
            content = content.replace(f'**狀態**：待審核', f'**狀態**：❌ 已否決（{reason}）', 1)
            pf.write_text(content)
        notify(f'❌ 已否決提案：{pid}，原因：{reason}')

    elif txt == '/help':
        help_text = '''🤖 AI 工廠指令列表
/run - 立即執行今日任務
/stop - 停止執行
/status - 查看今日狀態
/report - 收益報告
/week - 產生本週週報
/proposals - 查看待審核提案
/approve [ID] - 批准提案
/reject [ID] [原因] - 否決提案
一般文字 → 交給 chief-of-staff 處理'''
        notify(help_text)

    # ── 一般指令 → 放入 command queue，由 chief-of-staff 處理 ──
    elif not txt.startswith('/') and len(txt) > 3:
        qf = pathlib.Path(f'{BASE}/logs/command-queue.json')
        queue = json.loads(qf.read_text()) if qf.exists() else []
        queue.append({
            'command': txt,
            'timestamp': datetime.datetime.now().isoformat(),
            'status': 'pending'
        })
        qf.write_text(json.dumps(queue, ensure_ascii=False, indent=2))
        notify(f'📥 已收到：{txt[:50]}\n交給 chief-of-staff 在下次執行時處理')
" 2>/dev/null
