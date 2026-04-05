#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v9
— 像素辦公室：PixiJS 空間型辦公室 + 3 欄佈局 + 對話氣泡 + 檔案飛行動畫
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
#  資料函數（Python backend — 與 v7 相同，不動）
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
        # Minimax API 使用 ANTHROPIC_AUTH_TOKEN；標準 Anthropic 使用 ANTHROPIC_API_KEY
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
        # Minimax API 使用 Authorization: Bearer，標準 Anthropic 使用 x-api-key
        is_minimax = "minimax" in base_url.lower() or "api.minimax" in base_url.lower()
        if is_minimax:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        else:
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
        req = urllib.request.Request(f"{base_url}/v1/messages", data=payload,
            headers=headers)
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

# ══════════════════════════════════════════════════════════
#  HTML — Dashboard v8 像素辦公室
# ══════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 無人工廠 v9 — 指揮中心</title>
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/pixi.js@7.3.2/dist/pixi.min.js"></script>
<style>
:root{
  --bg0:#0D1117;--bg1:#161B22;--bg2:#1C2333;--bg3:#21262D;
  --b0:#30363D;--b1:#484F58;
  --t0:#E6EDF3;--t1:#8B949E;--t2:#484F58;
  --brand:#58A6FF;--brand-s:rgba(88,166,255,.10);--brand-m:rgba(88,166,255,.20);
  --ok:#3FB950;--ok-s:rgba(63,185,80,.12);
  --warn:#D29922;--warn-s:rgba(210,153,34,.12);
  --err:#F85149;--err-s:rgba(248,81,73,.12);
  --info:#58A6FF;--info-s:rgba(88,166,255,.10);
  --pur:#BC8CFF;--pur-s:rgba(188,140,255,.12);
  --px:'Press Start 2P',monospace;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;overflow:hidden;background:var(--bg0);color:var(--t0);
  font-family:'Hiragino Sans','Noto Sans TC',system-ui,sans-serif;
  font-size:12px;line-height:1.6;}
body{display:flex;flex-direction:column;}
@keyframes pls{0%,100%{opacity:1;}50%{opacity:.2;}}
@keyframes borderGlow{0%,100%{box-shadow:0 0 0 0 rgba(63,185,80,.4);}50%{box-shadow:0 0 6px 2px rgba(63,185,80,.2);}}

/* TOPBAR */
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:0 14px;height:42px;background:var(--bg1);
  border-bottom:2px solid var(--b0);flex-shrink:0;z-index:300;}
.logo{font-family:var(--px);font-size:9px;color:var(--brand);
  display:flex;align-items:center;gap:10px;}
.logo-v{font-size:7px;color:var(--t2);font-family:var(--px);}
.spill{display:flex;align-items:center;gap:5px;padding:2px 9px;
  border:1px solid var(--b0);font-size:9px;font-weight:700;background:var(--bg2);}
.sdot{width:6px;height:6px;border-radius:50%;}
.si .sdot{background:var(--t2);} .sr .sdot{background:var(--ok);animation:pls 1.5s infinite;} .se .sdot{background:var(--err);}
.si .stxt{color:var(--t2);} .sr .stxt{color:var(--ok);} .se .stxt{color:var(--err);}
.tb-r{display:flex;align-items:center;gap:10px;}
.ts-t{font-size:9px;color:var(--t2);}
.cdt{font-size:9px;color:var(--brand);min-width:20px;}
.rbtn{background:none;border:1px solid var(--b0);color:var(--t2);
  padding:3px 9px;cursor:pointer;font-size:9px;transition:.2s;}
.rbtn:hover{border-color:var(--brand);color:var(--brand);}

/* WARN STRIP */
.warn-strip{background:rgba(210,153,34,.08);border-bottom:1px solid rgba(210,153,34,.25);
  padding:4px 14px;font-size:10px;color:var(--warn);display:none;align-items:center;gap:8px;flex-shrink:0;}

/* KPI BAR */
.kpi-bar{display:grid;grid-template-columns:repeat(8,1fr);
  background:var(--bg1);border-bottom:2px solid var(--b0);flex-shrink:0;}
.kpi-c{padding:7px 10px;border-right:1px solid var(--b0);transition:.15s;}
.kpi-c:last-child{border-right:none;}
.kpi-c:hover{background:var(--bg2);}
.kpi-v{font-family:var(--px);font-size:13px;line-height:1.2;color:var(--t0);}
.kpi-v.accent{color:var(--brand);} .kpi-v.ok{color:var(--ok);} .kpi-v.warn{color:var(--warn);} .kpi-v.err{color:var(--err);}
.kpi-l{font-size:8px;color:var(--t2);margin-top:3px;}

/* 3-COL WORKSPACE */
.workspace{flex:1;display:grid;grid-template-columns:178px 1fr 298px;overflow:hidden;}

/* SIDEBAR */
.sidebar{background:var(--bg1);border-right:2px solid var(--b0);
  display:flex;flex-direction:column;overflow:hidden;}
.sb-head{padding:8px 10px;font-family:var(--px);font-size:7px;
  color:var(--brand);border-bottom:1px solid var(--b0);letter-spacing:.1em;flex-shrink:0;}
.sb-filter{display:flex;gap:3px;padding:5px 8px;flex-shrink:0;border-bottom:1px solid var(--b0);}
.sb-f{font-size:8px;font-weight:700;padding:2px 7px;border:1px solid var(--b0);cursor:pointer;
  color:var(--t2);transition:.15s;font-family:var(--px);}
.sb-f.active{border-color:var(--brand);color:var(--brand);background:var(--brand-s);}
.sb-list{flex:1;overflow-y:auto;padding:4px 6px;}
.sb-list::-webkit-scrollbar{width:3px;}
.sb-list::-webkit-scrollbar-thumb{background:var(--b0);}
.sb-agent{display:flex;align-items:center;gap:7px;padding:5px 6px;
  cursor:pointer;transition:.15s;border:1px solid transparent;margin-bottom:2px;}
.sb-agent:hover{background:var(--bg3);}
.sb-agent.selected{border-color:var(--brand);background:var(--brand-s);}
.sb-avatar{width:26px;height:26px;border:1px solid var(--b0);
  display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}
.sb-agent.working .sb-avatar{border-color:var(--ok);animation:borderGlow 1.4s infinite;}
.sb-agent.waiting .sb-avatar{border-color:var(--warn);}
.sb-info{flex:1;min-width:0;}
.sb-name{font-size:8px;font-weight:700;color:var(--t0);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--px);}
.sb-badge{display:inline-block;font-size:7px;font-weight:700;padding:1px 5px;margin-top:2px;font-family:var(--px);}
.sb-badge.working{background:rgba(63,185,80,.15);color:var(--ok);}
.sb-badge.waiting{background:rgba(210,153,34,.15);color:var(--warn);}
.sb-badge.idle{background:var(--bg3);color:var(--t2);}
.sb-health{padding:6px 8px;border-top:1px solid var(--b0);flex-shrink:0;}
.sb-hr{display:flex;justify-content:space-between;padding:2px 0;font-size:9px;}
.sb-hl{color:var(--t2);}
.sb-hv.ok{color:var(--ok);} .sb-hv.warn{color:var(--warn);} .sb-hv.err{color:var(--err);} .sb-hv.info{color:var(--info);}

/* CENTER OFFICE CANVAS */
.office-wrap{background:var(--bg0);display:flex;align-items:flex-start;
  justify-content:center;overflow:auto;padding:8px;}
.office-wrap canvas{image-rendering:pixelated;display:block;}
#pixi-fb{color:var(--t2);font-size:10px;padding:30px;text-align:center;}

/* RIGHT PANEL */
.right-panel{background:var(--bg1);border-left:2px solid var(--b0);
  display:flex;flex-direction:column;overflow:hidden;}
.rp-tabs{display:flex;border-bottom:2px solid var(--b0);flex-shrink:0;}
.rp-tab{flex:1;padding:7px 2px;text-align:center;font-size:8px;font-weight:700;
  cursor:pointer;color:var(--t2);border-right:1px solid var(--b0);
  font-family:var(--px);transition:.15s;}
.rp-tab:last-child{border-right:none;}
.rp-tab.active{color:var(--brand);background:var(--brand-s);}
.rp-tab:hover:not(.active){color:var(--t1);}
.rp-pane{flex:1;overflow-y:auto;display:none;flex-direction:column;}
.rp-pane.active{display:flex;}
.rp-pane::-webkit-scrollbar{width:3px;}
.rp-pane::-webkit-scrollbar-thumb{background:var(--b0);}

/* AGENT DETAIL */
.ad-head{display:flex;align-items:center;gap:9px;padding:10px 12px;
  border-bottom:1px solid var(--b0);flex-shrink:0;}
.ad-icon{width:36px;height:36px;border:1px solid var(--b0);
  display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}
.ad-name{font-size:11px;font-weight:700;color:var(--t0);}
.ad-badges{display:flex;gap:4px;margin-top:4px;flex-wrap:wrap;}
.badge{display:inline-flex;padding:2px 6px;font-size:8.5px;font-weight:700;}
.b-ok{background:var(--ok-s);color:var(--ok);}
.b-warn{background:var(--warn-s);color:var(--warn);}
.b-brand{background:var(--brand-s);color:var(--brand);}
.b-pur{background:var(--pur-s);color:var(--pur);}
.b-info{background:var(--info-s);color:var(--info);}
.ad-desc{padding:8px 12px;font-size:10.5px;color:var(--t1);line-height:1.6;
  border-bottom:1px solid var(--b0);}
.ad-sec{padding:7px 12px;}
.ad-sl{font-size:8px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:var(--t2);margin-bottom:5px;font-family:var(--px);}
.file-item{display:flex;align-items:center;gap:5px;font-size:10px;padding:2px 0;}
.file-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.file-dot.ok{background:var(--ok);} .file-dot.miss{background:var(--b0);}
.file-path{color:var(--t1);font-family:'SF Mono',Menlo,monospace;font-size:9.5px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:170px;}
.file-age{font-size:9px;color:var(--t2);white-space:nowrap;flex-shrink:0;}
.pills{display:flex;flex-wrap:wrap;gap:3px;}
.pill{font-size:8.5px;padding:2px 6px;white-space:nowrap;}
.pill.sk{background:var(--brand-s);color:var(--brand);}
.pill.sk-x{background:var(--bg3);color:var(--t2);}
.pill.hk{background:var(--ok-s);color:var(--ok);}
.pill.hk-x{background:var(--err-s);color:var(--err);}
.empty{color:var(--t2);font-style:italic;font-size:10px;padding:4px 0;}

/* FEED */
.feed-body{padding:6px 10px;}
.fi{display:flex;gap:7px;padding:5px 0;border-bottom:1px solid var(--b0);}
.fi:last-child{border-bottom:none;}
.fi-dot{width:6px;height:6px;border-radius:50%;margin-top:4px;flex-shrink:0;}
.fi-dot.success{background:var(--ok);} .fi-dot.warn{background:var(--warn);}
.fi-dot.error{background:var(--err);} .fi-dot.info{background:var(--t2);}
.fi-b{flex:1;min-width:0;}
.fi-badge{display:inline-block;font-size:8px;font-weight:700;padding:1px 5px;margin-bottom:2px;}
.fi-msg{font-size:10px;color:var(--t1);line-height:1.5;word-break:break-word;}
.fi-t{font-size:9px;color:var(--t2);margin-top:1px;}

/* CHAT */
.chat-msgs{flex:1;overflow-y:auto;padding:9px 10px;
  display:flex;flex-direction:column;gap:6px;min-height:80px;}
.chat-msgs::-webkit-scrollbar{width:3px;}
.chat-msgs::-webkit-scrollbar-thumb{background:var(--b0);}
.cm{max-width:94%;padding:6px 9px;font-size:11px;line-height:1.6;white-space:pre-wrap;}
.cm.user{background:var(--brand-s);border:1px solid var(--brand-m);color:var(--t0);align-self:flex-end;}
.cm.ai{background:var(--bg2);border:1px solid var(--b0);color:var(--t1);align-self:flex-start;}
.cm.sys{background:var(--warn-s);border:1px solid rgba(210,153,34,.2);
  color:var(--warn);align-self:center;font-size:9.5px;text-align:center;}
.chat-typing{color:var(--t2);font-size:9px;padding:2px 10px;animation:pls 1s infinite;flex-shrink:0;}
.chat-row{display:flex;gap:5px;padding:7px 8px;border-top:1px solid var(--b0);flex-shrink:0;}
.chat-in{flex:1;background:var(--bg2);border:1px solid var(--b0);
  color:var(--t0);padding:5px 9px;font-size:10.5px;font-family:inherit;
  outline:none;resize:none;transition:border-color .2s;}
.chat-in:focus{border-color:var(--brand);}
.chat-send{background:var(--brand);color:#fff;border:none;
  padding:5px 11px;cursor:pointer;font-size:10.5px;font-weight:700;transition:.15s;}
.chat-send:hover{background:#4493e0;}
.chat-send:disabled{opacity:.4;cursor:not-allowed;}

/* ARTICLES */
.arts-body{padding:5px 8px;}
.art-item{display:flex;align-items:center;gap:7px;padding:5px 3px;
  cursor:pointer;transition:.15s;border-bottom:1px solid var(--b0);}
.art-item:hover{background:var(--bg3);}
.art-item:last-child{border-bottom:none;}
.art-dot{width:6px;height:6px;border-radius:50%;background:var(--ok);flex-shrink:0;}
.art-title{flex:1;font-size:10px;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.art-w{font-size:9px;color:var(--t2);flex-shrink:0;}

/* MODAL */
.modal-ov{display:none;position:fixed;inset:0;z-index:500;
  background:rgba(0,0,0,.75);backdrop-filter:blur(5px);
  align-items:flex-start;justify-content:center;padding:36px 20px;}
.modal-ov.open{display:flex;}
.modal-box{background:var(--bg1);border:1px solid var(--b0);
  width:100%;max-width:800px;max-height:85vh;display:flex;flex-direction:column;
  box-shadow:0 20px 60px rgba(0,0,0,.6);}
.modal-hd{padding:10px 16px;border-bottom:1px solid var(--b0);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.modal-title{font-size:12px;font-weight:700;color:var(--t0);}
.modal-close{width:24px;height:24px;background:var(--bg2);border:1px solid var(--b0);
  color:var(--t2);cursor:pointer;font-size:12px;
  display:flex;align-items:center;justify-content:center;transition:.2s;}
.modal-close:hover{border-color:var(--brand);color:var(--brand);}
.modal-bd{flex:1;overflow-y:auto;padding:14px 18px;
  font-family:'SF Mono',Menlo,monospace;font-size:11.5px;
  line-height:1.9;color:var(--t1);white-space:pre-wrap;word-break:break-word;}
.modal-bd::-webkit-scrollbar{width:4px;}
.modal-bd::-webkit-scrollbar-thumb{background:var(--b0);}
.modal-ft{padding:6px 16px;border-top:1px solid var(--b0);
  font-size:9.5px;color:var(--t2);display:flex;align-items:center;gap:8px;flex-shrink:0;}
.devto-btn{background:var(--ok-s);color:var(--ok);border:1px solid rgba(63,185,80,.3);
  padding:3px 10px;font-size:9.5px;cursor:pointer;font-weight:700;transition:.2s;}
.devto-btn:hover{background:rgba(63,185,80,.2);}
.ch{padding:8px 12px;display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--b0);flex-shrink:0;}
.ct{font-size:8.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:var(--t2);display:flex;align-items:center;gap:5px;}
.cdot2{width:5px;height:5px;border-radius:50%;}
</style>
</head>
<body>

<nav class="topbar">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="logo">⬡ AI FACTORY<span class="logo-v">v9 HQ</span></div>
    <div class="spill si" id="spill"><span class="sdot"></span><span class="stxt">INIT</span></div>
  </div>
  <div class="tb-r">
    <span class="ts-t" id="ts">--</span>
    <span style="color:var(--t2)">·</span>
    <span class="cdt" id="cdt">5s</span>
    <button class="rbtn" onclick="fetchNow()">⟳ REFRESH</button>
  </div>
</nav>

<div class="warn-strip" id="wstrip">⚠ WHOP 連結尚未設定 — CLAUDE.md 含 PLACEHOLDER_WHOP_*</div>

<div class="kpi-bar">
  <div class="kpi-c"><div class="kpi-v accent" id="k0">0</div><div class="kpi-l">今日產出</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k1">0</div><div class="kpi-l">文章總數</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k2">0</div><div class="kpi-l">API 今日</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k3">0</div><div class="kpi-l">API 累計</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k4">--</div><div class="kpi-l">系統健康</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k5" style="font-size:9px;">--</div><div class="kpi-l">模型</div></div>
  <div class="kpi-c"><div class="kpi-v ok" id="k6">$0</div><div class="kpi-l">本月收益</div></div>
  <div class="kpi-c"><div class="kpi-v warn" id="k7">-$200</div><div class="kpi-l">距損益平衡</div></div>
</div>

<div class="workspace">

  <!-- LEFT SIDEBAR -->
  <div class="sidebar">
    <div class="sb-head">▣ TEAM STATUS</div>
    <div class="sb-filter">
      <div class="sb-f active" onclick="setSbFilter('all',this)">ALL</div>
      <div class="sb-f" onclick="setSbFilter('working',this)">WORK</div>
      <div class="sb-f" onclick="setSbFilter('idle',this)">IDLE</div>
    </div>
    <div class="sb-list" id="sb-list"></div>
    <div class="sb-health" id="sb-health"></div>
  </div>

  <!-- CENTER OFFICE CANVAS -->
  <div class="office-wrap" id="office-wrap">
    <div id="pixi-fb">PixiJS 載入中...<br><small style="color:var(--t2)">需要網路連線至 cdn.jsdelivr.net</small></div>
  </div>

  <!-- RIGHT PANEL -->
  <div class="right-panel">
    <div class="rp-tabs">
      <div class="rp-tab active" onclick="switchTab('detail',this)">AGENT</div>
      <div class="rp-tab" onclick="switchTab('feed',this)">活動</div>
      <div class="rp-tab" onclick="switchTab('chat',this)">聊天</div>
      <div class="rp-tab" onclick="switchTab('arts',this)">文章</div>
      <div class="rp-tab" onclick="switchTab('standup',this);loadStandup()">DAILY</div>
    </div>
    <div class="rp-pane active" id="pane-detail">
      <div id="ad-inner">
        <div style="padding:20px;text-align:center;color:var(--t2);font-size:10px;">
          點擊左側房間查看 Agent 詳情
        </div>
      </div>
    </div>
    <div class="rp-pane" id="pane-feed">
      <div class="ch" style="flex-shrink:0;">
        <div class="ct"><span class="cdot2" style="background:var(--brand);animation:pls 2s infinite;"></span>活動流</div>
      </div>
      <div class="feed-body" id="feed-list" style="flex:1;overflow-y:auto;"></div>
    </div>
    <div class="rp-pane" id="pane-chat">
      <div class="ch" style="flex-shrink:0;">
        <div class="ct"><span class="cdot2" style="background:var(--brand)"></span>控制台聊天</div>
        <span style="font-size:8px;color:var(--t2)">系統感知</span>
      </div>
      <div class="chat-msgs" id="chat-msgs">
        <div class="cm sys">AI 助手就緒 — 詢問系統狀態或設定問題</div>
      </div>
      <div id="chat-typing" class="chat-typing" style="display:none;">AI 回覆中...</div>
      <div class="chat-row">
        <textarea class="chat-in" id="chat-in" rows="2"
          placeholder="目前狀態？如何設定 API？" onkeydown="chatKey(event)"></textarea>
        <button class="chat-send" id="chat-btn" onclick="sendChat()">送出</button>
      </div>
    </div>
    <div class="rp-pane" id="pane-arts">
      <div class="ch" style="flex-shrink:0;">
        <div class="ct"><span class="cdot2" style="background:var(--ok)"></span>文章庫</div>
        <span id="arts-count" style="font-size:9px;color:var(--t2)"></span>
      </div>
      <div class="arts-body" id="arts-list" style="flex:1;overflow-y:auto;"></div>
    </div>
    <div class="rp-pane" id="pane-standup">
      <div class="ch" style="flex-shrink:0;">
        <div class="ct"><span class="cdot2" style="background:var(--pur);animation:pls 3s infinite;"></span>每日 Standup</div>
        <span style="font-size:8px;color:var(--t2)">08/16/00 自動</span>
      </div>
      <div id="standup-body" style="flex:1;overflow-y:auto;padding:10px;font-size:9px;line-height:1.7;color:var(--t1);white-space:pre-wrap;"></div>
    </div>
  </div>

</div><!-- /workspace -->

<!-- MODAL -->
<div class="modal-ov" id="modal" onclick="closeModal(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-hd">
      <div class="modal-title" id="mtitle">文章內容</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-bd" id="mbody">載入中...</div>
    <div class="modal-ft">
      <span id="mfoot" style="flex:1;"></span>
      <button class="devto-btn" id="devto-btn" onclick="postToDevto()">→ dev.to 草稿</button>
    </div>
  </div>
</div>

<script>
/* ─── GLOBALS ─── */
let countdown=5,timer,lastData=null,currentArticleName='';
let sbFilter='all',selectedId=null;
let pixiApp=null,roomC={},agentD={},fileAnims=[],prevWId=null;
const bubTmr={};

/* ─── PIPELINE META (mirrors Python PIPELINE_FLOW) ─── */
const FM=[
  {id:'researcher',order:1,label:'研究員',icon:'◎',phase:'探索',desc:'爬蟲 4 個 subreddit，評估需求，找 Amazon 聯盟商品'},
  {id:'topic-selector',order:2,label:'選題',icon:'◈',phase:'策略',desc:'合併需求信號，決定唯一下一篇主題，避免重複'},
  {id:'writer',order:3,label:'中文初稿',icon:'✦',phase:'生產',desc:'產出中文教學文章，植入 Whop 銷售連結'},
  {id:'seo-agent',order:4,label:'SEO',icon:'S',phase:'生產',desc:'產出 3 個標題候選，優化關鍵字位置'},
  {id:'english-writer',order:5,label:'英文寫手',icon:'E',phase:'生產',desc:'Reddit 摘要版 + Medium 完整版'},
  {id:'chinese-writer',order:6,label:'中文詮釋',icon:'中',phase:'生產',desc:'詮釋為台灣 Maker 中文版'},
  {id:'reviewer',order:7,label:'審稿',icon:'◉',phase:'品管',desc:'5 道自動關卡 + 邏輯審查'},
  {id:'poster',order:8,label:'發文',icon:'◆',phase:'發布',desc:'發布到 Reddit / Medium / dev.to'},
  {id:'feedback-collector',order:9,label:'回報收集',icon:'F',phase:'回饋',desc:'發文後 24h 收集 upvotes/comments'},
  {id:'style-updater',order:10,label:'風格進化',icon:'↺',phase:'進化',desc:'根據表現更新 writing-style.md'},
  {id:'knowledge-subagent',order:11,label:'知識庫',icon:'K',phase:'進化',desc:'任務結束前寫入知識庫'},
];
const FMI={};FM.forEach(a=>FMI[a.id]=a);

const PHEX={'探索':0x1F6FEB,'策略':0x8957E5,'生產':0x388BFD,'品管':0xD29922,'發布':0x3FB950,'回饋':0xD29922,'進化':0xBC8CFF};
const PCSS={'探索':'#1F6FEB','策略':'#8957E5','生產':'#388BFD','品管':'#D29922','發布':'#3FB950','回饋':'#D29922','進化':'#BC8CFF'};
const SHEX={working:0x3FB950,waiting:0xD29922,idle:0x484F58,done:0x3FB950};
const FEDC={writer:'#388BFD',researcher:'#1F6FEB',reviewer:'#D29922',poster:'#3FB950','quality-check':'#D29922','topic-selector':'#8957E5',system:'#8B949E',feedback:'#BC8CFF'};
const BLNS={
  researcher:['爬蟲中...','分析需求...','找到商品！'],
  'topic-selector':['比較主題...','避免重複...','已選定！'],
  writer:['寫作中...','加入範例碼...','完稿！','植入連結...'],
  'seo-agent':['優化標題...','SEO完成！'],
  'english-writer':['翻譯中...','英文稿完成！'],
  'chinese-writer':['詮釋中...','中文稿完成！'],
  reviewer:['審核中...','品質檢查...','通過 ✓'],
  poster:['準備發文...','發文成功！'],
  'feedback-collector':['收集回饋...','數據更新！'],
  'style-updater':['分析風格...','進化完成！'],
  'knowledge-subagent':['記錄中...','完成！'],
};

/* ─── ROOM LAYOUT ─── */
const CIDS=['researcher','topic-selector','writer','reviewer','poster','feedback-collector'];
const RLYT={'researcher':{c:0,r:0},'topic-selector':{c:1,r:0},'writer':{c:0,r:1},'reviewer':{c:1,r:1},'poster':{c:0,r:2},'feedback-collector':{c:1,r:2}};
const SIDS=['seo-agent','english-writer','chinese-writer','style-updater','knowledge-subagent'];
const RW=214,RH=120,RG=12,RP=10,SW=82,SH=60,SG=7;
const SY=RP+3*(RH+RG)+6;
const CW=RP*2+RW*2+RG, CH=SY+SH+RP;

function rOrg(id){
  if(RLYT[id]){const {c,r}=RLYT[id];return{x:RP+c*(RW+RG),y:RP+r*(RH+RG)};}
  const si=SIDS.indexOf(id);if(si>=0)return{x:RP+si*(SW+SG),y:SY};
  return null;
}
function rCtr(id){
  const o=rOrg(id);if(!o)return null;
  const s=SIDS.includes(id);return{x:o.x+(s?SW:RW)/2,y:o.y+(s?SH:RH)/2};
}

/* ─── PIXI INIT ─── */
function initPixi(){
  if(pixiApp)return;
  if(typeof PIXI==='undefined'){
    document.getElementById('pixi-fb').innerHTML='<span style="color:var(--err)">PixiJS 載入失敗</span><br><small>請檢查網路或改用純 CSS 版</small>';
    return;
  }
  const fb=document.getElementById('pixi-fb');if(fb)fb.remove();
  pixiApp=new PIXI.Application({width:CW,height:CH,backgroundColor:0x0D1117,antialias:false,resolution:1});
  pixiApp.view.style.imageRendering='pixelated';
  document.getElementById('office-wrap').appendChild(pixiApp.view);
  buildRooms(); buildAgents();
  pixiApp.ticker.add(tick);
}

/* ─── BUILD ROOMS ─── */
function buildRooms(){
  Object.values(roomC).forEach(c=>pixiApp.stage.removeChild(c));roomC={};
  CIDS.forEach(id=>mkRoom(id,RW,RH,false));
  SIDS.forEach(id=>mkRoom(id,SW,SH,true));
}
function mkRoom(id,w,h,isS){
  const m=FMI[id];if(!m)return;
  const o=rOrg(id);if(!o)return;
  const col=PHEX[m.phase]||0x58A6FF;
  const c=new PIXI.Container();c.x=o.x;c.y=o.y;
  c.interactive=true;c.cursor='pointer';
  c.on('pointerdown',()=>onRC(id));
  c.on('pointerover',()=>hlRoom(c,true));
  c.on('pointerout',()=>hlRoom(c,false));

  const bg=new PIXI.Graphics();
  bg.beginFill(0x161B22);bg.drawRect(0,0,w,h);bg.endFill();
  for(let ty=0;ty<h;ty+=4)for(let tx=0;tx<w;tx+=4){
    if((Math.floor(tx/4)+Math.floor(ty/4))%2===0){bg.beginFill(0x1A2030,.45);bg.drawRect(tx,ty,4,4);bg.endFill();}
  }
  c.addChild(bg);

  const bdr=new PIXI.Graphics();
  bdr.lineStyle(2,col,.75);bdr.drawRect(0,0,w,h);
  c.addChild(bdr);c._bdr=bdr;c._col=col;c._w=w;c._h=h;c._hl=false;

  if(!isS){
    const dk=new PIXI.Graphics();
    dk.beginFill(0x3D2B1F);dk.drawRect(w/2-22,h-38,44,13);dk.endFill();
    dk.beginFill(0x2A1C10);dk.drawRect(w/2-18,h-25,6,9);dk.drawRect(w/2+12,h-25,6,9);dk.endFill();
    c.addChild(dk);
  }
  const lbl=new PIXI.Text(m.label,{fontFamily:'Courier New,monospace',fontSize:isS?7:8,fill:col,fontWeight:'bold'});
  lbl.x=5;lbl.y=5;c.addChild(lbl);
  const ord=new PIXI.Text('#'+m.order,{fontFamily:'Courier New,monospace',fontSize:7,fill:0x484F58});
  ord.x=w-ord.width-5;ord.y=5;c.addChild(ord);

  pixiApp.stage.addChild(c);roomC[id]=c;
}
function hlRoom(c,on){
  if(!c._bdr)return;c._hl=on||c._sel;
  c._bdr.clear();
  const col=c._hl?0xCCDDFF:c._col;
  const lw=c._hl?2:1,alpha=c._hl?1:.75;
  c._bdr.lineStyle(lw,col,alpha);c._bdr.drawRect(0,0,c._w,c._h);
}
function selRoom(id){
  Object.entries(roomC).forEach(([rid,rc])=>{
    rc._sel=(rid===id);hlRoom(rc,false);
  });
}

/* ─── BUILD AGENTS ─── */
function buildAgents(){
  Object.values(agentD).forEach(d=>{if(d.c.parent)d.c.parent.removeChild(d.c);});agentD={};
  [...CIDS,...SIDS].forEach(id=>mkAgent(id));
}
function mkAgent(id){
  const m=FMI[id];if(!m)return;
  const rc=roomC[id];if(!rc)return;
  const isS=SIDS.includes(id);
  const col=PHEX[m.phase]||0x58A6FF;
  const dk=Math.floor(col*.55);
  const c=new PIXI.Container();
  const g=new PIXI.Graphics();
  if(isS){
    g.beginFill(col);g.drawCircle(0,-11,5);g.endFill();
    g.beginFill(dk);g.drawRect(-3,-6,6,8);g.endFill();
  } else {
    g.beginFill(col);g.drawCircle(0,-19,7);g.endFill();
    g.beginFill(dk);g.drawRect(-5,-12,10,12);g.endFill();
    g.beginFill(0x30363D);g.drawRect(-4,0,3,6);g.drawRect(1,0,3,6);g.endFill();
  }
  c.addChild(g);
  const ico=new PIXI.Text(m.icon,{fontFamily:'monospace',fontSize:isS?8:10,fill:0xE6EDF3});
  ico.anchor.set(.5);ico.y=isS?-23:-34;c.addChild(ico);
  const dot=new PIXI.Graphics();c.addChild(dot);c._dot=dot;
  const bub=new PIXI.Container();bub.visible=false;
  bub._bg=new PIXI.Graphics();bub._tx=new PIXI.Text('...',{fontFamily:'Courier New,monospace',fontSize:isS?7:8,fill:0xE6EDF3,wordWrap:true,wordWrapWidth:isS?66:84});
  bub.addChild(bub._bg);bub.addChild(bub._tx);
  bub.y=isS?-36:-50;c.addChild(bub);c._bub=bub;
  const w=isS?SW:RW,h=isS?SH:RH;
  c.x=w/2;c.y=isS?h-15:h-25;c._by=c.y;
  rc.addChild(c);
  agentD[id]={c,dot,bub,_st:'idle',_col:col,_isS:isS};
  updDot(id,'idle');
}
function updDot(id,st){
  const d=agentD[id];if(!d)return;
  const col=SHEX[st]||0x484F58,isS=d._isS;
  d.dot.clear();d.dot.beginFill(col);
  d.dot.drawCircle(isS?6:9,isS?-17:-25,4);d.dot.endFill();
}

/* ─── ANIMATION TICKER ─── */
function tick(){
  const t=Date.now();
  Object.entries(agentD).forEach(([id,d])=>{
    if(d._st==='working'){d.c.y=d.c._by+Math.sin(t*.0028)*2.5;d.c.alpha=1;}
    else if(d._st==='waiting'){d.c.alpha=.45+Math.abs(Math.sin(t*.0016))*.45;d.c.y=d.c._by;}
    else{d.c.alpha=.45;d.c.y=d.c._by;}
  });
  fileAnims=fileAnims.filter(a=>{
    a.t+=16.67;const p=Math.min(a.t/900,1);
    const e=p<.5?2*p*p:-1+(4-2*p)*p;
    const cpx=(a.sx+a.ex)/2,cpy=Math.min(a.sy,a.ey)-52;
    a.g.x=(1-e)*(1-e)*a.sx+2*(1-e)*e*cpx+e*e*a.ex;
    a.g.y=(1-e)*(1-e)*a.sy+2*(1-e)*e*cpy+e*e*a.ey;
    a.g.alpha=p>.75?(1-p)/.25:1;a.g.rotation+=.06;
    if(p>=1){pixiApp.stage.removeChild(a.g);return false;}return true;
  });
}
function spawnFile(sx,sy,ex,ey){
  if(!pixiApp)return;
  const g=new PIXI.Graphics();
  g.beginFill(0x58A6FF,.9);g.drawRect(-5,-6,10,12);g.endFill();
  g.lineStyle(1,0xE6EDF3,.4);g.moveTo(2,-6);g.lineTo(5,-3);g.lineTo(5,-6);
  g.x=sx;g.y=sy;pixiApp.stage.addChild(g);
  fileAnims.push({g,sx,sy,ex,ey,t:0});
}

/* ─── BUBBLE MANAGEMENT ─── */
function setBub(id,txt){
  const d=agentD[id];if(!d)return;
  const b=d.bub,isS=d._isS;
  b._tx.text=txt;
  const tw=Math.max(b._tx.width,16)+10,th=b._tx.height+8;
  b._bg.clear();
  b._bg.beginFill(0x1C2333,.97);b._bg.lineStyle(1,d._col||0x58A6FF,.8);
  b._bg.drawRoundedRect(-tw/2,-th,tw,th,3);b._bg.endFill();
  b._bg.beginFill(0x1C2333,.97);
  b._bg.moveTo(-4,0);b._bg.lineTo(0,6);b._bg.lineTo(4,0);b._bg.endFill();
  b._tx.x=-tw/2+5;b._tx.y=-th+4;b.visible=true;
}
function startBub(id){
  if(bubTmr[id])return;
  const ls=BLNS[id]||['工作中...'];let i=0;setBub(id,ls[0]);
  bubTmr[id]=setInterval(()=>{
    if(agentD[id]?._st!=='working'){stopBub(id);return;}
    i=(i+1)%ls.length;setBub(id,ls[i]);
  },2200);
}
function stopBub(id){
  if(bubTmr[id]){clearInterval(bubTmr[id]);delete bubTmr[id];}
  const d=agentD[id];if(d)d.bub.visible=false;
}

/* ─── UPDATE OFFICE (on each data refresh) ─── */
function updOffice(flow,pipe){
  if(!pixiApp)return;
  const bi={};(flow||[]).forEach(a=>bi[a.id]=a);
  const nw=(flow||[]).find(a=>a.status==='working');
  const nwId=nw?nw.id:null;
  if(nwId&&prevWId&&nwId!==prevWId){
    const fo=rCtr(prevWId),to=rCtr(nwId);
    const frc=roomC[prevWId],trc=roomC[nwId];
    if(fo&&to&&frc&&trc) spawnFile(fo.x+frc.x,fo.y+frc.y,to.x+trc.x,to.y+trc.y);
  }
  prevWId=nwId;
  (flow||[]).forEach(a=>{
    const d=agentD[a.id];if(!d)return;
    d._st=a.status;updDot(a.id,a.status);
    if(a.status==='working')startBub(a.id);else stopBub(a.id);
  });
}
function onRC(id){
  selectedId=id;selRoom(id);
  document.querySelectorAll('.rp-tab').forEach((t,i)=>{t.classList.toggle('active',i===0);});
  document.querySelectorAll('.rp-pane').forEach((p,i)=>{p.classList.toggle('active',i===0);});
  document.querySelectorAll('.sb-agent').forEach(el=>el.classList.toggle('selected',el.dataset.id===id));
  if(lastData)showAD(id,lastData.flow||[]);
}

/* ─── FETCH & RENDER ─── */
async function fetchNow(){
  clearInterval(timer);countdown=5;
  try{const r=await fetch('/api/status');const d=await r.json();lastData=d;render(d);}
  catch(e){setPill('se','OFFLINE');}
  fetchRevenue();
  startTimer();
}
async function fetchRevenue(){
  try{
    const r=await fetch('/api/revenue');const d=await r.json();
    const rev=d.total_revenue||0,cost=d.monthly_cost||200;
    const gap=rev-cost;
    document.getElementById('k6').textContent='$'+rev;
    document.getElementById('k6').className='kpi-v '+(rev>0?'ok':'warn');
    document.getElementById('k7').textContent=(gap>=0?'+':'')+'$'+gap;
    document.getElementById('k7').className='kpi-v '+(gap>=0?'ok':'warn');
  }catch(e){}
}
function startTimer(){
  clearInterval(timer);
  timer=setInterval(()=>{countdown--;const e=document.getElementById('cdt');if(e)e.textContent=countdown+'s';if(countdown<=0)fetchNow();},1000);
}
function render(d){
  document.getElementById('ts').textContent=d.ts;
  document.getElementById('wstrip').style.display=d.has_placeholder?'flex':'none';
  const sm={idle:'si',running:'sr',error:'se'},tx={idle:'IDLE',running:'RUNNING',error:'ERROR'};
  setPill(sm[d.state]||'si',tx[d.state]||d.state);
  document.getElementById('k0').textContent=d.pipeline?.count||0;
  document.getElementById('k1').textContent=d.article_count||0;
  document.getElementById('k2').textContent=d.usage?.today||0;
  document.getElementById('k3').textContent=d.usage?.total||0;
  const sc=d.diag?.score??100,se=document.getElementById('k4');
  se.textContent=sc+'%';se.className='kpi-v '+(sc>=85?'ok':sc>=60?'warn':'err');
  document.getElementById('k5').textContent=(d.api?.model||'--').slice(0,18);
  if(!pixiApp)initPixi();
  updOffice(d.flow||[],d.pipeline||{});
  renderSB(d.flow||[],d.diag||{});
  renderFeed(d.feed||[]);
  renderArts(d.articles||[]);
  if(selectedId)showAD(selectedId,d.flow||[]);
}
function setPill(cls,lbl){
  const el=document.getElementById('spill');el.className='spill '+cls;
  el.querySelector('.stxt').textContent=lbl;
}

/* ─── SIDEBAR ─── */
function setSbFilter(f,btn){
  sbFilter=f;document.querySelectorAll('.sb-f').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');if(lastData)renderSB(lastData.flow||[],lastData.diag||{});
}
function renderSB(flow,diag){
  const bi={};(flow||[]).forEach(a=>bi[a.id]=a);
  const vis=FM.filter(m=>{
    const a=bi[m.id];
    if(sbFilter==='working')return a?.status==='working';
    if(sbFilter==='idle')return a?.status!=='working';
    return true;
  });
  document.getElementById('sb-list').innerHTML=vis.map(m=>{
    const a=bi[m.id]||{},st=a.status||'idle',pc=PCSS[m.phase]||'#58A6FF';
    const sel=m.id===selectedId?' selected':'';
    return '<div class="sb-agent '+st+sel+'" data-id="'+esc(m.id)+'" onclick="onRC(\''+esc(m.id)+'\')">'
      +'<div class="sb-avatar" style="border-color:'+pc+'40;color:'+pc+'">'+esc(m.icon)+'</div>'
      +'<div class="sb-info"><div class="sb-name">'+esc(m.label.toUpperCase())+'</div>'
      +'<span class="sb-badge '+st+'">'+esc((a.status_txt||st).toUpperCase())+'</span></div></div>';
  }).join('');
  const h=diag.health||[];
  document.getElementById('sb-health').innerHTML=h.map(it=>'<div class="sb-hr"><span class="sb-hl">'+esc(it.name)+'</span><span class="sb-hv '+esc(it.status)+'">'+esc(it.val)+'</span></div>').join('')
    +'<div class="sb-hr" style="margin-top:4px;"><span class="sb-hl">健康度</span>'
    +'<span class="sb-hv '+(diag.score>=85?'ok':diag.score>=60?'warn':'err')+'">'+esc(String(diag.score??'--'))+'%</span></div>';
}

/* ─── AGENT DETAIL ─── */
function showAD(id,flow){
  const a=(flow||[]).find(x=>x.id===id);if(!a)return;
  const pc=PCSS[a.phase]||'#58A6FF';
  const sm={working:'b-ok',waiting:'b-warn',idle:'b-info',done:'b-ok'};
  const r=(a.reads_stat||[]).map(x=>fih(x.path,x.stat)).join('');
  const w=(a.writes_stat||[]).map(x=>fih(x.path,x.stat)).join('');
  const sk=(a.skills_avail||[]).map(s=>'<span class="pill '+(s.ok?'sk':'sk-x')+'">'+esc(s.name)+'</span>').join('');
  const hk=(a.hooks_avail||[]).map(h=>'<span class="pill '+(h.ok?'hk':'hk-x')+'">'+esc(h.name)+'</span>').join('');
  document.getElementById('ad-inner').innerHTML=
    '<div class="ad-head"><div class="ad-icon" style="border-color:'+pc+'40;color:'+pc+'">'+esc(a.icon)+'</div>'
    +'<div><div class="ad-name">'+esc(a.label)+'</div>'
    +'<div class="ad-badges"><span class="badge b-brand" style="color:'+pc+';background:'+pc+'18">'+esc(a.phase)+'</span>'
    +'<span class="badge '+(sm[a.status]||'b-info')+'">'+esc(a.status_txt||a.status)+'</span>'
    +'<span class="badge" style="background:var(--bg3);color:var(--t2)">#'+esc(String(a.order||''))+'</span>'
    +'</div></div></div>'
    +'<div class="ad-desc">'+esc(a.desc||'')+'</div>'
    +'<div class="ad-sec"><div class="ad-sl">INPUT</div>'+(r||'<div class="empty">—</div>')+'</div>'
    +'<div class="ad-sec"><div class="ad-sl">OUTPUT</div>'+(w||'<div class="empty">—</div>')+'</div>'
    +'<div class="ad-sec"><div class="ad-sl">SKILLS ('+esc(String((a.skills_avail||[]).length))+')</div><div class="pills">'+(sk||'<div class="empty">—</div>')+'</div></div>'
    +'<div class="ad-sec"><div class="ad-sl">HOOKS ('+esc(String((a.hooks_avail||[]).length))+')</div><div class="pills">'+(hk||'<div class="empty">—</div>')+'</div></div>';
}
function fih(path,stat){
  const ok=stat&&stat.ok,sh=path.split('/').pop().replace(/（.*?）/g,'');
  const age=ok?(stat.age<1440?stat.age+'m前':Math.floor(stat.age/1440)+'d前'):'';
  return '<div class="file-item"><div class="file-dot '+(ok?'ok':'miss')+'"></div>'
    +'<span class="file-path" title="'+esc(path)+'">'+esc(sh)+'</span>'
    +'<span class="file-age">'+esc(age)+'</span></div>';
}

/* ─── FEED ─── */
function renderFeed(feed){
  const el=document.getElementById('feed-list');
  if(!feed||!feed.length){el.innerHTML='<div class="empty" style="padding:14px;">尚無活動</div>';return;}
  el.innerHTML=feed.map(f=>{
    const col=FEDC[f.agent]||'#8B949E';
    return '<div class="fi"><div class="fi-dot '+esc(f.type)+'"></div>'
      +'<div class="fi-b"><span class="fi-badge" style="background:'+col+'18;color:'+col+';border:1px solid '+col+'30">'+esc(f.agent)+'</span>'
      +'<div class="fi-msg">'+esc(f.msg)+'</div>'+(f.time?'<div class="fi-t">'+esc(f.time)+'</div>':'')+'</div></div>';
  }).join('');
}

/* ─── ARTICLES ─── */
function renderArts(arts){
  const el=document.getElementById('arts-list'),cnt=document.getElementById('arts-count');
  if(!arts||!arts.length){el.innerHTML='<div class="empty" style="padding:12px;">尚無文章</div>';if(cnt)cnt.textContent='';return;}
  if(cnt)cnt.textContent=arts.length+' 篇';
  el.innerHTML=arts.slice(0,15).map(a=>
    '<div class="art-item" onclick="openArticle(\''+esc(a.name)+'\',\''+esc(a.title)+'\')">'
    +'<div class="art-dot"></div>'
    +'<div class="art-title" title="'+esc(a.title)+'">'+esc(a.title)+'</div>'
    +'<div class="art-w">'+esc(String(a.words))+'w</div></div>'
  ).join('');
}

/* ─── TAB SWITCH ─── */
function switchTab(name,btn){
  document.querySelectorAll('.rp-tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  const mp={detail:'pane-detail',feed:'pane-feed',chat:'pane-chat',arts:'pane-arts',standup:'pane-standup'};
  document.querySelectorAll('.rp-pane').forEach(p=>p.classList.remove('active'));
  const t=document.getElementById(mp[name]);if(t)t.classList.add('active');
}
async function loadStandup(){
  const el=document.getElementById('standup-body');
  if(!el)return;
  el.textContent='載入中...';
  try{
    const r=await fetch('/api/standup');const d=await r.json();
    const lines=(d.recent||[]).filter(l=>l.trim());
    el.textContent=lines.length?lines.join('\n'):'（尚無 standup 記錄）\n每天 08:00、16:00、00:00 自動生成';
  }catch(e){el.textContent='載入失敗';}
}

/* ─── CHAT ─── */
function addMsg(role,text){
  const box=document.getElementById('chat-msgs');
  const el=document.createElement('div');el.className='cm '+role;el.textContent=text;
  box.appendChild(el);box.scrollTop=box.scrollHeight;
}
async function sendChat(){
  const inp=document.getElementById('chat-in');const msg=inp.value.trim();if(!msg)return;
  inp.value='';addMsg('user',msg);
  document.getElementById('chat-btn').disabled=true;
  document.getElementById('chat-typing').style.display='block';
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const d=await r.json();addMsg('ai',d.reply||'（無回應）');
  }catch(e){addMsg('sys','連線失敗：'+e);}
  document.getElementById('chat-btn').disabled=false;
  document.getElementById('chat-typing').style.display='none';
  // switch to chat pane
  document.querySelectorAll('.rp-tab')[2].click();
}
function chatKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}}

/* ─── ARTICLE MODAL ─── */
async function openArticle(name,title){
  currentArticleName=name;
  document.getElementById('mtitle').textContent=title||name;
  document.getElementById('mbody').textContent='載入中...';
  document.getElementById('mfoot').textContent='';
  const b=document.getElementById('devto-btn');b.disabled=false;b.textContent='→ dev.to 草稿';
  document.getElementById('modal').classList.add('open');
  try{
    const r=await fetch('/api/article?name='+encodeURIComponent(name));
    if(r.ok){const t=await r.text();document.getElementById('mbody').textContent=t;document.getElementById('mfoot').textContent=name+'.md · '+t.split(/\s+/).length+' 詞';}
    else document.getElementById('mbody').textContent='找不到文章。';
  }catch(e){document.getElementById('mbody').textContent='載入失敗：'+e;}
}
async function postToDevto(){
  if(!currentArticleName)return;
  const btn=document.getElementById('devto-btn');btn.disabled=true;btn.textContent='發布中...';
  try{
    const r=await fetch('/api/post-devto',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:currentArticleName})});
    const d=await r.json();
    if(d.ok){btn.textContent='✓ 草稿建立';document.getElementById('mfoot').textContent+=' · '+(d.url||'草稿');}
    else{btn.textContent='✗ '+d.error.slice(0,35);btn.disabled=false;}
  }catch(e){btn.textContent='連線失敗';btn.disabled=false;}
}
function closeModal(e){if(!e||e.target.id==='modal')document.getElementById('modal').classList.remove('open');}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal({target:{id:'modal'}});});

function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

fetchNow();
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
            d = rj(".team-memory/revenue-tracking.json", {})
            self._json(json.dumps(d, ensure_ascii=False).encode())
        elif self.path=="/api/proposals":
            f = BASE/".team-memory/proposals.md"
            content = f.read_text(encoding="utf-8") if f.exists() else ""
            self._json(json.dumps({"content": content}, ensure_ascii=False).encode())
        elif self.path=="/api/standup":
            f = BASE/".team-memory/standup-log.md"
            lines = f.read_text(encoding="utf-8").strip().split("\n") if f.exists() else []
            self._json(json.dumps({"recent": lines[-30:]}, ensure_ascii=False).encode())
        elif self.path.startswith("/api/article"):
            parsed=urllib.parse.urlparse(self.path)
            params=urllib.parse.parse_qs(parsed.query)
            name=params.get("name",[""])[0]
            if name and re.match(r'^[\w\-\.]{1,100}$',name):
                c=get_article_content(name)
                if c:
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin","*")
                    self.end_headers()
                    self.wfile.write(c.encode("utf-8")); return
            self.send_response(404); self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

    def do_POST(self):
        length=int(self.headers.get("Content-Length",0))
        body=json.loads(self.rfile.read(length))
        if self.path=="/api/chat":
            msg=body.get("message","").strip()
            reply=do_chat(msg) if msg else "請輸入訊息。"
            self._json(json.dumps({"reply":reply},ensure_ascii=False).encode())
        elif self.path=="/api/post-devto":
            name=body.get("name","")
            result=post_to_devto(name) if name else {"ok":False,"error":"缺少 name"}
            self._json(json.dumps(result,ensure_ascii=False).encode())
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
    print(f"Dashboard v9 啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0",port),Handler).serve_forever()
