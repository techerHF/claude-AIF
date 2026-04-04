#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v4 — 高級控制台 + 診斷中心
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
    err_log  = [l for l in rt("logs/error.log", 3) if l.strip()]
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
        if "APPROVED"  in line: t, agent = "success", "quality-check"
        elif "REJECTED" in line: t, agent = "warn",    "quality-check"
        elif "error"   in line.lower(): t, agent = "error", "system"
        elif "writer"  in line.lower(): agent = "writer"
        elif "reviewer" in line.lower(): agent = "reviewer"
        elif "poster"  in line.lower(): agent = "poster"
        elif "feedback" in line.lower(): agent = "feedback"
        elif "researcher" in line.lower(): agent = "researcher"
        events.append({"time":"","agent":agent,"msg":line[:120],"type":t})
    for line in reversed(rt("logs/error.log",5)):
        if line.strip():
            events.append({"time":"","agent":"system","msg":line[:120],"type":"error"})
    return events[:30]

def pipeline_status():
    prog  = rj("logs/progress.json", [])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_items = [p for p in prog if p.get("date","") == today]
    stages = [
        {"id":"researcher",    "label":"研究員", "agent":"researcher"},
        {"id":"topic-selector","label":"選題",   "agent":"topic-selector"},
        {"id":"writer",        "label":"寫作",   "agent":"writer"},
        {"id":"reviewer",      "label":"審查",   "agent":"reviewer"},
        {"id":"poster",        "label":"發文準備","agent":"poster"},
        {"id":"published",     "label":"已發布", "agent":"publisher"},
    ]
    done_map = {
        "reviewed": ["researcher","topic-selector","writer","reviewer"],
        "posted":   ["researcher","topic-selector","writer","reviewer","poster"],
        "published":["researcher","topic-selector","writer","reviewer","poster","published"],
    }
    if today_items:
        item   = today_items[-1]
        status = item.get("status","")
        done   = set(done_map.get(status, []))
        for s in stages:
            s["done"] = s["id"] in done
        return {"stages":stages,"article":item,"count":len(today_items)}
    return {"stages":stages,"article":None,"count":0}

def api_usage():
    return rj("logs/api-usage.json", {"today":0,"total":0})

def list_articles():
    try:
        arts = sorted(BASE.glob("articles/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = []
        for a in arts[:20]:
            content = a.read_text(encoding="utf-8", errors="ignore")
            lines   = content.splitlines()
            title   = next((l.lstrip("#").strip() for l in lines if l.startswith("#")), a.stem)
            words   = len(re.sub(r'```.*?```','',content,flags=re.DOTALL).split())
            result.append({"name":a.stem,"title":title[:80],"size":len(content),"words":words})
        return result
    except:
        return []

def get_article_content(name):
    try:
        p = BASE / "articles" / f"{name}.md"
        if not p.exists(): return None
        return p.read_text(encoding="utf-8", errors="ignore")
    except:
        return None

def run_diagnostics():
    """從真實系統資料計算診斷報告"""
    issues = []
    score  = 100

    # ── 1. CLAUDE.md placeholder ──
    has_ph = False
    try: has_ph = "PLACEHOLDER" in (BASE/"CLAUDE.md").read_text(encoding="utf-8")
    except: pass
    if has_ph:
        issues.append({"level":"warn","title":"WHOP 連結未設定",
            "desc":"CLAUDE.md 含 PLACEHOLDER_WHOP_*，文章無法放銷售連結","tag":"設定"})
        score -= 15

    # ── 2. error.log ──
    err_lines = [l.strip() for l in rt("logs/error.log",5) if l.strip()]
    if err_lines:
        issues.append({"level":"error","title":f"系統錯誤 × {len(err_lines)}",
            "desc":err_lines[-1][:90],"tag":"錯誤"})
        score -= 20

    # ── 3. cron ──
    crons = cron_lines()
    if len(crons) == 0:
        issues.append({"level":"error","title":"排程器未設定",
            "desc":"未找到 ai-factory Cron 排程，系統不會自動執行","tag":"排程"})
        score -= 20
    elif len(crons) > 2:
        issues.append({"level":"warn","title":f"Cron 重複 ({len(crons)} 筆)",
            "desc":"偵測到重複排程，建議清理避免重複觸發","tag":"排程"})
        score -= 5
    else:
        issues.append({"level":"ok","title":"排程器正常",
            "desc":f"{len(crons)} 個排程運行中","tag":"排程"})

    # ── 4. model / API ──
    api = api_status()
    if api["minimax"]:
        issues.append({"level":"ok","title":"模型連線正常",
            "desc":api["model"],"tag":"API"})
    else:
        issues.append({"level":"info","title":"使用預設 Claude 模型",
            "desc":"未偵測到 MiniMax 設定，將使用 Claude 預設","tag":"API"})
        score -= 5

    # ── 5. 文章內容檢查 ──
    art_dir   = BASE / "articles"
    art_files = sorted(art_dir.glob("*.md"), reverse=True)[:5] if art_dir.exists() else []
    if art_files:
        ph_in_art = 0
        for f in art_files:
            try:
                if "PLACEHOLDER" in f.read_text("utf-8","ignore"): ph_in_art += 1
            except: pass
        if ph_in_art:
            issues.append({"level":"warn","title":f"文章含未替換連結 × {ph_in_art}",
                "desc":"部分文章仍有 PLACEHOLDER_WHOP_*","tag":"內容"})
            score -= 5

    # ── 6. 主題多樣性 ──
    prog = rj("logs/progress.json", [])
    if len(prog) >= 4:
        recent_str = " ".join(p.get("title","") for p in prog[-5:])
        dominant = None
        for kw in ["電容","壓力","手勢","IoT","ESP32","互動"]:
            if recent_str.count(kw) >= 2:
                dominant = kw; break
        if dominant:
            issues.append({"level":"info","title":"主題分佈偏向單一",
                "desc":f"最近文章「{dominant}」相關比例偏高，建議增加多樣性","tag":"內容"})

    # ── 7. cron.log 活躍度 ──
    cron_log_lines = rt("logs/cron.log", 10)
    if not cron_log_lines:
        issues.append({"level":"info","title":"尚無執行記錄",
            "desc":"cron.log 為空，等待首次自動執行","tag":"狀態"})

    # 全部正常時的提示
    if score >= 100 and not [i for i in issues if i["level"] in ("error","warn")]:
        issues.insert(0, {"level":"ok","title":"所有系統正常運行",
            "desc":"無待處理問題，工廠運行中","tag":"狀態"})

    # ── 健康指標四格 ──
    cron_s = "ok" if 0 < len(crons) <= 2 else ("warn" if len(crons) > 2 else "error")
    health = [
        {"name":"模型", "status":"ok" if api["minimax"] else "info",
         "val": "MiniMax" if api["minimax"] else "預設"},
        {"name":"排程", "status": cron_s,
         "val": f"{len(crons)} 個"},
        {"name":"錯誤", "status":"error" if err_lines else "ok",
         "val": str(len(err_lines)) if err_lines else "無"},
        {"name":"設定", "status":"warn" if has_ph else "ok",
         "val": "待完成" if has_ph else "正常"},
    ]

    return {"score": max(0, score), "health": health, "issues": issues[:10]}

def get_status_data():
    prog   = rj("logs/progress.json", [])
    perf   = rj("logs/topic-performance.json", {})
    api    = api_status()
    crons  = cron_lines()
    usage  = api_usage()
    pipe   = pipeline_status()
    feed   = activity_feed()
    state  = system_state()
    diag   = run_diagnostics()
    has_ph = False
    try: has_ph = "PLACEHOLDER" in (BASE/"CLAUDE.md").read_text(encoding="utf-8")
    except: pass
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
        "diag":            diag,
        "cron_log_tail":   rt("logs/cron.log", 60),
        "error_log":       rt("logs/error.log", 30),
    }

# ── HTML / CSS / JS ───────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 無人工廠</title>
<style>
/* ════════════════════════════════
   色彩 Token — v4 語意色規則
   cyan  = 品牌 / 互動 / 當前活躍
   green = 成功 / 完成
   amber = 警告 / 注意
   red   = 錯誤 / 阻塞
   text  = 資料數值（白）
   ════════════════════════════════ */
:root{
  /* 3 層深色背景 */
  --bg0:#06101C;
  --bg1:#0C1826;
  --bg2:#101F32;
  --bg3:#152640;

  /* 邊框 */
  --b0: rgba(255,255,255,0.04);
  --b1: rgba(255,255,255,0.09);
  --b-hover: rgba(34,211,238,0.28);
  --b-active: rgba(34,211,238,0.45);

  /* 文字 */
  --t0:#E8F1FA;   /* 主要文字 */
  --t1:#8BA5C0;   /* 次要文字 */
  --t2:#4A6480;   /* 輔助 / 標籤 */

  /* 品牌主色 — 只用 cyan */
  --cyan:#22D3EE;
  --cyan-s:rgba(34,211,238,0.12);
  --cyan-m:rgba(34,211,238,0.22);

  /* 語意色 */
  --ok:  #22C55E; --ok-s:  rgba(34,197,94,0.12);
  --warn:#F59E0B; --warn-s:rgba(245,158,11,0.12);
  --err: #EF4444; --err-s: rgba(239,68,68,0.12);
  --info:#60A5FA; --info-s:rgba(96,165,250,0.10);
  --pur: #A78BFA; --pur-s: rgba(167,139,250,0.12);
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{min-height:100%;background:var(--bg0);color:var(--t0);
  font-family:'SF Pro Display',system-ui,-apple-system,sans-serif;font-size:13px;}

/* ─── TOPBAR ─── */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:50px;
  background:var(--bg1);
  border-bottom:1px solid var(--b0);
  position:sticky;top:0;z-index:300;
}
.tb-left{display:flex;align-items:center;gap:14px;}
.logo{font-size:14px;font-weight:700;letter-spacing:-.2px;
  color:var(--cyan);display:flex;align-items:center;gap:7px;}
.logo-icon{font-size:16px;}
.logo-sub{font-size:12px;color:var(--t2);font-weight:400;}

.state-pill{
  display:flex;align-items:center;gap:6px;
  padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;
  background:var(--bg2);border:1px solid var(--b0);
}
.s-dot{width:6px;height:6px;border-radius:50%;}
.st-idle    .s-dot{background:var(--t2);}
.st-running .s-dot{background:var(--ok);box-shadow:0 0 8px var(--ok);animation:pulse 1.5s infinite;}
.st-error   .s-dot{background:var(--err);box-shadow:0 0 8px var(--err);}
.st-idle    .s-txt{color:var(--t2);}
.st-running .s-txt{color:var(--ok);}
.st-error   .s-txt{color:var(--err);}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.3;}}

.tb-right{display:flex;align-items:center;gap:12px;}
.ts-txt{font-size:11px;color:var(--t2);}
.cd{font-size:11px;color:var(--cyan);font-variant-numeric:tabular-nums;min-width:22px;}
.rbtn{
  background:none;border:1px solid var(--b1);color:var(--t2);
  padding:4px 12px;border-radius:6px;cursor:pointer;font-size:11px;
  transition:.2s;
}
.rbtn:hover{border-color:var(--cyan);color:var(--cyan);}

/* ─── WARN BANNER ─── */
.warn-strip{
  background:rgba(245,158,11,.055);
  border-bottom:1px solid rgba(245,158,11,.16);
  padding:6px 28px;font-size:11.5px;color:var(--warn);
  display:none;align-items:center;gap:8px;
}

/* ─── KPI BAR ─── */
.kpi-bar{
  display:grid;grid-template-columns:repeat(5,1fr);
  background:var(--bg1);
  border-bottom:1px solid var(--b0);
}
.kpi-cell{
  padding:12px 20px;border-right:1px solid var(--b0);
  transition:.2s;cursor:default;
}
.kpi-cell:last-child{border-right:none;}
.kpi-cell:hover{background:var(--bg2);}
/* 數值全白，不同顏色靠語意決定 */
.kpi-val{font-size:24px;font-weight:700;letter-spacing:-.5px;line-height:1;color:var(--t0);}
.kpi-val.accent{color:var(--cyan);}   /* 今日產出 — 品牌色 */
.kpi-val.warn  {color:var(--warn);}   /* 待處理警告 */
.kpi-val.ok    {color:var(--ok);}     /* 明確成功指標 */
.kpi-lbl{font-size:10.5px;color:var(--t2);margin-top:3px;letter-spacing:.02em;}

/* ─── MAIN LAYOUT ─── */
.main{
  display:grid;
  grid-template-columns:1fr 330px;
  gap:16px;
  padding:20px 28px;
  max-width:1520px;
  margin:0 auto;
}
.left-col{display:flex;flex-direction:column;gap:16px;}

/* ─── CARD BASE ─── */
.card{
  background:var(--bg1);
  border:1px solid var(--b0);
  border-radius:12px;
  overflow:hidden;
  transition:border-color .25s,box-shadow .25s;
}
.card:hover{
  border-color:var(--b1);
  box-shadow:0 6px 30px rgba(0,0,0,.3);
}
.c-head{
  padding:14px 18px 12px;
  display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--b0);
}
.c-title{
  font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--t2);display:flex;align-items:center;gap:6px;
}
.c-dot{width:5px;height:5px;border-radius:50%;}
.c-body{padding:16px 18px;}

/* ─── PIPELINE ─── */
.pipe-track{
  display:flex;align-items:flex-start;
  position:relative;padding:2px 0 6px;
}
.pipe-conn{
  flex:1;height:1px;background:var(--bg3);
  margin-top:13px;transition:background .4s;
  min-width:16px;
}
.pipe-conn.done  {background:var(--ok);}
.pipe-conn.active{background:linear-gradient(90deg,var(--ok),var(--cyan));}

.pipe-node{
  display:flex;flex-direction:column;align-items:center;
  flex-shrink:0;cursor:pointer;width:60px;
}
.p-ring{
  width:28px;height:28px;border-radius:50%;
  border:1.5px solid var(--bg3);
  background:var(--bg2);color:var(--t2);
  display:flex;align-items:center;justify-content:center;
  font-size:11px;transition:.3s;
}
.pipe-node.done   .p-ring{border-color:var(--ok); background:var(--ok-s); color:var(--ok);}
.pipe-node.active .p-ring{
  border-color:var(--cyan);background:var(--cyan-s);color:var(--cyan);
  box-shadow:0 0 0 4px rgba(34,211,238,.07),0 0 12px var(--cyan-s);
  animation:pulse 1.5s infinite;
}
.pipe-node.error  .p-ring{border-color:var(--err);background:var(--err-s);color:var(--err);}
.p-lbl{font-size:9.5px;color:var(--t2);margin-top:5px;text-align:center;white-space:nowrap;}
.pipe-node.done   .p-lbl{color:var(--ok);}
.pipe-node.active .p-lbl{color:var(--cyan);}

.art-slot{margin-top:14px;}
.art-banner{
  background:var(--bg2);border:1px solid var(--b0);border-radius:9px;
  padding:12px 16px;cursor:pointer;transition:.25s;
  display:flex;align-items:center;justify-content:space-between;gap:10px;
}
.art-banner:hover{border-color:var(--b-hover);background:var(--bg3);}
.art-banner-title{font-size:13px;font-weight:600;color:var(--t0);margin-bottom:3px;}
.art-banner-meta{font-size:11px;color:var(--t2);}
.art-view-btn{
  font-size:10px;color:var(--cyan);
  border:1px solid rgba(34,211,238,.22);padding:3px 10px;border-radius:6px;
  background:var(--cyan-s);white-space:nowrap;flex-shrink:0;
}
.pipe-empty{
  margin-top:14px;background:var(--bg2);border:1px dashed var(--b1);
  border-radius:9px;padding:18px;text-align:center;
  color:var(--t2);font-size:12px;line-height:1.8;
}

/* ─── MID ROW ─── */
.mid-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;}

/* ─── DIAGNOSTICS ─── */
.diag-health{
  display:grid;grid-template-columns:repeat(4,1fr);gap:8px;
  margin-bottom:14px;
}
.h-pill{
  background:var(--bg2);border:1px solid var(--b0);border-radius:8px;
  padding:10px 12px;text-align:center;transition:.2s;
}
.h-pill:hover{border-color:var(--b1);}
.h-name{font-size:9.5px;color:var(--t2);letter-spacing:.05em;margin-bottom:4px;}
.h-val{font-size:13px;font-weight:700;}
.h-val.ok  {color:var(--ok);}
.h-val.warn{color:var(--warn);}
.h-val.err {color:var(--err);}
.h-val.info{color:var(--info);}

.diag-score-row{
  display:flex;align-items:center;gap:10px;margin-bottom:14px;
}
.score-num{font-size:28px;font-weight:800;letter-spacing:-.5px;}
.score-bar{flex:1;background:var(--bg3);border-radius:4px;height:5px;overflow:hidden;}
.score-fill{height:100%;border-radius:4px;transition:width .6s ease;}

.diag-list{display:flex;flex-direction:column;gap:6px;}
.diag-item{
  display:flex;gap:10px;align-items:flex-start;
  background:var(--bg2);border:1px solid var(--b0);border-radius:8px;
  padding:9px 12px;transition:.2s;
}
.diag-item:hover{border-color:var(--b1);}
.di-icon{
  width:18px;height:18px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:9px;font-weight:700;flex-shrink:0;margin-top:1px;
}
.di-icon.ok  {background:var(--ok-s);  color:var(--ok);}
.di-icon.warn{background:var(--warn-s);color:var(--warn);}
.di-icon.err {background:var(--err-s); color:var(--err);}
.di-icon.info{background:var(--info-s);color:var(--info);}
.di-body{flex:1;min-width:0;}
.di-title{font-size:12px;font-weight:600;color:var(--t0);}
.di-desc{font-size:10.5px;color:var(--t2);margin-top:2px;line-height:1.5;}
.di-tag{
  font-size:9px;font-weight:700;letter-spacing:.05em;
  padding:1px 6px;border-radius:4px;background:var(--bg3);color:var(--t2);
  flex-shrink:0;margin-top:2px;align-self:center;
}

/* ─── TOPICS ─── */
.topics-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.topic-box{
  background:var(--bg2);border:1px solid var(--b0);
  border-radius:8px;padding:12px;transition:.2s;
}
.topic-box:hover{border-color:var(--b1);transform:translateY(-1px);}
.t-cat{font-size:9.5px;font-weight:700;letter-spacing:.07em;margin-bottom:5px;}
.t-name{font-size:11px;color:var(--t2);margin-bottom:8px;line-height:1.4;}
.t-val{font-size:22px;font-weight:800;letter-spacing:-.4px;line-height:1;}
.t-sub{font-size:10px;color:var(--t2);margin-top:2px;}
.t-bar{background:var(--bg3);border-radius:3px;height:3px;margin-top:8px;overflow:hidden;}
.t-fill{height:100%;border-radius:3px;transition:width .6s;}

/* ─── LOGS ─── */
.log-tabs{display:flex;gap:4px;padding:12px 18px 0;}
.log-tab{
  padding:4px 13px;border-radius:6px;font-size:11px;
  cursor:pointer;color:var(--t2);
  background:var(--bg2);border:1px solid var(--b0);transition:.2s;
}
.log-tab:hover{color:var(--t1);}
.log-tab.active{background:var(--cyan-s);border-color:rgba(34,211,238,.28);color:var(--cyan);}
.log-body{
  font-family:'SF Mono',Menlo,Consolas,monospace;
  font-size:11px;line-height:1.75;color:var(--t2);
  background:var(--bg2);margin:10px 18px 16px;
  border:1px solid var(--b0);border-radius:8px;
  padding:12px 14px;height:180px;overflow-y:auto;
  white-space:pre-wrap;word-break:break-all;
}
.log-body::-webkit-scrollbar{width:2px;}
.log-body::-webkit-scrollbar-thumb{background:var(--bg3);border-radius:2px;}
.ll-e{color:var(--err);}
.ll-s{color:var(--ok);}
.ll-w{color:var(--warn);}

/* ─── FEED ─── */
.feed-card{display:flex;flex-direction:column;}
.feed-scroll{flex:1;overflow-y:auto;padding:0 16px 16px;max-height:680px;}
.feed-scroll::-webkit-scrollbar{width:2px;}
.feed-scroll::-webkit-scrollbar-thumb{background:var(--bg3);border-radius:2px;}
.fi{
  display:flex;gap:10px;padding:9px 0;
  border-bottom:1px solid var(--b0);
  animation:slideIn .3s ease;
}
.fi:last-child{border-bottom:none;}
@keyframes slideIn{from{opacity:0;transform:translateX(6px);}to{opacity:1;transform:none;}}
.fi-dot{width:6px;height:6px;border-radius:50%;margin-top:4px;flex-shrink:0;}
.fi-dot.success{background:var(--ok);}
.fi-dot.warn   {background:var(--warn);}
.fi-dot.error  {background:var(--err);}
.fi-dot.info   {background:var(--t2);}
.fi-body{flex:1;min-width:0;}
.fi-badge{
  display:inline-block;font-size:9.5px;font-weight:700;
  padding:1px 7px;border-radius:4px;margin-bottom:4px;
  letter-spacing:.04em;
}
.fi-msg{font-size:11.5px;color:var(--t1);line-height:1.5;word-break:break-word;}
.fi-time{font-size:10px;color:var(--t2);margin-top:2px;}

/* ─── ARTICLES LIST (in pipeline) ─── */
.art-list{margin-top:12px;}
.art-list-title{
  font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--t2);margin-bottom:8px;
}
.al-item{
  display:flex;align-items:center;gap:8px;
  padding:7px 0;border-bottom:1px solid var(--b0);
}
.al-item:last-child{border-bottom:none;}
.al-name{flex:1;font-size:11.5px;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.al-meta{font-size:10.5px;color:var(--t2);white-space:nowrap;}
.al-btn{
  font-size:10px;color:var(--cyan);border:1px solid rgba(34,211,238,.2);
  padding:2px 8px;border-radius:5px;background:var(--cyan-s);
  cursor:pointer;flex-shrink:0;transition:.2s;
}
.al-btn:hover{background:var(--cyan-m);}

/* ─── BADGE ─── */
.badge{
  display:inline-flex;align-items:center;gap:3px;
  padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:600;
}
.b-ok  {background:var(--ok-s);  color:var(--ok);}
.b-warn{background:var(--warn-s);color:var(--warn);}
.b-cyan{background:var(--cyan-s);color:var(--cyan);}
.b-err {background:var(--err-s); color:var(--err);}

/* ─── MODAL ─── */
.modal-ov{
  display:none;position:fixed;inset:0;z-index:500;
  background:rgba(6,16,28,.88);backdrop-filter:blur(10px);
  align-items:flex-start;justify-content:center;padding:40px 24px;
}
.modal-ov.open{display:flex;}
.modal-box{
  background:var(--bg1);border:1px solid var(--b1);
  border-radius:14px;width:100%;max-width:800px;max-height:85vh;
  display:flex;flex-direction:column;
  box-shadow:0 24px 80px rgba(0,0,0,.65);
  animation:mIn .22s ease;
}
@keyframes mIn{from{opacity:0;transform:scale(.96)translateY(8px);}to{opacity:1;transform:none;}}
.modal-hd{
  padding:16px 20px;border-bottom:1px solid var(--b0);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;
}
.modal-title{font-size:14px;font-weight:600;color:var(--t0);}
.modal-close{
  width:28px;height:28px;border-radius:6px;
  background:var(--bg2);border:1px solid var(--b0);color:var(--t2);
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  font-size:13px;transition:.2s;
}
.modal-close:hover{border-color:var(--b-hover);color:var(--cyan);}
.modal-bd{
  flex:1;overflow-y:auto;padding:20px 24px;
  font-family:'SF Mono',Menlo,monospace;
  font-size:12.5px;line-height:1.85;color:var(--t1);
  white-space:pre-wrap;word-break:break-word;
}
.modal-bd::-webkit-scrollbar{width:4px;}
.modal-bd::-webkit-scrollbar-thumb{background:var(--bg3);border-radius:4px;}
.modal-ft{
  padding:10px 20px;border-top:1px solid var(--b0);
  font-size:10.5px;color:var(--t2);flex-shrink:0;
}

/* ─── MISC ─── */
.empty{color:var(--t2);font-style:italic;font-size:12px;padding:12px 0;}
</style>
</head>
<body>

<!-- TOPBAR -->
<nav class="topbar">
  <div class="tb-left">
    <div class="logo"><span class="logo-icon">⬡</span>AI 無人工廠<span class="logo-sub">/ 控制台</span></div>
    <div class="state-pill st-idle" id="state-pill">
      <span class="s-dot"></span><span class="s-txt">載入中</span>
    </div>
  </div>
  <div class="tb-right">
    <span class="ts-txt" id="ts">--</span>
    <span class="ts-txt">·</span>
    <span class="cd" id="cd">5s</span>
    <button class="rbtn" onclick="fetchNow()">⟳ 更新</button>
  </div>
</nav>

<!-- WARN STRIP -->
<div class="warn-strip" id="warn-strip">
  ⚠ <strong>待完成：</strong>CLAUDE.md 中仍有 PLACEHOLDER_WHOP_* — 填入真實 Whop 連結後才能在文章中放銷售連結
</div>

<!-- KPI BAR -->
<div class="kpi-bar">
  <div class="kpi-cell">
    <div class="kpi-val accent" id="k-today">0</div>
    <div class="kpi-lbl">今日產出</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-val" id="k-total">0</div>
    <div class="kpi-lbl">文章總數</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-val" id="k-api-today">0</div>
    <div class="kpi-lbl">今日 API 呼叫</div>
  </div>
  <div class="kpi-cell">
    <div class="kpi-val" id="k-api-total">0</div>
    <div class="kpi-lbl">累計 API 呼叫</div>
  </div>
  <div class="kpi-cell" id="k-health-cell">
    <div class="kpi-val" id="k-score">--</div>
    <div class="kpi-lbl">系統健康度</div>
  </div>
</div>

<!-- MAIN -->
<div class="main">

  <!-- ─ LEFT COL ─ -->
  <div class="left-col">

    <!-- Pipeline -->
    <div class="card">
      <div class="c-head">
        <div class="c-title">
          <span class="c-dot" style="background:var(--ok)"></span>
          生產流水線
        </div>
        <div id="model-badge"></div>
      </div>
      <div class="c-body">
        <div id="pipeline-track"></div>
        <div id="art-slot"></div>
      </div>
    </div>

    <!-- Mid row: Diag + Topics -->
    <div class="mid-row">

      <!-- Diagnostics -->
      <div class="card">
        <div class="c-head">
          <div class="c-title">
            <span class="c-dot" style="background:var(--warn)"></span>
            系統診斷
          </div>
          <div id="diag-score-badge"></div>
        </div>
        <div class="c-body">
          <div class="diag-health" id="diag-health"></div>
          <div class="diag-list"  id="diag-list"></div>
        </div>
      </div>

      <!-- Topics -->
      <div class="card">
        <div class="c-head">
          <div class="c-title">
            <span class="c-dot" style="background:var(--pur)"></span>
            主題表現
          </div>
        </div>
        <div class="c-body">
          <div class="topics-grid" id="topics-grid"></div>
        </div>
      </div>

    </div><!-- /mid-row -->

    <!-- Logs -->
    <div class="card">
      <div class="c-title" style="padding:14px 18px 0;">
        <span class="c-dot" style="background:var(--t2)"></span>
        執行日誌
      </div>
      <div class="log-tabs">
        <div class="log-tab active" onclick="switchLog('cron',this)">Cron</div>
        <div class="log-tab" onclick="switchLog('error',this)">錯誤</div>
      </div>
      <div class="log-body" id="log-body"></div>
    </div>

  </div><!-- /left-col -->

  <!-- ─ FEED (right) ─ -->
  <div class="card feed-card">
    <div class="c-head">
      <div class="c-title">
        <span class="c-dot" style="background:var(--cyan);box-shadow:0 0 6px var(--cyan);animation:pulse 2s infinite;"></span>
        團隊活動流
      </div>
    </div>
    <div class="feed-scroll" id="feed-list"></div>
  </div>

</div><!-- /main -->

<!-- MODAL -->
<div class="modal-ov" id="modal" onclick="closeModal(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-hd">
      <div class="modal-title" id="modal-title">文章內容</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-bd" id="modal-body">載入中...</div>
    <div class="modal-ft" id="modal-meta"></div>
  </div>
</div>

<script>
// ──────────────────────────
let currentLog = 'cron';
let countdown  = 5;
let timer;
let lastData   = null;

const AGENT_COLOR = {
  writer:'#22D3EE', reviewer:'#A78BFA', poster:'#22C55E',
  'quality-check':'#F59E0B', researcher:'#60A5FA',
  'topic-selector':'#22D3EE', feedback:'#A78BFA',
  publisher:'#22C55E', seo:'#F59E0B', system:'#4A6480',
};
const CAT_COLOR = {A:'#22D3EE',B:'#A78BFA',C:'#22C55E',D:'#60A5FA'};
const CAT_LABEL = {A:'電容/壓力感測',B:'手勢/彎曲感測',C:'互動設計',D:'IoT/ESP32'};

function ac(a){ return AGENT_COLOR[a]||'#4A6480'; }

// ── fetch & timer ──────────
async function fetchNow(){
  clearInterval(timer);
  countdown = 5;
  try{
    const r = await fetch('/api/status');
    const d = await r.json();
    lastData = d;
    render(d);
  }catch(e){
    setStatePill('error','連線失敗');
  }
  startTimer();
}

function startTimer(){
  clearInterval(timer);
  timer = setInterval(()=>{
    countdown--;
    const el = document.getElementById('cd');
    if(el) el.textContent = countdown+'s';
    if(countdown<=0) fetchNow();
  },1000);
}

// ── render ─────────────────
function render(d){
  document.getElementById('ts').textContent = d.ts;
  document.getElementById('warn-strip').style.display = d.has_placeholder?'flex':'none';
  setStatePill(d.state,{idle:'待機中',running:'執行中',error:'有錯誤'}[d.state]||d.state);

  // KPI — 數值全白，只有今日產出用品牌色（已在 HTML 中加 accent 類）
  document.getElementById('k-today').textContent     = d.pipeline.count||0;
  document.getElementById('k-total').textContent     = d.article_count||0;
  document.getElementById('k-api-today').textContent = d.usage.today||0;
  document.getElementById('k-api-total').textContent = d.usage.total||0;

  const score = d.diag?.score ?? 100;
  const scoreEl = document.getElementById('k-score');
  scoreEl.textContent = score + '%';
  scoreEl.className = 'kpi-val ' + (score>=85?'ok':score>=60?'warn':'err');

  // model badge
  document.getElementById('model-badge').innerHTML =
    `<span style="font-size:10.5px;color:var(--ok);font-weight:600;">● ${esc(d.api.model)}</span>`;

  renderPipeline(d.pipeline, d.articles||[]);
  renderDiag(d.diag||{});
  renderTopics(d.perf||{});
  renderFeed(d.feed||[]);
  renderLog(d);
}

function setStatePill(state, label){
  const el = document.getElementById('state-pill');
  el.className = 'state-pill st-'+state;
  el.querySelector('.s-txt').textContent = label;
}

// ── pipeline ───────────────
function renderPipeline(pipe, articles){
  const stages = pipe.stages||[];
  let html = '<div class="pipe-track">';
  stages.forEach((s,i)=>{
    const isDone   = s.done;
    const isActive = !isDone && i>0 && stages[i-1].done;
    const cls = isDone?'done':isActive?'active':'';
    const icon= isDone?'✓':isActive?'◉':'○';
    html += `<div class="pipe-node ${cls}" onclick="void(0)">
      <div class="p-ring">${icon}</div>
      <div class="p-lbl">${s.label}</div>
    </div>`;
    if(i < stages.length-1){
      const cc = isDone?(stages[i+1].done?'done':'active'):'';
      html += `<div class="pipe-conn ${cc}"></div>`;
    }
  });
  html += '</div>';
  document.getElementById('pipeline-track').innerHTML = html;

  const slot = document.getElementById('art-slot');
  if(pipe.article){
    const a = pipe.article;
    const statusBadge = `<span class="badge b-cyan">${esc(a.status||'')}</span>`;
    slot.innerHTML = `
      <div class="art-slot">
        <div class="art-banner" onclick="openArticle('${esc(a.name||'')}','${esc(a.title||a.name||'')}')">
          <div>
            <div class="art-banner-title">${esc(a.title||a.name||'未命名')}</div>
            <div class="art-banner-meta">狀態：${statusBadge} &nbsp;·&nbsp; ${esc(a.date||'')}</div>
          </div>
          <div class="art-view-btn">閱讀全文 →</div>
        </div>
        ${articles.length>1?buildArtList(articles):''}
      </div>`;
  } else {
    slot.innerHTML = `
      <div class="art-slot">
        <div class="pipe-empty">
          今日尚未產出文章<br>
          <span style="font-size:10.5px">Cron 排程每日 09:00 UTC 自動觸發</span>
        </div>
        ${articles.length?buildArtList(articles):''}
      </div>`;
  }
}

function buildArtList(arts){
  return `<div class="art-list">
    <div class="art-list-title">文章庫（最近 ${Math.min(arts.length,6)} 篇）</div>
    ${arts.slice(0,6).map(a=>`
      <div class="al-item">
        <div class="al-name" title="${esc(a.title)}">${esc(a.title)}</div>
        <div class="al-meta">${a.words||''} 詞</div>
        <div class="al-btn" onclick="openArticle('${esc(a.name)}','${esc(a.title)}')">閱讀</div>
      </div>`).join('')}
  </div>`;
}

// ── diagnostics ────────────
function renderDiag(diag){
  const health = diag.health || [];
  const issues = diag.issues || [];
  const score  = diag.score  ?? 100;

  // score badge
  const sc = score>=85?'ok':score>=60?'warn':'err';
  document.getElementById('diag-score-badge').innerHTML =
    `<span class="badge b-${sc==='ok'?'ok':sc==='warn'?'warn':'err'}"
      style="background:var(--${sc==='err'?'err':sc}-s);color:var(--${sc==='err'?'err':sc});">
      ${score}% 健康
    </span>`;

  // health pills
  const pillMap = {ok:'ok',warn:'warn',error:'err',info:'info'};
  document.getElementById('diag-health').innerHTML = health.map(h=>`
    <div class="h-pill">
      <div class="h-name">${esc(h.name)}</div>
      <div class="h-val ${pillMap[h.status]||'info'}">${esc(h.val)}</div>
    </div>`).join('');

  // issues list
  const iconMap = {ok:'✓',warn:'!',error:'✕',info:'i'};
  document.getElementById('diag-list').innerHTML = issues.length
    ? issues.map(it=>`
      <div class="diag-item">
        <div class="di-icon ${it.level}">${iconMap[it.level]||'i'}</div>
        <div class="di-body">
          <div class="di-title">${esc(it.title)}</div>
          <div class="di-desc">${esc(it.desc)}</div>
        </div>
        <div class="di-tag">${esc(it.tag||'')}</div>
      </div>`).join('')
    : '<div class="empty">診斷資料載入中...</div>';
}

// ── topics ─────────────────
function renderTopics(perf){
  const el = document.getElementById('topics-grid');
  el.innerHTML = ['A','B','C','D'].map(c=>{
    const d = perf[c]||{avg_upvotes:0,avg_comments:0,count:0};
    const w = Math.min((d.avg_upvotes||0)*2,100);
    const col = CAT_COLOR[c];
    return `<div class="topic-box">
      <div class="t-cat" style="color:${col}">${c} 類</div>
      <div class="t-name">${CAT_LABEL[c]}</div>
      <div class="t-val" style="color:${col}">${Number(d.avg_upvotes||0).toFixed(0)}</div>
      <div class="t-sub">avg upvotes · ${d.count||0} 篇</div>
      <div class="t-bar"><div class="t-fill" style="width:${w}%;background:${col}"></div></div>
    </div>`;
  }).join('');
}

// ── feed ───────────────────
function renderFeed(feed){
  const el = document.getElementById('feed-list');
  if(!feed||!feed.length){
    el.innerHTML='<div class="empty" style="padding:20px 0;text-align:center;">尚無活動記錄</div>';
    return;
  }
  el.innerHTML = feed.map(f=>`
    <div class="fi">
      <div class="fi-dot ${f.type}"></div>
      <div class="fi-body">
        <div>
          <span class="fi-badge"
            style="background:${ac(f.agent)}1a;color:${ac(f.agent)};border:1px solid ${ac(f.agent)}33;">
            ${esc(f.agent)}
          </span>
        </div>
        <div class="fi-msg">${esc(f.msg)}</div>
        ${f.time?`<div class="fi-time">${esc(f.time)}</div>`:''}
      </div>
    </div>`).join('');
}

// ── logs ───────────────────
function renderLog(d){
  const lines = currentLog==='cron'?d.cron_log_tail:d.error_log;
  const el = document.getElementById('log-body');
  if(!lines||!lines.length){ el.textContent='（無記錄）'; return; }
  el.innerHTML = lines.map(l=>{
    let c='';
    if(/error|fail|FAIL/i.test(l))          c='ll-e';
    else if(/APPROVED|success|完成/i.test(l)) c='ll-s';
    else if(/REJECTED|warn|WARNING/i.test(l)) c='ll-w';
    return c?`<span class="${c}">${esc(l)}</span>`:esc(l);
  }).join('\n');
  el.scrollTop = el.scrollHeight;
}

function switchLog(type,btn){
  currentLog=type;
  document.querySelectorAll('.log-tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  if(lastData) renderLog(lastData);
}

// ── article modal ──────────
async function openArticle(name, title){
  if(!name) return;
  document.getElementById('modal-title').textContent = title||name;
  document.getElementById('modal-body').textContent  = '載入中...';
  document.getElementById('modal-meta').textContent  = '';
  document.getElementById('modal').classList.add('open');
  try{
    const r = await fetch('/api/article?name='+encodeURIComponent(name));
    if(r.ok){
      const txt = await r.text();
      document.getElementById('modal-body').textContent = txt;
      document.getElementById('modal-meta').textContent =
        `${name}.md  ·  ${txt.split(/\s+/).length} 詞  ·  ${txt.length} 字元`;
    } else {
      document.getElementById('modal-body').textContent = '找不到文章。';
    }
  }catch(e){
    document.getElementById('modal-body').textContent = '載入失敗：'+e;
  }
}

function closeModal(e){
  if(!e||e.target.id==='modal')
    document.getElementById('modal').classList.remove('open');
}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape') closeModal({target:{id:'modal'}});
});

// ── util ───────────────────
function esc(s){
  return String(s||'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            self.wfile.write(data)

        elif self.path.startswith("/api/article"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            name   = params.get("name",[""])[0]
            if name and re.match(r'^[\w\-\.]{1,100}$', name):
                content = get_article_content(name)
                if content:
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin","*")
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))
                    return
            self.send_response(404); self.end_headers()

        else:
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT",3000))
    print(f"Dashboard v4 啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0",port), Handler).serve_forever()
