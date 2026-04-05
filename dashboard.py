#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v9
— 指揮中心 HUD：零外部依賴，純 CSS/JS
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
  {"id":"researcher",       "order":1,  "label":"研究員",   "icon":"◎", "phase":"探索",
   "desc":"爬蟲 4 個 subreddit，評估需求，找 Amazon.co.jp 聯盟商品",
   "reads": ["CLAUDE.md","logs/topic-performance.json",".knowledge/performance.md"],
   "writes":["logs/demand_signals.json","logs/affiliate-links.json"],
   "skills":["researcher-strategy","audience-targeting"],
   "hooks": []},

  {"id":"topic-selector",   "order":2,  "label":"選題",     "icon":"◈", "phase":"策略",
   "desc":"合併需求信號與歷史表現，決定唯一下一篇主題，避免重複",
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
    pipe   = pipeline_status()
    stages = pipe["stages"]
    active_id = None
    waiting  = set()
    for i,s in enumerate(stages):
        if not s.get("done") and (i==0 or stages[i-1].get("done")):
            active_id = s["id"]
            for j in range(i+1,len(stages)): waiting.add(stages[j]["id"])
            break
    result = {}
    for a in PIPELINE_FLOW:
        aid = a["id"]
        if aid == active_id:
            result[aid] = {"status":"working","txt":"工作中"}
        elif aid in waiting:
            result[aid] = {"status":"waiting","txt":"等待中"}
        else:
            result[aid] = {"status":"idle","txt":"休息中"}
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
            reply  = result["content"][0]["text"]
            _chat_history.append({"role":"user","content":message})
            _chat_history.append({"role":"assistant","content":reply})
            return reply
    except Exception as e:
        return f"❌ API 錯誤：{str(e)[:150]}"

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
#  HTML — Dashboard v9 指揮中心 HUD
# ══════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 指揮中心 v9</title>
<style>
:root{
  --bg0:#060a0f;--bg1:#0d1117;--bg2:#161b22;--bg3:#1c2333;
  --b0:#21262d;--b1:#30363d;
  --t0:#e6edf3;--t1:#8b949e;--t2:#484f58;
  --ok:#3fb950;--ok-s:rgba(63,185,80,.12);--ok-g:rgba(63,185,80,.04);
  --warn:#d29922;--warn-s:rgba(210,153,34,.12);
  --err:#f85149;--err-s:rgba(248,81,73,.12);
  --brand:#58a6ff;--brand-s:rgba(88,166,255,.08);
  --pur:#bc8cff;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;overflow:hidden;background:var(--bg0);color:var(--t0);
  font-family:'Hiragino Sans','Noto Sans TC',system-ui,sans-serif;font-size:12px;line-height:1.6;}
body{display:flex;flex-direction:column;}
@keyframes pls{0%,100%{opacity:1;}50%{opacity:.15;}}
@keyframes scan{0%{transform:translateY(-100%);}100%{transform:translateY(100vh);}}
@keyframes alertIn{0%{transform:scale(.92);opacity:0;}100%{transform:scale(1);opacity:1;}}
@keyframes borderPulse{0%,100%{box-shadow:0 0 0 0 rgba(248,81,73,.5);}50%{box-shadow:0 0 12px 3px rgba(248,81,73,.2);}}
@keyframes warnPulse{0%,100%{box-shadow:0 0 0 0 rgba(210,153,34,.5);}50%{box-shadow:0 0 10px 2px rgba(210,153,34,.15);}}

/* TOPBAR */
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:0 16px;height:44px;background:var(--bg1);
  border-bottom:1px solid var(--b0);flex-shrink:0;position:relative;z-index:100;}
.topbar::after{content:'';position:absolute;bottom:-1px;left:0;right:0;
  height:1px;background:linear-gradient(90deg,transparent,var(--brand),transparent);opacity:.3;}
.logo{font-size:11px;font-weight:700;color:var(--brand);letter-spacing:.12em;display:flex;align-items:center;gap:10px;}
.logo-sub{font-size:9px;color:var(--t2);letter-spacing:.05em;}
.status-pill{display:flex;align-items:center;gap:5px;padding:3px 10px;
  border:1px solid var(--b0);font-size:9px;font-weight:700;letter-spacing:.06em;}
.sdot{width:7px;height:7px;border-radius:50%;}
.s-idle .sdot{background:var(--t2);}
.s-run .sdot{background:var(--ok);animation:pls 1.2s infinite;}
.s-err .sdot{background:var(--err);animation:pls .6s infinite;}
.s-idle .stxt{color:var(--t2);} .s-run .stxt{color:var(--ok);} .s-err .stxt{color:var(--err);}
.tb-right{display:flex;align-items:center;gap:8px;}
.tb-ts{font-size:9px;color:var(--t2);}
.tb-btn{background:none;border:1px solid var(--b0);color:var(--t2);
  padding:4px 10px;cursor:pointer;font-size:9px;transition:.15s;letter-spacing:.04em;}
.tb-btn:hover{border-color:var(--brand);color:var(--brand);}
.tb-btn.danger{border-color:var(--err);color:var(--err);}
.tb-btn.danger:hover{background:var(--err-s);}
.tb-btn.run-btn{border-color:var(--ok);color:var(--ok);}
.tb-btn.run-btn:hover{background:var(--ok-s);}

/* KPI BAR */
.kpi-bar{display:grid;grid-template-columns:repeat(8,1fr);
  background:var(--bg1);border-bottom:1px solid var(--b0);flex-shrink:0;}
.kpi-c{padding:8px 12px;border-right:1px solid var(--b0);cursor:default;transition:.15s;}
.kpi-c:last-child{border-right:none;}
.kpi-c:hover{background:var(--bg2);}
.kpi-v{font-size:14px;font-weight:700;line-height:1.2;color:var(--t0);font-variant-numeric:tabular-nums;}
.kpi-v.ok{color:var(--ok);} .kpi-v.warn{color:var(--warn);} .kpi-v.err{color:var(--err);}
.kpi-v.brand{color:var(--brand);} .kpi-v.pur{color:var(--pur);}
.kpi-l{font-size:8px;color:var(--t2);margin-top:2px;letter-spacing:.04em;}

/* WORKSPACE */
.workspace{flex:1;display:grid;grid-template-columns:190px 1fr 290px;overflow:hidden;}

/* LEFT SIDEBAR */
.sidebar{background:var(--bg1);border-right:1px solid var(--b0);display:flex;flex-direction:column;overflow:hidden;}
.sb-hd{padding:9px 12px;font-size:8px;font-weight:700;letter-spacing:.12em;
  color:var(--brand);border-bottom:1px solid var(--b0);text-transform:uppercase;}
.sb-agents{flex:1;overflow-y:auto;padding:4px;}
.sb-agents::-webkit-scrollbar{width:2px;} .sb-agents::-webkit-scrollbar-thumb{background:var(--b0);}
.agent-card{display:flex;align-items:center;gap:8px;padding:6px 8px;
  cursor:pointer;border:1px solid transparent;margin-bottom:2px;transition:.12s;}
.agent-card:hover{background:var(--bg3);}
.agent-card.selected{border-color:var(--brand);background:var(--brand-s);}
.agent-card.working{border-color:rgba(63,185,80,.3);background:var(--ok-g);}
.agent-card.waiting{border-color:rgba(210,153,34,.2);}
.ac-icon{width:28px;height:28px;border:1px solid var(--b0);display:flex;align-items:center;
  justify-content:center;font-size:13px;flex-shrink:0;transition:.12s;}
.agent-card.working .ac-icon{border-color:var(--ok);box-shadow:0 0 6px rgba(63,185,80,.2);}
.agent-card.waiting .ac-icon{border-color:var(--warn);}
.ac-info{flex:1;min-width:0;}
.ac-name{font-size:9px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ac-status{font-size:8px;margin-top:1px;}
.ac-status.working{color:var(--ok);} .ac-status.waiting{color:var(--warn);} .ac-status.idle{color:var(--t2);}
.sb-proposals{border-top:1px solid var(--b0);padding:8px;flex-shrink:0;max-height:120px;overflow:hidden;}
.sb-ph{font-size:8px;color:var(--pur);font-weight:700;letter-spacing:.08em;margin-bottom:5px;}
.sb-p-item{font-size:9px;color:var(--t1);padding:2px 0;border-bottom:1px solid var(--b0);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;}
.sb-p-item:hover{color:var(--t0);}
.sb-p-empty{font-size:9px;color:var(--t2);font-style:italic;}

/* CENTER */
.center{background:var(--bg0);display:flex;flex-direction:column;overflow:hidden;}
.pipeline-wrap{padding:12px 16px;flex-shrink:0;border-bottom:1px solid var(--b0);}
.pipeline-title{font-size:8px;font-weight:700;letter-spacing:.1em;color:var(--t2);margin-bottom:8px;text-transform:uppercase;}
.pipeline-row{display:flex;align-items:center;gap:0;margin-bottom:4px;}
.pa{display:flex;align-items:center;gap:5px;padding:5px 8px;
  border:1px solid var(--b0);background:var(--bg2);flex:1;min-width:0;
  cursor:pointer;transition:.12s;position:relative;}
.pa:hover{border-color:var(--b1);background:var(--bg3);}
.pa.working{border-color:var(--ok);background:rgba(63,185,80,.05);}
.pa.waiting{border-color:var(--warn);opacity:.7;}
.pa.done{border-color:rgba(63,185,80,.3);background:rgba(63,185,80,.04);}
.pa-icon{font-size:10px;flex-shrink:0;}
.pa-name{font-size:8px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pa-phase{font-size:7px;color:var(--t2);position:absolute;top:2px;right:4px;}
.pa-dot{position:absolute;bottom:3px;right:4px;width:5px;height:5px;border-radius:50%;}
.pa.working .pa-dot{background:var(--ok);animation:pls 1s infinite;}
.pa.done .pa-dot{background:var(--ok);}
.pa.waiting .pa-dot{background:var(--warn);}
.pa.idle .pa-dot{background:var(--t2);}
.arr{color:var(--b1);font-size:10px;padding:0 2px;flex-shrink:0;}
.log-section{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.log-tabs{display:flex;border-bottom:1px solid var(--b0);flex-shrink:0;}
.log-tab{padding:5px 12px;font-size:8px;font-weight:700;cursor:pointer;
  color:var(--t2);border-right:1px solid var(--b0);letter-spacing:.06em;transition:.12s;}
.log-tab.active{color:var(--brand);background:var(--brand-s);}
.log-tab:hover:not(.active){color:var(--t1);}
.log-tail{flex:1;overflow-y:auto;padding:6px 12px;font-family:'SF Mono',Menlo,monospace;font-size:10px;}
.log-tail::-webkit-scrollbar{width:2px;} .log-tail::-webkit-scrollbar-thumb{background:var(--b0);}
.log-line{padding:1px 0;line-height:1.5;}
.log-line.ok{color:var(--ok);} .log-line.warn{color:var(--warn);} .log-line.err{color:var(--err);}
.log-line.info{color:var(--t2);} .log-line.normal{color:var(--t1);}

/* RIGHT PANEL */
.right{background:var(--bg1);border-left:1px solid var(--b0);display:flex;flex-direction:column;overflow:hidden;}
.rp-tabs{display:flex;border-bottom:1px solid var(--b0);flex-shrink:0;}
.rp-tab{flex:1;padding:8px 4px;text-align:center;font-size:8px;font-weight:700;
  cursor:pointer;color:var(--t2);border-right:1px solid var(--b0);letter-spacing:.04em;transition:.12s;}
.rp-tab:last-child{border-right:none;}
.rp-tab.active{color:var(--brand);background:var(--brand-s);}
.rp-pane{flex:1;overflow-y:auto;display:none;flex-direction:column;}
.rp-pane.active{display:flex;}
.rp-pane::-webkit-scrollbar{width:2px;} .rp-pane::-webkit-scrollbar-thumb{background:var(--b0);}

/* CMD PANEL */
.cmd-section{padding:10px 12px;border-bottom:1px solid var(--b0);}
.cmd-hd{font-size:8px;font-weight:700;letter-spacing:.08em;color:var(--t2);margin-bottom:7px;text-transform:uppercase;}
.cmd-btns{display:grid;grid-template-columns:1fr 1fr;gap:5px;}
.cmd-btn{padding:7px 8px;border:1px solid var(--b0);background:none;
  color:var(--t1);cursor:pointer;font-size:9px;font-weight:700;text-align:center;transition:.15s;}
.cmd-btn:hover{background:var(--bg3);}
.cmd-btn.run{border-color:var(--ok);color:var(--ok);}
.cmd-btn.run:hover{background:var(--ok-s);}
.cmd-btn.stop{border-color:var(--err);color:var(--err);}
.cmd-btn.stop:hover{background:var(--err-s);}
.cmd-input-row{display:flex;gap:5px;margin-top:6px;}
.cmd-input{flex:1;background:var(--bg2);border:1px solid var(--b0);
  color:var(--t0);padding:5px 8px;font-size:9px;outline:none;transition:.15s;}
.cmd-input:focus{border-color:var(--brand);}
.cmd-exec{background:var(--brand);color:#fff;border:none;padding:5px 10px;
  cursor:pointer;font-size:9px;font-weight:700;}

/* SETTINGS */
.set-section{padding:10px 12px;border-bottom:1px solid var(--b0);}
.set-row{margin-bottom:7px;}
.set-label{font-size:8px;color:var(--t2);margin-bottom:3px;letter-spacing:.04em;text-transform:uppercase;}
.set-input{width:100%;background:var(--bg2);border:1px solid var(--b0);
  color:var(--t0);padding:5px 8px;font-size:9px;font-family:monospace;outline:none;transition:.15s;}
.set-input:focus{border-color:var(--brand);}
.set-save{width:100%;padding:6px;background:none;border:1px solid var(--brand);
  color:var(--brand);cursor:pointer;font-size:9px;font-weight:700;margin-top:5px;transition:.15s;}
.set-save:hover{background:var(--brand-s);}

/* REVENUE */
.rev-section{padding:10px 12px;border-bottom:1px solid var(--b0);}
.rev-total{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;}
.rev-amount{font-size:18px;font-weight:700;color:var(--ok);}
.rev-label{font-size:8px;color:var(--t2);}
.rev-progress{height:4px;background:var(--b0);margin-bottom:8px;}
.rev-progress-bar{height:100%;background:var(--ok);transition:width .5s;}
.rev-platforms{display:grid;gap:3px;}
.rev-row{display:flex;justify-content:space-between;font-size:9px;padding:2px 0;border-bottom:1px solid var(--b0);}
.rev-row:last-child{border-bottom:none;}
.rev-name{color:var(--t2);} .rev-val{color:var(--t0);font-weight:700;}

/* CHAT */
.chat-msgs{flex:1;overflow-y:auto;padding:8px 10px;display:flex;flex-direction:column;gap:5px;}
.chat-msgs::-webkit-scrollbar{width:2px;} .chat-msgs::-webkit-scrollbar-thumb{background:var(--b0);}
.cm{max-width:95%;padding:6px 9px;font-size:10.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;}
.cm.user{background:var(--brand-s);border:1px solid rgba(88,166,255,.2);color:var(--t0);align-self:flex-end;}
.cm.ai{background:var(--bg2);border:1px solid var(--b0);color:var(--t1);align-self:flex-start;}
.cm.sys{background:var(--warn-s);border:1px solid rgba(210,153,34,.15);color:var(--warn);align-self:center;font-size:9px;}
.chat-typing{color:var(--t2);font-size:9px;padding:2px 10px;animation:pls .8s infinite;flex-shrink:0;}
.chat-row{display:flex;gap:4px;padding:7px 8px;border-top:1px solid var(--b0);flex-shrink:0;}
.chat-row textarea{flex:1;background:var(--bg2);border:1px solid var(--b0);color:var(--t0);
  padding:5px 8px;font-size:10px;font-family:inherit;outline:none;resize:none;transition:.15s;}
.chat-row textarea:focus{border-color:var(--brand);}
.chat-send{background:var(--brand);color:#fff;border:none;padding:5px 10px;cursor:pointer;font-size:10px;font-weight:700;}
.chat-send:disabled{opacity:.4;cursor:not-allowed;}

/* AGENT DETAIL */
.ad-head{display:flex;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid var(--b0);}
.ad-icon{width:36px;height:36px;border:1px solid var(--b0);display:flex;align-items:center;justify-content:center;font-size:18px;}
.ad-name{font-size:11px;font-weight:700;}
.ad-badges{display:flex;gap:4px;margin-top:4px;flex-wrap:wrap;}
.badge{display:inline-flex;padding:2px 6px;font-size:8px;font-weight:700;}
.b-ok{background:var(--ok-s);color:var(--ok);}
.b-warn{background:var(--warn-s);color:var(--warn);}
.b-brand{background:var(--brand-s);color:var(--brand);}
.b-pur{background:rgba(188,140,255,.12);color:var(--pur);}
.ad-desc{padding:8px 12px;font-size:10px;color:var(--t1);line-height:1.6;border-bottom:1px solid var(--b0);}
.ad-sec{padding:7px 12px;}
.ad-sl{font-size:8px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--t2);margin-bottom:5px;}
.file-item{display:flex;align-items:center;gap:5px;font-size:9.5px;padding:2px 0;}
.file-dot{width:5px;height:5px;border-radius:50%;}
.file-dot.ok{background:var(--ok);} .file-dot.miss{background:var(--b0);}
.file-path{color:var(--t1);font-family:monospace;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:170px;}
.file-age{font-size:8px;color:var(--t2);white-space:nowrap;}
.pills{display:flex;flex-wrap:wrap;gap:3px;}
.pill{font-size:8px;padding:2px 6px;}
.pill.sk{background:var(--brand-s);color:var(--brand);}
.pill.sk-x{background:var(--bg3);color:var(--t2);}
.pill.hk{background:var(--ok-s);color:var(--ok);}
.pill.hk-x{background:var(--err-s);color:var(--err);}

/* ARTICLES */
.arts-list{padding:4px 8px;}
.art-item{display:flex;align-items:center;gap:7px;padding:5px 3px;cursor:pointer;
  transition:.12s;border-bottom:1px solid var(--b0);}
.art-item:hover{background:var(--bg3);}
.art-dot{width:5px;height:5px;border-radius:50%;background:var(--ok);flex-shrink:0;}
.art-title{flex:1;font-size:9.5px;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.art-w{font-size:8px;color:var(--t2);}

/* MODAL */
.modal-ov{display:none;position:fixed;inset:0;z-index:500;
  background:rgba(0,0,0,.8);backdrop-filter:blur(4px);
  align-items:flex-start;justify-content:center;padding:30px 20px;}
.modal-ov.open{display:flex;}
.modal-box{background:var(--bg1);border:1px solid var(--b0);width:100%;max-width:800px;
  max-height:85vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.6);}
.modal-hd{padding:10px 16px;border-bottom:1px solid var(--b0);
  display:flex;align-items:center;justify-content:space-between;}
.modal-title{font-size:12px;font-weight:700;}
.modal-close{width:24px;height:24px;background:var(--bg2);border:1px solid var(--b0);
  color:var(--t2);cursor:pointer;font-size:12px;display:flex;align-items:center;justify-content:center;}
.modal-close:hover{border-color:var(--brand);color:var(--brand);}
.modal-bd{flex:1;overflow-y:auto;padding:14px 18px;font-family:monospace;font-size:11px;
  line-height:1.9;color:var(--t1);white-space:pre-wrap;word-break:break-word;}
.modal-ft{padding:6px 16px;border-top:1px solid var(--b0);font-size:9px;color:var(--t2);
  display:flex;align-items:center;gap:8px;}
.devto-btn{background:var(--ok-s);color:var(--ok);border:1px solid rgba(63,185,80,.3);
  padding:3px 10px;font-size:9px;cursor:pointer;font-weight:700;}

/* ALERT OVERLAY */
.alert-ov{display:none;position:fixed;inset:0;z-index:900;
  background:rgba(0,0,0,.88);align-items:center;justify-content:center;}
.alert-ov.show{display:flex;animation:alertIn .2s ease;}
.alert-box{padding:36px 56px;text-align:center;position:relative;overflow:hidden;
  border:2px solid var(--err);background:rgba(248,81,73,.04);max-width:480px;
  animation:borderPulse .8s infinite;}
.alert-box.warn-type{border-color:var(--warn);background:rgba(210,153,34,.04);animation:warnPulse 1s infinite;}
.alert-scan{position:absolute;left:0;right:0;height:2px;background:rgba(248,81,73,.25);
  animation:scan 2s linear infinite;}
.alert-box.warn-type .alert-scan{background:rgba(210,153,34,.2);}
.alert-level{font-size:9px;font-weight:700;letter-spacing:.2em;color:var(--err);margin-bottom:12px;}
.alert-box.warn-type .alert-level{color:var(--warn);}
.alert-title{font-size:22px;font-weight:700;color:var(--t0);margin-bottom:8px;}
.alert-desc{font-size:11px;color:var(--t1);line-height:1.7;margin-bottom:20px;}
.alert-close{padding:8px 24px;border:1px solid var(--err);color:var(--err);
  background:none;cursor:pointer;font-size:10px;font-weight:700;letter-spacing:.08em;}
.alert-close:hover{background:var(--err-s);}
.alert-box.warn-type .alert-close{border-color:var(--warn);color:var(--warn);}
body.alerting::before{content:'';position:fixed;inset:0;z-index:800;pointer-events:none;
  background:repeating-linear-gradient(0deg,rgba(248,81,73,.015) 0px,rgba(248,81,73,.015) 1px,transparent 1px,transparent 4px);}
</style>
</head>
<body>

<nav class="topbar">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="logo">⬡ AI FACTORY <span class="logo-sub">COMMAND CENTER v9</span></div>
    <div class="status-pill s-idle" id="spill"><span class="sdot"></span><span class="stxt" id="stxt">INIT</span></div>
  </div>
  <div class="tb-right">
    <span class="tb-ts" id="ts">--</span>
    <button class="tb-btn run-btn" onclick="triggerRun()">▶ 立即執行</button>
    <button class="tb-btn danger" onclick="triggerStop()">⏹ 停止</button>
    <button class="tb-btn" onclick="fetchNow()">⟳ 更新</button>
  </div>
</nav>

<div class="kpi-bar">
  <div class="kpi-c"><div class="kpi-v brand" id="k0">0</div><div class="kpi-l">今日產出</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k1">0</div><div class="kpi-l">文章總數</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k2">0</div><div class="kpi-l">API 今日</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k3">0</div><div class="kpi-l">API 累計</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k4">--</div><div class="kpi-l">系統健康</div></div>
  <div class="kpi-c"><div class="kpi-v ok" id="k5">$0</div><div class="kpi-l">本月收益</div></div>
  <div class="kpi-c"><div class="kpi-v warn" id="k6">-$200</div><div class="kpi-l">距損益平衡</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k7" style="font-size:9px;">--</div><div class="kpi-l">模型</div></div>
</div>

<div class="workspace">
  <div class="sidebar">
    <div class="sb-hd">▣ TEAM STATUS</div>
    <div class="sb-agents" id="sb-agents"></div>
    <div class="sb-proposals" id="sb-proposals">
      <div class="sb-ph">● 提案待審核</div>
      <div class="sb-p-empty">載入中...</div>
    </div>
  </div>

  <div class="center">
    <div class="pipeline-wrap">
      <div class="pipeline-title">▸ PIPELINE STATUS</div>
      <div class="pipeline-row" id="pipe-row1"></div>
      <div class="pipeline-row" id="pipe-row2"></div>
    </div>
    <div class="log-section">
      <div class="log-tabs">
        <div class="log-tab active" onclick="switchLog('cron',this)">CRON.LOG</div>
        <div class="log-tab" onclick="switchLog('error',this)">ERROR.LOG</div>
        <div class="log-tab" onclick="switchLog('standup',this)">STANDUP</div>
      </div>
      <div class="log-tail" id="log-display"></div>
    </div>
  </div>

  <div class="right">
    <div class="rp-tabs">
      <div class="rp-tab active" onclick="switchTab('agent',this)">AGENT</div>
      <div class="rp-tab" onclick="switchTab('cmd',this)">指令</div>
      <div class="rp-tab" onclick="switchTab('rev',this);fetchRevenue()">收益</div>
      <div class="rp-tab" onclick="switchTab('chat',this)">聊天</div>
      <div class="rp-tab" onclick="switchTab('arts',this)">文章</div>
    </div>

    <div class="rp-pane active" id="pane-agent">
      <div id="ad-inner" style="padding:20px;text-align:center;color:var(--t2);font-size:10px;">
        點擊左側 Agent 查看詳情
      </div>
    </div>

    <div class="rp-pane" id="pane-cmd">
      <div class="cmd-section">
        <div class="cmd-hd">快速指令</div>
        <div class="cmd-btns">
          <button class="cmd-btn run" onclick="triggerRun()">▶ 立即執行</button>
          <button class="cmd-btn stop" onclick="triggerStop()">⏹ 停止任務</button>
        </div>
        <div class="cmd-input-row">
          <input class="cmd-input" id="topic-input" placeholder="強制指定主題...">
          <button class="cmd-exec" onclick="triggerTopic()">執行</button>
        </div>
      </div>
      <div class="set-section">
        <div class="cmd-hd">系統設定</div>
        <div class="set-row">
          <div class="set-label">Minimax API Token</div>
          <input class="set-input" id="set-token" type="password" placeholder="已設定" autocomplete="off">
        </div>
        <div class="set-row">
          <div class="set-label">Whop Guide ($9)</div>
          <input class="set-input" id="set-whop-guide" placeholder="https://whop.com/...">
        </div>
        <div class="set-row">
          <div class="set-label">Whop Pack ($19)</div>
          <input class="set-input" id="set-whop-pack" placeholder="https://whop.com/...">
        </div>
        <div class="set-row">
          <div class="set-label">Whop Sub ($5/月)</div>
          <input class="set-input" id="set-whop-sub" placeholder="https://whop.com/...">
        </div>
        <button class="set-save" onclick="saveSettings()">💾 儲存設定</button>
      </div>
    </div>

    <div class="rp-pane" id="pane-rev">
      <div class="rev-section">
        <div class="rev-total">
          <div>
            <div class="rev-amount" id="rev-total-amt">$0</div>
            <div class="rev-label">本月總收益</div>
          </div>
          <div style="text-align:right">
            <div class="rev-amount" style="color:var(--warn)" id="rev-gap-amt">-$200</div>
            <div class="rev-label">損益缺口</div>
          </div>
        </div>
        <div class="rev-progress"><div class="rev-progress-bar" id="rev-bar" style="width:0%"></div></div>
        <div class="rev-platforms" id="rev-platforms">載入中...</div>
      </div>
    </div>

    <div class="rp-pane" id="pane-chat">
      <div class="chat-msgs" id="chat-msgs">
        <div class="cm sys">AI 助手就緒 — 詢問系統狀態或下達指令</div>
      </div>
      <div id="chat-typing" class="chat-typing" style="display:none">AI 回覆中...</div>
      <div class="chat-row">
        <textarea id="chat-in" rows="2" placeholder="詢問狀態、設定問題..." onkeydown="chatKey(event)"></textarea>
        <button class="chat-send" id="chat-btn" onclick="sendChat()">送出</button>
      </div>
    </div>

    <div class="rp-pane" id="pane-arts">
      <div style="padding:8px 12px;border-bottom:1px solid var(--b0);display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:8px;font-weight:700;letter-spacing:.08em;color:var(--t2);">文章庫</span>
        <span id="arts-count" style="font-size:9px;color:var(--t2)"></span>
      </div>
      <div class="arts-list" id="arts-list"></div>
    </div>
  </div>
</div>

<div class="modal-ov" id="modal" onclick="closeModal(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-hd">
      <div class="modal-title" id="mtitle">文章內容</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-bd" id="mbody">載入中...</div>
    <div class="modal-ft">
      <span id="mfoot" style="flex:1"></span>
      <button class="devto-btn" id="devto-btn" onclick="postToDevto()">→ dev.to 草稿</button>
    </div>
  </div>
</div>

<div class="alert-ov" id="alert-ov">
  <div class="alert-box" id="alert-box">
    <div class="alert-scan"></div>
    <div class="alert-level" id="alert-level">CRITICAL</div>
    <div class="alert-title" id="alert-title">系統錯誤</div>
    <div class="alert-desc" id="alert-desc"></div>
    <button class="alert-close" onclick="closeAlert()">確認</button>
  </div>
</div>

<script>
let countdown=5,timer=null,lastData=null,currentArticleName='';
let selectedAgentId=null,currentLogTab='cron';

const FM=[
  {id:'researcher',icon:'◎',label:'研究員',phase:'探索'},
  {id:'topic-selector',icon:'◈',label:'選題',phase:'策略'},
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

/* PIPELINE */
function renderPipeline(data){
  const flow=data.flow||[],st={};
  flow.forEach(a=>{st[a.id]=a;});
  const rows=[FM.slice(0,6),FM.slice(6)];
  rows.forEach((agents,ri)=>{
    const el=document.getElementById('pipe-row'+(ri+1));
    if(!el)return;
    el.innerHTML=agents.map((a,i)=>{
      const s=(st[a.id]||{}).status||'idle';
      return `<div class="pa ${s}" onclick="selectAgent('${a.id}')">
        <span class="pa-icon">${a.icon}</span>
        <span class="pa-name">${a.label}</span>
        <span class="pa-phase">${a.phase}</span>
        <span class="pa-dot"></span>
      </div>${i<agents.length-1?'<span class="arr">→</span>':''}`;
    }).join('');
  });
}

/* SIDEBAR */
function renderSidebar(data){
  const flow=data.flow||[],st={};
  flow.forEach(a=>{st[a.id]=a;});
  const el=document.getElementById('sb-agents');if(!el)return;
  el.innerHTML=FM.map(a=>{
    const s=(st[a.id]||{}).status||'idle';
    const stxt=s==='working'?'工作中':s==='waiting'?'等待中':'休息中';
    return `<div class="agent-card ${s}${selectedAgentId===a.id?' selected':''}" onclick="selectAgent('${a.id}')">
      <div class="ac-icon">${a.icon}</div>
      <div class="ac-info">
        <div class="ac-name">${a.label}</div>
        <div class="ac-status ${s}">${stxt}</div>
      </div>
    </div>`;
  }).join('');
}

/* SELECT AGENT */
function selectAgent(id){
  selectedAgentId=id;
  document.querySelectorAll('.rp-tab').forEach((t,i)=>{t.classList.toggle('active',i===0);});
  document.querySelectorAll('.rp-pane').forEach(p=>p.classList.remove('active'));
  document.getElementById('pane-agent').classList.add('active');
  if(!lastData)return;
  const aInfo=(lastData.flow||[]).find(a=>a.id===id);
  if(!aInfo){document.getElementById('ad-inner').innerHTML='<div style="padding:20px;color:var(--t2)">無資料</div>';return;}
  const s=aInfo.status||'idle';
  const sc={working:'b-ok',waiting:'b-warn',idle:'b-brand'};
  const stxt=s==='working'?'工作中':s==='waiting'?'等待中':'休息中';
  const readItems=(aInfo.reads_stat||[]).map(r=>{
    const ok=r.stat&&r.stat.ok;
    const age=ok&&r.stat.age!=null?`<span class="file-age">${r.stat.age}分前</span>`:'';
    return `<div class="file-item"><span class="file-dot ${ok?'ok':'miss'}"></span><span class="file-path">${esc(r.path)}</span>${age}</div>`;
  }).join('');
  const writeItems=(aInfo.writes_stat||[]).map(r=>{
    const ok=r.stat&&r.stat.ok;
    return `<div class="file-item"><span class="file-dot ${ok?'ok':'miss'}"></span><span class="file-path">${esc(r.path)}</span></div>`;
  }).join('');
  const skillPills=(aInfo.skills_avail||[]).map(s=>`<span class="pill ${s.ok?'sk':'sk-x'}">${esc(s.name)}</span>`).join('');
  const hookPills=(aInfo.hooks_avail||[]).map(h=>`<span class="pill ${h.ok?'hk':'hk-x'}">${esc(h.name)}</span>`).join('');
  document.getElementById('ad-inner').innerHTML=`
    <div class="ad-head">
      <div class="ad-icon">${aInfo.icon}</div>
      <div><div class="ad-name">${esc(aInfo.label)}</div>
        <div class="ad-badges">
          <span class="badge ${sc[s]||'b-brand'}">${stxt}</span>
          <span class="badge b-pur">${esc(aInfo.phase)}</span>
        </div>
      </div>
    </div>
    <div class="ad-desc">${esc(aInfo.desc||'')}</div>
    ${readItems?`<div class="ad-sec"><div class="ad-sl">讀取</div>${readItems}</div>`:''}
    ${writeItems?`<div class="ad-sec"><div class="ad-sl">寫入</div>${writeItems}</div>`:''}
    ${skillPills?`<div class="ad-sec"><div class="ad-sl">Skills</div><div class="pills">${skillPills}</div></div>`:''}
    ${hookPills?`<div class="ad-sec"><div class="ad-sl">Hooks</div><div class="pills">${hookPills}</div></div>`:''}`;
  if(lastData)renderSidebar(lastData);
}

/* KPI */
function renderKPI(data){
  const prog=data.pipeline||{},usage=data.usage||{};
  document.getElementById('k0').textContent=prog.count||0;
  document.getElementById('k1').textContent=data.article_count||0;
  document.getElementById('k2').textContent=usage.today||0;
  document.getElementById('k3').textContent=usage.total||0;
  const sc=(data.diag||{}).score||0;
  const k4=document.getElementById('k4');
  k4.className='kpi-v '+(sc>=80?'ok':sc>=50?'warn':'err');
  k4.textContent=sc+'%';
  document.getElementById('k7').textContent=((data.api||{}).model||'--').slice(0,15);
}

/* STATUS PILL */
function renderStatus(data){
  const pill=document.getElementById('spill'),stxt=document.getElementById('stxt');
  const s=data.state||'idle';
  pill.className='status-pill '+(s==='running'?'s-run':s==='error'?'s-err':'s-idle');
  stxt.textContent=s==='running'?'RUNNING':s==='error'?'ERROR':'IDLE';
  document.getElementById('ts').textContent=data.ts||'--';
}

/* REVENUE */
async function fetchRevenue(){
  try{
    const r=await fetch('/api/revenue');const d=await r.json();
    const total=d.total_revenue||0,cost=d.monthly_cost||200,gap=total-cost;
    document.getElementById('k5').textContent='$'+total;
    const k6=document.getElementById('k6');
    k6.textContent=(gap>=0?'+':'')+'$'+gap;
    k6.className='kpi-v '+(gap>=0?'ok':'warn');
    // Revenue panel
    document.getElementById('rev-total-amt').textContent='$'+total;
    const rg=document.getElementById('rev-gap-amt');
    rg.textContent=(gap>=0?'+':'')+'$'+gap;
    rg.style.color=gap>=0?'var(--ok)':'var(--warn)';
    document.getElementById('rev-bar').style.width=Math.min(100,Math.round(total/cost*100))+'%';
    const plats=d.platforms||{};
    document.getElementById('rev-platforms').innerHTML=Object.entries(plats).map(([k,v])=>
      `<div class="rev-row"><span class="rev-name">${esc(v.product||k)}</span><span class="rev-val">$${v.revenue||0}${v.sales!=null?' ('+v.sales+'筆)':''}</span></div>`
    ).join('')||'<div style="color:var(--t2);font-size:9px;padding:8px 0">尚無收益資料</div>';
  }catch(e){}
}

/* PROPOSALS */
function renderProposals(){
  fetch('/api/proposals').then(r=>r.json()).then(d=>{
    const el=document.getElementById('sb-proposals');if(!el)return;
    const lines=(d.content||'').split('\n').filter(l=>l.startsWith('## 提案-'));
    const ph=el.querySelector('.sb-ph');
    if(ph)ph.innerHTML='● 提案待審核'+(lines.length>0?' <b style="color:var(--pur)">('+lines.length+')</b>':'');
    el.querySelectorAll('.sb-p-item,.sb-p-empty').forEach(i=>i.remove());
    if(lines.length===0){
      el.insertAdjacentHTML('beforeend','<div class="sb-p-empty">目前無提案</div>');
    }else{
      lines.slice(-3).reverse().forEach(l=>{
        const t=l.replace('## 提案-','').trim();
        el.insertAdjacentHTML('beforeend',`<div class="sb-p-item" title="${esc(t)}">${esc(t)}</div>`);
      });
    }
  }).catch(()=>{});
}

/* LOG */
const LC={APPROVED:'ok',REJECTED:'warn',ERROR:'err',error:'err',Failed:'err',failed:'err',WARNING:'warn',INFO:'info'};
function colorLine(l){for(const[k,c]of Object.entries(LC)){if(l.includes(k))return c;}return 'normal';}
function renderLog(data,tab){
  const el=document.getElementById('log-display');if(!el)return;
  const lines=tab==='cron'?data.cron_log_tail||[]:data.error_log||[];
  el.innerHTML=lines.slice(-80).map(l=>`<div class="log-line ${colorLine(l)}">${esc(l)}</div>`).join('');
  el.scrollTop=el.scrollHeight;
}
function switchLog(tab,el){
  currentLogTab=tab;
  document.querySelectorAll('.log-tab').forEach(t=>t.classList.remove('active'));
  if(el)el.classList.add('active');
  if(tab==='standup'){
    fetch('/api/standup').then(r=>r.json()).then(d=>{
      document.getElementById('log-display').innerHTML=(d.recent||[]).map(l=>`<div class="log-line ${colorLine(l)}">${esc(l)}</div>`).join('');
    }).catch(()=>{});
  }else if(lastData){renderLog(lastData,tab);}
}

/* TABS */
function switchTab(id,el){
  document.querySelectorAll('.rp-tab').forEach(t=>t.classList.remove('active'));
  if(el)el.classList.add('active');
  document.querySelectorAll('.rp-pane').forEach(p=>p.classList.remove('active'));
  const pane=document.getElementById('pane-'+id);if(pane)pane.classList.add('active');
}

/* ARTICLES */
function renderArticles(data){
  const arts=data.articles||[];
  document.getElementById('arts-count').textContent=arts.length+' 篇';
  document.getElementById('arts-list').innerHTML=arts.map(a=>
    `<div class="art-item" onclick="openArticle('${esc(a.name)}')">
      <span class="art-dot"></span>
      <span class="art-title">${esc(a.title)}</span>
      <span class="art-w">${a.words}字</span>
    </div>`
  ).join('')||'<div style="padding:20px;text-align:center;color:var(--t2);font-size:10px">尚無文章</div>';
}

/* MAIN FETCH */
async function fetchNow(){
  try{
    const r=await fetch('/api/status');const d=await r.json();
    lastData=d;
    renderStatus(d);renderKPI(d);renderPipeline(d);renderSidebar(d);
    if(currentLogTab!=='standup')renderLog(d,currentLogTab);
    renderArticles(d);renderProposals();fetchRevenue();
    checkAlerts(d);
    if(selectedAgentId)selectAgent(selectedAgentId);
    countdown=5;
  }catch(e){console.error(e);}
}

/* ALERTS */
function checkAlerts(data){
  const errs=(data.error_log||[]).filter(l=>l.trim()&&l.includes('ERROR'));
  if(errs.length>0&&!document.getElementById('alert-ov').classList.contains('show'))
    showAlert('CRITICAL','系統錯誤',errs.slice(-1)[0],'err');
}
function showAlert(level,title,desc,type){
  document.getElementById('alert-level').textContent=level;
  document.getElementById('alert-title').textContent=title;
  document.getElementById('alert-desc').textContent=desc;
  document.getElementById('alert-box').className='alert-box'+(type==='warn'?' warn-type':'');
  document.getElementById('alert-ov').classList.add('show');
  document.body.classList.add('alerting');
}
function closeAlert(){
  document.getElementById('alert-ov').classList.remove('show');
  document.body.classList.remove('alerting');
}

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
function triggerTopic(){
  const t=document.getElementById('topic-input').value.trim();if(!t)return;
  document.getElementById('chat-in').value='強制執行今日主題：'+t;
  sendChat();switchTab('chat',null);
}
function saveSettings(){
  const token=document.getElementById('set-token').value.trim();
  const guide=document.getElementById('set-whop-guide').value.trim();
  let msg='設定已記錄。請在 VPS 執行：\n\n';
  if(token)msg+='ANTHROPIC_AUTH_TOKEN 更新\n';
  if(guide)msg+='Whop Guide URL: '+guide+'\n';
  alert(msg||'請先填入設定值');
}

/* MODAL */
let devtoName='';
async function openArticle(name){
  devtoName=name;
  document.getElementById('mtitle').textContent=name;
  document.getElementById('mbody').textContent='載入中...';
  document.getElementById('mfoot').textContent='';
  document.getElementById('devto-btn').disabled=false;
  document.getElementById('devto-btn').textContent='→ dev.to 草稿';
  document.getElementById('modal').classList.add('open');
  try{
    const r=await fetch('/api/article/'+encodeURIComponent(name));
    const d=await r.json();
    document.getElementById('mbody').textContent=d.content||'（無內容）';
    document.getElementById('mfoot').textContent=(d.content||'').split(/\s+/).length+' 詞';
  }catch(e){document.getElementById('mbody').textContent='載入失敗';}
}
function closeModal(e){
  if(!e||e.target===document.getElementById('modal'))
    document.getElementById('modal').classList.remove('open');
}
async function postToDevto(){
  const btn=document.getElementById('devto-btn');
  btn.disabled=true;btn.textContent='發布中...';
  try{
    const r=await fetch('/api/devto',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:devtoName})});
    const d=await r.json();
    if(d.ok){btn.textContent='✓ 已建立草稿';document.getElementById('mfoot').textContent='URL: '+(d.url||'草稿');}
    else{btn.textContent='✗ 失敗';btn.disabled=false;document.getElementById('mfoot').textContent=d.error||'';}
  }catch(e){btn.textContent='錯誤';btn.disabled=false;}
}

/* CHAT */
function chatKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}}
async function sendChat(){
  const inp=document.getElementById('chat-in');
  const msg=inp.value.trim();if(!msg)return;
  inp.value='';
  const msgs=document.getElementById('chat-msgs');
  msgs.insertAdjacentHTML('beforeend',`<div class="cm user">${esc(msg)}</div>`);
  msgs.scrollTop=msgs.scrollHeight;
  document.getElementById('chat-btn').disabled=true;
  document.getElementById('chat-typing').style.display='block';
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const d=await r.json();
    msgs.insertAdjacentHTML('beforeend',`<div class="cm ai">${esc(d.reply||'')}</div>`);
  }catch(e){msgs.insertAdjacentHTML('beforeend','<div class="cm ai">❌ 連接失敗</div>');}
  document.getElementById('chat-btn').disabled=false;
  document.getElementById('chat-typing').style.display='none';
  msgs.scrollTop=msgs.scrollHeight;
}

/* TIMER */
function startTimer(){
  timer=setInterval(()=>{countdown--;if(countdown<=0){fetchNow();countdown=5;}},1000);
}
fetchNow();startTimer();
setInterval(()=>{if(currentLogTab!=='standup'&&lastData)renderLog(lastData,currentLogTab);},2000);
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
            # Path-based: /api/article/article-name
            raw=self.path[len("/api/article/"):]
            name=urllib.parse.unquote(raw)
            if name and re.match(r'^[\w\-\.]{1,100}$',name):
                c=get_article_content(name)
                if c:
                    self._json(json.dumps({"content":c},ensure_ascii=False).encode())
                    return
            self.send_response(404); self.end_headers()
        elif self.path.startswith("/api/article"):
            # Legacy query-param: /api/article?name=X
            parsed=urllib.parse.urlparse(self.path)
            params=urllib.parse.parse_qs(parsed.query)
            name=params.get("name",[""])[0]
            if name and re.match(r'^[\w\-\.]{1,100}$',name):
                c=get_article_content(name)
                if c:
                    self._json(json.dumps({"content":c},ensure_ascii=False).encode())
                    return
            self.send_response(404); self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
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
        self.end_headers()
        self.wfile.write(data)

    def log_message(self,*a): pass

if __name__=="__main__":
    port=int(os.environ.get("DASHBOARD_PORT",3000))
    print(f"Dashboard v9 指揮中心啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0",port),Handler).serve_forever()
