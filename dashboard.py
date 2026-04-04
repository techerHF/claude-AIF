#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v3 — 高級控制台版
執行：python3 ~/ai-factory/dashboard.py
訪問：http://VPS_IP:3000
"""

import json, os, re, subprocess, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent

# ── 資料層 ────────────────────────────────────────────

def rj(path, default=None):
    try:
        return json.loads((BASE / path).read_text(encoding="utf-8"))
    except:
        return default if default is not None else {}

def rt(path, n=80):
    try:
        lines = (BASE / path).read_text(encoding="utf-8").splitlines()
        return lines[-n:]
    except:
        return []

def api_status():
    try:
        s = json.loads(Path.home().joinpath(".claude/settings.json").read_text())
        m = s.get("env", {}).get("ANTHROPIC_MODEL", "")
        return {"model": m or "Claude（預設）", "minimax": "MiniMax" in m}
    except:
        return {"model": "Claude（預設）", "minimax": False}

def cron_lines():
    try:
        r = subprocess.run(["crontab","-l"], capture_output=True, text=True, timeout=3)
        return [l for l in r.stdout.splitlines() if "ai-factory" in l]
    except:
        return []

def system_state():
    err_log  = rt("logs/error.log", 3)
    cron_log = rt("logs/cron.log", 5)
    if err_log:
        return "error"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if any(today[:7] in l or "2026" in l for l in cron_log):
        return "running"
    return "idle"

def activity_feed():
    events = []
    prog = rj("logs/progress.json", [])
    for p in reversed(prog[-8:]):
        events.append({
            "time": p.get("timestamp","")[:16].replace("T"," "),
            "agent": "writer",
            "msg": f"文章完成：{p.get('title','')}",
            "type": "success"
        })
    for line in reversed(rt("logs/cron.log", 30)):
        line = line.strip()
        if not line: continue
        agent, t = "system", "info"
        if "APPROVED" in line:  t, agent = "success", "quality-check"
        elif "REJECTED" in line: t, agent = "warn",    "quality-check"
        elif "error" in line.lower(): t, agent = "error", "system"
        elif "writer" in line.lower(): agent = "writer"
        elif "reviewer" in line.lower(): agent = "reviewer"
        elif "poster" in line.lower(): agent = "poster"
        elif "feedback" in line.lower(): agent = "feedback"
        elif "researcher" in line.lower(): agent = "researcher"
        events.append({"time": "", "agent": agent, "msg": line[:120], "type": t})
    for line in reversed(rt("logs/error.log", 5)):
        if line.strip():
            events.append({"time":"","agent":"system","msg":line[:120],"type":"error"})
    return events[:30]

def pipeline_status():
    prog  = rj("logs/progress.json", [])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_items = [p for p in prog if p.get("date","") == today]
    stages = [
        {"id":"researcher",     "label":"研究員",   "agent":"researcher"},
        {"id":"topic-selector", "label":"選題",     "agent":"topic-selector"},
        {"id":"writer",         "label":"寫作",     "agent":"writer"},
        {"id":"reviewer",       "label":"審查",     "agent":"reviewer"},
        {"id":"poster",         "label":"發文準備", "agent":"poster"},
        {"id":"published",      "label":"已發布",   "agent":"publisher"},
    ]
    done_map = {
        "reviewed":  ["researcher","topic-selector","writer","reviewer"],
        "posted":    ["researcher","topic-selector","writer","reviewer","poster"],
        "published": ["researcher","topic-selector","writer","reviewer","poster","published"],
    }
    if today_items:
        item   = today_items[-1]
        status = item.get("status","")
        done   = set(done_map.get(status, []))
        for s in stages:
            s["done"] = s["id"] in done
        return {"stages": stages, "article": item, "count": len(today_items)}
    return {"stages": stages, "article": None, "count": 0}

def api_usage():
    return rj("logs/api-usage.json", {"today":0,"total":0})

def list_articles():
    """列出 articles/ 目錄下的文章，最新在前"""
    try:
        arts = sorted(BASE.glob("articles/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = []
        for a in arts[:20]:
            content = a.read_text(encoding="utf-8", errors="ignore")
            lines   = content.splitlines()
            title   = next((l.lstrip("#").strip() for l in lines if l.startswith("#")), a.stem)
            word_cnt = len(re.sub(r'```.*?```','',content,flags=re.DOTALL).replace('\n',' ').split())
            result.append({"name": a.stem, "title": title[:80], "size": len(content), "words": word_cnt})
        return result
    except:
        return []

def get_article_content(name):
    """回傳單一文章全文"""
    try:
        p = BASE / "articles" / f"{name}.md"
        if not p.exists():
            # 安全：只允許讀 articles/ 目錄內的 .md 檔
            return None
        return p.read_text(encoding="utf-8", errors="ignore")
    except:
        return None

def get_status_data():
    prog   = rj("logs/progress.json", [])
    perf   = rj("logs/topic-performance.json", {})
    api    = api_status()
    crons  = cron_lines()
    usage  = api_usage()
    pipe   = pipeline_status()
    feed   = activity_feed()
    state  = system_state()
    has_ph = False
    try:
        has_ph = "PLACEHOLDER" in (BASE/"CLAUDE.md").read_text(encoding="utf-8")
    except:
        pass
    articles = list_articles()
    return {
        "ts":              datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "state":           state,
        "api":             api,
        "cron_count":      len(crons),
        "has_placeholder": has_ph,
        "article_count":   len(prog),
        "articles":        articles,
        "pipeline":        pipe,
        "feed":            feed,
        "usage":           usage,
        "perf":            perf.get("categories", {}),
        "cron_log_tail":   rt("logs/cron.log", 60),
        "error_log":       rt("logs/error.log", 30),
    }

# ── HTML ──────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 無人工廠</title>
<style>
/* ── 色彩系統 (3 層深色) ── */
:root{
  --bg0:#07111F;
  --bg1:#0D1826;
  --bg2:#111D2E;
  --bg3:#162436;
  --border:rgba(255,255,255,0.06);
  --border-hover:rgba(34,211,238,0.35);
  --text:#DDE7F5;
  --text2:#8CA0B8;
  --text3:#4A6480;
  /* brand — 只用一個主色 */
  --cyan:#22D3EE;
  --cyan-glow:rgba(34,211,238,0.15);
  /* 語意色 */
  --green:#22C55E;
  --green-glow:rgba(34,197,94,0.15);
  --amber:#F59E0B;
  --amber-glow:rgba(245,158,11,0.12);
  --red:#EF4444;
  --red-glow:rgba(239,68,68,0.15);
  --purple:#A78BFA;
  --purple-glow:rgba(167,139,250,0.15);
  --blue:#60A5FA;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;background:var(--bg0);color:var(--text);
  font-family:'SF Pro Display',system-ui,-apple-system,sans-serif;font-size:13px;}

/* ── TOPBAR ── */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:52px;
  background:var(--bg1);
  border-bottom:1px solid var(--border);
  position:sticky;top:0;z-index:200;
}
.topbar-brand{display:flex;align-items:center;gap:16px;}
.logo{font-size:14px;font-weight:700;letter-spacing:-.2px;color:var(--cyan);}
.logo span{color:var(--text);font-weight:400;opacity:.7;}
.state-pill{
  display:flex;align-items:center;gap:6px;
  padding:3px 10px;border-radius:999px;
  font-size:11px;font-weight:600;
  background:var(--bg2);border:1px solid var(--border);
  transition:.3s;
}
.state-pill .dot{width:7px;height:7px;border-radius:50%;}
.state-idle    .dot{background:var(--text3);}
.state-running .dot{background:var(--green);box-shadow:0 0 8px var(--green);animation:blink 1.5s infinite;}
.state-error   .dot{background:var(--red);  box-shadow:0 0 8px var(--red);}
.state-idle    .state-txt{color:var(--text3);}
.state-running .state-txt{color:var(--green);}
.state-error   .state-txt{color:var(--red);}
@keyframes blink{0%,100%{opacity:1;}50%{opacity:.35;}}

.topbar-right{display:flex;align-items:center;gap:14px;}
.ts-label{font-size:11px;color:var(--text3);}
.countdown{font-size:11px;color:var(--cyan);font-variant-numeric:tabular-nums;min-width:20px;}
.refresh-btn{
  background:none;border:1px solid var(--border);color:var(--text3);
  padding:4px 12px;border-radius:6px;cursor:pointer;font-size:11px;
  transition:.2s;letter-spacing:.02em;
}
.refresh-btn:hover{border-color:var(--cyan);color:var(--cyan);}

/* ── WARN BANNER ── */
.warn-banner{
  background:rgba(245,158,11,.06);
  border-bottom:1px solid rgba(245,158,11,.18);
  padding:7px 28px;font-size:11.5px;color:var(--amber);
  display:none;align-items:center;gap:10px;
}
.warn-banner strong{color:var(--amber);}

/* ── KPI BAR ── */
.kpi-bar{
  display:grid;grid-template-columns:repeat(5,1fr);
  gap:1px;background:var(--border);
  border-bottom:1px solid var(--border);
}
.kpi-item{
  background:var(--bg1);padding:12px 20px;
  display:flex;flex-direction:column;gap:2px;
  transition:.2s;cursor:default;
}
.kpi-item:hover{background:var(--bg2);}
.kpi-val{font-size:22px;font-weight:700;line-height:1;letter-spacing:-.5px;}
.kpi-lbl{font-size:10.5px;color:var(--text3);letter-spacing:.03em;}
.kv-cyan  {color:var(--cyan);}
.kv-green {color:var(--green);}
.kv-amber {color:var(--amber);}
.kv-purple{color:var(--purple);}
.kv-blue  {color:var(--blue);}

/* ── MAIN LAYOUT ── */
.main{
  display:grid;
  grid-template-columns:1fr 340px;
  grid-template-rows:auto auto auto;
  gap:0;
  padding:20px 28px;
  gap:16px;
  max-width:1500px;
  margin:0 auto;
}

/* ── CARD BASE ── */
.card{
  background:var(--bg1);
  border:1px solid var(--border);
  border-radius:12px;
  transition:border-color .25s,box-shadow .25s;
  overflow:hidden;
}
.card:hover{
  border-color:rgba(255,255,255,0.1);
  box-shadow:0 8px 32px rgba(0,0,0,.35);
}
.card-header{
  padding:14px 18px 0;
  display:flex;align-items:center;justify-content:space-between;
}
.section-label{
  font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--text3);display:flex;align-items:center;gap:6px;
}
.section-label .dot{width:5px;height:5px;border-radius:50%;}
.card-body{padding:14px 18px 18px;}

/* ── PIPELINE ── */
.pipeline-card{grid-column:1;}
.pipeline-track{
  display:flex;align-items:flex-start;
  padding:0 4px;
  position:relative;
}
.pipeline-track::before{
  content:'';position:absolute;
  top:14px;left:18px;right:18px;height:1px;
  background:linear-gradient(90deg,var(--bg3),var(--bg3));
  z-index:0;
}
.pipe-node{
  flex:1;display:flex;flex-direction:column;align-items:center;
  position:relative;z-index:1;cursor:pointer;
}
.pipe-ring{
  width:28px;height:28px;border-radius:50%;
  border:1.5px solid var(--bg3);
  background:var(--bg2);
  display:flex;align-items:center;justify-content:center;
  font-size:10px;color:var(--text3);
  transition:.3s;position:relative;
}
.pipe-node.done   .pipe-ring{border-color:var(--green);background:var(--green-glow);color:var(--green);}
.pipe-node.active .pipe-ring{
  border-color:var(--cyan);background:var(--cyan-glow);color:var(--cyan);
  box-shadow:0 0 14px var(--cyan-glow),0 0 0 4px rgba(34,211,238,.07);
  animation:blink 1.5s infinite;
}
.pipe-node.error  .pipe-ring{border-color:var(--red);background:var(--red-glow);color:var(--red);}
.pipe-name{
  font-size:9.5px;color:var(--text3);margin-top:6px;text-align:center;
  letter-spacing:.02em;white-space:nowrap;
}
.pipe-node.done   .pipe-name{color:var(--green);}
.pipe-node.active .pipe-name{color:var(--cyan);}

/* connector lines */
.pipe-conn{
  flex:1;height:1px;background:var(--bg3);
  margin-top:13px;transition:.3s;
}
.pipe-conn.done{background:var(--green);}
.pipe-conn.active{background:linear-gradient(90deg,var(--green),var(--cyan));}

/* article card in pipeline */
.article-card{
  margin-top:14px;
  background:var(--bg2);border:1px solid var(--border);
  border-radius:9px;padding:12px 16px;
  cursor:pointer;transition:.25s;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
}
.article-card:hover{border-color:var(--border-hover);background:var(--bg3);}
.article-card-left{}
.article-title{font-size:13px;font-weight:600;color:var(--text);line-height:1.4;}
.article-meta{font-size:11px;color:var(--text3);margin-top:4px;}
.article-card-right{flex-shrink:0;}
.view-btn{
  font-size:10px;color:var(--cyan);border:1px solid rgba(34,211,238,.25);
  padding:3px 10px;border-radius:6px;white-space:nowrap;
  background:var(--cyan-glow);
}
.pipe-none{
  margin-top:14px;text-align:center;padding:20px 0;
  color:var(--text3);font-size:12px;line-height:1.8;
}

/* ── FEED ── */
.feed-card{grid-column:2;grid-row:1/3;}
.feed-scroll{max-height:560px;overflow-y:auto;padding:0 18px 16px;}
.feed-scroll::-webkit-scrollbar{width:2px;}
.feed-scroll::-webkit-scrollbar-thumb{background:var(--bg3);border-radius:2px;}
.feed-item{
  display:flex;gap:10px;padding:9px 0;
  border-bottom:1px solid var(--border);
  animation:fadeIn .3s ease;
}
.feed-item:last-child{border-bottom:none;}
@keyframes fadeIn{from{opacity:0;transform:translateY(-4px);}to{opacity:1;transform:none;}}
.feed-dot{
  width:6px;height:6px;border-radius:50%;margin-top:4px;flex-shrink:0;
}
.feed-dot.success{background:var(--green);}
.feed-dot.warn   {background:var(--amber);}
.feed-dot.error  {background:var(--red);}
.feed-dot.info   {background:var(--text3);}
.feed-body{flex:1;min-width:0;}
.feed-agent-badge{
  display:inline-block;font-size:9.5px;font-weight:700;
  padding:1px 7px;border-radius:4px;margin-bottom:4px;
  letter-spacing:.04em;
}
.feed-msg{font-size:11.5px;color:var(--text2);line-height:1.5;word-break:break-word;}
.feed-time{font-size:10px;color:var(--text3);margin-top:2px;}

/* ── TOPICS ── */
.topics-card{grid-column:1;}
.topics-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.topic-box{
  background:var(--bg2);border:1px solid var(--border);
  border-radius:9px;padding:14px;transition:.25s;cursor:default;
}
.topic-box:hover{border-color:rgba(255,255,255,.12);transform:translateY(-1px);}
.topic-cat{font-size:10px;font-weight:700;letter-spacing:.08em;color:var(--text3);margin-bottom:8px;}
.topic-name{font-size:11.5px;color:var(--text2);margin-bottom:10px;line-height:1.4;}
.topic-val{font-size:26px;font-weight:800;line-height:1;letter-spacing:-.5px;}
.topic-sub{font-size:10px;color:var(--text3);margin-top:3px;}
.topic-bar{background:var(--bg3);border-radius:3px;height:3px;margin-top:10px;overflow:hidden;}
.topic-fill{height:100%;border-radius:3px;transition:width .6s ease;}

/* ── LOGS ── */
.logs-card{grid-column:1/3;}
.log-tabs{display:flex;gap:4px;padding:14px 18px 0;}
.log-tab{
  padding:4px 14px;border-radius:6px;font-size:11px;
  cursor:pointer;color:var(--text3);
  background:var(--bg2);border:1px solid var(--border);
  transition:.2s;
}
.log-tab:hover{color:var(--text2);}
.log-tab.active{background:var(--cyan-glow);border-color:rgba(34,211,238,.3);color:var(--cyan);}
.log-body{
  font-family:'SF Mono',Menlo,Consolas,monospace;
  font-size:11px;line-height:1.7;color:var(--text3);
  background:var(--bg2);margin:12px 18px 18px;
  border:1px solid var(--border);border-radius:8px;
  padding:12px 14px;height:180px;overflow-y:auto;
  white-space:pre-wrap;word-break:break-all;
}
.log-body::-webkit-scrollbar{width:2px;}
.log-body::-webkit-scrollbar-thumb{background:var(--bg3);}
.ll-e{color:var(--red);}
.ll-s{color:var(--green);}
.ll-w{color:var(--amber);}

/* ── ARTICLE MODAL ── */
.modal-overlay{
  display:none;position:fixed;inset:0;z-index:500;
  background:rgba(7,17,31,.85);backdrop-filter:blur(8px);
  align-items:flex-start;justify-content:center;padding:40px 24px;
}
.modal-overlay.open{display:flex;}
.modal-box{
  background:var(--bg1);border:1px solid var(--border);
  border-radius:14px;width:100%;max-width:780px;max-height:85vh;
  display:flex;flex-direction:column;
  box-shadow:0 24px 80px rgba(0,0,0,.6);
  animation:modalIn .25s ease;
}
@keyframes modalIn{from{opacity:0;transform:scale(.96);}to{opacity:1;transform:none;}}
.modal-header{
  padding:16px 20px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
  flex-shrink:0;
}
.modal-title{font-size:14px;font-weight:600;color:var(--text);}
.modal-close{
  width:28px;height:28px;border-radius:6px;background:var(--bg2);
  border:1px solid var(--border);color:var(--text3);cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-size:14px;
  transition:.2s;
}
.modal-close:hover{border-color:var(--border-hover);color:var(--cyan);}
.modal-body{
  flex:1;overflow-y:auto;padding:20px 24px;
  font-size:13px;line-height:1.8;color:var(--text2);
  white-space:pre-wrap;word-break:break-word;
  font-family:'SF Mono',Menlo,monospace;
}
.modal-body::-webkit-scrollbar{width:4px;}
.modal-body::-webkit-scrollbar-thumb{background:var(--bg3);border-radius:4px;}
.modal-meta{
  padding:10px 20px;border-top:1px solid var(--border);
  font-size:10.5px;color:var(--text3);flex-shrink:0;
}

/* ── ARTICLES LIST ── */
.articles-list{margin-top:6px;}
.art-item{
  display:flex;align-items:center;justify-content:space-between;
  padding:8px 0;border-bottom:1px solid var(--border);gap:10px;
}
.art-item:last-child{border-bottom:none;}
.art-name{font-size:12px;color:var(--text);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.art-meta{font-size:10.5px;color:var(--text3);white-space:nowrap;}
.art-btn{
  font-size:10px;color:var(--cyan);border:1px solid rgba(34,211,238,.2);
  padding:2px 8px;border-radius:5px;background:var(--cyan-glow);
  cursor:pointer;white-space:nowrap;flex-shrink:0;transition:.2s;
}
.art-btn:hover{background:rgba(34,211,238,.25);}

/* ── STATUS BADGE ── */
.badge{
  display:inline-flex;align-items:center;gap:4px;
  padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:600;
}
.badge-green {background:var(--green-glow); color:var(--green);}
.badge-amber {background:var(--amber-glow); color:var(--amber);}
.badge-cyan  {background:var(--cyan-glow);  color:var(--cyan);}
.badge-red   {background:var(--red-glow);   color:var(--red);}
.badge-purple{background:var(--purple-glow);color:var(--purple);}

.model-badge{
  font-size:11.5px;font-weight:600;
  display:flex;align-items:center;gap:5px;
  color:var(--green);
}

/* ── API USAGE ── */
.usage-row{display:flex;justify-content:space-between;align-items:center;
  padding:7px 0;border-bottom:1px solid var(--border);}
.usage-row:last-child{border-bottom:none;}
.usage-key{font-size:11.5px;color:var(--text3);}
.usage-val{font-size:14px;font-weight:700;color:var(--text);}
</style>
</head>
<body>

<!-- TOPBAR -->
<nav class="topbar">
  <div class="topbar-brand">
    <div class="logo">AI 無人工廠 <span>/ 控制台</span></div>
    <div class="state-pill state-idle" id="state-pill">
      <span class="dot"></span>
      <span class="state-txt">載入中</span>
    </div>
  </div>
  <div class="topbar-right">
    <span class="ts-label" id="ts">--</span>
    <span class="ts-label">·</span>
    <span class="countdown" id="countdown">5s</span>
    <button class="refresh-btn" onclick="fetchNow()">⟳ 更新</button>
  </div>
</nav>

<!-- WARN BANNER -->
<div class="warn-banner" id="warn-banner">
  ⚠ <strong>待完成：</strong>CLAUDE.md 中仍有 PLACEHOLDER_WHOP_* — 填入真實 Whop 連結後才能在文章中放銷售連結
</div>

<!-- KPI BAR -->
<div class="kpi-bar">
  <div class="kpi-item">
    <div class="kpi-val kv-cyan"  id="k-today">0</div>
    <div class="kpi-lbl">今日產出</div>
  </div>
  <div class="kpi-item">
    <div class="kpi-val kv-green" id="k-total">0</div>
    <div class="kpi-lbl">文章總數</div>
  </div>
  <div class="kpi-item">
    <div class="kpi-val kv-blue"  id="k-api-today">0</div>
    <div class="kpi-lbl">今日 API 呼叫</div>
  </div>
  <div class="kpi-item">
    <div class="kpi-val kv-purple"id="k-api-total">0</div>
    <div class="kpi-lbl">累計 API 呼叫</div>
  </div>
  <div class="kpi-item">
    <div class="kpi-val kv-amber" id="k-cron">0</div>
    <div class="kpi-lbl">Cron 排程</div>
  </div>
</div>

<!-- MAIN -->
<div class="main">

  <!-- PIPELINE -->
  <div class="card pipeline-card">
    <div class="card-header">
      <div class="section-label">
        <span class="dot" style="background:var(--green)"></span>生產流水線
      </div>
      <div id="model-badge"></div>
    </div>
    <div class="card-body">
      <div id="pipeline-track"></div>
      <div id="pipe-article-slot"></div>
    </div>
  </div>

  <!-- FEED -->
  <div class="card feed-card">
    <div class="card-header" style="padding-bottom:10px;">
      <div class="section-label">
        <span class="dot" style="background:var(--cyan);box-shadow:0 0 6px var(--cyan);animation:blink 2s infinite;"></span>
        團隊活動流
      </div>
    </div>
    <div class="feed-scroll" id="feed-list"></div>
  </div>

  <!-- TOPICS -->
  <div class="card topics-card">
    <div class="card-header">
      <div class="section-label">
        <span class="dot" style="background:var(--purple)"></span>主題表現
      </div>
    </div>
    <div class="card-body">
      <div class="topics-grid" id="topics-grid"></div>
    </div>
  </div>

  <!-- LOGS -->
  <div class="card logs-card">
    <div class="section-label" style="padding:14px 18px 0;">
      <span class="dot" style="background:var(--text3)"></span>執行日誌
    </div>
    <div class="log-tabs">
      <div class="log-tab active" onclick="switchLog('cron',this)">Cron</div>
      <div class="log-tab" onclick="switchLog('error',this)">錯誤</div>
    </div>
    <div class="log-body" id="log-body"></div>
  </div>

</div>

<!-- ARTICLE MODAL -->
<div class="modal-overlay" id="modal" onclick="closeModal(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-header">
      <div class="modal-title" id="modal-title">文章內容</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modal-body">載入中...</div>
    <div class="modal-meta" id="modal-meta"></div>
  </div>
</div>

<script>
// ── 狀態 ──────────────────────────
let currentLog = 'cron';
let countdown  = 5;
let timer;
let lastData   = null;

const AGENT_COLORS = {
  'writer':         '#22D3EE',
  'reviewer':       '#A78BFA',
  'poster':         '#22C55E',
  'quality-check':  '#F59E0B',
  'researcher':     '#60A5FA',
  'topic-selector': '#22D3EE',
  'feedback':       '#A78BFA',
  'publisher':      '#22C55E',
  'seo':            '#F59E0B',
  'system':         '#4A6480',
};
function agentColor(a){ return AGENT_COLORS[a] || '#4A6480'; }

const CAT_COLORS = {
  A:'#22D3EE', B:'#A78BFA', C:'#22C55E', D:'#60A5FA'
};
const CAT_LABELS = {
  A:'電容/壓力感測', B:'手勢/彎曲感測', C:'互動設計', D:'IoT/ESP32'
};

// ── 主循環 ──────────────────────────
async function fetchNow(){
  clearInterval(timer);
  countdown = 5;
  try{
    const r   = await fetch('/api/status');
    const d   = await r.json();
    lastData  = d;
    render(d);
  }catch(e){
    setPill('error','連線失敗');
  }
  startTimer();
}

function startTimer(){
  clearInterval(timer);
  timer = setInterval(()=>{
    countdown--;
    const el = document.getElementById('countdown');
    if(el) el.textContent = countdown + 's';
    if(countdown <= 0) fetchNow();
  }, 1000);
}

// ── 渲染 ──────────────────────────
function render(d){
  document.getElementById('ts').textContent = d.ts;
  document.getElementById('warn-banner').style.display = d.has_placeholder ? 'flex':'none';

  setPill(d.state, {idle:'待機中', running:'執行中', error:'有錯誤'}[d.state] || d.state);

  // KPI
  document.getElementById('k-today').textContent     = d.pipeline.count || 0;
  document.getElementById('k-total').textContent     = d.article_count  || 0;
  document.getElementById('k-api-today').textContent = d.usage.today    || 0;
  document.getElementById('k-api-total').textContent = d.usage.total    || 0;
  document.getElementById('k-cron').textContent      = d.cron_count     || 0;

  // model badge
  const mb = document.getElementById('model-badge');
  mb.innerHTML = `<div class="model-badge">
    <span style="color:var(--green)">●</span>
    <span style="font-size:11px;color:var(--text3)">${esc(d.api.model)}</span>
  </div>`;

  renderPipeline(d.pipeline, d.articles || []);
  renderFeed(d.feed);
  renderTopics(d.perf);
  renderLog(d);
}

function setPill(state, label){
  const el = document.getElementById('state-pill');
  el.className = 'state-pill state-' + state;
  el.querySelector('.state-txt').textContent = label;
}

function renderPipeline(pipe, articles){
  const track = document.getElementById('pipeline-track');
  const STAGES = pipe.stages;
  let html = '<div class="pipeline-track">';
  STAGES.forEach((s,i)=>{
    const isDone   = s.done;
    const isActive = !isDone && i > 0 && STAGES[i-1].done;
    const cls = isDone?'done': isActive?'active':'';
    const icon = isDone?'✓': isActive?'◉':'○';
    html += `<div class="pipe-node ${cls}" title="${s.label}">
      <div class="pipe-ring">${icon}</div>
      <div class="pipe-name">${s.label}</div>
    </div>`;
    if(i < STAGES.length-1){
      const connCls = isDone ? (STAGES[i+1].done ? 'done' : 'active') : '';
      html += `<div class="pipe-conn ${connCls}"></div>`;
    }
  });
  html += '</div>';
  track.innerHTML = html;

  // article slot
  const slot = document.getElementById('pipe-article-slot');
  if(pipe.article){
    const a = pipe.article;
    slot.innerHTML = `<div class="article-card" onclick="openArticle('${esc(a.name||'')}','${esc(a.title||a.name||'')}')">
      <div class="article-card-left">
        <div class="article-title">${esc(a.title || a.name || '未命名')}</div>
        <div class="article-meta">
          狀態：<span class="badge badge-cyan">${esc(a.status||'')}</span>
          &nbsp;·&nbsp;${esc(a.date||'')}
        </div>
      </div>
      <div class="article-card-right">
        <div class="view-btn">閱讀全文 →</div>
      </div>
    </div>
    ${articles.length>1?renderArticleList(articles):''}`;
  } else {
    slot.innerHTML = `<div class="pipe-none">
      今日尚未產出文章<br>
      <span style="font-size:10px">Cron 每日 09:00 UTC 自動執行</span>
      ${articles.length?renderArticleList(articles):''}
    </div>`;
  }
}

function renderArticleList(arts){
  if(!arts||!arts.length) return '';
  return `<div class="articles-list">
    <div class="section-label" style="margin-bottom:8px;margin-top:14px;">
      <span class="dot" style="background:var(--text3)"></span>文章庫
    </div>
    ${arts.slice(0,6).map(a=>`
      <div class="art-item">
        <div class="art-name" title="${esc(a.title)}">${esc(a.title)}</div>
        <div class="art-meta">${a.words||''} 字</div>
        <div class="art-btn" onclick="openArticle('${esc(a.name)}','${esc(a.title)}')">閱讀</div>
      </div>`).join('')}
  </div>`;
}

function renderFeed(feed){
  const el = document.getElementById('feed-list');
  if(!feed||!feed.length){
    el.innerHTML = '<div style="padding:20px 0;text-align:center;color:var(--text3);font-size:12px;">尚無活動記錄</div>';
    return;
  }
  el.innerHTML = feed.map(f=>`
    <div class="feed-item">
      <div class="feed-dot ${f.type}"></div>
      <div class="feed-body">
        <div>
          <span class="feed-agent-badge"
            style="background:${agentColor(f.agent)}22;color:${agentColor(f.agent)};border:1px solid ${agentColor(f.agent)}44;">
            ${esc(f.agent)}
          </span>
        </div>
        <div class="feed-msg">${esc(f.msg)}</div>
        ${f.time?`<div class="feed-time">${esc(f.time)}</div>`:''}
      </div>
    </div>`).join('');
}

function renderTopics(perf){
  const el = document.getElementById('topics-grid');
  el.innerHTML = ['A','B','C','D'].map(c=>{
    const d   = perf[c] || {avg_upvotes:0,avg_comments:0,count:0};
    const w   = Math.min(d.avg_upvotes * 2, 100);
    const col = CAT_COLORS[c];
    return `<div class="topic-box">
      <div class="topic-cat" style="color:${col}">${c} 類</div>
      <div class="topic-name">${CAT_LABELS[c]}</div>
      <div class="topic-val" style="color:${col}">${Number(d.avg_upvotes||0).toFixed(0)}</div>
      <div class="topic-sub">avg upvotes · ${d.count} 篇</div>
      <div class="topic-bar">
        <div class="topic-fill" style="width:${w}%;background:${col}"></div>
      </div>
    </div>`;
  }).join('');
}

function renderLog(d){
  const el    = document.getElementById('log-body');
  const lines = currentLog==='cron' ? d.cron_log_tail : d.error_log;
  if(!lines||!lines.length){ el.textContent='（無記錄）'; return; }
  el.innerHTML = lines.map(l=>{
    let cls='';
    if(/error|fail|FAIL/i.test(l))          cls='ll-e';
    else if(/APPROVED|success|完成/i.test(l)) cls='ll-s';
    else if(/REJECTED|warn|WARNING/i.test(l)) cls='ll-w';
    return cls ? `<span class="${cls}">${esc(l)}</span>` : esc(l);
  }).join('\n');
  el.scrollTop = el.scrollHeight;
}

function switchLog(type, btn){
  currentLog = type;
  document.querySelectorAll('.log-tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  if(lastData) renderLog(lastData);
}

// ── 文章 Modal ──────────────────────
async function openArticle(name, title){
  if(!name) return;
  document.getElementById('modal-title').textContent = title || name;
  document.getElementById('modal-body').textContent  = '載入中...';
  document.getElementById('modal-meta').textContent  = '';
  document.getElementById('modal').classList.add('open');
  try{
    const r = await fetch('/api/article?name=' + encodeURIComponent(name));
    if(r.ok){
      const txt = await r.text();
      document.getElementById('modal-body').textContent = txt;
      document.getElementById('modal-meta').textContent =
        `${name}.md  ·  ${txt.length} 字元`;
    } else {
      document.getElementById('modal-body').textContent = '找不到文章。';
    }
  }catch(e){
    document.getElementById('modal-body').textContent = '載入失敗：' + e;
  }
}

function closeModal(e){
  if(!e || e.target.id==='modal'){
    document.getElementById('modal').classList.remove('open');
  }
}

document.addEventListener('keydown', e=>{
  if(e.key==='Escape') closeModal({target:{id:'modal'}});
});

// ── 工具 ──────────────────────────
function esc(s){
  return String(s||'')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

fetchNow();
</script>
</body>
</html>"""

# ── HTTP Server ───────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            data = json.dumps(get_status_data(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        elif self.path.startswith("/api/article"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            name   = params.get("name", [""])[0]
            # 安全性：只允許字母、數字、連字號、底線、日期格式
            if name and re.match(r'^[\w\-\.]{1,100}$', name):
                content = get_article_content(name)
                if content:
                    body = content.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                    return
            self.send_response(404)
            self.end_headers()

        else:
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 3000))
    print(f"Dashboard v3 啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
