#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v6
— 完整流程看板：11 Agent × 26 Skill × 11 Hook × 檔案傳遞可視化 + 智能聊天
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

# agent 之間的檔案傳遞標示（顯示在連接線上）
FILE_TRANSFERS = [
  ["demand_signals.json","affiliate-links.json"],   # 1→2
  ["progress.json（主題）"],                          # 2→3
  ["articles/*.md"],                                  # 3→4
  ["articles/*.md（SEO完成）"],                       # 4→5
  ["articles/*-medium.md"],                           # 5→6
  ["articles/*-zh.md"],                               # 6→7
  ["articles/*.md（審核通過）"],                      # 7→8
  ["reddit-history.json"],                            # 8→9
  ["topic-performance.json"],                         # 9→10
  ["writing-style.md（更新）"],                       # 10→11
]

PHASE_COLOR = {
  "探索":"#8193A8","策略":"#8B85A0","生產":"#727A8C",
  "品管":"#B89B72","發布":"#7C9A7E","回饋":"#B89B72","進化":"#8B85A0",
}

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
        return (env.get("ANTHROPIC_API_KEY",""),
                env.get("ANTHROPIC_BASE_URL","https://api.anthropic.com").rstrip("/"),
                env.get("ANTHROPIC_MODEL","claude-3-5-sonnet-20241022"))
    except: return ("","https://api.anthropic.com","claude-3-5-sonnet-20241022")

def cron_lines():
    try:
        r = subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=3)
        return [l for l in r.stdout.splitlines() if "ai-factory" in l]
    except: return []

def file_stat(path_str):
    """回傳檔案狀態（是否存在、距今幾分鐘、大小）"""
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
    clog   = " ".join(rt("logs/cron.log",50)).lower()
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
            "agent":"writer","msg":f"文章完成：{p.get('title','')}","type":"success"})
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
            "desc":"demand_signals.json 不存在，researcher 尚未執行","tag":"狀態"})

    prog = rj("logs/progress.json",[])
    if len(prog)>=4:
        recent = " ".join(p.get("title","") for p in prog[-5:])
        for kw in ["電容","壓力","手勢","IoT","ESP32"]:
            if recent.count(kw)>=2:
                issues.append({"level":"info","title":"主題略偏集中",
                    "desc":f"近期「{kw}」題材偏多","tag":"內容"}); break

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
    """給 chat AI 的系統狀態摘要"""
    state  = rj("logs/progress.json",[])
    diag   = run_diagnostics()
    api    = api_status()
    crons  = cron_lines()
    knows  = knowledge_summary()
    perf   = rj("logs/topic-performance.json",{})
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
        return "⚠ 未設定 ANTHROPIC_API_KEY，無法使用聊天。請確認 ~/.claude/settings.json 有 ANTHROPIC_API_KEY。"
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
        req = urllib.request.Request(f"{base_url}/v1/messages", data=payload,
            headers={"x-api-key":api_key,"anthropic-version":"2023-06-01",
                     "content-type":"application/json"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read())
            reply  = result["content"][0]["text"]
            _chat_history.append({"role":"user","content":message})
            _chat_history.append({"role":"assistant","content":reply})
            return reply
    except Exception as e:
        return f"❌ API 錯誤：{str(e)[:150]}"

def post_to_devto(article_name):
    """發布文章草稿到 dev.to（需要 DEVTO_API_KEY 環境變數）"""
    api_key = os.environ.get("DEVTO_API_KEY","")
    if not api_key:
        try:
            s = json.loads(Path.home().joinpath(".claude/settings.json").read_text())
            api_key = s.get("env",{}).get("DEVTO_API_KEY","")
        except: pass
    if not api_key:
        return {"ok":False,"error":"未設定 DEVTO_API_KEY。請在 ~/.claude/settings.json 加入 DEVTO_API_KEY。"}
    content = get_article_content(article_name)
    if not content: return {"ok":False,"error":"找不到文章"}
    lines = content.splitlines()
    title = next((l.lstrip("#").strip() for l in lines if l.startswith("#")), article_name)
    try:
        payload = json.dumps({"article":{
            "title": title,
            "body_markdown": content,
            "published": False,  # 先存草稿供審閱
            "tags": ["arduino","sensors","maker","diy"]
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
    perf   = rj("logs/topic-performance.json",{})
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

    # 為每個 pipeline agent 加上 file_stat
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
        "perf":         perf.get("categories",{}),
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
#  HTML
# ══════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 無人工廠 v6</title>
<style>
:root{
  --bg0:#F6F3EE; --bg1:#FBFAF7; --bg2:#F1EEE8; --bg3:#E8E3DA;
  --b0:#D8D2C7; --b1:#C4BDB5; --ba:#727A8C;
  --t0:#2F2A24; --t1:#5B544C; --t2:#8A837A;
  --brand:#727A8C; --brand-s:rgba(114,122,140,0.10); --brand-m:rgba(114,122,140,0.20);
  --ok:#7C9A7E; --ok-s:rgba(124,154,126,0.12);
  --warn:#B89B72; --warn-s:rgba(184,155,114,0.12);
  --err:#B36A6A; --err-s:rgba(179,106,106,0.12);
  --info:#8193A8; --info-s:rgba(129,147,168,0.10);
  --pur:#8B85A0; --pur-s:rgba(139,133,160,0.12);
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{min-height:100%;background:var(--bg0);color:var(--t0);
  font-family:'Hiragino Sans','Noto Sans TC',system-ui,-apple-system,sans-serif;
  font-size:13px;line-height:1.6;}

/* ── TOPBAR ── */
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:50px;background:var(--bg1);
  border-bottom:1px solid var(--b0);position:sticky;top:0;z-index:300;}
.tb-l{display:flex;align-items:center;gap:14px;}
.logo{font-size:14px;font-weight:700;color:var(--brand);display:flex;align-items:center;gap:7px;}
.logo-sub{font-size:11.5px;color:var(--t2);font-weight:400;}
.spill{display:flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;
  font-size:11px;font-weight:600;background:var(--bg2);border:1px solid var(--b0);}
.sdot{width:6px;height:6px;border-radius:50%;}
.si .sdot{background:var(--t2);}
.sr .sdot{background:var(--ok);animation:pls 1.5s infinite;}
.se .sdot{background:var(--err);}
.si .stxt{color:var(--t2);} .sr .stxt{color:var(--ok);} .se .stxt{color:var(--err);}
@keyframes pls{0%,100%{opacity:1;}50%{opacity:.3;}}
.tb-r{display:flex;align-items:center;gap:12px;}
.ts-t{font-size:11px;color:var(--t2);}
.cdt{font-size:11px;color:var(--brand);font-variant-numeric:tabular-nums;min-width:22px;}
.rbtn{background:none;border:1px solid var(--b0);color:var(--t2);
  padding:4px 12px;border-radius:6px;cursor:pointer;font-size:11px;transition:.2s;}
.rbtn:hover{border-color:var(--brand);color:var(--brand);}

/* ── WARN STRIP ── */
.warn-strip{background:rgba(184,155,114,.07);border-bottom:1px solid rgba(184,155,114,.22);
  padding:6px 28px;font-size:11.5px;color:var(--warn);display:none;align-items:center;gap:8px;}

/* ── KPI BAR ── */
.kpi-bar{display:grid;grid-template-columns:repeat(6,1fr);
  background:var(--bg1);border-bottom:1px solid var(--b0);}
.kpi-c{padding:11px 18px;border-right:1px solid var(--b0);transition:.15s;}
.kpi-c:last-child{border-right:none;}
.kpi-c:hover{background:var(--bg2);}
.kpi-v{font-size:22px;font-weight:700;letter-spacing:-.4px;line-height:1;color:var(--t0);}
.kpi-v.accent{color:var(--brand);}
.kpi-v.ok{color:var(--ok);} .kpi-v.warn{color:var(--warn);} .kpi-v.err{color:var(--err);}
.kpi-l{font-size:10px;color:var(--t2);margin-top:3px;}

/* ── LAYOUT ── */
.main{display:grid;grid-template-columns:1fr 300px;gap:16px;padding:20px 28px;
  max-width:1520px;margin:0 auto;}
.left{display:flex;flex-direction:column;gap:16px;}

/* ── CARD ── */
.card{background:var(--bg1);border:1px solid var(--b0);border-radius:12px;overflow:hidden;
  box-shadow:0 1px 3px rgba(50,40,30,.04);transition:box-shadow .2s,border-color .2s;}
.card:hover{border-color:var(--b1);box-shadow:0 2px 8px rgba(50,40,30,.06);}
.ch{padding:12px 18px 10px;display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--b0);}
.ct{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--t2);display:flex;align-items:center;gap:6px;}
.cdot{width:5px;height:5px;border-radius:50%;}
.cb{padding:14px 18px;}

/* ══════════════════════════════════
   PIPELINE FLOW BOARD
══════════════════════════════════ */
.flow-board{padding:14px 18px 18px;display:flex;flex-direction:column;gap:0;}

/* 每個 agent 的卡片 */
.pf-card{
  border:1px solid var(--b0);border-radius:10px;
  background:var(--bg1);overflow:hidden;transition:.25s;
}
.pf-card:hover{border-color:var(--b1);box-shadow:0 2px 8px rgba(50,40,30,.05);}
.pf-card.working{border-color:rgba(114,122,140,.35);background:var(--brand-s);}
.pf-card.waiting{opacity:.7;}
.pf-card.idle{opacity:.85;}

/* 卡片頭部 */
.pf-head{
  display:flex;align-items:center;gap:12px;padding:10px 14px;
  cursor:pointer;user-select:none;
}
.pf-num{width:20px;height:20px;border-radius:50%;background:var(--bg3);
  font-size:9.5px;font-weight:700;color:var(--t2);display:flex;align-items:center;
  justify-content:center;flex-shrink:0;}
.pf-card.working .pf-num{background:var(--brand);color:#fff;}
.pf-icon{font-size:18px;width:28px;text-align:center;flex-shrink:0;}
.pf-card.working .pf-icon{animation:working 1.2s ease-in-out infinite;}
@keyframes working{0%,100%{transform:scale(1);}50%{transform:scale(1.12);}}
.pf-name-col{flex:1;min-width:0;}
.pf-name{font-size:13px;font-weight:700;color:var(--t0);}
.pf-desc{font-size:11px;color:var(--t2);line-height:1.4;margin-top:1px;}
.pf-phase{font-size:9.5px;font-weight:700;padding:2px 7px;border-radius:999px;
  letter-spacing:.05em;margin-right:6px;}
.pf-sbadge{font-size:10px;font-weight:600;padding:2px 8px;border-radius:999px;}
.pf-sbadge.working{background:var(--brand-s);color:var(--brand);}
.pf-sbadge.waiting{background:var(--bg3);color:var(--t2);}
.pf-sbadge.idle{background:var(--bg3);color:var(--t2);}
.pf-toggle{font-size:11px;color:var(--t2);margin-left:4px;transition:.2s;}

/* 卡片詳情（可折疊）*/
.pf-body{border-top:1px solid var(--b0);padding:12px 14px;background:var(--bg2);}
.pf-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;}
.pf-section-label{font-size:9.5px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:var(--t2);margin-bottom:5px;}

/* 檔案列表 */
.file-item{
  display:flex;align-items:center;gap:5px;
  font-size:10.5px;padding:2px 0;
}
.file-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.file-dot.ok{background:var(--ok);}
.file-dot.miss{background:var(--b0);}
.file-path{color:var(--t1);font-family:'SF Mono',Menlo,monospace;font-size:10px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:160px;}
.file-age{font-size:9.5px;color:var(--t2);white-space:nowrap;flex-shrink:0;}

/* Skill / Hook pills */
.pill-list{display:flex;flex-wrap:wrap;gap:4px;}
.pill{font-size:9.5px;padding:2px 7px;border-radius:999px;white-space:nowrap;}
.pill.skill-ok{background:var(--brand-s);color:var(--brand);}
.pill.skill-miss{background:var(--bg3);color:var(--t2);}
.pill.hook-ok{background:var(--ok-s);color:var(--ok);}
.pill.hook-miss{background:var(--err-s);color:var(--err);}

/* 檔案傳遞連接線 */
.pf-transfer{
  display:flex;align-items:center;gap:8px;
  padding:5px 0 5px 24px;
}
.pf-tline{width:1px;height:20px;background:var(--b0);margin:0 7px;flex-shrink:0;}
.pf-tfiles{display:flex;flex-wrap:wrap;gap:4px;}
.pf-tfile{
  font-size:9.5px;padding:2px 8px;border-radius:999px;
  background:var(--bg2);border:1px solid var(--b0);
  color:var(--t2);font-family:'SF Mono',Menlo,monospace;
}

/* ── KNOWLEDGE LOOP ── */
.know-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.know-box{background:var(--bg2);border:1px solid var(--b0);border-radius:8px;padding:11px;}
.know-label{font-size:10.5px;font-weight:700;color:var(--t1);margin-bottom:5px;}
.know-val{font-size:20px;font-weight:800;color:var(--pur);letter-spacing:-.4px;line-height:1;}
.know-sub{font-size:10px;color:var(--t2);margin-top:2px;}
.know-bar{background:var(--b0);border-radius:3px;height:2px;margin-top:6px;overflow:hidden;}
.know-fill{height:100%;background:var(--pur);border-radius:3px;}
.learn-arrow{
  font-size:11px;color:var(--t2);text-align:center;padding:8px 0;
  letter-spacing:.06em;
}

/* ── MID ROW ── */
.mid-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;}

/* ── DIAG ── */
.dh{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:10px;}
.hp{background:var(--bg2);border:1px solid var(--b0);border-radius:7px;
  padding:8px 10px;text-align:center;}
.hp-n{font-size:9.5px;color:var(--t2);margin-bottom:2px;}
.hp-v{font-size:13px;font-weight:700;}
.hp-v.ok{color:var(--ok);} .hp-v.warn{color:var(--warn);}
.hp-v.error{color:var(--err);} .hp-v.info{color:var(--info);}
.dl{display:flex;flex-direction:column;gap:5px;}
.di{display:flex;gap:8px;align-items:flex-start;background:var(--bg2);
  border:1px solid var(--b0);border-radius:7px;padding:8px 11px;transition:.15s;}
.di:hover{border-color:var(--b1);}
.di-ic{width:16px;height:16px;border-radius:50%;flex-shrink:0;margin-top:1px;
  display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;}
.di-ic.ok{background:var(--ok-s);color:var(--ok);}
.di-ic.warn{background:var(--warn-s);color:var(--warn);}
.di-ic.error{background:var(--err-s);color:var(--err);}
.di-ic.info{background:var(--info-s);color:var(--info);}
.di-b{flex:1;min-width:0;}
.di-t{font-size:11.5px;font-weight:600;color:var(--t0);}
.di-d{font-size:10px;color:var(--t2);margin-top:1px;}
.di-tag{font-size:9px;font-weight:700;padding:1px 6px;border-radius:4px;
  background:var(--bg3);color:var(--t2);flex-shrink:0;align-self:center;}

/* ── TOPICS ── */
.tg{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.tb2{background:var(--bg2);border:1px solid var(--b0);border-radius:8px;
  padding:11px;transition:.2s;}
.tb2:hover{border-color:var(--b1);}
.t-cat{font-size:9.5px;font-weight:700;letter-spacing:.07em;margin-bottom:3px;}
.t-nm{font-size:10.5px;color:var(--t2);margin-bottom:6px;line-height:1.3;}
.t-vl{font-size:20px;font-weight:800;letter-spacing:-.4px;line-height:1;}
.t-sb{font-size:10px;color:var(--t2);margin-top:2px;}
.t-br{background:var(--b0);border-radius:3px;height:2px;margin-top:7px;overflow:hidden;}
.t-fl{height:100%;border-radius:3px;}

/* ── LOGS ── */
.log-tabs{display:flex;gap:4px;padding:10px 18px 0;}
.log-tab{padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer;
  color:var(--t2);background:var(--bg2);border:1px solid var(--b0);transition:.15s;}
.log-tab:hover{color:var(--t1);}
.log-tab.active{background:var(--brand-s);border-color:rgba(114,122,140,.3);color:var(--brand);}
.log-bd{font-family:'SF Mono',Menlo,monospace;font-size:11px;line-height:1.7;color:var(--t2);
  background:var(--bg2);margin:8px 18px 16px;border:1px solid var(--b0);border-radius:8px;
  padding:10px 13px;height:160px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;}
.log-bd::-webkit-scrollbar{width:3px;}
.log-bd::-webkit-scrollbar-thumb{background:var(--b0);}
.ll-e{color:var(--err);} .ll-s{color:var(--ok);} .ll-w{color:var(--warn);}

/* ── FEED (right) ── */
.feed-scroll{max-height:calc(55vh);overflow-y:auto;padding:0 16px 14px;}
.feed-scroll::-webkit-scrollbar{width:3px;}
.feed-scroll::-webkit-scrollbar-thumb{background:var(--b0);}
.fi{display:flex;gap:9px;padding:8px 0;border-bottom:1px solid var(--b0);}
.fi:last-child{border-bottom:none;}
.fi-dot{width:6px;height:6px;border-radius:50%;margin-top:4px;flex-shrink:0;}
.fi-dot.success{background:var(--ok);} .fi-dot.warn{background:var(--warn);}
.fi-dot.error{background:var(--err);} .fi-dot.info{background:var(--t2);}
.fi-body{flex:1;min-width:0;}
.fi-badge{display:inline-block;font-size:9.5px;font-weight:700;
  padding:1px 7px;border-radius:4px;margin-bottom:3px;}
.fi-msg{font-size:11px;color:var(--t1);line-height:1.5;word-break:break-word;}
.fi-time{font-size:10px;color:var(--t2);margin-top:1px;}

/* ── CHAT ── */
.chat-msgs{height:190px;overflow-y:auto;padding:12px 16px;
  display:flex;flex-direction:column;gap:7px;}
.chat-msgs::-webkit-scrollbar{width:3px;}
.chat-msgs::-webkit-scrollbar-thumb{background:var(--b0);}
.cm{max-width:92%;padding:7px 11px;border-radius:8px;font-size:12px;line-height:1.6;}
.cm.user{background:var(--brand-s);border:1px solid var(--brand-m);
  color:var(--t0);align-self:flex-end;border-radius:8px 8px 2px 8px;}
.cm.ai{background:var(--bg2);border:1px solid var(--b0);
  color:var(--t1);align-self:flex-start;border-radius:2px 8px 8px 8px;}
.cm.sys{background:var(--warn-s);border:1px solid rgba(184,155,114,.2);
  color:var(--warn);align-self:center;font-size:10.5px;border-radius:6px;text-align:center;}
.chat-typing{color:var(--t2);font-size:11px;padding:2px 16px;animation:pls 1s infinite;}
.chat-row{display:flex;gap:7px;padding:9px 14px 13px;border-top:1px solid var(--b0);}
.chat-in{flex:1;background:var(--bg2);border:1px solid var(--b0);
  border-radius:8px;padding:7px 11px;font-size:12px;color:var(--t0);
  font-family:inherit;outline:none;resize:none;transition:border-color .2s;}
.chat-in:focus{border-color:var(--ba);}
.chat-send{background:var(--brand);color:#fff;border:none;
  padding:7px 13px;border-radius:7px;cursor:pointer;font-size:12px;font-weight:600;
  transition:.15s;align-self:flex-end;}
.chat-send:hover{background:#5e6675;}
.chat-send:disabled{opacity:.5;cursor:not-allowed;}

/* ── MODAL ── */
.modal-ov{display:none;position:fixed;inset:0;z-index:500;
  background:rgba(47,42,36,.7);backdrop-filter:blur(8px);
  align-items:flex-start;justify-content:center;padding:40px 24px;}
.modal-ov.open{display:flex;}
.modal-box{background:var(--bg1);border:1px solid var(--b0);border-radius:14px;
  width:100%;max-width:800px;max-height:85vh;display:flex;flex-direction:column;
  box-shadow:0 20px 60px rgba(50,40,30,.18);animation:mIn .22s ease;}
@keyframes mIn{from{opacity:0;transform:scale(.96) translateY(8px);}to{opacity:1;transform:none;}}
.modal-hd{padding:13px 20px;border-bottom:1px solid var(--b0);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.modal-title{font-size:14px;font-weight:600;color:var(--t0);}
.modal-close{width:27px;height:27px;border-radius:6px;background:var(--bg2);
  border:1px solid var(--b0);color:var(--t2);cursor:pointer;font-size:13px;
  display:flex;align-items:center;justify-content:center;transition:.2s;}
.modal-close:hover{border-color:var(--ba);color:var(--brand);}
.modal-bd{flex:1;overflow-y:auto;padding:18px 22px;font-family:'SF Mono',Menlo,monospace;
  font-size:12px;line-height:1.9;color:var(--t1);white-space:pre-wrap;word-break:break-word;}
.modal-bd::-webkit-scrollbar{width:4px;}
.modal-bd::-webkit-scrollbar-thumb{background:var(--bg3);}
.modal-ft{padding:8px 20px;border-top:1px solid var(--b0);
  font-size:10.5px;color:var(--t2);flex-shrink:0;display:flex;align-items:center;gap:10px;}
.devto-btn{background:var(--ok-s);color:var(--ok);border:1px solid rgba(124,154,126,.3);
  padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer;font-weight:600;transition:.2s;}
.devto-btn:hover{background:rgba(124,154,126,.2);}

/* ── MISC ── */
.badge{display:inline-flex;align-items:center;gap:3px;
  padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:600;}
.b-ok{background:var(--ok-s);color:var(--ok);}
.b-warn{background:var(--warn-s);color:var(--warn);}
.b-brand{background:var(--brand-s);color:var(--brand);}
.empty{color:var(--t2);font-style:italic;font-size:12px;padding:8px 0;}
</style>
</head>
<body>

<nav class="topbar">
  <div class="tb-l">
    <div class="logo">⬡ AI 無人工廠<span class="logo-sub">/ 11 Agents · 26 Skills · 11 Hooks</span></div>
    <div class="spill si" id="spill"><span class="sdot"></span><span class="stxt">載入中</span></div>
  </div>
  <div class="tb-r">
    <span class="ts-t" id="ts">--</span>·<span class="cdt" id="cdt">5s</span>
    <button class="rbtn" onclick="fetchNow()">⟳ 更新</button>
  </div>
</nav>

<div class="warn-strip" id="wstrip">
  ⚠ <strong>待完成：</strong>CLAUDE.md 中仍有 PLACEHOLDER_WHOP_*，文章無法放銷售連結
</div>

<div class="kpi-bar">
  <div class="kpi-c"><div class="kpi-v accent" id="k0">0</div><div class="kpi-l">今日產出</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k1">0</div><div class="kpi-l">文章總數</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k2">0</div>
    <div class="kpi-l">今日 API 呼叫 <span title="需要 api-usage.json hook" style="color:var(--t2)">(?)</span></div></div>
  <div class="kpi-c"><div class="kpi-v" id="k3">0</div><div class="kpi-l">累計 API 呼叫</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k4">--</div><div class="kpi-l">系統健康度</div></div>
  <div class="kpi-c"><div class="kpi-v" id="k5" style="color:var(--t2);font-size:13px;">--</div>
    <div class="kpi-l">模型</div></div>
</div>

<div class="main">
 <div class="left">

  <!-- ══ 完整流程看板 ══ -->
  <div class="card">
    <div class="ch">
      <div class="ct"><span class="cdot" style="background:var(--brand)"></span>
        完整生產流程 — Agent × 檔案 × Skill × Hook</div>
      <span id="flow-summary" style="font-size:10.5px;color:var(--t2)"></span>
    </div>
    <div class="flow-board" id="flow-board"></div>
  </div>

  <!-- ══ 智能體進化循環 ══ -->
  <div class="card">
    <div class="ch">
      <div class="ct"><span class="cdot" style="background:var(--pur)"></span>
        智能體進化循環 — 知識庫</div>
      <span style="font-size:10px;color:var(--t2)">feedback → style-updater → writing-style → 下一篇</span>
    </div>
    <div class="cb">
      <div class="learn-arrow">Reddit 互動數據 → feedback-collector → style-updater 更新 writing-style.md → 下一輪寫作品質提升 ↺</div>
      <div style="height:10px"></div>
      <div class="know-grid" id="know-grid"></div>
    </div>
  </div>

  <!-- ══ 診斷 + 主題 ══ -->
  <div class="mid-row">
    <div class="card">
      <div class="ch">
        <div class="ct"><span class="cdot" style="background:var(--warn)"></span>系統診斷</div>
        <div id="dscore"></div>
      </div>
      <div class="cb">
        <div class="dh" id="dhealth"></div>
        <div class="dl" id="dlist"></div>
      </div>
    </div>
    <div class="card">
      <div class="ch"><div class="ct"><span class="cdot" style="background:var(--pur)"></span>主題表現</div></div>
      <div class="cb"><div class="tg" id="tgrid"></div></div>
    </div>
  </div>

  <!-- ══ 日誌 ══ -->
  <div class="card">
    <div class="ct" style="padding:12px 18px 0;"><span class="cdot" style="background:var(--t2)"></span>執行日誌</div>
    <div class="log-tabs">
      <div class="log-tab active" onclick="switchLog('cron',this)">Cron</div>
      <div class="log-tab" onclick="switchLog('error',this)">錯誤</div>
    </div>
    <div class="log-bd" id="logbd"></div>
  </div>

 </div><!-- /left -->

 <!-- ══ 右側：Feed + Chat ══ -->
 <div style="display:flex;flex-direction:column;gap:16px;">

  <!-- Feed -->
  <div class="card" style="flex:1;">
    <div class="ch">
      <div class="ct">
        <span class="cdot" style="background:var(--brand);animation:pls 2s infinite;"></span>
        團隊活動流
      </div>
    </div>
    <div class="feed-scroll" id="feed-list"></div>
  </div>

  <!-- Chat -->
  <div class="card" style="flex-shrink:0;">
    <div class="ch">
      <div class="ct"><span class="cdot" style="background:var(--brand)"></span>控制台對話</div>
      <span style="font-size:10px;color:var(--t2)">具備系統狀態感知</span>
    </div>
    <div class="chat-msgs" id="chat-msgs">
      <div class="cm sys">智能助手已就緒 — 可詢問系統狀態、設定問題、流程說明</div>
    </div>
    <div id="chat-typing" class="chat-typing" style="display:none;">AI 回覆中...</div>
    <div class="chat-row">
      <textarea class="chat-in" id="chat-in" rows="2"
        placeholder="例：目前系統狀態？如何清 Cron？為何沒有 API 呼叫？"
        onkeydown="chatKey(event)"></textarea>
      <button class="chat-send" id="chat-btn" onclick="sendChat()">送出</button>
    </div>
  </div>

 </div>
</div><!-- /main -->

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
      <button class="devto-btn" id="devto-btn" onclick="postToDevto()">發布到 dev.to 草稿</button>
    </div>
  </div>
</div>

<script>
let currentLog='cron', countdown=5, timer, lastData=null, currentArticleName='';

const CAT_C={A:'#727A8C',B:'#8B85A0',C:'#7C9A7E',D:'#8193A8'};
const CAT_L={A:'電容/壓力感測',B:'手勢/彎曲感測',C:'互動設計',D:'IoT/ESP32'};
const FEED_C={'writer':'#727A8C','researcher':'#8193A8','reviewer':'#8B85A0',
  'poster':'#7C9A7E','quality-check':'#B89B72','topic-selector':'#727A8C',
  'system':'#8A837A','feedback':'#8B85A0'};

async function fetchNow(){
  clearInterval(timer); countdown=5;
  try{
    const r=await fetch('/api/status'); const d=await r.json();
    lastData=d; render(d);
  }catch(e){ setPill('se','連線失敗'); }
  startTimer();
}
function startTimer(){
  clearInterval(timer);
  timer=setInterval(()=>{
    countdown--;
    const el=document.getElementById('cdt');
    if(el) el.textContent=countdown+'s';
    if(countdown<=0) fetchNow();
  },1000);
}

function render(d){
  document.getElementById('ts').textContent=d.ts;
  document.getElementById('wstrip').style.display=d.has_placeholder?'flex':'none';
  const sm={idle:'si',running:'sr',error:'se'};
  const tx={idle:'待機中',running:'執行中',error:'有錯誤'};
  setPill(sm[d.state]||'si',tx[d.state]||d.state);
  document.getElementById('k0').textContent=d.pipeline.count||0;
  document.getElementById('k1').textContent=d.article_count||0;
  document.getElementById('k2').textContent=d.usage.today||0;
  document.getElementById('k3').textContent=d.usage.total||0;
  const sc=d.diag?.score??100;
  const se=document.getElementById('k4');
  se.textContent=sc+'%';
  se.className='kpi-v '+(sc>=85?'ok':sc>=60?'warn':'err');
  document.getElementById('k5').textContent=d.api.model;
  renderFlow(d.flow||[], d.file_transfers||[]);
  renderKnowledge(d.knowledge||[]);
  renderDiag(d.diag||{});
  renderTopics(d.perf||{});
  renderFeed(d.feed||[]);
  renderLog(d);
  const wc=(d.flow||[]).filter(a=>a.status==='working').length;
  const wa=(d.flow||[]).filter(a=>a.status==='waiting').length;
  document.getElementById('flow-summary').textContent=
    wc>0?`${wc} 個工作中`:wa>0?`${wa} 個等待中`:'全員待命';
}

function setPill(cls,label){
  const el=document.getElementById('spill');
  el.className='spill '+cls;
  el.querySelector('.stxt').textContent=label;
}

// ── Pipeline Flow ──────────────────────────────────
function renderFlow(flow, transfers){
  const board=document.getElementById('flow-board');
  let html='';
  const phaseColors={'探索':'#8193A8','策略':'#8B85A0','生產':'#727A8C',
    '品管':'#B89B72','發布':'#7C9A7E','回饋':'#B89B72','進化':'#8B85A0'};

  flow.forEach((a,i)=>{
    const st=a.status||'idle';
    const isOpen=st==='working'||st==='waiting';

    // agent card
    html+=`<div class="pf-card ${st}" id="pfc-${esc(a.id)}">
      <div class="pf-head" onclick="toggleFlow('${esc(a.id)}')">
        <div class="pf-num">${a.order}</div>
        <div class="pf-icon" style="${st==='working'?'':'font-size:16px'}">${esc(a.icon)}</div>
        <div class="pf-name-col">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
            <span class="pf-name">${esc(a.label)}</span>
            <span class="pf-phase" style="background:${phaseColors[a.phase]||'#8A837A'}18;color:${phaseColors[a.phase]||'#8A837A'}">${esc(a.phase)}</span>
          </div>
          <div class="pf-desc">${esc(a.desc)}</div>
        </div>
        <span class="pf-sbadge ${st}">${esc(a.status_txt)}</span>
        <span class="pf-toggle" id="tgl-${esc(a.id)}">${isOpen?'▲':'▼'}</span>
      </div>`;

    // detail body
    const disp=isOpen?'block':'none';
    html+=`<div class="pf-body" id="pfb-${esc(a.id)}" style="display:${disp}">
      <div class="pf-grid">
        <div>
          <div class="pf-section-label">讀取（Input）</div>
          ${(a.reads_stat||[]).map(r=>fileItem(r.path,r.stat)).join('')}
        </div>
        <div>
          <div class="pf-section-label">寫入（Output）</div>
          ${(a.writes_stat||[]).map(w=>fileItem(w.path,w.stat)).join('')}
        </div>
        <div>
          <div class="pf-section-label">使用 Skill (${(a.skills_avail||[]).length})</div>
          <div class="pill-list">${(a.skills_avail||[]).map(s=>
            `<span class="pill ${s.ok?'skill-ok':'skill-miss'}">${esc(s.name)}</span>`).join('')||'<span class="empty">（無）</span>'}
          </div>
        </div>
        <div>
          <div class="pf-section-label">執行 Hook (${(a.hooks_avail||[]).length})</div>
          <div class="pill-list">${(a.hooks_avail||[]).map(h=>
            `<span class="pill ${h.ok?'hook-ok':'hook-miss'}">${esc(h.name)}</span>`).join('')||'<span class="empty">（無）</span>'}
          </div>
        </div>
      </div>
    </div>`;
    html+='</div>';// end pf-card

    // transfer line to next agent
    if(i<flow.length-1){
      const tf=(transfers[i]||[]);
      html+=`<div class="pf-transfer">
        <div class="pf-tline"></div>
        <div class="pf-tfiles">${tf.map(f=>`<span class="pf-tfile">${esc(f)}</span>`).join('')}</div>
      </div>`;
    }
  });
  board.innerHTML=html;
}

function fileItem(path,stat){
  const ok=stat&&stat.ok;
  const short=path.split('/').pop().replace(/（.*?）/g,'');
  const age=ok?(stat.age<1440?stat.age+'m前':Math.floor(stat.age/1440)+'d前'):'';
  return `<div class="file-item">
    <div class="file-dot ${ok?'ok':'miss'}"></div>
    <span class="file-path" title="${esc(path)}">${esc(short)}</span>
    <span class="file-age">${age}</span>
  </div>`;
}

function toggleFlow(id){
  const body=document.getElementById('pfb-'+id);
  const tgl =document.getElementById('tgl-'+id);
  if(!body) return;
  const open=body.style.display==='block';
  body.style.display=open?'none':'block';
  if(tgl) tgl.textContent=open?'▼':'▲';
}

// ── Knowledge ─────────────────────────────────────
function renderKnowledge(knows){
  const el=document.getElementById('know-grid');
  el.innerHTML=knows.map(k=>{
    const w=Math.min(k.lines*5,100);
    const age=k.age<0?'尚未建立':k.age<60?k.age+'m前':k.age<1440?Math.floor(k.age/60)+'h前':Math.floor(k.age/1440)+'d前';
    return `<div class="know-box">
      <div class="know-label">${esc(k.label)}</div>
      <div class="know-val">${k.lines}</div>
      <div class="know-sub">${age}</div>
      <div class="know-bar"><div class="know-fill" style="width:${w}%"></div></div>
    </div>`;
  }).join('');
}

// ── Diag ──────────────────────────────────────────
function renderDiag(diag){
  const sc=diag.score??100;
  const sc_c=sc>=85?'ok':sc>=60?'warn':'err';
  const bm={ok:'b-ok',warn:'b-warn',err:'b-err'};
  document.getElementById('dscore').innerHTML=
    `<span class="badge ${bm[sc_c]}">${sc}% 健康</span>`;
  const pm={ok:'ok',warn:'warn',error:'error',info:'info'};
  document.getElementById('dhealth').innerHTML=(diag.health||[]).map(h=>`
    <div class="hp"><div class="hp-n">${esc(h.name)}</div>
    <div class="hp-v ${pm[h.status]||'info'}">${esc(h.val)}</div></div>`).join('');
  const im={ok:'✓',warn:'!',error:'✕',info:'i'};
  document.getElementById('dlist').innerHTML=(diag.issues||[]).map(it=>`
    <div class="di">
      <div class="di-ic ${it.level}">${im[it.level]||'i'}</div>
      <div class="di-b"><div class="di-t">${esc(it.title)}</div>
        ${it.desc?`<div class="di-d">${esc(it.desc)}</div>`:''}</div>
      <div class="di-tag">${esc(it.tag||'')}</div>
    </div>`).join('')||'<div class="empty">無診斷項目</div>';
}

// ── Topics ────────────────────────────────────────
function renderTopics(perf){
  document.getElementById('tgrid').innerHTML=['A','B','C','D'].map(c=>{
    const d=perf[c]||{avg_upvotes:0,count:0};
    const w=Math.min((d.avg_upvotes||0)*2,100);
    const col=CAT_C[c];
    return `<div class="tb2">
      <div class="t-cat" style="color:${col}">${c} 類</div>
      <div class="t-nm">${CAT_L[c]}</div>
      <div class="t-vl" style="color:${col}">${Number(d.avg_upvotes||0).toFixed(0)}</div>
      <div class="t-sb">avg upvotes · ${d.count||0} 篇</div>
      <div class="t-br"><div class="t-fl" style="width:${w}%;background:${col}"></div></div>
    </div>`;
  }).join('');
}

// ── Feed ──────────────────────────────────────────
function renderFeed(feed){
  const el=document.getElementById('feed-list');
  if(!feed||!feed.length){
    el.innerHTML='<div class="empty" style="padding:16px;text-align:center;">尚無活動記錄</div>';
    return;
  }
  el.innerHTML=feed.map(f=>{
    const col=FEED_C[f.agent]||'#8A837A';
    return `<div class="fi">
      <div class="fi-dot ${f.type}"></div>
      <div class="fi-body">
        <span class="fi-badge" style="background:${col}18;color:${col};border:1px solid ${col}30;">${esc(f.agent)}</span>
        <div class="fi-msg">${esc(f.msg)}</div>
        ${f.time?`<div class="fi-time">${esc(f.time)}</div>`:''}
      </div>
    </div>`;
  }).join('');
}

// ── Log ───────────────────────────────────────────
function renderLog(d){
  const lines=currentLog==='cron'?d.cron_log_tail:d.error_log;
  const el=document.getElementById('logbd');
  if(!lines||!lines.length){el.textContent='（無記錄）';return;}
  el.innerHTML=lines.map(l=>{
    let c='';
    if(/error|fail|FAIL/i.test(l)) c='ll-e';
    else if(/APPROVED|success|完成/i.test(l)) c='ll-s';
    else if(/REJECTED|warn|WARNING/i.test(l)) c='ll-w';
    return c?`<span class="${c}">${esc(l)}</span>`:esc(l);
  }).join('\n');
  el.scrollTop=el.scrollHeight;
}
function switchLog(t,btn){
  currentLog=t;
  document.querySelectorAll('.log-tab').forEach(x=>x.classList.remove('active'));
  btn.classList.add('active');
  if(lastData) renderLog(lastData);
}

// ── Chat ──────────────────────────────────────────
function addMsg(role,text){
  const box=document.getElementById('chat-msgs');
  const el=document.createElement('div');
  el.className='cm '+role;
  el.textContent=text;
  box.appendChild(el);
  box.scrollTop=box.scrollHeight;
}
async function sendChat(){
  const inp=document.getElementById('chat-in');
  const msg=inp.value.trim();
  if(!msg) return;
  inp.value='';
  addMsg('user',msg);
  document.getElementById('chat-btn').disabled=true;
  document.getElementById('chat-typing').style.display='block';
  try{
    const r=await fetch('/api/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const d=await r.json();
    addMsg('ai',d.reply||'（無回應）');
  }catch(e){addMsg('sys','連線失敗：'+e);}
  document.getElementById('chat-btn').disabled=false;
  document.getElementById('chat-typing').style.display='none';
}
function chatKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}}

// ── Article Modal ─────────────────────────────────
async function openArticle(name,title){
  if(!name) return;
  currentArticleName=name;
  document.getElementById('mtitle').textContent=title||name;
  document.getElementById('mbody').textContent='載入中...';
  document.getElementById('mfoot').textContent='';
  document.getElementById('modal').classList.add('open');
  try{
    const r=await fetch('/api/article?name='+encodeURIComponent(name));
    if(r.ok){
      const txt=await r.text();
      document.getElementById('mbody').textContent=txt;
      document.getElementById('mfoot').textContent=
        `${name}.md  ·  ${txt.split(/\s+/).length} 詞`;
    }else{document.getElementById('mbody').textContent='找不到文章。';}
  }catch(e){document.getElementById('mbody').textContent='載入失敗：'+e;}
}

async function postToDevto(){
  if(!currentArticleName) return;
  const btn=document.getElementById('devto-btn');
  btn.disabled=true; btn.textContent='發布中...';
  try{
    const r=await fetch('/api/post-devto',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:currentArticleName})});
    const d=await r.json();
    if(d.ok){
      btn.textContent='✓ 已建立草稿';
      document.getElementById('mfoot').textContent+=`  ·  dev.to: ${d.url||'(草稿)'}`;
    }else{
      btn.textContent='✗ 失敗：'+d.error.slice(0,40);
      btn.disabled=false;
    }
  }catch(e){btn.textContent='連線失敗';btn.disabled=false;}
}

function closeModal(e){
  if(!e||e.target.id==='modal')
    document.getElementById('modal').classList.remove('open');
}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape') closeModal({target:{id:'modal'}});
});

function esc(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

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
    print(f"Dashboard v6 啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0",port),Handler).serve_forever()
