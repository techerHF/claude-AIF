#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard v5
— 日系亮色 + Agent 可視化 + 聊天介面
執行：python3 ~/ai-factory/dashboard.py
"""

import json, os, re, subprocess, urllib.parse, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent

# ── 全域聊天記憶 ─────────────────────────
_chat_history = []

# ── Agent 定義 ───────────────────────────
AGENTS = [
    # pipeline agents
    {"id":"researcher",       "label":"研究員",  "role":"pipeline", "icon":"◎"},
    {"id":"topic-selector",   "label":"選題",    "role":"pipeline", "icon":"◈"},
    {"id":"writer",           "label":"寫手",    "role":"pipeline", "icon":"✦"},
    {"id":"reviewer",         "label":"審稿",    "role":"pipeline", "icon":"◉"},
    {"id":"poster",           "label":"發文",    "role":"pipeline", "icon":"◆"},
    # support agents
    {"id":"english-writer",   "label":"英文版",  "role":"support",  "icon":"E"},
    {"id":"chinese-writer",   "label":"中文版",  "role":"support",  "icon":"中"},
    {"id":"seo-agent",        "label":"SEO",     "role":"support",  "icon":"S"},
    {"id":"feedback-collector","label":"回報",   "role":"support",  "icon":"F"},
    {"id":"knowledge-subagent","label":"知識庫", "role":"support",  "icon":"K"},
]

# ── 資料函數 ─────────────────────────────

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

def read_api_env():
    try:
        s = json.loads(Path.home().joinpath(".claude/settings.json").read_text())
        env = s.get("env", {})
        return (
            env.get("ANTHROPIC_API_KEY",""),
            env.get("ANTHROPIC_BASE_URL","https://api.anthropic.com").rstrip("/"),
            env.get("ANTHROPIC_MODEL","claude-3-5-sonnet-20241022"),
        )
    except:
        return ("","https://api.anthropic.com","claude-3-5-sonnet-20241022")

def cron_lines():
    try:
        r = subprocess.run(["crontab","-l"], capture_output=True, text=True, timeout=3)
        return [l for l in r.stdout.splitlines() if "ai-factory" in l]
    except:
        return []

def system_state():
    err_log  = [l for l in rt("logs/error.log",3) if l.strip()]
    cron_log = rt("logs/cron.log",5)
    if err_log: return "error"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if any(today[:7] in l or "2026" in l for l in cron_log): return "running"
    return "idle"

def activity_feed():
    events = []
    prog = rj("logs/progress.json", [])
    for p in reversed(prog[-8:]):
        events.append({"time":p.get("timestamp","")[:16].replace("T"," "),
            "agent":"writer","msg":f"文章完成：{p.get('title','')}","type":"success"})
    for line in reversed(rt("logs/cron.log",30)):
        line = line.strip()
        if not line: continue
        agent, t = "system","info"
        if "APPROVED"  in line: t,agent = "success","quality-check"
        elif "REJECTED" in line: t,agent = "warn","quality-check"
        elif "error"   in line.lower(): t,agent = "error","system"
        elif "writer"  in line.lower(): agent = "writer"
        elif "reviewer" in line.lower(): agent = "reviewer"
        elif "poster"  in line.lower(): agent = "poster"
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
        {"id":"researcher",    "label":"研究員"},
        {"id":"topic-selector","label":"選題"},
        {"id":"writer",        "label":"寫作"},
        {"id":"reviewer",      "label":"審查"},
        {"id":"poster",        "label":"發文準備"},
        {"id":"published",     "label":"已發布"},
    ]
    done_map = {
        "reviewed": ["researcher","topic-selector","writer","reviewer"],
        "posted":   ["researcher","topic-selector","writer","reviewer","poster"],
        "published":["researcher","topic-selector","writer","reviewer","poster","published"],
    }
    if today_items:
        item = today_items[-1]
        done = set(done_map.get(item.get("status",""), []))
        for s in stages: s["done"] = s["id"] in done
        return {"stages":stages,"article":item,"count":len(today_items)}
    return {"stages":stages,"article":None,"count":0}

def compute_agent_states():
    """從 pipeline 狀態推斷各 agent 目前的工作狀態"""
    pipe   = pipeline_status()
    stages = pipe["stages"]
    cron_log = " ".join(rt("logs/cron.log",50)).lower()

    # 找出 active stage
    active_id = None
    waiting_ids = set()
    for i, s in enumerate(stages):
        if not s["done"] and (i == 0 or stages[i-1]["done"]):
            active_id = s["id"]
            for j in range(i+1, len(stages)):
                waiting_ids.add(stages[j]["id"])
            break

    result = {}
    for a in AGENTS:
        aid = a["id"]
        if aid == active_id:
            result[aid] = {"status":"working","txt":"工作中"}
        elif aid in waiting_ids:
            result[aid] = {"status":"waiting","txt":"等待中"}
        elif aid in cron_log:
            result[aid] = {"status":"idle","txt":"待命"}
        else:
            result[aid] = {"status":"idle","txt":"休息中"}
    return result

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
            result.append({"name":a.stem,"title":title[:80],"words":words})
        return result
    except:
        return []

def get_article_content(name):
    try:
        p = BASE / "articles" / f"{name}.md"
        return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else None
    except:
        return None

def run_diagnostics():
    issues = []
    score  = 100
    api    = api_status()
    crons  = cron_lines()
    has_ph = False
    try: has_ph = "PLACEHOLDER" in (BASE/"CLAUDE.md").read_text(encoding="utf-8")
    except: pass
    err_lines = [l.strip() for l in rt("logs/error.log",5) if l.strip()]

    if has_ph:
        issues.append({"level":"warn","title":"WHOP 連結未設定",
            "desc":"CLAUDE.md 含 PLACEHOLDER_WHOP_*，文章無法放銷售連結","tag":"設定"})
        score -= 15
    if err_lines:
        issues.append({"level":"error","title":f"系統錯誤 × {len(err_lines)}",
            "desc":err_lines[-1][:90],"tag":"錯誤"})
        score -= 20
    if len(crons) == 0:
        issues.append({"level":"error","title":"排程器未設定",
            "desc":"未找到 ai-factory Cron 排程","tag":"排程"})
        score -= 20
    elif len(crons) > 2:
        issues.append({"level":"warn","title":f"Cron 重複 ({len(crons)} 筆)",
            "desc":"建議清理重複排程","tag":"排程"})
        score -= 5
    else:
        issues.append({"level":"ok","title":"排程器正常",
            "desc":f"{len(crons)} 個排程運行中","tag":"排程"})

    if api["minimax"]:
        issues.append({"level":"ok","title":"模型連線正常","desc":api["model"],"tag":"API"})
    else:
        issues.append({"level":"info","title":"使用預設 Claude 模型",
            "desc":"未偵測到 MiniMax 設定","tag":"API"})

    art_files = sorted((BASE/"articles").glob("*.md"),reverse=True)[:5] if (BASE/"articles").exists() else []
    if art_files:
        ph_in = sum(1 for f in art_files if "PLACEHOLDER" in f.read_text("utf-8","ignore"))
        if ph_in:
            issues.append({"level":"warn","title":f"文章含未替換連結 × {ph_in}","desc":"","tag":"內容"})
            score -= 5
    # topic diversity
    prog = rj("logs/progress.json",[])
    if len(prog) >= 4:
        recent = " ".join(p.get("title","") for p in prog[-5:])
        for kw in ["電容","壓力","手勢","IoT","ESP32"]:
            if recent.count(kw) >= 2:
                issues.append({"level":"info","title":"主題略偏集中",
                    "desc":f"近期「{kw}」相關題材偏多","tag":"內容"})
                break
    # api usage notice
    usage = api_usage()
    if usage.get("today",0) == 0 and usage.get("total",0) == 0:
        issues.append({"level":"info","title":"API 呼叫尚未追蹤",
            "desc":"logs/api-usage.json 不存在，需要在 agent 流程加入追蹤 hook","tag":"追蹤"})

    if score >= 100 and not [i for i in issues if i["level"] in ("error","warn")]:
        issues.insert(0,{"level":"ok","title":"所有系統正常","desc":"","tag":"狀態"})

    cron_s = "ok" if 0<len(crons)<=2 else ("warn" if len(crons)>2 else "error")
    health = [
        {"name":"模型","status":"ok" if api["minimax"] else "info","val":"MiniMax" if api["minimax"] else "預設"},
        {"name":"排程","status":cron_s,"val":f"{len(crons)} 個"},
        {"name":"錯誤","status":"error" if err_lines else "ok","val":str(len(err_lines)) if err_lines else "無"},
        {"name":"設定","status":"warn" if has_ph else "ok","val":"待完成" if has_ph else "正常"},
    ]
    return {"score":max(0,score),"health":health,"issues":issues[:10]}

def do_chat(message):
    """呼叫 MiniMax / Claude API 進行對話"""
    global _chat_history
    api_key, base_url, model = read_api_env()
    if not api_key:
        return "⚠ 未設定 ANTHROPIC_API_KEY，無法使用聊天功能。請在 ~/.claude/settings.json 中設定。"
    try:
        _chat_history = _chat_history[-8:]
        msgs = _chat_history + [{"role":"user","content":message}]
        payload = json.dumps({
            "model": model,
            "max_tokens": 600,
            "system": (
                "你是 AI 無人工廠的控制台助手（AI Factory Assistant）。"
                "協助用戶管理系統設定、排程、文章生產流程。"
                "用繁體中文回答，簡潔、直接、實用。"
            ),
            "messages": msgs
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read())
            reply = result["content"][0]["text"]
            _chat_history.append({"role":"user","content":message})
            _chat_history.append({"role":"assistant","content":reply})
            return reply
    except Exception as e:
        return f"❌ 錯誤：{str(e)[:150]}"

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
    agents = compute_agent_states()
    has_ph = False
    try: has_ph = "PLACEHOLDER" in (BASE/"CLAUDE.md").read_text(encoding="utf-8")
    except: pass
    return {
        "ts":              datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "state":           state,
        "api":             api,
        "cron_count":      len(crons),
        "has_placeholder": has_ph,
        "article_count":   len(prog),
        "articles":        list_articles(),
        "pipeline":        pipe,
        "feed":            feed,
        "usage":           usage,
        "perf":            perf.get("categories", {}),
        "diag":            diag,
        "agents":          agents,
        "cron_log_tail":   rt("logs/cron.log", 60),
        "error_log":       rt("logs/error.log", 30),
    }

# ── HTML ─────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 無人工廠</title>
<style>
/* ════════════════════════════════
   色彩系統 v5 — 日系低調亮色
   主色：藍灰 #727A8C（品牌/互動）
   成功：灰綠 #7C9A7E
   警告：土黃 #B89B72
   錯誤：枯紅 #B36A6A
   ════════════════════════════════ */
:root{
  --bg0:#F6F3EE;   /* 頁面底 */
  --bg1:#FBFAF7;   /* 卡片 */
  --bg2:#F1EEE8;   /* 卡片內塊 */
  --bg3:#E8E3DA;   /* 強調區塊 */
  --b0: #D8D2C7;   /* 預設邊框 */
  --b1: #C4BDB5;   /* hover 邊框 */
  --ba: #727A8C;   /* active 邊框 */
  --t0: #2F2A24;   /* 主文字 */
  --t1: #5B544C;   /* 次文字 */
  --t2: #8A837A;   /* 輔助文字 */
  --brand: #727A8C;
  --brand-s: rgba(114,122,140,0.10);
  --brand-m: rgba(114,122,140,0.18);
  --ok:   #7C9A7E; --ok-s:  rgba(124,154,126,0.12);
  --warn: #B89B72; --warn-s:rgba(184,155,114,0.12);
  --err:  #B36A6A; --err-s: rgba(179,106,106,0.12);
  --info: #8193A8; --info-s:rgba(129,147,168,0.10);
  --pur:  #8B85A0; --pur-s: rgba(139,133,160,0.12);
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{min-height:100%;background:var(--bg0);color:var(--t0);
  font-family:'Hiragino Sans','Noto Sans TC',system-ui,-apple-system,sans-serif;
  font-size:13px;line-height:1.6;}

/* ─── TOPBAR ─── */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:50px;
  background:var(--bg1);
  border-bottom:1px solid var(--b0);
  position:sticky;top:0;z-index:300;
}
.tb-l{display:flex;align-items:center;gap:14px;}
.logo{font-size:14px;font-weight:700;color:var(--brand);
  display:flex;align-items:center;gap:7px;letter-spacing:-.1px;}
.logo-sub{font-size:12px;color:var(--t2);font-weight:400;}

.state-pill{
  display:flex;align-items:center;gap:5px;
  padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;
  background:var(--bg2);border:1px solid var(--b0);
}
.sdot{width:6px;height:6px;border-radius:50%;}
.si   .sdot{background:var(--t2);}
.sr   .sdot{background:var(--ok);animation:pls 1.5s infinite;}
.se   .sdot{background:var(--err);}
.si   .stxt{color:var(--t2);}
.sr   .stxt{color:var(--ok);}
.se   .stxt{color:var(--err);}
@keyframes pls{0%,100%{opacity:1;}50%{opacity:.3;}}

.tb-r{display:flex;align-items:center;gap:12px;}
.ts-t{font-size:11px;color:var(--t2);}
.cdt{font-size:11px;color:var(--brand);font-variant-numeric:tabular-nums;min-width:22px;}
.rbtn{
  background:none;border:1px solid var(--b0);color:var(--t2);
  padding:4px 12px;border-radius:6px;cursor:pointer;font-size:11px;transition:.2s;
}
.rbtn:hover{border-color:var(--brand);color:var(--brand);}

/* ─── WARN STRIP ─── */
.warn-strip{
  background:rgba(184,155,114,.07);
  border-bottom:1px solid rgba(184,155,114,.22);
  padding:7px 28px;font-size:11.5px;color:var(--warn);
  display:none;align-items:center;gap:8px;
}

/* ─── KPI BAR ─── */
.kpi-bar{
  display:grid;grid-template-columns:repeat(5,1fr);
  background:var(--bg1);border-bottom:1px solid var(--b0);
}
.kpi-c{
  padding:12px 20px;border-right:1px solid var(--b0);transition:.15s;
}
.kpi-c:last-child{border-right:none;}
.kpi-c:hover{background:var(--bg2);}
.kpi-v{font-size:24px;font-weight:700;letter-spacing:-.5px;line-height:1;
  color:var(--t0);}
.kpi-v.accent{color:var(--brand);}
.kpi-v.ok    {color:var(--ok);}
.kpi-v.warn  {color:var(--warn);}
.kpi-l{font-size:10.5px;color:var(--t2);margin-top:3px;}

/* ─── LAYOUT ─── */
.main{
  display:grid;
  grid-template-columns:1fr 310px;
  gap:16px;
  padding:20px 28px;
  max-width:1500px;margin:0 auto;
}
.left{display:flex;flex-direction:column;gap:16px;}
.right{display:flex;flex-direction:column;gap:16px;}

/* ─── CARD ─── */
.card{
  background:var(--bg1);
  border:1px solid var(--b0);
  border-radius:12px;
  overflow:hidden;
  box-shadow:0 1px 3px rgba(50,40,30,.04),0 4px 12px rgba(50,40,30,.03);
  transition:box-shadow .2s,border-color .2s;
}
.card:hover{
  border-color:var(--b1);
  box-shadow:0 2px 8px rgba(50,40,30,.07),0 8px 24px rgba(50,40,30,.05);
}
.ch{  /* card header */
  padding:13px 18px 11px;
  display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--b0);
}
.ct{  /* card title */
  font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--t2);display:flex;align-items:center;gap:6px;
}
.cdot{width:5px;height:5px;border-radius:50%;}
.cb{padding:16px 18px;}  /* card body */

/* ─── PIPELINE ─── */
.pipe-track{display:flex;align-items:flex-start;padding:2px 0 6px;}
.pipe-conn{
  flex:1;height:1px;background:var(--b0);margin-top:13px;
  min-width:12px;transition:background .4s;
}
.pipe-conn.done  {background:var(--ok);}
.pipe-conn.active{background:linear-gradient(90deg,var(--ok),var(--brand));}
.pipe-node{
  display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:56px;
}
.p-ring{
  width:28px;height:28px;border-radius:50%;
  border:1.5px solid var(--b0);background:var(--bg2);color:var(--t2);
  display:flex;align-items:center;justify-content:center;
  font-size:11px;transition:.3s;
}
.pipe-node.done   .p-ring{border-color:var(--ok);background:var(--ok-s);color:var(--ok);}
.pipe-node.active .p-ring{
  border-color:var(--brand);background:var(--brand-s);color:var(--brand);
  box-shadow:0 0 0 4px var(--brand-s);
  animation:pls 1.5s infinite;
}
.p-lbl{font-size:9.5px;color:var(--t2);margin-top:5px;text-align:center;white-space:nowrap;}
.pipe-node.done   .p-lbl{color:var(--ok);}
.pipe-node.active .p-lbl{color:var(--brand);}

.art-banner{
  margin-top:14px;background:var(--bg2);border:1px solid var(--b0);
  border-radius:9px;padding:12px 16px;cursor:pointer;transition:.2s;
  display:flex;align-items:center;justify-content:space-between;gap:10px;
}
.art-banner:hover{border-color:var(--ba);background:var(--bg3);}
.art-title{font-size:13px;font-weight:600;color:var(--t0);margin-bottom:3px;}
.art-meta{font-size:11px;color:var(--t2);}
.view-btn{
  font-size:10px;color:var(--brand);border:1px solid var(--brand-m);
  padding:3px 10px;border-radius:6px;background:var(--brand-s);white-space:nowrap;
}
.pipe-empty{
  margin-top:14px;background:var(--bg2);border:1px dashed var(--b0);
  border-radius:9px;padding:18px;text-align:center;
  color:var(--t2);font-size:12px;line-height:1.8;
}

/* ─── ARTICLE LIST ─── */
.art-list{margin-top:12px;}
.art-list-hd{font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--t2);margin-bottom:8px;}
.ali{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--b0);}
.ali:last-child{border-bottom:none;}
.ali-name{flex:1;font-size:11.5px;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.ali-meta{font-size:10.5px;color:var(--t2);white-space:nowrap;}
.ali-btn{
  font-size:10px;color:var(--brand);border:1px solid var(--brand-m);
  padding:2px 8px;border-radius:5px;background:var(--brand-s);
  cursor:pointer;flex-shrink:0;transition:.2s;
}
.ali-btn:hover{background:var(--brand-m);}

/* ─── AGENT GRID ─── */
.agent-section{display:flex;flex-direction:column;gap:12px;}
.agent-group-label{
  font-size:9.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--t2);margin-bottom:6px;
}
.agent-grid{
  display:grid;grid-template-columns:repeat(5,1fr);gap:8px;
}
.agent-card{
  background:var(--bg2);border:1px solid var(--b0);
  border-radius:10px;padding:12px 8px;
  text-align:center;transition:.25s;
}
.agent-card.working{
  background:var(--brand-s);border-color:rgba(114,122,140,.3);
}
.agent-card.waiting{
  background:var(--bg2);border-color:var(--b0);
  opacity:.75;
}
.agent-card.idle{
  background:var(--bg1);border-color:var(--b0);
  opacity:.55;
}
.agent-icon{
  width:36px;height:36px;border-radius:50%;
  background:var(--bg3);
  display:flex;align-items:center;justify-content:center;
  font-size:14px;font-weight:700;color:var(--t2);
  margin:0 auto 7px;
  transition:.3s;
}
.agent-card.working .agent-icon{
  background:var(--brand-s);color:var(--brand);
  box-shadow:0 0 0 3px var(--brand-s);
  animation:working 1.2s ease-in-out infinite;
}
.agent-card.waiting .agent-icon{
  animation:waiting 2s ease-in-out infinite;
}
@keyframes working{
  0%,100%{transform:scale(1);box-shadow:0 0 0 3px var(--brand-s);}
  50%{transform:scale(1.08);box-shadow:0 0 0 6px var(--brand-s);}
}
@keyframes waiting{
  0%,100%{opacity:.5;}50%{opacity:1;}
}
.agent-name{font-size:10.5px;font-weight:600;color:var(--t1);margin-bottom:3px;}
.agent-status-txt{
  font-size:9.5px;padding:2px 6px;border-radius:999px;
  display:inline-block;
}
.working .agent-status-txt{background:var(--brand-s);color:var(--brand);}
.waiting .agent-status-txt{background:var(--bg3);color:var(--t2);}
.idle    .agent-status-txt{background:var(--bg3);color:var(--t2);}

/* ─── MID ROW ─── */
.mid-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;}

/* ─── DIAGNOSTICS ─── */
.diag-health{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:12px;}
.hp{
  background:var(--bg2);border:1px solid var(--b0);border-radius:8px;
  padding:9px 10px;text-align:center;
}
.hp-n{font-size:9.5px;color:var(--t2);letter-spacing:.05em;margin-bottom:3px;}
.hp-v{font-size:13px;font-weight:700;}
.hp-v.ok  {color:var(--ok);}
.hp-v.warn{color:var(--warn);}
.hp-v.error{color:var(--err);}
.hp-v.info{color:var(--info);}
.diag-list{display:flex;flex-direction:column;gap:5px;}
.di{
  display:flex;gap:9px;align-items:flex-start;
  background:var(--bg2);border:1px solid var(--b0);
  border-radius:7px;padding:8px 11px;transition:.15s;
}
.di:hover{border-color:var(--b1);}
.di-ic{
  width:17px;height:17px;border-radius:50%;flex-shrink:0;margin-top:1px;
  display:flex;align-items:center;justify-content:center;
  font-size:9px;font-weight:700;
}
.di-ic.ok  {background:var(--ok-s);  color:var(--ok);}
.di-ic.warn{background:var(--warn-s);color:var(--warn);}
.di-ic.error{background:var(--err-s);color:var(--err);}
.di-ic.info{background:var(--info-s);color:var(--info);}
.di-b{flex:1;min-width:0;}
.di-t{font-size:11.5px;font-weight:600;color:var(--t0);}
.di-d{font-size:10.5px;color:var(--t2);margin-top:2px;line-height:1.4;}
.di-tag{
  font-size:9px;font-weight:700;letter-spacing:.04em;
  padding:1px 6px;border-radius:4px;
  background:var(--bg3);color:var(--t2);flex-shrink:0;align-self:center;
}

/* ─── TOPICS ─── */
.topics-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.tb{
  background:var(--bg2);border:1px solid var(--b0);
  border-radius:8px;padding:12px;transition:.2s;
}
.tb:hover{border-color:var(--b1);transform:translateY(-1px);}
.t-cat{font-size:9.5px;font-weight:700;letter-spacing:.07em;margin-bottom:4px;}
.t-nm{font-size:11px;color:var(--t2);margin-bottom:7px;line-height:1.3;}
.t-vl{font-size:22px;font-weight:800;letter-spacing:-.4px;line-height:1;}
.t-sb{font-size:10px;color:var(--t2);margin-top:2px;}
.t-br{background:var(--b0);border-radius:3px;height:3px;margin-top:8px;overflow:hidden;}
.t-fl{height:100%;border-radius:3px;transition:width .6s;}

/* ─── BOTTOM ROW (logs + chat) ─── */
.bottom-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;}

/* ─── LOG ─── */
.log-tabs{display:flex;gap:4px;padding:12px 18px 0;}
.log-tab{
  padding:4px 13px;border-radius:6px;font-size:11px;
  cursor:pointer;color:var(--t2);
  background:var(--bg2);border:1px solid var(--b0);transition:.15s;
}
.log-tab:hover{color:var(--t1);}
.log-tab.active{background:var(--brand-s);border-color:rgba(114,122,140,.3);color:var(--brand);}
.log-bd{
  font-family:'SF Mono',Menlo,Consolas,monospace;
  font-size:11px;line-height:1.7;color:var(--t2);
  background:var(--bg2);margin:10px 18px 16px;
  border:1px solid var(--b0);border-radius:8px;
  padding:11px 13px;height:180px;overflow-y:auto;
  white-space:pre-wrap;word-break:break-all;
}
.log-bd::-webkit-scrollbar{width:3px;}
.log-bd::-webkit-scrollbar-thumb{background:var(--b0);border-radius:2px;}
.ll-e{color:var(--err);}
.ll-s{color:var(--ok);}
.ll-w{color:var(--warn);}

/* ─── CHAT ─── */
.chat-messages{
  height:200px;overflow-y:auto;padding:12px 16px;
  display:flex;flex-direction:column;gap:8px;
}
.chat-messages::-webkit-scrollbar{width:3px;}
.chat-messages::-webkit-scrollbar-thumb{background:var(--b0);}
.cm{max-width:90%;padding:8px 12px;border-radius:8px;font-size:12px;line-height:1.6;}
.cm.user{
  background:var(--brand-s);border:1px solid var(--brand-m);
  color:var(--t0);align-self:flex-end;border-radius:8px 8px 2px 8px;
}
.cm.ai{
  background:var(--bg2);border:1px solid var(--b0);
  color:var(--t1);align-self:flex-start;border-radius:2px 8px 8px 8px;
}
.cm.sys{
  background:var(--warn-s);border:1px solid rgba(184,155,114,.2);
  color:var(--warn);align-self:center;font-size:11px;border-radius:6px;
  text-align:center;max-width:100%;
}
.chat-input-row{
  display:flex;gap:8px;padding:10px 16px 14px;border-top:1px solid var(--b0);
}
.chat-input{
  flex:1;background:var(--bg2);border:1px solid var(--b0);
  border-radius:8px;padding:8px 12px;font-size:12px;color:var(--t0);
  font-family:inherit;outline:none;resize:none;
  transition:border-color .2s;
}
.chat-input:focus{border-color:var(--ba);}
.chat-send{
  background:var(--brand);color:#fff;border:none;
  padding:8px 14px;border-radius:8px;cursor:pointer;
  font-size:12px;font-weight:600;transition:.15s;
  white-space:nowrap;align-self:flex-end;
}
.chat-send:hover{background:#5e6675;}
.chat-send:disabled{opacity:.5;cursor:not-allowed;}
.chat-typing{color:var(--t2);font-size:11px;padding:0 16px 6px;animation:pls 1s infinite;}

/* ─── FEED (right sidebar) ─── */
.feed-card{display:flex;flex-direction:column;}
.feed-scroll{flex:1;overflow-y:auto;padding:0 16px 16px;max-height:calc(100vh - 200px);}
.feed-scroll::-webkit-scrollbar{width:3px;}
.feed-scroll::-webkit-scrollbar-thumb{background:var(--b0);}
.fi{
  display:flex;gap:9px;padding:9px 0;
  border-bottom:1px solid var(--b0);animation:fadeIn .3s ease;
}
.fi:last-child{border-bottom:none;}
@keyframes fadeIn{from{opacity:0;transform:translateY(-3px);}to{opacity:1;}}
.fi-dot{width:6px;height:6px;border-radius:50%;margin-top:4px;flex-shrink:0;}
.fi-dot.success{background:var(--ok);}
.fi-dot.warn   {background:var(--warn);}
.fi-dot.error  {background:var(--err);}
.fi-dot.info   {background:var(--t2);}
.fi-body{flex:1;min-width:0;}
.fi-badge{
  display:inline-block;font-size:9.5px;font-weight:700;
  padding:1px 7px;border-radius:4px;margin-bottom:3px;
}
.fi-msg{font-size:11.5px;color:var(--t1);line-height:1.5;word-break:break-word;}
.fi-time{font-size:10px;color:var(--t2);margin-top:1px;}

/* ─── BADGE ─── */
.badge{
  display:inline-flex;align-items:center;gap:3px;
  padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:600;
}
.b-ok  {background:var(--ok-s);  color:var(--ok);}
.b-warn{background:var(--warn-s);color:var(--warn);}
.b-brand{background:var(--brand-s);color:var(--brand);}
.b-err {background:var(--err-s); color:var(--err);}

/* ─── MODAL ─── */
.modal-ov{
  display:none;position:fixed;inset:0;z-index:500;
  background:rgba(47,42,36,.7);backdrop-filter:blur(8px);
  align-items:flex-start;justify-content:center;padding:40px 24px;
}
.modal-ov.open{display:flex;}
.modal-box{
  background:var(--bg1);border:1px solid var(--b0);
  border-radius:14px;width:100%;max-width:800px;max-height:85vh;
  display:flex;flex-direction:column;
  box-shadow:0 20px 60px rgba(50,40,30,.18);
  animation:mIn .22s ease;
}
@keyframes mIn{from{opacity:0;transform:scale(.96)translateY(8px);}to{opacity:1;transform:none;}}
.modal-hd{
  padding:14px 20px;border-bottom:1px solid var(--b0);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;
}
.modal-title{font-size:14px;font-weight:600;color:var(--t0);}
.modal-close{
  width:28px;height:28px;border-radius:6px;
  background:var(--bg2);border:1px solid var(--b0);
  color:var(--t2);cursor:pointer;font-size:13px;
  display:flex;align-items:center;justify-content:center;transition:.2s;
}
.modal-close:hover{border-color:var(--ba);color:var(--brand);}
.modal-bd{
  flex:1;overflow-y:auto;padding:18px 22px;
  font-family:'SF Mono',Menlo,monospace;
  font-size:12px;line-height:1.9;color:var(--t1);
  white-space:pre-wrap;word-break:break-word;background:var(--bg1);
}
.modal-ft{
  padding:9px 20px;border-top:1px solid var(--b0);
  font-size:10.5px;color:var(--t2);flex-shrink:0;
}
.empty{color:var(--t2);font-style:italic;font-size:12px;padding:10px 0;}
</style>
</head>
<body>

<!-- TOPBAR -->
<nav class="topbar">
  <div class="tb-l">
    <div class="logo">⬡ AI 無人工廠<span class="logo-sub">/ 控制台</span></div>
    <div class="state-pill si" id="spill">
      <span class="sdot"></span><span class="stxt">載入中</span>
    </div>
  </div>
  <div class="tb-r">
    <span class="ts-t" id="ts">--</span>
    <span class="ts-t">·</span>
    <span class="cdt" id="cdt">5s</span>
    <button class="rbtn" onclick="fetchNow()">⟳ 更新</button>
  </div>
</nav>

<!-- WARN STRIP -->
<div class="warn-strip" id="wstrip">
  ⚠ <strong>待完成：</strong>CLAUDE.md 中仍有 PLACEHOLDER_WHOP_* — 請填入真實 Whop 連結
</div>

<!-- KPI BAR -->
<div class="kpi-bar">
  <div class="kpi-c">
    <div class="kpi-v accent" id="k0">0</div><div class="kpi-l">今日產出</div>
  </div>
  <div class="kpi-c">
    <div class="kpi-v" id="k1">0</div><div class="kpi-l">文章總數</div>
  </div>
  <div class="kpi-c">
    <div class="kpi-v" id="k2">0</div>
    <div class="kpi-l">今日 API 呼叫
      <span style="color:var(--t2);font-size:9.5px;" title="需要在 agent 流程加入 api-usage.json 追蹤 hook">(?)</span>
    </div>
  </div>
  <div class="kpi-c">
    <div class="kpi-v" id="k3">0</div><div class="kpi-l">累計 API 呼叫</div>
  </div>
  <div class="kpi-c" id="k4c">
    <div class="kpi-v" id="k4">--</div><div class="kpi-l">系統健康度</div>
  </div>
</div>

<!-- MAIN -->
<div class="main">

  <!-- LEFT COL -->
  <div class="left">

    <!-- 生產流水線 -->
    <div class="card">
      <div class="ch">
        <div class="ct"><span class="cdot" style="background:var(--ok)"></span>生產流水線</div>
        <div id="mbadge"></div>
      </div>
      <div class="cb">
        <div id="ptrace"></div>
        <div id="aslot"></div>
      </div>
    </div>

    <!-- Agent 狀態 -->
    <div class="card">
      <div class="ch">
        <div class="ct"><span class="cdot" style="background:var(--brand)"></span>Agent 工作台</div>
        <span style="font-size:10.5px;color:var(--t2)" id="agent-summary"></span>
      </div>
      <div class="cb">
        <div class="agent-section">
          <div>
            <div class="agent-group-label">核心流程 Agent</div>
            <div class="agent-grid" id="agent-pipeline"></div>
          </div>
          <div>
            <div class="agent-group-label">支援 Agent</div>
            <div class="agent-grid" id="agent-support"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 診斷 + 主題 -->
    <div class="mid-row">
      <div class="card">
        <div class="ch">
          <div class="ct"><span class="cdot" style="background:var(--warn)"></span>系統診斷</div>
          <div id="dscore"></div>
        </div>
        <div class="cb">
          <div class="diag-health" id="dhealth"></div>
          <div class="diag-list" id="dlist"></div>
        </div>
      </div>
      <div class="card">
        <div class="ch">
          <div class="ct"><span class="cdot" style="background:var(--pur)"></span>主題表現</div>
        </div>
        <div class="cb">
          <div class="topics-grid" id="tgrid"></div>
        </div>
      </div>
    </div>

    <!-- 日誌 + 聊天 -->
    <div class="bottom-row">
      <!-- Log -->
      <div class="card">
        <div class="ct" style="padding:13px 18px 0;">
          <span class="cdot" style="background:var(--t2)"></span>執行日誌
        </div>
        <div class="log-tabs">
          <div class="log-tab active" onclick="switchLog('cron',this)">Cron</div>
          <div class="log-tab" onclick="switchLog('error',this)">錯誤</div>
        </div>
        <div class="log-bd" id="logbd"></div>
      </div>

      <!-- Chat -->
      <div class="card" style="display:flex;flex-direction:column;">
        <div class="ch">
          <div class="ct"><span class="cdot" style="background:var(--brand)"></span>控制台對話</div>
          <span style="font-size:10px;color:var(--t2)">MiniMax / Claude</span>
        </div>
        <div class="chat-messages" id="chat-msgs"></div>
        <div id="chat-typing" class="chat-typing" style="display:none;">AI 回覆中...</div>
        <div class="chat-input-row">
          <textarea class="chat-input" id="chat-in" rows="2"
            placeholder="輸入指令或問題，例如：目前系統狀態？如何清理重複 Cron？"
            onkeydown="chatKey(event)"></textarea>
          <button class="chat-send" id="chat-btn" onclick="sendChat()">送出</button>
        </div>
      </div>
    </div>

  </div><!-- /left -->

  <!-- RIGHT SIDEBAR: Activity Feed -->
  <div class="card feed-card">
    <div class="ch">
      <div class="ct">
        <span class="cdot" style="background:var(--brand);animation:pls 2s infinite;"></span>
        團隊活動流
      </div>
    </div>
    <div class="feed-scroll" id="feed-list"></div>
  </div>

</div><!-- /main -->

<!-- ARTICLE MODAL -->
<div class="modal-ov" id="modal" onclick="closeModal(event)">
  <div class="modal-box" onclick="event.stopPropagation()">
    <div class="modal-hd">
      <div class="modal-title" id="mtitle">文章內容</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-bd" id="mbody">載入中...</div>
    <div class="modal-ft" id="mfoot"></div>
  </div>
</div>

<script>
// ── 狀態 ──────────────────────────
let currentLog = 'cron';
let countdown  = 5;
let timer;
let lastData   = null;

const AGENT_DEF = [
  {id:'researcher',      label:'研究員',  icon:'◎', role:'pipeline'},
  {id:'topic-selector',  label:'選題',    icon:'◈', role:'pipeline'},
  {id:'writer',          label:'寫手',    icon:'✦', role:'pipeline'},
  {id:'reviewer',        label:'審稿',    icon:'◉', role:'pipeline'},
  {id:'poster',          label:'發文',    icon:'◆', role:'pipeline'},
  {id:'english-writer',  label:'英文版',  icon:'E', role:'support'},
  {id:'chinese-writer',  label:'中文版',  icon:'中',role:'support'},
  {id:'seo-agent',       label:'SEO',     icon:'S', role:'support'},
  {id:'feedback-collector',label:'回報',  icon:'F', role:'support'},
  {id:'knowledge-subagent',label:'知識庫',icon:'K', role:'support'},
];

const AGENT_FEED_COLOR = {
  writer:'#727A8C',researcher:'#8193A8',reviewer:'#8B85A0',
  poster:'#7C9A7E','quality-check':'#B89B72',
  'topic-selector':'#727A8C',system:'#8A837A',
  feedback:'#8B85A0',
};

const CAT_COLOR = {A:'#727A8C',B:'#8B85A0',C:'#7C9A7E',D:'#8193A8'};
const CAT_LABEL = {A:'電容/壓力感測',B:'手勢/彎曲感測',C:'互動設計',D:'IoT/ESP32'};

// ── fetch loop ─────────────────────
async function fetchNow(){
  clearInterval(timer);
  countdown = 5;
  try{
    const r = await fetch('/api/status');
    const d = await r.json();
    lastData = d;
    render(d);
  }catch(e){
    setPill('se','連線失敗');
  }
  startTimer();
}

function startTimer(){
  clearInterval(timer);
  timer = setInterval(()=>{
    countdown--;
    const el = document.getElementById('cdt');
    if(el) el.textContent = countdown+'s';
    if(countdown<=0) fetchNow();
  },1000);
}

// ── main render ────────────────────
function render(d){
  document.getElementById('ts').textContent = d.ts;
  document.getElementById('wstrip').style.display = d.has_placeholder?'flex':'none';
  const stMap = {idle:'si',running:'sr',error:'se'};
  const stTxt = {idle:'待機中',running:'執行中',error:'有錯誤'};
  setPill(stMap[d.state]||'si', stTxt[d.state]||d.state);

  // KPI — 全白字，只有今日產出用品牌色
  document.getElementById('k0').textContent = d.pipeline.count||0;
  document.getElementById('k1').textContent = d.article_count||0;
  document.getElementById('k2').textContent = d.usage.today||0;
  document.getElementById('k3').textContent = d.usage.total||0;
  const sc = d.diag?.score??100;
  const se = document.getElementById('k4');
  se.textContent = sc+'%';
  se.className = 'kpi-v '+(sc>=85?'ok':sc>=60?'warn':'err');

  document.getElementById('mbadge').innerHTML =
    `<span style="font-size:10.5px;color:var(--ok);font-weight:600;">● ${esc(d.api.model)}</span>`;

  renderPipeline(d.pipeline, d.articles||[]);
  renderAgents(d.agents||{});
  renderDiag(d.diag||{});
  renderTopics(d.perf||{});
  renderFeed(d.feed||[]);
  renderLog(d);
}

function setPill(cls, label){
  const el = document.getElementById('spill');
  el.className = 'state-pill '+cls;
  el.querySelector('.stxt').textContent = label;
}

// ── pipeline ───────────────────────
function renderPipeline(pipe, arts){
  const stages = pipe.stages||[];
  let h = '<div class="pipe-track">';
  stages.forEach((s,i)=>{
    const done   = s.done;
    const active = !done && i>0 && stages[i-1].done;
    const cls = done?'done':active?'active':'';
    h += `<div class="pipe-node ${cls}">
      <div class="p-ring">${done?'✓':active?'◉':'○'}</div>
      <div class="p-lbl">${s.label}</div>
    </div>`;
    if(i<stages.length-1){
      const cc = done?(stages[i+1].done?'done':'active'):'';
      h += `<div class="pipe-conn ${cc}"></div>`;
    }
  });
  h += '</div>';
  document.getElementById('ptrace').innerHTML = h;

  const slot = document.getElementById('aslot');
  if(pipe.article){
    const a = pipe.article;
    slot.innerHTML = `
      <div class="art-banner" onclick="openArticle('${esc(a.name||'')}','${esc(a.title||a.name||'')}')">
        <div>
          <div class="art-title">${esc(a.title||a.name||'未命名')}</div>
          <div class="art-meta">狀態：<span class="badge b-brand">${esc(a.status||'')}</span>
            &nbsp;·&nbsp;${esc(a.date||'')}</div>
        </div>
        <div class="view-btn">閱讀全文 →</div>
      </div>
      ${arts.length>1?buildArtList(arts):''}`;
  } else {
    slot.innerHTML = `
      <div class="pipe-empty">
        今日尚未產出文章<br>
        <span style="font-size:10.5px">Cron 排程每日 09:00 UTC 自動觸發</span>
      </div>
      ${arts.length?buildArtList(arts):''}`;
  }
}

function buildArtList(arts){
  return `<div class="art-list">
    <div class="art-list-hd">文章庫（共 ${arts.length} 篇）</div>
    ${arts.slice(0,6).map(a=>`
      <div class="ali">
        <div class="ali-name" title="${esc(a.title)}">${esc(a.title)}</div>
        <div class="ali-meta">${a.words||''} 詞</div>
        <div class="ali-btn" onclick="openArticle('${esc(a.name)}','${esc(a.title)}')">閱讀</div>
      </div>`).join('')}
  </div>`;
}

// ── agents ─────────────────────────
function renderAgents(states){
  const pipeline = AGENT_DEF.filter(a=>a.role==='pipeline');
  const support  = AGENT_DEF.filter(a=>a.role==='support');
  let wc=0, waiting=0;

  function buildGrid(list){
    return list.map(a=>{
      const s = states[a.id]||{status:'idle',txt:'休息中'};
      if(s.status==='working') wc++;
      if(s.status==='waiting') waiting++;
      return `<div class="agent-card ${s.status}">
        <div class="agent-icon">${esc(a.icon)}</div>
        <div class="agent-name">${a.label}</div>
        <div class="agent-status-txt">${s.txt}</div>
      </div>`;
    }).join('');
  }

  document.getElementById('agent-pipeline').innerHTML = buildGrid(pipeline);
  document.getElementById('agent-support').innerHTML  = buildGrid(support);
  document.getElementById('agent-summary').textContent =
    wc>0?`${wc} 個工作中` : waiting>0?`${waiting} 個等待中`:'全部休息中';
}

// ── diag ───────────────────────────
function renderDiag(diag){
  const sc = diag.score??100;
  const sc_cls = sc>=85?'ok':sc>=60?'warn':'err';
  const scBadge = {ok:'b-ok',warn:'b-warn',err:'b-err'}[sc_cls];
  document.getElementById('dscore').innerHTML =
    `<span class="badge ${scBadge}">${sc}% 健康</span>`;

  const pm = {ok:'ok',warn:'warn',error:'error',info:'info'};
  document.getElementById('dhealth').innerHTML = (diag.health||[]).map(h=>`
    <div class="hp">
      <div class="hp-n">${esc(h.name)}</div>
      <div class="hp-v ${pm[h.status]||'info'}">${esc(h.val)}</div>
    </div>`).join('');

  const im = {ok:'✓',warn:'!',error:'✕',info:'i'};
  document.getElementById('dlist').innerHTML = (diag.issues||[]).map(it=>`
    <div class="di">
      <div class="di-ic ${it.level}">${im[it.level]||'i'}</div>
      <div class="di-b">
        <div class="di-t">${esc(it.title)}</div>
        ${it.desc?`<div class="di-d">${esc(it.desc)}</div>`:''}
      </div>
      <div class="di-tag">${esc(it.tag||'')}</div>
    </div>`).join('') || '<div class="empty">無診斷項目</div>';
}

// ── topics ─────────────────────────
function renderTopics(perf){
  document.getElementById('tgrid').innerHTML = ['A','B','C','D'].map(c=>{
    const d = perf[c]||{avg_upvotes:0,count:0};
    const w = Math.min((d.avg_upvotes||0)*2,100);
    const col = CAT_COLOR[c];
    return `<div class="tb">
      <div class="t-cat" style="color:${col}">${c} 類</div>
      <div class="t-nm">${CAT_LABEL[c]}</div>
      <div class="t-vl" style="color:${col}">${Number(d.avg_upvotes||0).toFixed(0)}</div>
      <div class="t-sb">avg upvotes · ${d.count||0} 篇</div>
      <div class="t-br"><div class="t-fl" style="width:${w}%;background:${col}"></div></div>
    </div>`;
  }).join('');
}

// ── feed ───────────────────────────
function renderFeed(feed){
  const el = document.getElementById('feed-list');
  if(!feed||!feed.length){
    el.innerHTML='<div class="empty" style="padding:20px;text-align:center;">尚無活動記錄</div>';
    return;
  }
  el.innerHTML = feed.map(f=>`
    <div class="fi">
      <div class="fi-dot ${f.type}"></div>
      <div class="fi-body">
        <span class="fi-badge"
          style="background:${(AGENT_FEED_COLOR[f.agent]||'#8A837A')}18;
            color:${AGENT_FEED_COLOR[f.agent]||'#8A837A'};
            border:1px solid ${(AGENT_FEED_COLOR[f.agent]||'#8A837A')}30;">
          ${esc(f.agent)}
        </span>
        <div class="fi-msg">${esc(f.msg)}</div>
        ${f.time?`<div class="fi-time">${esc(f.time)}</div>`:''}
      </div>
    </div>`).join('');
}

// ── log ────────────────────────────
function renderLog(d){
  const lines = currentLog==='cron'?d.cron_log_tail:d.error_log;
  const el = document.getElementById('logbd');
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

function switchLog(type, btn){
  currentLog = type;
  document.querySelectorAll('.log-tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  if(lastData) renderLog(lastData);
}

// ── chat ───────────────────────────
function addChatMsg(role, text){
  const box = document.getElementById('chat-msgs');
  const el  = document.createElement('div');
  el.className = 'cm '+(role==='user'?'user':role==='ai'?'ai':'sys');
  el.textContent = text;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

async function sendChat(){
  const inp = document.getElementById('chat-in');
  const msg = inp.value.trim();
  if(!msg) return;
  inp.value = '';
  addChatMsg('user', msg);
  document.getElementById('chat-btn').disabled = true;
  document.getElementById('chat-typing').style.display = 'block';
  try{
    const r = await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message:msg})
    });
    const d = await r.json();
    addChatMsg('ai', d.reply||'（無回應）');
  }catch(e){
    addChatMsg('sys','連線失敗：'+e);
  }
  document.getElementById('chat-btn').disabled = false;
  document.getElementById('chat-typing').style.display = 'none';
}

function chatKey(e){
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendChat(); }
}

// ── article modal ──────────────────
async function openArticle(name,title){
  if(!name) return;
  document.getElementById('mtitle').textContent = title||name;
  document.getElementById('mbody').textContent  = '載入中...';
  document.getElementById('mfoot').textContent  = '';
  document.getElementById('modal').classList.add('open');
  try{
    const r = await fetch('/api/article?name='+encodeURIComponent(name));
    if(r.ok){
      const txt = await r.text();
      document.getElementById('mbody').textContent = txt;
      document.getElementById('mfoot').textContent =
        `${name}.md  ·  ${txt.split(/\s+/).length} 詞  ·  ${txt.length} 字元`;
    }else{ document.getElementById('mbody').textContent='找不到文章。'; }
  }catch(e){ document.getElementById('mbody').textContent='載入失敗：'+e; }
}

function closeModal(e){
  if(!e||e.target.id==='modal') document.getElementById('modal').classList.remove('open');
}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape') closeModal({target:{id:'modal'}});
});

function esc(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

fetchNow();
</script>
</body>
</html>"""

# ── HTTP Handler ──────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            data = json.dumps(get_status_data(), ensure_ascii=False).encode("utf-8")
            self._json(data)
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

    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length",0))
            body   = json.loads(self.rfile.read(length))
            msg    = body.get("message","").strip()
            reply  = do_chat(msg) if msg else "請輸入訊息。"
            self._json(json.dumps({"reply":reply}, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404); self.end_headers()

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT",3000))
    print(f"Dashboard v5 啟動：http://0.0.0.0:{port}")
    HTTPServer(("0.0.0.0",port), Handler).serve_forever()
