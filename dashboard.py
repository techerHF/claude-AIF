#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v11
— GameMaster 控制台：深色像素作戰室 + 扁平團隊協作 + 即時指揮
執行：python3 ~/ai-factory/dashboard.py
"""

import json, os, re, subprocess, time, urllib.parse, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
_chat_history = []

# ══════════════════════════════════════════════════════════
#  完整流程定義（11 Agents、檔案 I/O、Skills、Hooks）
# ══════════════════════════════════════════════════════════
PIPELINE_FLOW = [
  {"id":"researcher",       "order":1,  "label":"秘書",   "icon":"◎", "phase":"協調",
   "desc":"老闆需求翻譯 + 對外資源窗口，負責提案/請示/對話與任務分派",
   "reads": ["CLAUDE.md","logs/topic-performance.json",".knowledge/performance.md"],
   "writes":["logs/demand_signals.json","logs/affiliate-links.json"],
   "skills":["researcher-strategy","audience-targeting"],
   "hooks": []},

  {"id":"topic-selector",   "order":2,  "label":"經理",     "icon":"◈", "phase":"統籌",
   "desc":"技術統籌與團隊把關，協調多 Agent 平行工作並決策技術路線",
   "reads": ["logs/demand_signals.json",".knowledge/posted-articles.md",".knowledge/performance.md"],
   "writes":["logs/progress.json"],
   "skills":["topic-selection","content-calendar"],
   "hooks": ["duplicate-check.sh","topic-tracker.sh"]},

  {"id":"writer",           "order":3,  "label":"中文初稿", "icon":"✦", "phase":"生產",
   "desc":"產出中文教學文章，植入 Whop 銷售連結，符合張旭豐學術→教學語氣",
   "reads": ["logs/progress.json",".claude/skills/writing-style.md",
             ".claude/skills/article-structure.md",".knowledge/good-titles.md"],
   "writes":["articles/YYYY-MM-DD-*.md"],
   "skills":["writing-style","article-structure","code-writing","topic-hook",
             "persona","digital-twin-voice","whop-product"],
   "hooks": ["quality-check.sh","ai-detection.sh","code-syntax-check.sh",
             "word-count.sh","checkpoint.sh"]},

  {"id":"seo-agent",        "order":4,  "label":"SEO",      "icon":"S", "phase":"生產",
   "desc":"產出 3 個標題候選，選最佳，優化關鍵字放置位置",
   "reads": ["articles/*.md",".claude/skills/seo-optimization.md"],
   "writes":["articles/*.md（標題更新）"],
   "skills":["seo-optimization","platform-rules","reddit-post"],
   "hooks": ["link-validation.sh"]},

  {"id":"english-writer",   "order":5,  "label":"英文寫手", "icon":"E", "phase":"生產",
   "desc":"產出 Reddit 摘要版（600-900字）+ Medium 完整版（1500+字），含聯盟連結",
   "reads": ["articles/*.md",".claude/skills/english-writing.md",
             ".claude/skills/medium-post.md",".claude/skills/whop-copy.md"],
   "writes":["articles/*-reddit.md","articles/*-medium.md"],
   "skills":["digital-twin-voice","english-writing","medium-post",
             "whop-copy","monetization-strategy"],
   "hooks": ["quality-check.sh","word-count.sh"]},

  {"id":"chinese-writer",   "order":6,  "label":"中文詮釋", "icon":"中", "phase":"生產",
   "desc":"將英文文章詮釋為台灣 Maker 社群中文版，非翻譯，加台灣場景",
   "reads": ["articles/*-medium.md",".claude/skills/chinese-writing.md"],
   "writes":["articles/*-zh.md"],
   "skills":["chinese-writing","audience-targeting"],
   "hooks": []},

  {"id":"reviewer",         "order":7,  "label":"審稿",     "icon":"◉", "phase":"品管",
   "desc":"5 道自動關卡（品質/AI偵測/語法/字數/重複）+ 手動邏輯審查",
   "reads": ["articles/*.md",".claude/skills/writing-style.md"],
   "writes":["logs/progress.json（reviewed）"],
   "skills":["writing-style","feedback-interpretation"],
   "hooks": ["quality-check.sh","duplicate-check.sh","ai-detection.sh",
             "code-syntax-check.sh","word-count.sh"]},

  {"id":"poster",           "order":8,  "label":"發文",     "icon":"◆", "phase":"發布",
   "desc":"發布到 Reddit / Medium / dev.to，管理每週 2 篇限制",
   "reads": ["articles/*.md","CLAUDE.md","logs/reddit-history.json"],
   "writes":["logs/reddit-history.json","logs/progress.json（posted）"],
   "skills":["platform-rules","reddit-post","medium-post","comment-strategy"],
   "hooks": ["reddit-rate-limit.sh","link-validation.sh"]},

  {"id":"feedback-collector","order":9, "label":"回報收集", "icon":"F", "phase":"回饋",
   "desc":"發文後 24 小時收集 upvotes/comments，分類 high/medium/low",
   "reads": ["logs/reddit-history.json"],
   "writes":["logs/topic-performance.json"],
   "skills":["feedback-interpretation"],
   "hooks": []},

  {"id":"style-updater",    "order":10, "label":"風格進化", "icon":"↺", "phase":"進化",
   "desc":"根據表現數據自動更新 writing-style.md — 系統自我學習核心",
   "reads": ["logs/topic-performance.json"],
   "writes":[".claude/skills/writing-style.md（更新）","logs/topic-performance.json"],
   "skills":["feedback-interpretation","writing-style"],
   "hooks": []},

  {"id":"knowledge-subagent","order":11,"label":"知識庫",   "icon":"K", "phase":"進化",
   "desc":"任務結束前強制寫入知識庫，Stop Hook 觸發，確保記錄不遺漏",
   "reads": ["logs/progress.json","logs/topic-performance.json"],
   "writes":[".knowledge/posted-articles.md",".knowledge/lessons.md",
             ".knowledge/good-titles.md",".knowledge/performance.md"],
   "skills":["knowledge-update"],
   "hooks": ["memory-update.sh"]},
]

FILE_TRANSFERS = [
  ["demand_signals.json","affiliate-links.json"],
  ["progress.json（主題）"],
  ["articles/*.md"],
  ["articles/*.md（SEO完成）"],
  ["articles/*-medium.md"],
  ["articles/*-zh.md"],
  ["articles/*.md（審核通過）"],
  ["reddit-history.json"],
  ["topic-performance.json"],
  ["writing-style.md（更新）"],
]

HOOK_CATALOG = sorted({h for a in PIPELINE_FLOW for h in a.get("hooks", [])})

# ══════════════════════════════════════════════════════════
#  資料函數
# ══════════════════════════════════════════════════════════

def rj(path, default=None):
    try: return json.loads((BASE/path).read_text(encoding="utf-8"))
    except: return default if default is not None else {}

def rt(path, n=80):
    try:
        lines = (BASE/path).read_text(encoding="utf-8").splitlines()
        return lines[-n:]
    except: return []

def api_status():
    try:
        s = json.loads(Path.home().joinpath(".claude/settings.json").read_text())
        m = s.get("env",{}).get("ANTHROPIC_MODEL","")
        return {"model":m or "Claude（預設）","minimax":"MiniMax" in m}
    except: return {"model":"Claude（預設）","minimax":False}

def read_api_env():
    try:
        s = json.loads(Path.home().joinpath(".claude/settings.json").read_text())
        env = s.get("env",{})
        token = env.get("ANTHROPIC_AUTH_TOKEN","") or env.get("ANTHROPIC_API_KEY","")
        return (token,
                env.get("ANTHROPIC_BASE_URL","https://api.anthropic.com").rstrip("/"),
                env.get("ANTHROPIC_MODEL","claude-3-5-sonnet-20241022"))
    except: return ("","https://api.anthropic.com","claude-3-5-sonnet-20241022")

def cron_lines():
    try:
        r = subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=3)
        return [l for l in r.stdout.splitlines() if "ai-factory" in l]
    except: return []

def file_stat(path_str):
    clean = re.sub(r'（.*?）','',path_str).replace('（','').replace('）','').strip()
    if '*' in clean:
        try:
            matches = sorted(BASE.glob(clean), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                age = time.time() - matches[0].stat().st_mtime
                return {"ok":True,"age":int(age/60),"count":len(matches)}
        except: pass
        return {"ok":False}
    p = BASE/clean
    if not p.exists(): return {"ok":False}
    age = time.time() - p.stat().st_mtime
    return {"ok":True,"age":int(age/60),"size":p.stat().st_size}

def pipeline_status():
    prog  = rj("logs/progress.json",[])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_items = [p for p in prog if p.get("date","") == today]
    stages = [{"id":a["id"],"label":a["label"]} for a in PIPELINE_FLOW[:8]]
    done_map = {
        "reviewed": ["researcher","topic-selector","writer","seo-agent","english-writer","chinese-writer","reviewer"],
        "posted":   ["researcher","topic-selector","writer","seo-agent","english-writer","chinese-writer","reviewer","poster"],
        "published":["researcher","topic-selector","writer","seo-agent","english-writer","chinese-writer","reviewer","poster"],
    }
    if today_items:
        item = today_items[-1]
        done = set(done_map.get(item.get("status",""),[]))
        for s in stages: s["done"] = s["id"] in done
        return {"stages":stages,"article":item,"count":len(today_items)}
    return {"stages":stages,"article":None,"count":0}

def compute_agent_states():
    """
    扁平化團隊狀態：允許多位 Agent 同時工作，而非單一路徑串接。
    依據最近 cron 日誌提及頻率判定 working/waiting，未提及則 idle。
    """
    recent = [l.lower() for l in rt("logs/cron.log", 160)]
    short = recent[-24:]
    mid = recent[-80:]
    result = {}
    for a in PIPELINE_FLOW:
        aid = a["id"]
        aliases = {aid.lower(), a["label"].lower()}
        hit_short = any(any(alias in line for alias in aliases) for line in short)
        hit_mid = any(any(alias in line for alias in aliases) for line in mid)
        if hit_short:
            result[aid] = {"status":"working","txt":"工作中"}
        elif hit_mid:
            result[aid] = {"status":"waiting","txt":"同步中"}
        else:
            result[aid] = {"status":"idle","txt":"休息中"}
    working_count = sum(1 for v in result.values() if v["status"] == "working")
    if working_count == 0:
        result["topic-selector"] = {"status":"working","txt":"工作中"}
        result["researcher"] = {"status":"working","txt":"工作中"}
    return result

def activity_feed():
    events = []
    prog = rj("logs/progress.json",[])
    for p in reversed(prog[-8:]):
        events.append({"time":p.get("timestamp","")[:16].replace("T"," "),
            "agent":"writer","msg":"文章完成："+p.get("title",""),"type":"success"})
    for line in reversed(rt("logs/cron.log",30)):
        line = line.strip()
        if not line: continue
        agent,t = "system","info"
        if "APPROVED" in line: t,agent="success","quality-check"
        elif "REJECTED" in line: t,agent="warn","quality-check"
        elif "error" in line.lower(): t,agent="error","system"
        elif "writer" in line.lower(): agent="writer"
        elif "reviewer" in line.lower(): agent="reviewer"
        elif "poster" in line.lower(): agent="poster"
        elif "researcher" in line.lower(): agent="researcher"
        events.append({"time":"","agent":agent,"msg":line[:120],"type":t})
    for line in reversed(rt("logs/error.log",5)):
        if line.strip():
            events.append({"time":"","agent":"system","msg":line[:120],"type":"error"})
    return events[:30]

def knowledge_summary():
    files = [
      {"name":"posted-articles.md","label":"已發文章"},
      {"name":"lessons.md","label":"經驗教訓"},
      {"name":"good-titles.md","label":"成功標題"},
      {"name":"performance.md","label":"表現記錄"},
    ]
    result = []
    for f in files:
        p = BASE/".knowledge"/f["name"]
        if p.exists():
            txt   = p.read_text(encoding="utf-8",errors="ignore")
            lines = [l for l in txt.splitlines() if l.strip() and not l.startswith("#")]
            age   = int((time.time()-p.stat().st_mtime)/60)
            result.append({"name":f["name"],"label":f["label"],
                "lines":len(lines),"age":age,"size":len(txt)})
        else:
            result.append({"name":f["name"],"label":f["label"],"lines":0,"age":-1,"size":0})
    return result

def api_usage():
    return rj("logs/api-usage.json",{"today":0,"total":0})

def list_articles():
    try:
        arts = sorted(BASE.glob("articles/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = []
        for a in arts[:20]:
            content = a.read_text(encoding="utf-8",errors="ignore")
            lines   = content.splitlines()
            title   = next((l.lstrip("#").strip() for l in lines if l.startswith("#")),a.stem)
            words   = len(re.sub(r'```.*?```','',content,flags=re.DOTALL).split())
            result.append({"name":a.stem,"title":title[:80],"words":words})
        return result
    except: return []

def get_article_content(name):
    try:
        p = BASE/"articles"/f"{name}.md"
        return p.read_text(encoding="utf-8",errors="ignore") if p.exists() else None
    except: return None

def run_diagnostics():
    issues = []; score = 100
    api    = api_status(); crons = cron_lines()
    has_ph = False
    try: has_ph = "PLACEHOLDER" in (BASE/"CLAUDE.md").read_text(encoding="utf-8")
    except: pass
    err_lines = [l.strip() for l in rt("logs/error.log",5) if l.strip()]
    if has_ph:
        issues.append({"level":"warn","title":"WHOP 連結未設定",
            "desc":"CLAUDE.md 含 PLACEHOLDER_WHOP_*","tag":"設定"}); score-=15
    if err_lines:
        issues.append({"level":"error","title":f"系統錯誤 × {len(err_lines)}",
            "desc":err_lines[-1][:80],"tag":"錯誤"}); score-=20
    if len(crons)==0:
        issues.append({"level":"error","title":"排程器未設定","desc":"未找到 ai-factory Cron","tag":"排程"}); score-=20
    elif len(crons)>2:
        issues.append({"level":"warn","title":f"Cron 重複 ({len(crons)} 筆)","desc":"建議清理","tag":"排程"}); score-=5
    else:
        issues.append({"level":"ok","title":"排程器正常","desc":f"{len(crons)} 個排程","tag":"排程"})
    if api["minimax"]:
        issues.append({"level":"ok","title":"MiniMax 連線正常","desc":api["model"],"tag":"API"})
    else:
        issues.append({"level":"info","title":"使用預設 Claude","desc":"未偵測到 MiniMax 設定","tag":"API"})
    usage = api_usage()
    if usage.get("today",0)==0:
        issues.append({"level":"info","title":"API 呼叫追蹤未啟用",
            "desc":"需在 agent 流程加入 logs/api-usage.json 追蹤","tag":"追蹤"})
    if not (BASE/"logs"/"demand_signals.json").exists():
        issues.append({"level":"info","title":"尚未執行完整自動循環",
            "desc":"demand_signals.json 不存在","tag":"狀態"})
    cron_s = "ok" if 0<len(crons)<=2 else ("warn" if len(crons)>2 else "error")
    health = [
        {"name":"模型","status":"ok" if api["minimax"] else "info",
         "val":"MiniMax" if api["minimax"] else "預設"},
        {"name":"排程","status":cron_s,"val":f"{len(crons)} 個"},
        {"name":"錯誤","status":"error" if err_lines else "ok",
         "val":str(len(err_lines)) if err_lines else "無"},
        {"name":"設定","status":"warn" if has_ph else "ok",
         "val":"待完成" if has_ph else "正常"},
    ]
    return {"score":max(0,score),"health":health,"issues":issues[:10]}

def get_system_context_summary():
    state  = rj("logs/progress.json",[])
    diag   = run_diagnostics()
    api    = api_status()
    crons  = cron_lines()
    knows  = knowledge_summary()
    arts   = list_articles()
    today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_arts = [p for p in state if p.get("date","")==today]
    warn_issues = [i for i in diag["issues"] if i["level"] in ("warn","error")]
    lines = [
        f"系統狀態：健康度 {diag['score']}%，今日文章 {len(today_arts)} 篇",
        f"API 模型：{api['model']}，Cron 排程：{len(crons)} 個",
        f"文章庫：共 {len(arts)} 篇，知識庫 4 個檔案",
        f"待處理問題：{len(warn_issues)} 個",
    ]
    if warn_issues:
        lines.append("問題清單：" + "；".join(i["title"] for i in warn_issues[:3]))
    know_active = [k for k in knows if k["lines"]>0]
    if know_active:
        lines.append("知識庫：" + "、".join(f"{k['label']}({k['lines']}條)" for k in know_active))
    return "\n".join(lines)

def do_chat(message):
    global _chat_history
    api_key, base_url, model = read_api_env()
    if not api_key:
        return (
            "⚠ 未設定 ANTHROPIC_AUTH_TOKEN\n\n"
            "在 VPS 執行：\n"
            "python3 -c \"\nimport json,pathlib\n"
            "f=pathlib.Path.home()/'.claude/settings.json'\n"
            "s=json.loads(f.read_text()) if f.exists() else {}\n"
            "s.setdefault('env',{})['ANTHROPIC_AUTH_TOKEN']='your-minimax-token'\n"
            "f.write_text(json.dumps(s,indent=2))\nprint('OK')\n\"\n\n"
            "替換 your-minimax-token 後重啟 dashboard。"
        )
    try:
        _chat_history = _chat_history[-8:]
        msgs = _chat_history + [{"role":"user","content":message}]
        sys_ctx = get_system_context_summary()
        payload = json.dumps({
            "model": model, "max_tokens": 700,
            "system": (
                "你是 AI 無人工廠的智慧控制台助手。\n"
                "這個工廠由 11 個 Agent 組成，自動產出 Arduino/感測器教學文章，發布到 Reddit/Medium/dev.to。\n"
                "作者是張旭豐，機械工程博士，雲林科技大學，研究觸覺感測器。\n\n"
                f"當前系統狀態：\n{sys_ctx}\n\n"
                "用繁體中文回答，簡潔、直接、務實。如果問到技術設定請給具體指令。"
            ),
            "messages": msgs
        }).encode()
        is_minimax = "minimax" in base_url.lower() or "api.minimax" in base_url.lower()
        if is_minimax:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        else:
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
        req = urllib.request.Request(f"{base_url}/v1/messages", data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read())
            # Anthropic format (incl. MiniMax-M2.7 thinking blocks)
            # content array may have: [{"type":"thinking","thinking":"..."},{"type":"text","text":"..."}]
            if "content" in result and isinstance(result["content"], list) and result["content"]:
                reply = ""
                for item in result["content"]:
                    if isinstance(item, dict) and item.get("type") == "text":
                        reply = item.get("text",""); break
                if not reply:  # fallback: any item with "text" key
                    for item in result["content"]:
                        if isinstance(item, dict) and item.get("text"):
                            reply = item["text"]; break
                if not reply:
                    reply = f"[解析失敗] {json.dumps(result['content'])[:200]}"
            # OpenAI/MiniMax chat format: {"choices": [{"message":{"content":"..."}}]}
            elif "choices" in result and result["choices"]:
                reply = result["choices"][0].get("message",{}).get("content","（空回應）")
            # Direct string content
            elif "content" in result and isinstance(result["content"], str):
                reply = result["content"]
            else:
                reply = f"[回應格式未知] {json.dumps(result)[:300]}"
            _chat_history.append({"role":"user","content":message})
            _chat_history.append({"role":"assistant","content":reply})
            return reply
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:200]
        return f"❌ HTTP {e.code}：{body}"
    except Exception as e:
        return f"❌ API 錯誤：{type(e).__name__}: {str(e)[:150]}"

def post_to_devto(article_name):
    api_key = os.environ.get("DEVTO_API_KEY","")
    if not api_key:
        try:
            s = json.loads(Path.home().joinpath(".claude/settings.json").read_text())
            api_key = s.get("env",{}).get("DEVTO_API_KEY","")
        except: pass
    if not api_key:
        return {"ok":False,"error":"未設定 DEVTO_API_KEY"}
    content = get_article_content(article_name)
    if not content: return {"ok":False,"error":"找不到文章"}
    lines = content.splitlines()
    title = next((l.lstrip("#").strip() for l in lines if l.startswith("#")), article_name)
    try:
        payload = json.dumps({"article":{
            "title": title, "body_markdown": content,
            "published": False, "tags": ["arduino","sensors","maker","diy"]
        }}).encode()
        req = urllib.request.Request("https://dev.to/api/articles", data=payload,
            headers={"api-key":api_key,"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            r = json.loads(resp.read())
            return {"ok":True,"url":r.get("url",""),"id":r.get("id",""),"title":r.get("title","")}
    except Exception as e:
        return {"ok":False,"error":str(e)[:100]}

def get_status_data():
    prog   = rj("logs/progress.json",[])
    api    = api_status()
    crons  = cron_lines()
    usage  = api_usage()
    pipe   = pipeline_status()
    agents = compute_agent_states()
    feed   = activity_feed()
    diag   = run_diagnostics()
    knows  = knowledge_summary()
    hooks  = hook_runtime_summary()
    has_ph = False
    try: has_ph = "PLACEHOLDER" in (BASE/"CLAUDE.md").read_text(encoding="utf-8")
    except: pass
    flow = []
    for a in PIPELINE_FLOW:
        st = agents.get(a["id"],{"status":"idle","txt":"休息中"})
        flow.append({**a,
            "status":  st["status"],
            "status_txt": st["txt"],
            "reads_stat":  [{"path":p,"stat":file_stat(p)} for p in a["reads"]],
            "writes_stat": [{"path":p,"stat":file_stat(p)} for p in a["writes"]],
            "skills_avail": check_skills(a["skills"]),
            "hooks_avail":  check_hooks(a["hooks"]),
        })
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "ts":           datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "state":        "error" if [l for l in rt("logs/error.log",3) if l.strip()] else
                        ("running" if any(today[:7] in l for l in rt("logs/cron.log",5)) else "idle"),
        "api":          api,
        "cron_count":   len(crons),
        "has_placeholder": has_ph,
        "article_count":   len(prog),
        "articles":     list_articles(),
        "pipeline":     pipe,
        "flow":         flow,
        "feed":         feed,
        "usage":        usage,
        "perf":         rj("logs/topic-performance.json",{}).get("categories",{}),
        "diag":         diag,
        "knowledge":    knows,
        "hooks":        hooks,
        "file_transfers": FILE_TRANSFERS,
        "cron_log_tail": rt("logs/cron.log",60),
        "error_log":    rt("logs/error.log",30),
    }

def check_skills(skill_list):
    skill_dir = BASE/".claude/skills"
    avail = {f.stem for f in skill_dir.glob("*.md")} if skill_dir.exists() else set()
    return [{"name":s,"ok":s in avail} for s in skill_list]

def check_hooks(hook_list):
    hook_dir = BASE/".claude/hooks"
    avail = {f.name for f in hook_dir.glob("*.sh")} if hook_dir.exists() else set()
    return [{"name":h,"ok":h in avail} for h in hook_list]

def hook_runtime_summary():
    hook_dir = BASE/".claude/hooks"
    cron_tail = rt("logs/cron.log", 240)
    err_tail = rt("logs/error.log", 120)
    rows = []
    for name in HOOK_CATALOG:
        exists = (hook_dir / name).exists()
        hit = next((line for line in reversed(cron_tail) if name in line), "")
        err = next((line for line in reversed(err_tail) if name in line), "")
        rows.append({
            "name": name,
            "exists": exists,
            "last_seen": hit[:120] if hit else "",
            "error": err[:120] if err else ""
        })
    ok = len([r for r in rows if r["exists"] and not r["error"]])
    missing = len([r for r in rows if not r["exists"]])
    with_error = len([r for r in rows if r["error"]])
    return {
        "total": len(rows),
        "ok": ok,
        "missing": missing,
        "error": with_error,
        "items": rows
    }

def revenue_data():
    f = BASE / ".team-memory/revenue-tracking.json"
    if not f.exists():
        return {"monthly_cost":200,"total_revenue":0,"profit_loss":-200,
                "break_even_progress":"0%","platforms":{}}
    try: return json.loads(f.read_text(encoding="utf-8"))
    except: return {}

def proposals_data():
    f = BASE / ".team-memory/proposals.md"
    if not f.exists(): return {"content":"","count":0}
    txt = f.read_text(encoding="utf-8",errors="ignore")
    count = txt.count("## 提案-")
    return {"content":txt[-3000:],"count":count}

def standup_data():
    f = BASE / ".team-memory/standup-log.md"
    if not f.exists(): return {"recent":[]}
    lines = f.read_text(encoding="utf-8",errors="ignore").strip().split("\n")
    return {"recent":lines[-30:]}

# ══════════════════════════════════════════════════════════
#  HTML — Dashboard v11 AI 無人工廠控制室
# ══════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 無人工廠 v11</title>
<style>
:root{
  --bg0:#0a1020;--bg1:#101a30;--bg2:#162340;--bg3:#1d2f54;
  --b0:#2d4576;--b1:#3d5c99;
  --t0:#e6f2ff;--t1:#a8c0e6;--t2:#7f97c4;
  --ok:#3bd58f;--ok-bg:#0f2e25;
  --wait:#5ea6ff;--wait-bg:#102746;
  --warn:#ffb657;--warn-bg:#392713;
  --err:#ff6f83;--err-bg:#3a1b23;
  --brand:#73b4ff;--brand-bg:#122949;
  --accent:#b08bff;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;overflow:hidden;background:radial-gradient(circle at 12% 8%,#1a2f54 0%,#0a1020 45%,#080d1a 100%);color:var(--t0);
  font-family:system-ui,-apple-system,'Hiragino Sans','Noto Sans TC',sans-serif;
  font-size:14px;line-height:1.5;}
body{display:flex;flex-direction:column;}
@keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.07)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
@keyframes flow{from{stroke-dashoffset:28}to{stroke-dashoffset:0}}

/* TOPBAR */
.topbar{display:flex;align-items:center;height:48px;padding:0 16px;
  background:linear-gradient(180deg,#101a30,#0e1730);border-bottom:1px solid var(--b0);flex-shrink:0;gap:10px;position:relative;overflow:hidden;}
#tb-bar{position:absolute;bottom:0;left:0;height:2px;width:100%;background:var(--brand);transition:width 1s linear;pointer-events:none;}
.logo{font-size:12px;font-weight:700;color:var(--brand);letter-spacing:.05em;white-space:nowrap;}
.logo-v{font-size:9px;color:var(--t2);font-weight:400;margin-left:3px;}
.mode-tabs{display:flex;gap:2px;flex:1;}
.mt{background:none;border:none;padding:6px 11px;font-size:11px;color:var(--t1);
  cursor:pointer;border-radius:4px;font-family:inherit;transition:all .14s;}
.mt:hover{background:var(--bg3);color:var(--t0);}
.mt.active{background:var(--brand-bg);color:var(--brand);font-weight:600;}
.tb-right{display:flex;align-items:center;gap:8px;}
.tb-ts{font-size:9px;color:var(--t2);}
.status-pill{display:flex;align-items:center;gap:5px;padding:4px 10px;
  border:1px solid var(--b0);border-radius:4px;font-size:9px;font-weight:700;letter-spacing:.06em;}
.sdot{width:6px;height:6px;border-radius:50%;}
.s-idle .sdot{background:var(--t2);}
.s-run .sdot{background:var(--ok);animation:pulse 1.2s infinite;}
.s-err .sdot{background:var(--err);animation:pulse .6s infinite;}
.s-idle .stxt{color:var(--t2);}
.s-run .stxt{color:var(--ok);}
.s-err .stxt{color:var(--err);}
.tb-btn{background:none;border:1px solid var(--b0);color:var(--t1);padding:4px 10px;
  border-radius:4px;cursor:pointer;font-size:10px;font-family:inherit;transition:all .12s;}
.tb-btn:hover{border-color:var(--brand);color:var(--brand);}

/* WORKSPACE */
.workspace{flex:1;display:grid;grid-template-columns:220px 1fr 300px;overflow:hidden;min-height:0;}

/* LEFT PANEL */
.left-panel{background:linear-gradient(180deg,#111d36,#0d162b);border-right:1px solid var(--b0);
  overflow-y:auto;padding:0;display:flex;flex-direction:column;}
.brand-box{padding:10px 14px 10px;font-size:11px;font-weight:700;color:var(--brand);
  letter-spacing:.04em;border-bottom:1px solid var(--b0);}
.stat-section{padding:10px 14px 8px;border-bottom:1px solid var(--b0);}
.stat-hd{font-size:8.5px;font-weight:700;color:var(--t2);letter-spacing:.1em;
  text-transform:uppercase;margin-bottom:6px;}
.stat-row{display:flex;justify-content:space-between;align-items:baseline;padding:2px 0;gap:4px;}
.sl{font-size:10px;color:var(--t1);white-space:nowrap;flex-shrink:0;}
.sv{font-size:10px;color:var(--t0);font-weight:500;text-align:right;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:95px;}
.sv.ok{color:var(--ok);}
.sv.warn{color:var(--warn);}
.sv.err{color:var(--err);}

/* CENTER STAGE */
.center-stage{background:radial-gradient(circle at 50% -20%,rgba(115,180,255,.15),transparent 45%),linear-gradient(180deg,#0f1830 0%,#0a1122 100%);overflow:hidden;display:flex;flex-direction:column;position:relative;}
.mode-panel{display:none;flex:1;flex-direction:column;overflow:hidden;animation:fadeIn .18s ease;}
body[data-mode="overview"]   .mode-overview{display:flex;}
body[data-mode="diagnostic"] .mode-diagnostic{display:flex;}
body[data-mode="content"]    .mode-content{display:flex;}
body[data-mode="activity"]   .mode-activity{display:flex;}
body[data-mode="control"]    .mode-control{display:flex;}

/* HERO SECTION */
.hero{flex-shrink:0;padding:16px 18px 12px;background:linear-gradient(135deg,#122b52 0%,#0f1d3d 55%,#0d1732 100%);border-bottom:2px solid var(--b0);display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;}
.hero{box-shadow:inset 0 1px 0 rgba(199,223,255,.25),0 8px 24px rgba(0,0,0,.25);}
.hero-left{display:flex;flex-direction:column;gap:6px;}
.boss-chip{display:inline-flex;align-items:center;gap:6px;font-size:10px;color:#d7e8ff;background:rgba(17,29,56,.78);border:1px solid rgba(122,169,255,.35);border-radius:999px;padding:3px 8px;width:max-content;}
.boss-hints{display:flex;gap:6px;flex-wrap:wrap;}
.bh{display:inline-flex;align-items:center;gap:5px;padding:2px 7px;border-radius:999px;font-size:9px;color:#b8cdf2;background:rgba(17,29,56,.6);border:1px solid rgba(122,169,255,.24);}
.bh strong{color:#e5f1ff;font-weight:700;}
.hero-status{display:flex;align-items:center;gap:10px;}
.hero-dot{width:10px;height:10px;border-radius:50%;background:var(--t2);flex-shrink:0;}
.hero.running .hero-dot{background:var(--ok);animation:pulse 1.2s infinite;}
.hero.error .hero-dot{background:var(--err);animation:pulse .6s infinite;}
.hero-state{font-size:20px;font-weight:800;color:var(--t0);letter-spacing:.01em;}
.hero.running .hero-state{color:var(--ok);}
.hero.error .hero-state{color:var(--err);}
.hero-topic{font-size:12px;color:#d5e7ff;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:480px;}
.hero-meta{display:flex;gap:12px;align-items:center;}
.hero-stage{font-size:11px;color:var(--brand);font-weight:600;}
.hero-ts{font-size:10px;color:var(--t2);}
.hero-next{font-size:10px;color:var(--t1);}
.hero-next{padding:2px 8px;border-radius:999px;background:rgba(255,255,255,.5);border:1px solid rgba(184,179,171,.55);}
.hero-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:4px;}
.hkpi{background:rgba(255,255,255,.55);border:1px solid var(--b0);border-radius:8px;padding:6px 8px;display:flex;flex-direction:column;gap:2px;min-width:0;}
.hkpi .k{font-size:9px;color:var(--t2);letter-spacing:.04em;}
.hkpi .v{font-size:13px;font-weight:700;color:var(--t0);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.hero-actions{display:flex;gap:8px;align-items:center;flex-shrink:0;}
.hero-run{background:var(--ok-bg);border:1px solid var(--ok);color:var(--ok);padding:7px 14px;border-radius:5px;cursor:pointer;font-size:11px;font-family:inherit;font-weight:600;transition:all .12s;}
.hero-run:hover{background:var(--ok);color:#fff;}
.hero-stop{background:var(--warn-bg);border:1px solid var(--warn);color:var(--warn);padding:7px 14px;border-radius:5px;cursor:pointer;font-size:11px;font-family:inherit;font-weight:600;transition:all .12s;}
.hero-stop:hover{background:var(--warn);color:#fff;}
.hero-diag{background:var(--brand-bg);border:1px solid var(--brand);color:var(--brand);padding:7px 12px;border-radius:5px;cursor:pointer;font-size:11px;font-family:inherit;font-weight:600;transition:all .12s;}
.hero-diag:hover{background:var(--brand);color:#fff;}

/* OFFICE STAGE */
.overview-wrap{flex:1;display:flex;flex-direction:column;min-height:0;padding:10px 14px 14px;gap:10px;}
.scene-caption{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:2px 2px 0;}
.scene-title{font-size:13px;font-weight:600;color:var(--t1);letter-spacing:.01em;}
.scene-sub{font-size:10px;color:var(--t2);}
.scene-sub{letter-spacing:.01em;}
.scene-meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;}
.scene-pill{padding:3px 7px;border:1px solid var(--b0);border-radius:999px;font-size:9.5px;color:var(--t2);background:rgba(255,255,255,.35);}
.scene-pill strong{color:var(--t1);font-weight:600;}
.office-room{flex:1;min-height:0;position:relative;border:1px solid #273252;border-radius:18px;overflow:hidden;
  background:
    linear-gradient(transparent 93%, rgba(45,73,125,.35) 100%),
    linear-gradient(90deg, transparent 93%, rgba(45,73,125,.32) 100%),
    radial-gradient(circle at 50% 28%, rgba(137,186,255,.2), transparent 45%),
    linear-gradient(180deg,#1a2540 0%,#111a30 100%);
  background-size:30px 30px,30px 30px,100% 100%,100% 100%;
  box-shadow:inset 0 1px 0 rgba(168,202,255,.25), inset 0 -20px 30px rgba(8,13,24,.38);
}
.office-room:before{content:"";position:absolute;inset:14px;border:1px solid rgba(154,187,245,.26);border-radius:14px;pointer-events:none;}
.office-room:after{content:"";position:absolute;left:50%;top:50%;width:52%;height:46%;transform:translate(-50%,-50%);border-radius:34px;
  border:1px dashed rgba(122,169,255,.35);pointer-events:none;}
.room-tag{position:absolute;padding:4px 8px;border-radius:999px;background:rgba(17,26,48,.82);border:1px solid rgba(122,169,255,.35);
  font-size:10px;color:#a6bce6;backdrop-filter:blur(4px);}
.room-tag strong{color:#d7e8ff;font-weight:700;}
.room-tag.rt-nw{top:18px;left:18px;}
.room-tag.rt-ne{top:18px;right:18px;}
.room-tag.rt-sw{bottom:18px;left:18px;}
.room-tag.rt-se{bottom:18px;right:18px;}
.office-grid{position:absolute;inset:26px;display:grid;grid-template-columns:1fr 1fr 1.18fr 1fr;grid-template-rows:1fr 1fr 1fr 1fr;
  grid-template-areas:
    "res top wri seo"
    "eng TBL TBL chi"
    "rev TBL TBL pos"
    "fdb sty kno .  ";
  gap:14px;align-items:stretch;}
.ws{position:relative;min-height:112px;padding:10px;border-radius:16px;border:1px solid rgba(84,113,168,.85);
  background:linear-gradient(180deg,rgba(30,44,77,.95),rgba(23,34,61,.95));
  box-shadow:0 8px 22px rgba(8,13,24,.28), inset 0 1px 0 rgba(168,202,255,.12);
  display:flex;flex-direction:column;cursor:pointer;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease,opacity .16s ease;}
.ws:hover{transform:translateY(-1px);border-color:#8bb5ff;box-shadow:0 10px 26px rgba(8,13,24,.34);}
.ws.selected{border-color:#9fd0ff;box-shadow:0 12px 28px rgba(80,142,255,.28), inset 0 1px 0 rgba(178,209,255,.22);}
.ws.dimmed{opacity:.48;}
.ws.working{border-color:rgba(56,212,142,.6);background:linear-gradient(180deg,rgba(17,62,53,.95),rgba(20,45,56,.94));}
.ws.waiting{border-color:rgba(122,169,255,.6);background:linear-gradient(180deg,rgba(22,49,89,.95),rgba(23,34,61,.94));}
.ws-hd{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.ws-icon{width:28px;height:28px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:14px;background:var(--bg2);color:var(--t0);box-shadow:inset 0 1px 0 rgba(255,255,255,.6);}
.ws.working .ws-icon{background:rgba(90,138,106,.14);color:var(--ok);}
.ws.waiting .ws-icon{background:rgba(122,143,168,.14);color:var(--wait);}
.ws-copy{display:flex;flex-direction:column;min-width:0;}
.ws-name{font-size:13px;font-weight:700;color:#e6f2ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ws-phase{font-size:10px;color:#8eadde;}
.ws-led{width:9px;height:9px;border-radius:50%;margin-left:auto;background:var(--b0);box-shadow:0 0 0 3px rgba(204,200,192,.22);flex-shrink:0;}
.ws.working .ws-led{background:var(--ok);box-shadow:0 0 0 4px rgba(90,138,106,.16);animation:pulse 1.4s infinite;}
.ws.waiting .ws-led{background:var(--wait);box-shadow:0 0 0 4px rgba(122,143,168,.12);}
.ws.selected .ws-led{background:var(--brand);box-shadow:0 0 0 4px rgba(74,122,138,.16);}
.ws-desk{position:relative;flex:1;min-height:54px;border-radius:12px;background:linear-gradient(180deg,#24365f,#1d2b4d);border:1px solid rgba(96,129,189,.65);
  box-shadow:inset 0 1px 0 rgba(170,202,255,.2);padding:10px 10px 8px;display:flex;align-items:flex-end;justify-content:space-between;gap:8px;}
.ws.working .ws-desk{background:linear-gradient(180deg,rgba(16,74,63,.92),rgba(22,53,62,.95));}
.ws.waiting .ws-desk{background:linear-gradient(180deg,rgba(31,70,125,.92),rgba(24,44,82,.95));}
.ws-monitor{width:26px;height:17px;border-radius:5px;background:#d6e6ff;border:1px solid rgba(96,129,189,.8);position:relative;box-shadow:0 1px 0 rgba(195,220,255,.8);}
.ws-monitor:after{content:"";position:absolute;left:50%;bottom:-5px;transform:translateX(-50%);width:10px;height:3px;border-radius:999px;background:rgba(184,179,171,.8);}
.ws-paper{flex:1;height:22px;border-radius:7px;background:rgba(214,230,255,.18);border:1px dashed rgba(122,169,255,.7);}
.ws-chair{position:absolute;left:50%;bottom:-9px;transform:translateX(-50%);width:28px;height:12px;border-radius:0 0 999px 999px;background:rgba(85,115,173,.2);border:1px solid rgba(96,129,189,.5);}
.ws-avatar{position:absolute;left:8px;top:-11px;width:22px;height:22px;border-radius:6px;background:linear-gradient(180deg,#ffdcad,#d6ae7d);border:2px solid #24365f;box-shadow:0 4px 0 #1a2745,0 0 0 1px rgba(170,202,255,.35);}
.ws-avatar:before{content:"";position:absolute;left:4px;top:6px;width:3px;height:3px;background:#2a2730;box-shadow:9px 0 0 #2a2730;}
.ws-avatar:after{content:"";position:absolute;left:5px;bottom:4px;width:10px;height:2px;background:#7a4f3f;}
.ws-meta{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:8px;}
.ws-stxt{font-size:10px;color:#aac3ea;padding:2px 7px;border-radius:999px;background:rgba(122,169,255,.14);border:1px solid rgba(122,169,255,.35);}
.ws-stxt.working{color:var(--ok);font-weight:700;background:var(--ok-bg);border-color:rgba(90,138,106,.4);}
.ws-stxt.waiting{color:var(--wait);font-weight:700;background:var(--wait-bg);border-color:rgba(122,143,168,.4);}
.ws-brief{font-size:9px;color:#9fb6de;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:72px;text-align:right;}
.ws-researcher{grid-area:res;}.ws-topic-selector{grid-area:top;}.ws-writer{grid-area:wri;}.ws-seo-agent{grid-area:seo;}
.ws-english-writer{grid-area:eng;}.ws-chinese-writer{grid-area:chi;}.ws-reviewer{grid-area:rev;}.ws-poster{grid-area:pos;}
.ws-feedback-collector{grid-area:fdb;}.ws-style-updater{grid-area:sty;}.ws-knowledge-subagent{grid-area:kno;}
.center-table{grid-area:TBL;position:relative;display:flex;align-items:center;justify-content:center;padding:18px;min-height:250px;}
.table-surface{position:relative;width:100%;height:100%;min-height:230px;border-radius:32px;background:
  radial-gradient(circle at 50% 30%, rgba(255,255,255,.85), transparent 35%),
  linear-gradient(180deg,#ddd7ce,#d4cec5);
  border:1px solid rgba(184,179,171,.85);box-shadow:0 18px 36px rgba(44,40,37,.08), inset 0 1px 0 rgba(255,255,255,.8);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:18px 24px;text-align:center;overflow:hidden;}
.table-surface:before{content:"";position:absolute;inset:16px;border-radius:24px;border:1px dashed rgba(74,122,138,.24);}
.table-surface:after{content:"";position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:62%;height:42%;border-radius:999px;background:rgba(255,255,255,.3);}
.table-chair{position:absolute;width:34px;height:14px;border-radius:999px;background:rgba(122,143,168,.18);border:1px solid rgba(184,179,171,.5);}
.table-chair.t1{top:16px;left:50%;transform:translateX(-50%);} .table-chair.t2{right:18px;top:50%;transform:translateY(-50%) rotate(90deg);} .table-chair.t3{bottom:16px;left:50%;transform:translateX(-50%);} .table-chair.t4{left:18px;top:50%;transform:translateY(-50%) rotate(90deg);} 
.table-label{position:relative;z-index:1;font-size:11px;font-weight:700;color:var(--t2);letter-spacing:.12em;text-transform:uppercase;}
.table-status{position:relative;z-index:1;font-size:22px;font-weight:800;color:var(--t0);letter-spacing:.02em;}
.table-divider{position:relative;z-index:1;width:42px;height:1px;background:var(--b0);}
.table-topic{position:relative;z-index:1;font-size:12px;color:var(--t1);width:100%;line-height:1.55;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;}
.table-note{position:relative;z-index:1;font-size:10px;color:var(--t2);}
.collab-lane{position:relative;z-index:2;display:flex;gap:8px;flex-wrap:wrap;justify-content:center;max-width:92%;}
.collab-agent{display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:10px;border:1px solid rgba(122,169,255,.45);background:rgba(17,29,56,.72);}
.collab-agent.working{border-color:rgba(56,212,142,.65);background:rgba(18,57,52,.68);}
.ca-avatar{width:16px;height:16px;border-radius:4px;background:linear-gradient(180deg,#ffd8a8,#cfa26f);position:relative;}
.ca-avatar:before{content:"";position:absolute;left:3px;top:4px;width:2px;height:2px;background:#211f27;box-shadow:7px 0 0 #211f27;}
.ca-name{font-size:9px;color:#d8e8ff;}
.ca-bubble{font-size:8px;color:#afc9f3;background:rgba(122,169,255,.15);border:1px solid rgba(122,169,255,.28);padding:2px 5px;border-radius:999px;}
.team-bar{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;flex-shrink:0;}
.tbs{padding:10px 12px;border:1px solid var(--b0);border-radius:12px;background:rgba(255,255,255,.48);font-size:11px;color:var(--t1);display:flex;flex-direction:column;gap:4px;}
.tbs{box-shadow:0 2px 8px rgba(44,40,37,.04);}
.tbs span{font-size:18px;line-height:1;font-weight:800;color:var(--t0);}
.tbs.ok span{color:var(--ok);} .tbs.wait span{color:var(--wait);} .tbs.brand span{color:var(--brand);}
/* PIPELINE STRIP */
.pipe-strip{padding:12px 16px 12px;border-top:1px solid var(--b0);flex-shrink:0;}
.pipe-strip-hd{font-size:9px;font-weight:700;color:var(--t2);letter-spacing:.1em;
  text-transform:uppercase;margin-bottom:8px;}
.pipe-row{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:5px;}
.pa{display:flex;flex-direction:column;align-items:center;padding:8px 10px;
  border:1px solid var(--b0);border-radius:6px;cursor:pointer;
  transition:all .14s;background:var(--bg1);min-width:60px;}
.pa:hover{border-color:var(--brand);background:var(--brand-bg);}
.pa.working{border-color:var(--ok);background:var(--ok-bg);}
.pa.waiting{border-color:var(--wait);background:var(--wait-bg);}
.pa.done{opacity:.55;}
.pa-icon{font-size:16px;}
.pa-name{font-size:9.5px;color:var(--t1);white-space:nowrap;font-weight:600;margin-top:3px;}
.pa-phase{font-size:8px;color:var(--t2);margin-top:1px;}
.arr{color:var(--t2);font-size:11px;align-self:center;}

/* DIAGNOSTIC */
.diag-body{flex:1;overflow-y:auto;padding:16px;display:flex;gap:20px;flex-wrap:wrap;align-content:flex-start;}
.diag-gauge-wrap{display:flex;flex-direction:column;align-items:center;gap:8px;}
.gauge-ring{width:110px;height:110px;border-radius:50%;
  background:conic-gradient(var(--ok) 0% var(--gauge-pct,0%),var(--bg2) var(--gauge-pct,0%) 100%);
  display:flex;align-items:center;justify-content:center;}
.gauge-inner{width:80px;height:80px;border-radius:50%;background:var(--bg0);
  display:flex;flex-direction:column;align-items:center;justify-content:center;}
.gauge-score{font-size:20px;font-weight:700;color:var(--t0);}
.gauge-lbl{font-size:8.5px;color:var(--t2);}
.diag-issues{flex:1;min-width:180px;}
.diag-issue{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid var(--b0);align-items:flex-start;}
.diag-tag{font-size:8px;padding:2px 5px;border-radius:3px;white-space:nowrap;
  font-weight:600;flex-shrink:0;margin-top:1px;}
.diag-tag.ok{background:var(--ok-bg);color:var(--ok);}
.diag-tag.warn{background:var(--warn-bg);color:var(--warn);}
.diag-tag.error{background:var(--err-bg);color:var(--err);}
.diag-tag.info{background:var(--brand-bg);color:var(--brand);}
.diag-it{font-size:10px;font-weight:600;color:var(--t0);}
.diag-id{font-size:9px;color:var(--t1);}

/* CONTENT */
.content-layout{flex:1;display:flex;overflow:hidden;}
.content-list{width:210px;border-right:1px solid var(--b0);overflow-y:auto;flex-shrink:0;}
.content-hd{padding:10px 12px 6px;font-size:10px;font-weight:700;color:var(--t1);}
.art-item{padding:7px 12px;cursor:pointer;border-bottom:1px solid var(--b0);transition:background .12s;}
.art-item:hover{background:var(--bg2);}
.art-item.selected{background:var(--brand-bg);border-left:2px solid var(--brand);}
.art-title{display:block;font-size:10px;color:var(--t0);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.art-w{font-size:8.5px;color:var(--t2);}
.content-preview{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.preview-hd{padding:10px 14px;font-size:11px;font-weight:600;color:var(--t0);
  border-bottom:1px solid var(--b0);flex-shrink:0;}
.preview-body{flex:1;overflow-y:auto;padding:12px 14px;font-size:10px;
  line-height:1.7;color:var(--t1);white-space:pre-wrap;font-family:system-ui,sans-serif;}
.preview-foot{padding:7px 14px;border-top:1px solid var(--b0);
  display:flex;justify-content:space-between;align-items:center;flex-shrink:0;}
.devto-btn{background:none;border:1px solid var(--b0);color:var(--t1);
  padding:4px 10px;border-radius:4px;cursor:pointer;font-size:10px;
  font-family:inherit;transition:all .12s;}
.devto-btn:not(:disabled):hover{border-color:var(--brand);color:var(--brand);}
.devto-btn:disabled{opacity:.4;cursor:default;}

/* ACTIVITY */
.activity-hd{padding:10px 16px 4px;font-size:10px;font-weight:700;color:var(--t1);flex-shrink:0;}
.log-tabs{display:flex;gap:2px;padding:4px 12px 8px;flex-shrink:0;}
.log-tab{background:none;border:1px solid var(--b0);padding:4px 10px;
  font-size:10px;color:var(--t1);cursor:pointer;border-radius:4px;
  font-family:inherit;transition:all .12s;}
.log-tab.active{background:var(--brand-bg);color:var(--brand);border-color:var(--brand);}
.log-display{flex:1;overflow-y:auto;padding:0 14px;font-size:11px;
  font-family:ui-monospace,monospace;line-height:1.7;}
.log-line{border-bottom:1px solid var(--b0);padding:1px 0;color:var(--t1);}
.log-line.ok{color:var(--ok);}
.log-line.warn{color:var(--warn);}
.log-line.err{color:var(--err);}
.log-line.info{color:var(--brand);}

/* CONTROL — 左右兩欄 */
.ctrl-wrap{flex:1;overflow:hidden;padding:14px;display:grid;grid-template-columns:1fr 1fr;gap:14px;align-content:start;}
.ctrl-section{background:var(--bg1);border:1px solid var(--b0);border-radius:6px;padding:12px 14px;}
.ctrl-section.chat-section{display:flex;flex-direction:column;height:100%;max-height:calc(100vh - 160px);}
.ctrl-hd{font-size:8.5px;font-weight:700;color:var(--t2);
  letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px;}
.ctrl-btns{display:flex;gap:8px;margin-bottom:10px;}
.ctrl-run,.ctrl-stop{padding:7px 14px;border-radius:4px;cursor:pointer;
  font-size:11px;font-family:inherit;font-weight:600;transition:all .12s;border:1px solid;}
.ctrl-run{background:var(--ok-bg);border-color:var(--ok);color:var(--ok);}
.ctrl-run:hover{background:var(--ok);color:#fff;}
.ctrl-stop{background:var(--warn-bg);border-color:var(--warn);color:var(--warn);}
.ctrl-stop:hover{background:var(--warn);color:#fff;}
.ctrl-topic{display:flex;gap:6px;}
.topic-inp{flex:1;background:var(--bg0);border:1px solid var(--b0);color:var(--t0);
  padding:5px 8px;border-radius:4px;font-size:10px;font-family:inherit;}
.topic-inp:focus{outline:none;border-color:var(--brand);}
.topic-btn{background:none;border:1px solid var(--b0);color:var(--t1);
  padding:5px 10px;border-radius:4px;cursor:pointer;font-size:10px;
  font-family:inherit;transition:all .12s;}
.topic-btn:hover{border-color:var(--brand);color:var(--brand);}
.chat-msgs{flex:1;min-height:80px;overflow-y:auto;margin-bottom:8px;
  display:flex;flex-direction:column;gap:4px;}
.cm{padding:6px 9px;border-radius:5px;font-size:10px;line-height:1.5;
  animation:fadeIn .15s ease;max-width:88%;}
.cm.user{background:var(--brand-bg);color:var(--brand);align-self:flex-end;}
.cm.ai{background:var(--bg2);color:var(--t0);align-self:flex-start;}
.chat-typing{font-size:9px;color:var(--t2);margin-bottom:4px;font-style:italic;}
.chat-row{display:flex;gap:6px;align-items:flex-end;}
.chat-in{flex:1;background:var(--bg0);border:1px solid var(--b0);color:var(--t0);
  padding:5px 8px;border-radius:4px;font-size:10px;font-family:inherit;resize:none;}
.chat-in:focus{outline:none;border-color:var(--brand);}
.chat-btn{background:var(--brand-bg);border:1px solid var(--brand);color:var(--brand);
  padding:5px 11px;border-radius:4px;cursor:pointer;font-size:10px;
  font-family:inherit;transition:all .12s;white-space:nowrap;}
.chat-btn:hover:not(:disabled){background:var(--brand);color:#fff;}
.chat-btn:disabled{opacity:.4;cursor:default;}
.set-row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--b0);}
.set-key{font-size:10px;color:var(--t1);}
.set-val{font-size:10px;color:var(--t0);font-weight:500;}
.set-val.ok{color:var(--ok);}
.set-val.warn{color:var(--warn);}

/* RIGHT PANEL */
.right-panel{background:linear-gradient(180deg,#111d36,#0d162b);border-left:1px solid var(--b0);
  overflow:hidden;display:flex;flex-direction:column;}
.rp-hd{padding:10px 12px 6px;font-size:8.5px;font-weight:700;color:var(--t2);
  letter-spacing:.1em;text-transform:uppercase;border-bottom:1px solid var(--b0);flex-shrink:0;}
#right-feed{flex:1;overflow-y:auto;}
.feed-item{padding:7px 12px;border-bottom:1px solid var(--b0);animation:fadeIn .2s ease;}
.fi-top{display:flex;align-items:baseline;gap:5px;}
.fi-icon{font-size:11px;}
.fi-agent{font-size:8.5px;color:var(--t2);}
.fi-time{font-size:8px;color:var(--t2);margin-left:auto;}
.fi-msg{font-size:9.5px;color:var(--t1);margin-top:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.fi-msg.ok{color:var(--ok);}
.fi-msg.warn{color:var(--warn);}
.fi-msg.error{color:var(--err);}

/* AGENT DETAIL */
#agent-detail{flex:1;overflow-y:auto;display:none;flex-direction:column;}
.ad-head{display:flex;align-items:center;gap:10px;padding:12px;
  border-bottom:1px solid var(--b0);}
.ad-icon{font-size:20px;width:36px;height:36px;background:var(--brand-bg);
  border-radius:50%;display:flex;align-items:center;justify-content:center;}
.ad-name{font-size:12px;font-weight:700;color:var(--t0);}
.ad-badges{display:flex;gap:4px;margin-top:3px;}
.badge{font-size:8px;padding:2px 5px;border-radius:3px;font-weight:600;}
.b-ok{background:var(--ok-bg);color:var(--ok);}
.b-warn{background:var(--warn-bg);color:var(--warn);}
.b-brand{background:var(--brand-bg);color:var(--brand);}
.b-accent{background:#f0edf5;color:var(--accent);}
.ad-desc{padding:8px 12px;font-size:9.5px;color:var(--t1);
  border-bottom:1px solid var(--b0);line-height:1.5;}
.ad-sec{padding:7px 12px;border-bottom:1px solid var(--b0);}
.ad-sl{font-size:8px;font-weight:700;color:var(--t2);letter-spacing:.06em;
  text-transform:uppercase;margin-bottom:5px;}
.file-item{display:flex;align-items:center;gap:5px;padding:2px 0;}
.file-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0;}
.file-dot.ok{background:var(--ok);}
.file-dot.miss{background:var(--b0);}
.file-path{font-size:9px;color:var(--t1);font-family:ui-monospace,monospace;}
.file-age{font-size:8px;color:var(--t2);margin-left:auto;}
.pills{display:flex;flex-wrap:wrap;gap:3px;}
.pill{font-size:8px;padding:2px 5px;border-radius:3px;font-weight:500;}
.sk{background:var(--ok-bg);color:var(--ok);}
.sk-x{background:var(--bg2);color:var(--t2);}
.hk{background:var(--ok-bg);color:var(--ok);}
.hk-x{background:var(--err-bg);color:var(--err);}
.back-btn{margin:8px 12px 4px;background:none;border:1px solid var(--b0);color:var(--t1);
  padding:5px 10px;border-radius:4px;cursor:pointer;font-size:10px;
  font-family:inherit;transition:all .12s;flex-shrink:0;}
.back-btn:hover{border-color:var(--brand);color:var(--brand);}
#ad-inner{flex:1;overflow-y:auto;}
.ad-chat{padding:10px 12px;border-top:1px solid var(--b0);display:flex;flex-direction:column;gap:6px;background:rgba(17,29,56,.15);}
.ad-chat-log{max-height:160px;overflow-y:auto;display:flex;flex-direction:column;gap:4px;}
.ad-bubble{font-size:9px;line-height:1.45;padding:5px 7px;border-radius:6px;max-width:92%;}
.ad-bubble.user{align-self:flex-end;background:var(--brand-bg);color:var(--brand);}
.ad-bubble.agent{align-self:flex-start;background:var(--bg2);color:var(--t0);}
.ad-chat-row{display:flex;gap:5px;}
.ad-chat-in{flex:1;border:1px solid var(--b0);border-radius:4px;padding:4px 6px;font-size:9px;background:var(--bg0);color:var(--t0);}
.ad-chat-btn{border:1px solid var(--brand);background:var(--brand-bg);color:var(--brand);border-radius:4px;padding:4px 8px;font-size:9px;cursor:pointer;}

/* ALERT */
.alert-ov{position:fixed;inset:0;background:rgba(44,40,37,.4);
  display:none;align-items:center;justify-content:center;z-index:200;}
.alert-ov.show{display:flex;}
.alert-box{background:var(--bg1);border:1px solid var(--b0);border-radius:8px;
  padding:20px;max-width:360px;width:90%;animation:fadeIn .18s ease;}
.alert-box.warn-type{border-color:var(--warn);}
.alert-lv{font-size:8.5px;font-weight:700;letter-spacing:.1em;color:var(--t2);margin-bottom:4px;}
.alert-title{font-size:13px;font-weight:700;color:var(--t0);margin-bottom:6px;}
.alert-desc{font-size:10px;color:var(--t1);margin-bottom:14px;line-height:1.5;}
.alert-close{background:var(--bg2);border:1px solid var(--b0);color:var(--t1);
  padding:5px 14px;border-radius:4px;cursor:pointer;font-size:10px;font-family:inherit;}

::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--b0);border-radius:2px;}
</style>
</head>

<body data-mode="overview">

<!-- TOPBAR -->
<nav class="topbar">
  <div class="logo">AI 無人工廠<span class="logo-v">v11</span></div>
  <div class="mode-tabs">
    <button class="mt active" data-mode="overview" onclick="setMode('overview',this)">總覽</button>
    <button class="mt" data-mode="diagnostic" onclick="setMode('diagnostic',this)">診斷</button>
    <button class="mt" data-mode="content" onclick="setMode('content',this)">內容</button>
    <button class="mt" data-mode="activity" onclick="setMode('activity',this)">活動</button>
    <button class="mt" data-mode="control" onclick="setMode('control',this)">控制</button>
  </div>
  <div class="tb-right">
    <div id="spill" class="status-pill s-idle">
      <span class="sdot"></span>
      <span class="stxt" id="stxt">待命</span>
    </div>
    <span class="tb-ts" id="ts">--</span>
  </div>
  <div id="tb-bar"></div>
</nav>

<!-- WORKSPACE -->
<div class="workspace">

  <!-- LEFT PANEL -->
  <aside class="left-panel">
    <div class="brand-box">AI 無人工廠</div>

    <div class="stat-section">
      <div class="stat-hd">今日狀態</div>
      <div class="stat-row"><span class="sl">活躍 Agent</span><span class="sv" id="k1">— / 11</span></div>
      <div class="stat-row"><span class="sl">今日產出</span><span class="sv" id="k0">0 篇</span></div>
      <div class="stat-row"><span class="sl">系統健康</span><span class="sv" id="k4">—</span></div>
    </div>

    <div class="stat-section">
      <div class="stat-hd">任務流程</div>
      <div class="stat-row"><span class="sl">當前階段</span><span class="sv" id="k-stage">—</span></div>
      <div class="stat-row"><span class="sl">API 今日</span><span class="sv" id="k2">0 次</span></div>
      <div class="stat-row"><span class="sl">API 總計</span><span class="sv" id="k3">0</span></div>
    </div>

    <div class="stat-section">
      <div class="stat-hd">收益摘要</div>
      <div class="stat-row"><span class="sl">本月收益</span><span class="sv" id="k5">$0</span></div>
      <div class="stat-row"><span class="sl">距損益平衡</span><span class="sv" id="k6">−$200</span></div>
    </div>

    <div class="stat-section">
      <div class="stat-hd">外部模組</div>
      <div class="stat-row"><span class="sl">Claude API</span><span class="sv" id="m-api">—</span></div>
      <div class="stat-row"><span class="sl">排程器</span><span class="sv" id="m-cron">—</span></div>
      <div class="stat-row"><span class="sl">Whop</span><span class="sv" id="m-whop">—</span></div>
      <div class="stat-row"><span class="sl">模型</span><span class="sv" id="k7">—</span></div>
    </div>

    <div class="stat-section">
      <div class="stat-hd">CD Hook 狀態</div>
      <div class="stat-row"><span class="sl">Hook 作用</span><span class="sv">語氣/品質過濾</span></div>
      <div class="stat-row"><span class="sl">可用 Hook</span><span class="sv" id="h0">—</span></div>
      <div class="stat-row"><span class="sl">缺失 Hook</span><span class="sv" id="h1">—</span></div>
      <div class="stat-row"><span class="sl">最近錯誤</span><span class="sv" id="h2">—</span></div>
    </div>
  </aside>

  <!-- CENTER STAGE -->
  <main class="center-stage">

    <!-- OVERVIEW -->
    <div class="mode-panel mode-overview">
      <!-- HERO -->
      <div class="hero" id="hero-bar">
        <div class="hero-left">
          <div class="boss-chip">👑 Boss Console｜你下達絕對指令，團隊自主管理執行</div>
          <div class="boss-hints">
            <span class="bh">目前焦點：<strong id="boss-focus">秘書</strong></span>
            <span class="bh">團隊負載：<strong id="boss-load">2 活躍</strong></span>
            <span class="bh">操作提示：點選 Agent 可直接對話</span>
          </div>
          <div class="hero-status">
            <span class="hero-dot"></span>
            <span class="hero-state" id="hero-state">待命中</span>
          </div>
          <div class="hero-topic" id="hero-topic">尚未開始任務</div>
          <div class="hero-meta">
            <span class="hero-stage" id="hero-stage">—</span>
            <span class="hero-ts" id="hero-ts">—</span>
            <span class="hero-next" id="hero-next">下一步：等待手動觸發</span>
          </div>
          <div class="hero-kpis">
            <div class="hkpi"><span class="k">今日產出</span><span class="v" id="hk0">0 篇</span></div>
            <div class="hkpi"><span class="k">活躍 Agent</span><span class="v" id="hk1">0 / 11</span></div>
            <div class="hkpi"><span class="k">API 今日</span><span class="v" id="hk2">0 次</span></div>
            <div class="hkpi"><span class="k">本月收益</span><span class="v" id="hk5">$0</span></div>
          </div>
        </div>
        <div class="hero-actions">
          <button class="hero-run" onclick="triggerRun()">▶ 立即執行</button>
          <button class="hero-diag" onclick="setMode('diagnostic',null)">🩺 查看診斷</button>
          <button class="hero-stop" onclick="triggerStop()">⏹ 停止</button>
        </div>
      </div>
      <div class="overview-wrap">
        <div class="scene-caption">
          <div>
            <div class="scene-title">AI 團隊工作空間</div>
            <div class="scene-sub">扁平化團隊：秘書/經理為內部 GameMaster，其他 Agent 平行協作</div>
          </div>
          <div class="scene-meta">
            <div class="scene-pill">選中 <strong id="overview-selected">無</strong></div>
            <div class="scene-pill">工作中 <strong id="overview-topic-chip">0</strong></div>
          </div>
        </div>
        <div class="office-room">
          <div class="room-tag rt-nw"><strong>探索區</strong> 探索與協調</div>
          <div class="room-tag rt-ne"><strong>生產區</strong> 內容與 SEO</div>
          <div class="room-tag rt-sw"><strong>回饋區</strong> 審稿與觀測</div>
          <div class="room-tag rt-se"><strong>知識區</strong> 發布與演化</div>
          <div class="office-grid">
            <div class="ws ws-researcher" id="ws-researcher" onclick="selectAgent('researcher')">
              <div class="ws-hd"><span class="ws-icon">◎</span><div class="ws-copy"><span class="ws-name">秘書</span><span class="ws-phase">協調</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-researcher">休息中</span><span class="ws-brief">需求翻譯</span></div>
            </div>
            <div class="ws ws-topic-selector" id="ws-topic-selector" onclick="selectAgent('topic-selector')">
              <div class="ws-hd"><span class="ws-icon">◈</span><div class="ws-copy"><span class="ws-name">經理</span><span class="ws-phase">統籌</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-topic-selector">休息中</span><span class="ws-brief">技術統籌</span></div>
            </div>
            <div class="ws ws-writer" id="ws-writer" onclick="selectAgent('writer')">
              <div class="ws-hd"><span class="ws-icon">✦</span><div class="ws-copy"><span class="ws-name">中文初稿</span><span class="ws-phase">生產</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-writer">休息中</span><span class="ws-brief">內容寫作</span></div>
            </div>
            <div class="ws ws-seo-agent" id="ws-seo-agent" onclick="selectAgent('seo-agent')">
              <div class="ws-hd"><span class="ws-icon">S</span><div class="ws-copy"><span class="ws-name">SEO</span><span class="ws-phase">生產</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-seo-agent">休息中</span><span class="ws-brief">關鍵字優化</span></div>
            </div>
            <div class="ws ws-english-writer" id="ws-english-writer" onclick="selectAgent('english-writer')">
              <div class="ws-hd"><span class="ws-icon">E</span><div class="ws-copy"><span class="ws-name">英文寫手</span><span class="ws-phase">生產</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-english-writer">休息中</span><span class="ws-brief">雙語輸出</span></div>
            </div>
            <div class="center-table">
              <div class="table-surface">
                <span class="table-chair t1"></span><span class="table-chair t2"></span><span class="table-chair t3"></span><span class="table-chair t4"></span>
                <div class="table-label">AI Factory Core</div>
                <div class="table-status" id="table-status">待命中</div>
                <div class="table-divider"></div>
                <div class="table-topic" id="table-topic">等待任務</div>
                <div id="collab-lane" class="collab-lane"></div>
                <div class="table-note">中央協作桌會同步顯示本輪主題與整體狀態</div>
              </div>
            </div>
            <div class="ws ws-chinese-writer" id="ws-chinese-writer" onclick="selectAgent('chinese-writer')">
              <div class="ws-hd"><span class="ws-icon">中</span><div class="ws-copy"><span class="ws-name">中文詮釋</span><span class="ws-phase">生產</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-chinese-writer">休息中</span><span class="ws-brief">台灣語境</span></div>
            </div>
            <div class="ws ws-reviewer" id="ws-reviewer" onclick="selectAgent('reviewer')">
              <div class="ws-hd"><span class="ws-icon">◉</span><div class="ws-copy"><span class="ws-name">審稿</span><span class="ws-phase">品管</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-reviewer">休息中</span><span class="ws-brief">品質檢查</span></div>
            </div>
            <div class="ws ws-poster" id="ws-poster" onclick="selectAgent('poster')">
              <div class="ws-hd"><span class="ws-icon">◆</span><div class="ws-copy"><span class="ws-name">發文</span><span class="ws-phase">發布</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-poster">休息中</span><span class="ws-brief">上架平台</span></div>
            </div>
            <div class="ws ws-feedback-collector" id="ws-feedback-collector" onclick="selectAgent('feedback-collector')">
              <div class="ws-hd"><span class="ws-icon">F</span><div class="ws-copy"><span class="ws-name">回報收集</span><span class="ws-phase">回饋</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-feedback-collector">休息中</span><span class="ws-brief">表現追蹤</span></div>
            </div>
            <div class="ws ws-style-updater" id="ws-style-updater" onclick="selectAgent('style-updater')">
              <div class="ws-hd"><span class="ws-icon">↺</span><div class="ws-copy"><span class="ws-name">風格進化</span><span class="ws-phase">進化</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-style-updater">休息中</span><span class="ws-brief">策略調整</span></div>
            </div>
            <div class="ws ws-knowledge-subagent" id="ws-knowledge-subagent" onclick="selectAgent('knowledge-subagent')">
              <div class="ws-hd"><span class="ws-icon">K</span><div class="ws-copy"><span class="ws-name">知識庫</span><span class="ws-phase">進化</span></div><span class="ws-led"></span></div>
              <div class="ws-desk"><span class="ws-avatar"></span><span class="ws-monitor"></span><span class="ws-paper"></span><span class="ws-chair"></span></div>
              <div class="ws-meta"><span class="ws-stxt idle" id="wst-knowledge-subagent">休息中</span><span class="ws-brief">資料沉澱</span></div>
            </div>
          </div>
        </div>
        <div class="team-bar">
          <div class="tbs ok" id="tb-working">工作中 <span>0</span></div>
          <div class="tbs wait" id="tb-waiting">等待中 <span>0</span></div>
          <div class="tbs" id="tb-idle">休息中 <span>11</span></div>
          <div class="tbs brand">已選取 <span id="tb-selected">無</span></div>
        </div>
      </div>
    </div>

    <!-- DIAGNOSTIC -->
    <div class="mode-panel mode-diagnostic">
      <div class="diag-body">
        <div class="diag-gauge-wrap">
          <div class="gauge-ring" id="gauge-ring">
            <div class="gauge-inner">
              <div class="gauge-score" id="gauge-score">—</div>
              <div class="gauge-lbl">系統健康</div>
            </div>
          </div>
        </div>
        <div class="diag-issues" id="diag-issues"></div>
      </div>
    </div>

    <!-- CONTENT -->
    <div class="mode-panel mode-content">
      <div class="content-layout">
        <div class="content-list">
          <div class="content-hd">內容檔案 <span id="arts-count" style="color:var(--t2)"></span></div>
          <div id="arts-list"></div>
        </div>
        <div class="content-preview">
          <div class="preview-hd" id="preview-hd">選擇文章預覽</div>
          <div id="preview-body" class="preview-body">—</div>
          <div class="preview-foot">
            <span id="preview-words" style="font-size:9px;color:var(--t2)"></span>
            <button id="devto-btn" class="devto-btn" onclick="postToDevto()" disabled>→ dev.to 草稿</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ACTIVITY -->
    <div class="mode-panel mode-activity">
      <div class="activity-hd">系統動態</div>
      <div class="pipe-strip">
        <div class="pipe-strip-hd">任務流程</div>
        <div class="pipe-row" id="pipe-row1"></div>
        <div class="pipe-row" id="pipe-row2"></div>
      </div>
      <div class="log-tabs">
        <button class="log-tab active" onclick="switchLog('cron',this)">執行日誌</button>
        <button class="log-tab" onclick="switchLog('error',this)">錯誤日誌</button>
        <button class="log-tab" onclick="switchLog('standup',this)">Standup</button>
      </div>
      <div id="log-display" class="log-display"></div>
    </div>

    <!-- CONTROL -->
    <div class="mode-panel mode-control">
      <div class="ctrl-wrap">
        <!-- 左欄：系統控制 -->
        <div style="display:flex;flex-direction:column;gap:14px;">
          <div class="ctrl-section">
            <div class="ctrl-hd">強制主題</div>
            <div class="ctrl-topic">
              <input id="topic-input" class="topic-inp" placeholder="輸入主題後套用…"/>
              <button class="topic-btn" onclick="triggerTopic()">套用</button>
            </div>
          </div>
          <div class="ctrl-section">
            <div class="ctrl-hd">系統設定狀態</div>
            <div id="ctrl-settings"></div>
          </div>
        </div>
        <!-- 右欄：聊天對話 -->
        <div class="ctrl-section chat-section">
          <div class="ctrl-hd">控制對話</div>
          <div id="chat-msgs" class="chat-msgs"></div>
          <div id="chat-typing" class="chat-typing" style="display:none">AI 思考中...</div>
          <div class="chat-row">
            <textarea id="chat-in" class="chat-in" rows="2" placeholder="輸入指令..." onkeydown="chatKey(event)"></textarea>
            <button id="chat-btn" class="chat-btn" onclick="sendChat()">送出</button>
          </div>
        </div>
      </div>
    </div>

  </main>

  <!-- RIGHT PANEL -->
  <aside id="right-panel" class="right-panel">
    <div id="right-feed">
      <div class="rp-hd">系統動態</div>
      <div id="feed-items"></div>
    </div>
    <div id="agent-detail">
      <button class="back-btn" onclick="deselectAgent()">← 返回動態</button>
      <div id="ad-inner"></div>
    </div>
  </aside>

</div>

<!-- ALERT OVERLAY -->
<div id="alert-ov" class="alert-ov" onclick="closeAlert()">
  <div id="alert-box" class="alert-box">
    <div class="alert-lv" id="alert-level">INFO</div>
    <div class="alert-title" id="alert-title"></div>
    <div class="alert-desc" id="alert-desc"></div>
    <button class="alert-close" onclick="event.stopPropagation();closeAlert()">關閉</button>
  </div>
</div>

<script>
let countdown=5,timer=null,lastData=null,devtoName='';
let selectedAgentId=null,currentLogTab='cron';
let fetchFailCount=0,lastFetchErr='';
const agentChatHistories={};

const FM=[
  {id:'researcher',icon:'◎',label:'秘書',phase:'協調'},
  {id:'topic-selector',icon:'◈',label:'經理',phase:'統籌'},
  {id:'writer',icon:'✦',label:'中文初稿',phase:'生產'},
  {id:'seo-agent',icon:'S',label:'SEO',phase:'生產'},
  {id:'english-writer',icon:'E',label:'英文寫手',phase:'生產'},
  {id:'chinese-writer',icon:'中',label:'中文詮釋',phase:'生產'},
  {id:'reviewer',icon:'◉',label:'審稿',phase:'品管'},
  {id:'poster',icon:'◆',label:'發文',phase:'發布'},
  {id:'feedback-collector',icon:'F',label:'回報收集',phase:'回饋'},
  {id:'style-updater',icon:'↺',label:'風格進化',phase:'進化'},
  {id:'knowledge-subagent',icon:'K',label:'知識庫',phase:'進化'},
];

function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function utcStamp(){
  return new Date().toISOString().slice(0,16).replace('T',' ')+' UTC';
}

/* MODE SWITCHING */
function setMode(mode,btn){
  document.body.dataset.mode=mode;
  document.querySelectorAll('.mt').forEach(t=>t.classList.remove('active'));
  if(btn)btn.classList.add('active');
  else{const b=document.querySelector('.mt[data-mode="'+mode+'"]');if(b)b.classList.add('active');}
  if(mode!=='overview'&&selectedAgentId)deselectAgent();
}

/* OFFICE WORKSTATIONS */
let _lastShownError='';
function updateWorkstations(data){
  const st={};(data.flow||[]).forEach(a=>{st[a.id]=a;});
  const hasSel=!!selectedAgentId;
  let wk=0,wt=0,id=0;
  const collabAgents=[];
  FM.forEach(a=>{
    const s=(st[a.id]||{}).status||'idle';
    if(s==='working')wk++;else if(s==='waiting')wt++;else id++;
    if(s==='working'||s==='waiting')collabAgents.push({id:a.id,label:a.label,status:s});
    const el=document.getElementById('ws-'+a.id);
    if(!el)return;
    let cls='ws ws-'+a.id+' '+s;
    if(selectedAgentId===a.id)cls+=' selected';
    else if(hasSel)cls+=' dimmed';
    el.className=cls;
    const stxt=document.getElementById('wst-'+a.id);
    if(stxt){
      const sm=s==='working'?'🟢 工作中':s==='waiting'?'🔵 等待中':'⚪ 休息中';
      stxt.textContent=sm;stxt.className='ws-stxt '+s;
    }
  });
  const state=data.state||'idle';
  const ts=document.getElementById('table-status');
  const stateText=state==='running'?'執行中':state==='error'?'異常':'待命中';
  if(ts)ts.textContent=stateText;
  const pipe=data.pipeline||{};
  const topicText=(pipe.article&&pipe.article.title)?pipe.article.title:'等待任務';
  const tt=document.getElementById('table-topic');
  if(tt)tt.textContent=topicText;
  const lane=document.getElementById('collab-lane');
  if(lane){
    lane.innerHTML=collabAgents.slice(0,5).map((a,idx)=>
      '<div class="collab-agent '+a.status+'">'+
      '<span class="ca-avatar"></span>'+
      '<span class="ca-name">'+esc(a.label)+'</span>'+
      '<span class="ca-bubble">'+(a.status==='working'?'討論中':'待交接')+(idx===0?' · 主講':'')+'</span>'+
      '</div>'
    ).join('') || '<div class="collab-agent"><span class="ca-avatar"></span><span class="ca-name">團隊待命</span><span class="ca-bubble">等待下一輪任務</span></div>';
  }
  const selectedLabel = selectedAgentId ? ((FM.find(a=>a.id===selectedAgentId)||{}).label||selectedAgentId) : '無';
  const selectedEl=document.getElementById('overview-selected'); if(selectedEl) selectedEl.textContent=selectedLabel;
  const tbSel=document.getElementById('tb-selected'); if(tbSel) tbSel.textContent=selectedLabel;
  const tw=document.getElementById('tb-working');if(tw){const sp=tw.querySelector('span');if(sp)sp.textContent=wk;}
  const twa=document.getElementById('tb-waiting');if(twa){const sp=twa.querySelector('span');if(sp)sp.textContent=wt;}
  const ti=document.getElementById('tb-idle');if(ti){const sp=ti.querySelector('span');if(sp)sp.textContent=id;}
}

/* PIPELINE */
function renderPipeline(data){
  const st={};(data.flow||[]).forEach(a=>{st[a.id]=a;});
  [FM.slice(0,6),FM.slice(6)].forEach((agents,ri)=>{
    const el=document.getElementById('pipe-row'+(ri+1));if(!el)return;
    el.innerHTML=agents.map((a,i)=>{
      const s=(st[a.id]||{}).status||'idle';
      return '<div class="pa '+s+'" onclick="selectAgent(\''+a.id+'\')">'+
        '<span class="pa-icon">'+a.icon+'</span>'+
        '<span class="pa-name">'+a.label+'</span>'+
        '<span class="pa-phase">'+a.phase+'</span>'+
        '</div>'+(i<agents.length-1?'<span class="arr">→</span>':'');
    }).join('');
  });
}

/* SELECT AGENT */
function selectAgent(id){
  selectedAgentId=id;
  document.getElementById('right-feed').style.display='none';
  const ad=document.getElementById('agent-detail');
  ad.style.display='flex';ad.style.flexDirection='column';
  if(!lastData)return;
  const aInfo=(lastData.flow||[]).find(a=>a.id===id);
  if(!aInfo){document.getElementById('ad-inner').innerHTML='<div style="padding:16px;color:var(--t2)">無資料</div>';return;}
  const s=aInfo.status||'idle';
  const sc={working:'b-ok',waiting:'b-warn',idle:'b-brand'};
  const stxt=s==='working'?'工作中':s==='waiting'?'等待中':'休息中';
  const ri=(aInfo.reads_stat||[]).map(r=>{
    const ok=r.stat&&r.stat.ok;
    const age=ok&&r.stat.age!=null?'<span class="file-age">'+r.stat.age+'分前</span>':'';
    return '<div class="file-item"><span class="file-dot '+(ok?'ok':'miss')+'"></span><span class="file-path">'+esc(r.path)+'</span>'+age+'</div>';
  }).join('');
  const wi=(aInfo.writes_stat||[]).map(r=>{
    const ok=r.stat&&r.stat.ok;
    return '<div class="file-item"><span class="file-dot '+(ok?'ok':'miss')+'"></span><span class="file-path">'+esc(r.path)+'</span></div>';
  }).join('');
  const sp=(aInfo.skills_avail||[]).map(s=>'<span class="pill '+(s.ok?'sk':'sk-x')+'">'+esc(s.name)+'</span>').join('');
  const hp=(aInfo.hooks_avail||[]).map(h=>'<span class="pill '+(h.ok?'hk':'hk-x')+'">'+esc(h.name)+'</span>').join('');
  document.getElementById('ad-inner').innerHTML=
    '<div class="ad-head"><div class="ad-icon">'+aInfo.icon+'</div>'+
    '<div><div class="ad-name">'+esc(aInfo.label)+'</div>'+
    '<div class="ad-badges"><span class="badge '+(sc[s]||'b-brand')+'">'+stxt+'</span>'+
    '<span class="badge b-accent">'+esc(aInfo.phase)+'</span></div></div></div>'+
    '<div class="ad-desc">'+esc(aInfo.desc||'')+'</div>'+
    (ri?'<div class="ad-sec"><div class="ad-sl">讀取</div>'+ri+'</div>':'')+
    (wi?'<div class="ad-sec"><div class="ad-sl">寫入</div>'+wi+'</div>':'')+
    (sp?'<div class="ad-sec"><div class="ad-sl">Skills</div><div class="pills">'+sp+'</div></div>':'')+
    (hp?'<div class="ad-sec"><div class="ad-sl">Hooks</div><div class="pills">'+hp+'</div></div>':'')+
    '<div class="ad-chat">'+
      '<div class="ad-sl">與 Agent 對話（GameMaster）</div>'+
      '<div id="agent-chat-log" class="ad-chat-log"></div>'+
      '<div class="ad-chat-row">'+
        '<input id="agent-chat-in" class="ad-chat-in" placeholder="輸入要給 '+esc(aInfo.label)+' 的指令..." onkeydown="if(event.key===\\'Enter\\'){event.preventDefault();sendAgentChat();}"/>'+
        '<button class="ad-chat-btn" onclick="sendAgentChat()">送出</button>'+
      '</div>'+
    '</div>';
  renderAgentChat(id);
  if(lastData)updateWorkstations(lastData);
}

function deselectAgent(){
  selectedAgentId=null;
  document.getElementById('agent-detail').style.display='none';
  document.getElementById('right-feed').style.display='block';
  if(lastData)updateWorkstations(lastData);
}

function renderAgentChat(agentId){
  const log=document.getElementById('agent-chat-log');
  if(!log)return;
  const hist=agentChatHistories[agentId]||[];
  log.innerHTML=hist.map(m=>'<div class="ad-bubble '+m.role+'">'+esc(m.text)+'</div>').join('')||
    '<div class="ad-bubble agent">尚未對話。你可以直接下達指令給此 Agent。</div>';
  log.scrollTop=log.scrollHeight;
}

async function sendAgentChat(){
  if(!selectedAgentId)return;
  const input=document.getElementById('agent-chat-in');
  if(!input)return;
  const msg=input.value.trim();
  if(!msg)return;
  input.value='';
  const agent=(FM.find(a=>a.id===selectedAgentId)||{label:selectedAgentId}).label;
  agentChatHistories[selectedAgentId]=agentChatHistories[selectedAgentId]||[];
  agentChatHistories[selectedAgentId].push({role:'user',text:msg});
  renderAgentChat(selectedAgentId);
  try{
    const prompt='你現在扮演「'+agent+'」Agent，請用團隊內部回報格式，簡短回覆：'+msg;
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:prompt})});
    const d=await r.json();
    agentChatHistories[selectedAgentId].push({role:'agent',text:d.reply||'（無回應）'});
  }catch(e){
    agentChatHistories[selectedAgentId].push({role:'agent',text:'❌ 無法連線到 Agent 對話服務'});
  }
  renderAgentChat(selectedAgentId);
}

/* KPI + LEFT PANEL */
function renderKPI(data){
  const prog=data.pipeline||{},usage=data.usage||{};
  const q=(id)=>document.getElementById(id);
  if(q('k0'))q('k0').textContent=(prog.count||0)+' 篇';
  if(q('hk0'))q('hk0').textContent=(prog.count||0)+' 篇';
  if(q('k2'))q('k2').textContent=(usage.today||0)+' 次';
  if(q('hk2'))q('hk2').textContent=(usage.today||0)+' 次';
  if(q('k3'))q('k3').textContent=usage.total||0;
  const sc=(data.diag||{}).score||0;
  const k4=q('k4');
  if(k4){k4.className='sv '+(sc>=80?'ok':sc>=50?'warn':'err');k4.textContent=sc+'%';}
  const flow=data.flow||[];
  const active=flow.filter(a=>a.status==='working'||a.status==='waiting').length;
  if(q('k1'))q('k1').textContent=active+' / 11';
  if(q('hk1'))q('hk1').textContent=active+' / 11';
  if(q('boss-load'))q('boss-load').textContent=active+' 活躍';
  const working=flow.find(a=>a.status==='working');
  if(q('k-stage'))q('k-stage').textContent=working?working.label:'—';
  if(q('boss-focus'))q('boss-focus').textContent=working?working.label:'經理';
  if(q('k7'))q('k7').textContent=((data.api||{}).model||'—').slice(0,14);
  const cronCnt=data.cron_count||0;
  const mapi=q('m-api');if(mapi){mapi.textContent=(data.api&&data.api.model)?'✓ 正常':'⚠ 未知';mapi.className='sv '+((data.api&&data.api.model)?'ok':'warn');}
  const mcron=q('m-cron');if(mcron){mcron.textContent=cronCnt>0?'✓ '+cronCnt+' 個':'⚠ 未設定';mcron.className='sv '+(cronCnt>0?'ok':'warn');}
  const mw=q('m-whop');if(mw){mw.textContent=data.has_placeholder?'待設定':'✓ 已設定';mw.className='sv '+(data.has_placeholder?'':'ok');}
  const hooks=data.hooks||{};
  const h0=q('h0');if(h0){h0.textContent=(hooks.ok||0)+' / '+(hooks.total||0);h0.className='sv '+((hooks.missing||0)===0?'ok':'warn');}
  const h1=q('h1');if(h1){h1.textContent=String(hooks.missing||0);h1.className='sv '+((hooks.missing||0)>0?'warn':'ok');}
  const h2=q('h2');if(h2){h2.textContent=String(hooks.error||0);h2.className='sv '+((hooks.error||0)>0?'err':'ok');}
  // diagnostic gauge
  const gs=q('gauge-score');if(gs)gs.textContent=sc+'%';
  const gr=q('gauge-ring');if(gr)gr.style.setProperty('--gauge-pct',Math.max(0,Math.min(100,sc))+'%');
  renderDiagIssues(data.diag||{});
  renderCtrlSettings(data);
}

function renderDiagIssues(diag){
  const el=document.getElementById('diag-issues');if(!el)return;
  el.innerHTML=(diag.issues||[]).map(iss=>
    '<div class="diag-issue">'+
    '<span class="diag-tag '+esc(iss.level)+'">'+esc(iss.tag||iss.level)+'</span>'+
    '<div><div class="diag-it">'+esc(iss.title)+'</div>'+
    '<div class="diag-id">'+esc(iss.desc||'')+'</div></div></div>'
  ).join('');
}

function renderCtrlSettings(data){
  const el=document.getElementById('ctrl-settings');if(!el)return;
  const tok=(data.api&&data.api.model)?'已設定':'未設定';
  const tc=(data.api&&data.api.model)?'ok':'warn';
  const wp=data.has_placeholder?'待設定':'已設定';
  const wc=data.has_placeholder?'warn':'ok';
  el.innerHTML=
    '<div class="set-row"><span class="set-key">ANTHROPIC_AUTH_TOKEN</span><span class="set-val '+tc+'">'+tok+'</span></div>'+
    '<div class="set-row"><span class="set-key">Whop 連結</span><span class="set-val '+wc+'">'+wp+'</span></div>'+
    '<div class="set-row"><span class="set-key">模型</span><span class="set-val">'+esc((data.api||{}).model||'—')+'</span></div>'+
    '<div class="set-row"><span class="set-key">排程器</span><span class="set-val '+(data.cron_count>0?'ok':'warn')+'">'+(data.cron_count||0)+' 個</span></div>';
}

/* STATUS */
function renderStatus(data){
  const pill=document.getElementById('spill'),stxt=document.getElementById('stxt');
  if(!pill||!stxt)return;
  const s=data.state||'idle';
  pill.className='status-pill '+(s==='running'?'s-run':s==='error'?'s-err':'s-idle');
  stxt.textContent=s==='running'?'執行中':s==='error'?'異常':'待命';
  const ts=document.getElementById('ts');if(ts)ts.textContent=data.ts||'--';
  // Hero sync
  const hero=document.getElementById('hero-bar');
  if(hero){hero.className='hero'+(s==='running'?' running':s==='error'?' error':'');}
  const hs=document.getElementById('hero-state');
  if(hs)hs.textContent=s==='running'?'執行中':s==='error'?'異常':'待命中';
  const hts=document.getElementById('hero-ts');
  if(hts)hts.textContent=data.ts?'最後更新 '+data.ts:'—';
  const pipe=data.pipeline||{};
  const ht=document.getElementById('hero-topic');
  if(ht)ht.textContent=(pipe.article&&pipe.article.title)?pipe.article.title:'尚未開始任務';
  const flow=data.flow||[];
  const working=flow.find(a=>a.status==='working');
  const hstage=document.getElementById('hero-stage');
  if(hstage)hstage.textContent=working?'▸ '+working.label:'—';
  const hnext=document.getElementById('hero-next');
  if(hnext){
    let txt='下一步：等待手動觸發';
    if(s==='running'){
      if(working){
        txt='下一步：由「'+working.label+'」回報，秘書/經理同步協調下一批任務';
      }else{
        txt='下一步：秘書與經理盤點各 Agent 工作負載';
      }
    }else if(s==='error'){
      txt='下一步：查看診斷或活動頁定位錯誤';
    }
    hnext.textContent=txt;
  }
  // overview-topic-chip now shows working count
  const wk=flow.filter(a=>a.status==='working').length;
  const otc=document.getElementById('overview-topic-chip');
  if(otc)otc.textContent=wk;
}

/* REVENUE */
async function fetchRevenue(){
  try{
    const r=await fetch('/api/revenue');const d=await r.json();
    const total=d.total_revenue||0,cost=d.monthly_cost||200,gap=total-cost;
    const k5=document.getElementById('k5');if(k5)k5.textContent='$'+total;
    const hk5=document.getElementById('hk5');if(hk5)hk5.textContent='$'+total;
    const k6=document.getElementById('k6');
    if(k6){k6.textContent=(gap>=0?'+':'')+'$'+gap;k6.className='sv '+(gap>=0?'ok':'warn');}
  }catch(e){}
}

/* FEED (right panel) — diff-based, only animates new items */
let _lastFeedSig='';
function renderFeed(data){
  const el=document.getElementById('feed-items');if(!el)return;
  const feed=data.feed||[];
  if(!feed.length){
    if(_lastFeedSig!=='__empty__'){_lastFeedSig='__empty__';el.innerHTML='<div style="padding:14px 12px;color:var(--t2);font-size:9.5px">尚無活動記錄</div>';}
    return;
  }
  const top20=feed.slice(0,20);
  const newSig=top20.slice(0,3).map(e=>(e.time||'')+e.msg).join('|');
  if(newSig===_lastFeedSig)return;
  const prevSig=_lastFeedSig;_lastFeedSig=newSig;
  const tm={success:'ok',warn:'warn',error:'error',info:''};
  const makeItem=(ev,isNew)=>{
    const ag=FM.find(a=>a.id===ev.agent);
    const icon=ag?ag.icon:'◌';
    const tc=tm[ev.type]||'';
    const style=isNew?'':' style="animation:none"';
    return '<div class="feed-item"'+style+'>'+
      '<div class="fi-top"><span class="fi-icon">'+icon+'</span>'+
      '<span class="fi-agent">'+esc(ev.agent)+'</span>'+
      (ev.time?'<span class="fi-time">'+esc(ev.time)+'</span>':'')+
      '</div><div class="fi-msg '+tc+'">'+esc(ev.msg)+'</div></div>';
  };
  if(!prevSig){el.innerHTML=top20.map(ev=>makeItem(ev,false)).join('');return;}
  // find new items at the front
  const existSigs=new Set(
    Array.from(el.querySelectorAll('.feed-item')).map(e=>{
      const t=e.querySelector('.fi-time');const m=e.querySelector('.fi-msg');
      return (t?t.textContent:'')+(m?m.textContent:'');
    })
  );
  const newItems=top20.filter(ev=>!existSigs.has((ev.time||'')+ev.msg));
  if(!newItems.length)return;
  const frag=document.createDocumentFragment();
  newItems.reverse().forEach(ev=>{
    const tmp=document.createElement('div');tmp.innerHTML=makeItem(ev,true);
    frag.prepend(tmp.firstChild);
  });
  el.prepend(frag);
  const all=el.querySelectorAll('.feed-item');
  for(let i=20;i<all.length;i++)all[i].remove();
}

/* LOG — only re-renders when content actually changes */
const LC={APPROVED:'ok',REJECTED:'warn',ERROR:'err',error:'err',Failed:'err',failed:'err',WARNING:'warn',INFO:'info'};
function colorLine(l){for(const[k,c]of Object.entries(LC)){if(l.includes(k))return c;}return 'normal';}
let _lastLogSig='';
function renderLog(data,tab){
  const el=document.getElementById('log-display');if(!el)return;
  const lines=tab==='cron'?data.cron_log_tail||[]:data.error_log||[];
  const tail=lines.slice(-80);
  const sig=tail.slice(-3).join('');
  if(sig===_lastLogSig)return;
  _lastLogSig=sig;
  const wasAtBottom=el.scrollHeight-el.scrollTop-el.clientHeight<40;
  el.innerHTML=tail.map(l=>'<div class="log-line '+colorLine(l)+'">'+esc(l)+'</div>').join('');
  if(wasAtBottom)el.scrollTop=el.scrollHeight;
}
function switchLog(tab,el){
  currentLogTab=tab;
  document.querySelectorAll('.log-tab').forEach(t=>t.classList.remove('active'));
  if(el)el.classList.add('active');
  if(tab==='standup'){
    fetch('/api/standup').then(r=>r.json()).then(d=>{
      const e=document.getElementById('log-display');
      if(e)e.innerHTML=(d.recent||[]).map(l=>'<div class="log-line '+colorLine(l)+'">'+esc(l)+'</div>').join('');
    }).catch(()=>{});
  }else if(lastData){renderLog(lastData,tab);}
}

/* ARTICLES */
function renderArticles(data){
  const arts=data.articles||[];
  const ac=document.getElementById('arts-count');if(ac)ac.textContent=arts.length+' 篇';
  const al=document.getElementById('arts-list');if(!al)return;
  al.innerHTML=arts.map(a=>
    '<div class="art-item" data-name="'+esc(a.name)+'" onclick="openArticle(\''+esc(a.name)+'\')">'+
    '<span class="art-title" title="'+esc(a.title)+'">'+esc(a.title)+'</span>'+
    '<span class="art-w">'+a.words+' 字</span></div>'
  ).join('')||'<div style="padding:14px 12px;color:var(--t2);font-size:9.5px">尚無文章</div>';
}

function renderProposals(){}

/* MAIN FETCH */
async function fetchNow(){
  try{
    const ctrl=new AbortController();
    const tid=setTimeout(()=>ctrl.abort(),8000);
    const r=await fetch('/api/status',{signal:ctrl.signal});
    clearTimeout(tid);
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();
    fetchFailCount=0;lastFetchErr='';
    lastData=d;
    renderStatus(d);renderKPI(d);updateWorkstations(d);renderPipeline(d);
    if(currentLogTab!=='standup')renderLog(d,currentLogTab);
    renderArticles(d);renderFeed(d);fetchRevenue();
    checkAlerts(d);
    if(selectedAgentId)selectAgent(selectedAgentId);
    countdown=5;
  }catch(e){
    fetchFailCount++;
    lastFetchErr=(e&&e.name==='AbortError')?'請求逾時（8秒）':((e&&e.message)?e.message:'未知錯誤');
    console.error('fetch /api/status failed:',e);
    const fallback={
      state:'error',ts:utcStamp(),pipeline:{stages:[],article:null,count:0},flow:[],
      usage:{today:0,total:0},diag:{score:0,issues:[]},api:{model:'離線'},cron_count:0,
      has_placeholder:false,articles:[],
      feed:[{time:'',agent:'system',msg:'監控連線失敗：'+lastFetchErr,type:'error'}],
      error_log:['FETCH_ERROR: '+lastFetchErr]
    };
    renderStatus(fallback);renderFeed(fallback);
    if(fetchFailCount===1||fetchFailCount%6===0){
      showAlert('CRITICAL','監控連線異常','無法讀取 /api/status：'+lastFetchErr,'err');
    }
    countdown=5;
  }
}

/* ALERTS */
function checkAlerts(data){
  const errs=(data.error_log||[]).filter(l=>l.trim()&&l.includes('ERROR'));
  if(errs.length>0){
    const latest=errs.slice(-1)[0];
    if(latest!==_lastShownError){
      _lastShownError=latest;
      showAlert('CRITICAL','系統錯誤',latest,'err');
    }
  }
}
function showAlert(level,title,desc,type){
  document.getElementById('alert-level').textContent=level;
  document.getElementById('alert-title').textContent=title;
  document.getElementById('alert-desc').textContent=desc;
  document.getElementById('alert-box').className='alert-box'+(type==='warn'?' warn-type':'');
  document.getElementById('alert-ov').classList.add('show');
}
function closeAlert(){document.getElementById('alert-ov').classList.remove('show');}

/* COMMANDS */
async function triggerRun(){
  try{
    await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    showAlert('INFO','任務已啟動','run.sh 已在背景執行，30秒後更新狀態','warn');
    setTimeout(closeAlert,2500);
  }catch(e){alert('無法連接 API');}
}
async function triggerStop(){
  try{
    await fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    showAlert('INFO','停止信號已發送','正在停止執行中的任務...','warn');
    setTimeout(closeAlert,2000);
  }catch(e){alert('無法連接 API');}
}
async function sendChatDirect(msg){
  const msgs=document.getElementById('chat-msgs');if(!msgs)return;
  msgs.insertAdjacentHTML('beforeend','<div class="cm user">'+esc(msg)+'</div>');
  msgs.scrollTop=msgs.scrollHeight;
  const typing=document.getElementById('chat-typing');if(typing)typing.style.display='block';
  const btn=document.getElementById('chat-btn');if(btn)btn.disabled=true;
  try{
    const ctrl=new AbortController();const tid=setTimeout(()=>ctrl.abort(),15000);
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg}),signal:ctrl.signal});
    clearTimeout(tid);
    const d=await r.json();
    msgs.insertAdjacentHTML('beforeend','<div class="cm ai">'+esc(d.reply||d.error||'（無回應）')+'</div>');
  }catch(e){
    msgs.insertAdjacentHTML('beforeend','<div class="cm ai">'+(e.name==='AbortError'?'⏱ 請求逾時':'❌ 無法連線')+'</div>');
  }
  if(btn)btn.disabled=false;
  if(typing)typing.style.display='none';
  msgs.scrollTop=msgs.scrollHeight;
}
function triggerTopic(){
  const t=document.getElementById('topic-input');if(!t)return;
  const v=t.value.trim();if(!v)return;
  t.value='';
  setMode('control',null);
  sendChatDirect('強制執行今日主題：'+v);
}

/* ARTICLE PREVIEW */
async function openArticle(name){
  devtoName=name;
  if(document.body.dataset.mode!=='content')setMode('content',null);
  document.querySelectorAll('.art-item').forEach(el=>el.classList.toggle('selected',el.dataset.name===name));
  const ph=document.getElementById('preview-hd');if(ph)ph.textContent=name;
  const pb=document.getElementById('preview-body');if(pb)pb.textContent='載入中...';
  const pw=document.getElementById('preview-words');if(pw)pw.textContent='';
  const db=document.getElementById('devto-btn');if(db){db.disabled=false;db.textContent='→ dev.to 草稿';}
  try{
    const r=await fetch('/api/article/'+encodeURIComponent(name));
    const d=await r.json();
    if(pb)pb.textContent=d.content||'（無內容）';
    if(pw)pw.textContent=(d.content||'').length+' 字';
  }catch(e){if(pb)pb.textContent='載入失敗';}
}
async function postToDevto(){
  const btn=document.getElementById('devto-btn');if(!btn)return;
  btn.disabled=true;btn.textContent='發布中...';
  try{
    const r=await fetch('/api/devto',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:devtoName})});
    const d=await r.json();
    if(d.ok){btn.textContent='✓ 已建立草稿';}
    else{btn.textContent='✗ 失敗';btn.disabled=false;}
  }catch(e){btn.textContent='錯誤';btn.disabled=false;}
}

/* CHAT */
function chatKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}}
async function sendChat(){
  const inp=document.getElementById('chat-in');if(!inp)return;
  const msg=inp.value.trim();if(!msg)return;
  inp.value='';
  const msgs=document.getElementById('chat-msgs');if(!msgs)return;
  msgs.insertAdjacentHTML('beforeend','<div class="cm user">'+esc(msg)+'</div>');
  msgs.scrollTop=msgs.scrollHeight;
  const btn=document.getElementById('chat-btn');if(btn)btn.disabled=true;
  const typing=document.getElementById('chat-typing');if(typing)typing.style.display='block';
  try{
    const ctrl=new AbortController();const tid=setTimeout(()=>ctrl.abort(),15000);
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg}),signal:ctrl.signal});
    clearTimeout(tid);
    const d=await r.json();
    const reply=d.reply||d.error||'（無回應）';
    msgs.insertAdjacentHTML('beforeend','<div class="cm ai">'+esc(reply)+'</div>');
  }catch(e){
    const msg2=e.name==='AbortError'?'⏱ 請求逾時（15秒），請重試':'❌ 無法連線，請確認伺服器狀態';
    msgs.insertAdjacentHTML('beforeend','<div class="cm ai">'+msg2+'</div>');
  }
  if(btn)btn.disabled=false;
  if(typing)typing.style.display='none';
  msgs.scrollTop=msgs.scrollHeight;
}

/* TIMER */
function startTimer(){
  timer=setInterval(()=>{
    countdown--;
    const bar=document.getElementById('tb-bar');
    if(bar)bar.style.width=(countdown/5*100)+'%';
    if(countdown<=0){fetchNow();countdown=5;}
  },1000);
}
/* ESCAPE key closes alert */
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeAlert();});
fetchNow();startTimer();
// click blank area in office room to deselect agent
document.addEventListener('DOMContentLoaded',()=>{
  const room=document.querySelector('.office-room');
  if(room)room.addEventListener('click',e=>{
    if(!e.target.closest('.ws')&&selectedAgentId)deselectAgent();
  });
});
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════
#  HTTP Handler
# ══════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=="/api/status":
            self._json(json.dumps(get_status_data(),ensure_ascii=False).encode())
        elif self.path=="/api/revenue":
            self._json(json.dumps(revenue_data(),ensure_ascii=False).encode())
        elif self.path=="/api/proposals":
            self._json(json.dumps(proposals_data(),ensure_ascii=False).encode())
        elif self.path=="/api/standup":
            self._json(json.dumps(standup_data(),ensure_ascii=False).encode())
        elif self.path.startswith("/api/article/"):
            raw=self.path[len("/api/article/"):]
            name=urllib.parse.unquote(raw)
            if name and re.match(r'^[\w\-\.]{1,100}$',name):
                c=get_article_content(name)
                if c:
                    self._json(json.dumps({"content":c},ensure_ascii=False).encode())
                    return
            self.send_response(404); self.end_headers()
        elif self.path=="/api/health":
            api_key, base_url, model = read_api_env()
            crons = cron_lines()
            err_lines = [l.strip() for l in rt("logs/error.log",3) if l.strip()]
            cron_tail = rt("logs/cron.log",3)
            checks = {
                "api_token":  "ok" if api_key else "missing",
                "base_url":   base_url or "not set",
                "model":      model or "not set",
                "run_sh":     "ok" if (BASE/"run.sh").exists() else "missing",
                "logs_dir":   "ok" if (BASE/"logs").exists() else "missing",
                "crontab":    f"{len(crons)} jobs",
                "last_error": err_lines[-1][:100] if err_lines else "none",
                "last_cron":  cron_tail[-1][:100] if cron_tail else "no log",
            }
            self._json(json.dumps({"status":"ok","checks":checks},ensure_ascii=False).encode())
        elif self.path.startswith("/api/article"):
            parsed=urllib.parse.urlparse(self.path)
            params=urllib.parse.parse_qs(parsed.query)
            name=params.get("name",[""])[0].strip()
            if not name:
                suffix=parsed.path[len("/api/article"):].lstrip("/")
                name=urllib.parse.unquote(suffix).strip()
            if name and re.match(r'^[\w\-\.]{1,100}$',name):
                c=get_article_content(name)
                if c:
                    self._json(json.dumps({"content":c},ensure_ascii=False).encode())
                    return
            self.send_response(404); self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.send_header("Expires","0")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

    def do_POST(self):
        length=int(self.headers.get("Content-Length",0))
        body={}
        if length>0:
            try: body=json.loads(self.rfile.read(length))
            except: pass
        if self.path=="/api/chat":
            msg=body.get("message","").strip()
            reply=do_chat(msg) if msg else "請輸入訊息。"
            self._json(json.dumps({"reply":reply},ensure_ascii=False).encode())
        elif self.path in ("/api/devto","/api/post-devto"):
            name=body.get("name","")
            result=post_to_devto(name) if name else {"ok":False,"error":"缺少 name"}
            self._json(json.dumps(result,ensure_ascii=False).encode())
        elif self.path=="/api/run":
            subprocess.Popen(["bash",str(BASE/"run.sh")])
            self._json(json.dumps({"ok":True,"msg":"run.sh 已啟動"},ensure_ascii=False).encode())
        elif self.path=="/api/stop":
            subprocess.run(["pkill","-f","run.sh"],capture_output=True)
            self._json(json.dumps({"ok":True,"msg":"已發送停止信號"},ensure_ascii=False).encode())
        else:
            self.send_response(404); self.end_headers()

    def _json(self,data):
        self.send_response(200)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma","no-cache")
        self.send_header("Expires","0")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self,*a): pass

if __name__=="__main__":
    port=int(os.environ.get("DASHBOARD_PORT",3000))
    print(f"Dashboard v11 AI 無人工廠控制室啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0",port),Handler).serve_forever()
