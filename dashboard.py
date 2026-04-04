#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v2 — 即時互動版
執行：python3 ~/ai-factory/dashboard.py
訪問：http://VPS_IP:3000
"""

import json, os, re, subprocess, time
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
    """判斷系統目前狀態"""
    cron_log = rt("logs/cron.log", 5)
    err_log  = rt("logs/error.log", 3)
    prog     = rj("logs/progress.json", [])

    # 有錯誤日誌且在過去10分鐘？
    if err_log:
        return "error"

    # cron 日誌有最新活動（今天）
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if any(today[:7] in l or "2026" in l for l in cron_log):
        return "running"

    return "idle"

def activity_feed():
    """從 logs 重建活動流水線"""
    events = []

    # 從 progress.json 取文章進度
    prog = rj("logs/progress.json", [])
    for p in reversed(prog[-10:]):
        events.append({
            "time": p.get("timestamp","")[:16].replace("T"," "),
            "agent": "writer",
            "msg": f"文章完成：{p.get('title','')}",
            "type": "success"
        })

    # 從 cron.log 取執行記錄
    for line in reversed(rt("logs/cron.log", 20)):
        line = line.strip()
        if not line: continue
        agent = "system"
        t = "info"
        if "APPROVED" in line: t = "success"; agent = "quality-check"
        elif "REJECTED" in line: t = "warn";    agent = "quality-check"
        elif "ERROR" in line or "error" in line.lower(): t = "error"; agent = "system"
        elif "writer" in line.lower(): agent = "writer"
        elif "reviewer" in line.lower(): agent = "reviewer"
        elif "poster" in line.lower(): agent = "poster"
        elif "feedback" in line.lower(): agent = "feedback"
        events.append({"time": "", "agent": agent, "msg": line[:120], "type": t})

    # 從 error.log 取錯誤
    for line in reversed(rt("logs/error.log", 5)):
        if line.strip():
            events.append({"time":"","agent":"system","msg":line[:120],"type":"error"})

    return events[:25]

def pipeline_status():
    """今日生產流水線狀態"""
    prog = rj("logs/progress.json", [])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_items = [p for p in prog if p.get("date","") == today]

    stages = [
        {"id":"researcher",     "label":"研究員",    "done": False},
        {"id":"topic-selector", "label":"選題",      "done": False},
        {"id":"writer",         "label":"寫作",      "done": False},
        {"id":"reviewer",       "label":"審查",      "done": False},
        {"id":"poster",         "label":"發文準備",  "done": False},
        {"id":"published",      "label":"已發布",    "done": False},
    ]

    if today_items:
        status = today_items[-1].get("status","")
        done_map = {
            "reviewed": ["researcher","topic-selector","writer","reviewer"],
            "posted":   ["researcher","topic-selector","writer","reviewer","poster"],
            "published":["researcher","topic-selector","writer","reviewer","poster","published"],
        }
        done_ids = done_map.get(status, [])
        for s in stages:
            if s["id"] in done_ids:
                s["done"] = True
        return {"stages": stages, "article": today_items[-1], "count": len(today_items)}

    return {"stages": stages, "article": None, "count": 0}

def api_usage():
    """API 使用次數統計（從 logs 估算）"""
    usage = rj("logs/api-usage.json", {"today":0,"total":0,"sessions":[]})
    return usage

def get_status_data():
    """組合所有狀態資料，回傳 JSON"""
    prog   = rj("logs/progress.json", [])
    perf   = rj("logs/topic-performance.json", {})
    api    = api_status()
    crons  = cron_lines()
    usage  = api_usage()
    pipe   = pipeline_status()
    feed   = activity_feed()
    state  = system_state()
    has_ph = "PLACEHOLDER" in (BASE / "CLAUDE.md").read_text(encoding="utf-8") if (BASE/"CLAUDE.md").exists() else True

    articles = sorted((BASE/"articles").glob("20*.md"), reverse=True)
    latest_article = None
    if articles:
        a = articles[0]
        content = a.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        title = next((l.lstrip("#").strip() for l in lines if l.startswith("#")), a.stem)
        size  = len(content)
        latest_article = {"name": a.stem, "title": title[:60], "size": size}

    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "state": state,
        "api": api,
        "cron_count": len(crons),
        "has_placeholder": has_ph,
        "article_count": len(prog),
        "latest": latest_article,
        "pipeline": pipe,
        "feed": feed,
        "usage": usage,
        "perf": perf.get("categories", {}),
        "cron_log_tail": rt("logs/cron.log", 40),
        "error_log": rt("logs/error.log", 20),
    }

# ── HTML ──────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 無人工廠</title>
<style>
:root{
  --bg:#070d1a;--card:#0f1829;--card2:#141f30;--border:#1e3a5f;
  --text:#e2eaf5;--muted:#5a7a9a;--accent:#38bdf8;
  --green:#22d45a;--yellow:#f5a623;--red:#f04455;--purple:#a78bfa;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'SF Pro Display',system-ui,sans-serif;font-size:13px;min-height:100vh;}

/* TOP BAR */
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;height:52px;background:var(--card);
  border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;}
.topbar-left{display:flex;align-items:center;gap:12px;}
.logo{font-size:15px;font-weight:700;color:var(--accent);letter-spacing:-.3px;}
.state-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px;}
.state-idle   .state-dot{background:var(--muted);}
.state-running .state-dot{background:var(--green);box-shadow:0 0 6px var(--green);animation:pulse 1.5s infinite;}
.state-error  .state-dot{background:var(--red);box-shadow:0 0 6px var(--red);}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.4;}}
.state-label{font-size:12px;font-weight:600;}
.state-idle    .state-label{color:var(--muted);}
.state-running .state-label{color:var(--green);}
.state-error   .state-label{color:var(--red);}
.ts-label{font-size:11px;color:var(--muted);}
.refresh-btn{background:none;border:1px solid var(--border);color:var(--muted);
  padding:4px 10px;border-radius:6px;cursor:pointer;font-size:11px;transition:.2s;}
.refresh-btn:hover{border-color:var(--accent);color:var(--accent);}

/* WARN BANNER */
.warn-banner{background:rgba(245,166,35,.07);border-bottom:1px solid rgba(245,166,35,.2);
  padding:8px 24px;font-size:12px;color:var(--yellow);display:flex;align-items:center;gap:8px;}

/* LAYOUT */
.main{padding:16px 24px;display:grid;
  grid-template-columns:280px 1fr 320px;
  grid-template-rows:auto auto 1fr;
  gap:14px;max-width:1600px;margin:0 auto;}

/* CARDS */
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;}
.card-title{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;
  color:var(--muted);margin-bottom:12px;display:flex;align-items:center;gap:6px;}
.card-title .dot{width:6px;height:6px;border-radius:50%;background:currentColor;}

/* TODAY STATUS */
.today-card{grid-row:1;}
.stat-big{font-size:42px;font-weight:800;color:var(--accent);line-height:1;}
.stat-sub{font-size:11px;color:var(--muted);margin-top:2px;}
.today-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px;}
.today-stat{background:var(--card2);border:1px solid var(--border);border-radius:8px;
  padding:10px 12px;}
.today-stat .val{font-size:22px;font-weight:700;}
.today-stat .lbl{font-size:10px;color:var(--muted);margin-top:1px;}
.val-green{color:var(--green);}
.val-yellow{color:var(--yellow);}
.val-accent{color:var(--accent);}
.val-purple{color:var(--purple);}

/* PIPELINE */
.pipeline-card{grid-column:2;grid-row:1;}
.pipeline{display:flex;align-items:center;gap:0;margin-top:4px;}
.pipe-stage{flex:1;display:flex;flex-direction:column;align-items:center;position:relative;}
.pipe-stage::after{content:'';position:absolute;top:14px;left:50%;width:100%;height:2px;
  background:var(--border);z-index:0;}
.pipe-stage:last-child::after{display:none;}
.pipe-circle{width:28px;height:28px;border-radius:50%;border:2px solid var(--border);
  display:flex;align-items:center;justify-content:center;z-index:1;
  background:var(--card2);font-size:12px;transition:.3s;}
.pipe-stage.done .pipe-circle{border-color:var(--green);background:rgba(34,212,90,.15);color:var(--green);}
.pipe-stage.done::after{background:var(--green);}
.pipe-stage.active .pipe-circle{border-color:var(--accent);background:rgba(56,189,248,.15);
  color:var(--accent);box-shadow:0 0 10px rgba(56,189,248,.3);animation:pulse 1.5s infinite;}
.pipe-lbl{font-size:10px;color:var(--muted);margin-top:5px;text-align:center;}
.pipe-stage.done .pipe-lbl{color:var(--green);}
.pipe-stage.active .pipe-lbl{color:var(--accent);}
.pipe-article{margin-top:14px;background:var(--card2);border:1px solid var(--border);
  border-radius:8px;padding:10px 14px;font-size:12px;}
.pipe-article .title{color:var(--text);font-weight:500;margin-bottom:4px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;}
.pipe-article .meta{color:var(--muted);font-size:11px;}
.pipe-none{color:var(--muted);font-size:12px;text-align:center;padding:20px 0;}

/* API 使用量 */
.api-card{grid-row:1;}
.api-model{font-size:13px;font-weight:600;color:var(--green);margin-bottom:10px;}
.api-row{display:flex;justify-content:space-between;align-items:center;
  padding:7px 0;border-bottom:1px solid rgba(30,58,95,.5);}
.api-row:last-child{border-bottom:none;}
.api-key{color:var(--muted);font-size:12px;}
.api-val{font-weight:600;font-size:13px;}
.usage-bar-wrap{margin-top:10px;}
.usage-bar-label{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-bottom:4px;}
.usage-bar{background:var(--card2);border-radius:4px;height:4px;overflow:hidden;}
.usage-fill{background:linear-gradient(90deg,var(--accent),var(--purple));height:100%;
  border-radius:4px;transition:width .5s ease;}

/* FEED */
.feed-card{grid-column:3;grid-row:1/3;display:flex;flex-direction:column;}
.feed-list{flex:1;overflow-y:auto;max-height:500px;display:flex;flex-direction:column;gap:6px;}
.feed-list::-webkit-scrollbar{width:3px;}
.feed-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}
.feed-item{display:flex;gap:8px;padding:7px 10px;border-radius:7px;
  background:var(--card2);border:1px solid var(--border);font-size:11px;
  transition:border-color .2s;}
.feed-item:hover{border-color:var(--accent);}
.feed-item.success{border-left:2px solid var(--green);}
.feed-item.warn   {border-left:2px solid var(--yellow);}
.feed-item.error  {border-left:2px solid var(--red);}
.feed-item.info   {border-left:2px solid var(--border);}
.feed-agent{font-weight:600;white-space:nowrap;min-width:70px;color:var(--accent);}
.feed-msg{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.feed-time{color:var(--muted);font-size:10px;opacity:.6;white-space:nowrap;}

/* PERF */
.perf-card{grid-column:1/3;grid-row:2;}
.perf-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.perf-box{background:var(--card2);border:1px solid var(--border);border-radius:8px;padding:12px;}
.perf-cat{font-size:22px;font-weight:800;color:var(--accent);margin-bottom:4px;}
.perf-num{font-size:26px;font-weight:700;color:var(--text);}
.perf-label{font-size:10px;color:var(--muted);}
.perf-bar-wrap{margin-top:8px;}
.perf-bar{background:var(--border);border-radius:3px;height:3px;overflow:hidden;}
.perf-fill{background:var(--accent);height:100%;border-radius:3px;transition:width .5s;}

/* LOG */
.log-card{grid-column:1/4;grid-row:3;}
.log-tabs{display:flex;gap:4px;margin-bottom:10px;}
.log-tab{padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer;
  background:var(--card2);border:1px solid var(--border);color:var(--muted);transition:.2s;}
.log-tab.active{background:rgba(56,189,248,.1);border-color:var(--accent);color:var(--accent);}
.log-content{font-family:monospace;font-size:11px;color:var(--muted);
  background:var(--card2);border:1px solid var(--border);border-radius:8px;
  padding:12px 14px;height:200px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;}
.log-content::-webkit-scrollbar{width:3px;}
.log-content::-webkit-scrollbar-thumb{background:var(--border);}
.log-line-error{color:var(--red);}
.log-line-success{color:var(--green);}
.log-line-warn{color:var(--yellow);}

/* MISC */
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:999px;
  font-size:11px;font-weight:600;}
.badge-green{background:rgba(34,212,90,.12);color:var(--green);}
.badge-red  {background:rgba(240,68,85,.12); color:var(--red);}
.badge-yellow{background:rgba(245,166,35,.12);color:var(--yellow);}
.badge-blue {background:rgba(56,189,248,.12);color:var(--accent);}
.no-data{color:var(--muted);font-style:italic;font-size:12px;padding:10px 0;}
.blink{animation:pulse 1s infinite;}
</style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar" id="topbar">
  <div class="topbar-left">
    <span class="logo">🏭 AI 無人工廠</span>
    <div id="state-indicator" class="state-idle">
      <span class="state-dot"></span>
      <span class="state-label">載入中...</span>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:14px;">
    <span class="ts-label" id="ts">--</span>
    <span class="ts-label" id="refresh-countdown" style="color:var(--accent);font-size:11px;"></span>
    <button class="refresh-btn" onclick="fetchNow()">⟳ 立即更新</button>
  </div>
</div>

<!-- WARN BANNER -->
<div class="warn-banner" id="warn-banner" style="display:none">
  ⚠️ <strong>待完成：</strong>CLAUDE.md 中仍有 PLACEHOLDER_WHOP_* — 填入真實連結後才能在文章中放置銷售連結
</div>

<div class="main">

  <!-- TODAY STATUS -->
  <div class="card today-card" id="today-card">
    <div class="card-title"><span class="dot" style="background:var(--accent)"></span>今日任務</div>
    <div class="stat-big" id="today-count">0</div>
    <div class="stat-sub">篇文章已產出</div>
    <div class="today-grid">
      <div class="today-stat">
        <div class="val val-green" id="usage-today">0</div>
        <div class="lbl">今日 API 呼叫</div>
      </div>
      <div class="today-stat">
        <div class="val val-accent" id="usage-total">0</div>
        <div class="lbl">累計呼叫</div>
      </div>
      <div class="today-stat">
        <div class="val val-yellow" id="cron-count">0</div>
        <div class="lbl">Cron 排程</div>
      </div>
      <div class="today-stat">
        <div class="val val-purple" id="article-total">0</div>
        <div class="lbl">總文章數</div>
      </div>
    </div>
    <div style="margin-top:12px;" id="api-status-row"></div>
  </div>

  <!-- PIPELINE -->
  <div class="card pipeline-card">
    <div class="card-title"><span class="dot" style="background:var(--green)"></span>生產流水線</div>
    <div class="pipeline" id="pipeline"></div>
    <div id="pipe-article"></div>
  </div>

  <!-- FEED -->
  <div class="card feed-card" style="grid-row:1/3">
    <div class="card-title"><span class="dot blink" style="background:var(--accent)"></span>團隊活動流</div>
    <div class="feed-list" id="feed-list"></div>
  </div>

  <!-- PERF -->
  <div class="card perf-card">
    <div class="card-title"><span class="dot" style="background:var(--purple)"></span>主題表現</div>
    <div class="perf-grid" id="perf-grid"></div>
  </div>

  <!-- LOG -->
  <div class="card log-card">
    <div class="card-title"><span class="dot" style="background:var(--muted)"></span>執行日誌</div>
    <div class="log-tabs">
      <div class="log-tab active" onclick="switchLog('cron')">Cron 日誌</div>
      <div class="log-tab" onclick="switchLog('error')">錯誤日誌</div>
    </div>
    <div class="log-content" id="log-content"></div>
  </div>

</div>

<script>
let currentLog = 'cron';
let countdown = 5;
let timer;
let lastData = null;

const AGENT_COLORS = {
  'writer':'#38bdf8','reviewer':'#a78bfa','poster':'#22d45a',
  'quality-check':'#f5a623','researcher':'#f04455','system':'#5a7a9a',
  'feedback':'#a78bfa','topic-selector':'#38bdf8','seo':'#22d45a',
};

function agentColor(a){ return AGENT_COLORS[a] || '#5a7a9a'; }

async function fetchNow(){
  clearInterval(timer);
  countdown = 5;
  try{
    const r = await fetch('/api/status');
    const d = await r.json();
    lastData = d;
    render(d);
  }catch(e){
    document.getElementById('state-indicator').className='state-error';
    document.getElementById('state-indicator').querySelector('.state-label').textContent='連線失敗';
  }
  startTimer();
}

function startTimer(){
  clearInterval(timer);
  countdown = 5;
  timer = setInterval(()=>{
    countdown--;
    const el = document.getElementById('refresh-countdown');
    if(el) el.textContent = `${countdown}s`;
    if(countdown <= 0){ fetchNow(); }
  }, 1000);
}

function render(d){
  // timestamp
  document.getElementById('ts').textContent = d.ts;

  // warn banner
  const wb = document.getElementById('warn-banner');
  wb.style.display = d.has_placeholder ? 'flex' : 'none';

  // state
  const si = document.getElementById('state-indicator');
  si.className = 'state-' + d.state;
  si.querySelector('.state-label').textContent =
    d.state==='running'?'執行中': d.state==='error'?'有錯誤':'待機中';

  // today
  document.getElementById('today-count').textContent = d.pipeline.count || 0;
  document.getElementById('usage-today').textContent = d.usage.today || 0;
  document.getElementById('usage-total').textContent = d.usage.total || 0;
  document.getElementById('cron-count').textContent = d.cron_count;
  document.getElementById('article-total').textContent = d.article_count;

  const apiRow = document.getElementById('api-status-row');
  apiRow.innerHTML = `<span class="badge ${d.api.minimax?'badge-green':'badge-yellow'}">
    ${d.api.minimax?'✓':'⚠'} ${d.api.model}</span>`;

  // pipeline
  renderPipeline(d.pipeline);

  // feed
  renderFeed(d.feed);

  // perf
  renderPerf(d.perf);

  // log
  renderLog(d);
}

function renderPipeline(pipe){
  const el = document.getElementById('pipeline');
  el.innerHTML = pipe.stages.map((s,i)=>{
    const isDone = s.done;
    const isActive = !isDone && i > 0 && pipe.stages[i-1].done;
    const cls = isDone?'done': isActive?'active':'';
    const icon = isDone?'✓': isActive?'●':'○';
    return `<div class="pipe-stage ${cls}">
      <div class="pipe-circle">${icon}</div>
      <div class="pipe-lbl">${s.label}</div>
    </div>`;
  }).join('');

  const pa = document.getElementById('pipe-article');
  if(pipe.article){
    pa.innerHTML = `<div class="pipe-article">
      <div class="title">📄 ${pipe.article.title||pipe.article.name||'未命名'}</div>
      <div class="meta">狀態：<span class="badge badge-blue">${pipe.article.status}</span>
        &nbsp;日期：${pipe.article.date||''}</div>
    </div>`;
  } else {
    pa.innerHTML = `<div class="pipe-none">今日尚未產出文章<br><span style="font-size:10px;color:var(--muted)">Cron 每日 09:00 UTC 自動執行</span></div>`;
  }
}

function renderFeed(feed){
  const el = document.getElementById('feed-list');
  if(!feed||!feed.length){
    el.innerHTML = '<div class="no-data">尚無活動記錄</div>'; return;
  }
  el.innerHTML = feed.map(f=>`
    <div class="feed-item ${f.type}">
      <span class="feed-agent" style="color:${agentColor(f.agent)}">${f.agent}</span>
      <span class="feed-msg">${esc(f.msg)}</span>
      ${f.time?`<span class="feed-time">${f.time}</span>`:''}
    </div>`).join('');
}

function renderPerf(perf){
  const el = document.getElementById('perf-grid');
  const cats = ['A','B','C','D'];
  const labels = {A:'電容/壓力感測',B:'手勢/彎曲感測',C:'互動設計',D:'IoT/ESP32'};
  el.innerHTML = cats.map(c=>{
    const d = perf[c]||{avg_upvotes:0,avg_comments:0,count:0};
    const w = Math.min(d.avg_upvotes*2,100);
    return `<div class="perf-box">
      <div class="perf-cat">${c}</div>
      <div style="font-size:10px;color:var(--muted);margin-bottom:6px">${labels[c]}</div>
      <div class="perf-num">${d.avg_upvotes.toFixed(0)}</div>
      <div class="perf-label">avg upvotes · ${d.count} 篇</div>
      <div class="perf-bar-wrap">
        <div class="perf-bar"><div class="perf-fill" style="width:${w}%"></div></div>
      </div>
    </div>`;
  }).join('');
}

function renderLog(d){
  const el = document.getElementById('log-content');
  const lines = currentLog==='cron' ? d.cron_log_tail : d.error_log;
  if(!lines||!lines.length){ el.textContent='（無記錄）'; return; }
  el.innerHTML = lines.map(l=>{
    let cls='';
    if(/error|fail|FAIL/i.test(l)) cls='log-line-error';
    else if(/APPROVED|success|完成/i.test(l)) cls='log-line-success';
    else if(/REJECTED|warn|WARNING/i.test(l)) cls='log-line-warn';
    return `<span class="${cls}">${esc(l)}</span>`;
  }).join('\n');
  el.scrollTop = el.scrollHeight;
}

function switchLog(type){
  currentLog = type;
  document.querySelectorAll('.log-tab').forEach((t,i)=>{
    t.classList.toggle('active', (i===0&&type==='cron')||(i===1&&type==='error'));
  });
  if(lastData) renderLog(lastData);
}

function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// 初始載入
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
        else:
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 3000))
    print(f"Dashboard v2 啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
