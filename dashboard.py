#!/usr/bin/env python3
"""
AI 無人工廠 Dashboard
執行：python3 ~/ai-factory/dashboard.py
訪問：http://VPS_IP:3000
"""

import json, os, re, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent

# ── 資料讀取 ──────────────────────────────────────────

def read_json(path, default=None):
    try:
        return json.loads(Path(BASE / path).read_text(encoding="utf-8"))
    except:
        return default or {}

def read_text(path, lines=50):
    try:
        content = Path(BASE / path).read_text(encoding="utf-8")
        return "\n".join(content.splitlines()[-lines:])
    except:
        return ""

def count_files(pattern):
    try:
        return len(list(Path(BASE).glob(pattern)))
    except:
        return 0

def check_placeholder():
    try:
        content = (BASE / "CLAUDE.md").read_text(encoding="utf-8")
        return "PLACEHOLDER" in content
    except:
        return True

def get_cron_status():
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=3)
        lines = [l for l in result.stdout.splitlines() if "ai-factory" in l]
        return lines
    except:
        return []

def get_api_model():
    try:
        settings = json.loads(Path.home().joinpath(".claude/settings.json").read_text())
        return settings.get("env", {}).get("ANTHROPIC_MODEL", "未設定")
    except:
        return "Claude（預設）"

# ── HTML 生成 ─────────────────────────────────────────

def render():
    progress   = read_json("logs/progress.json", [])
    perf       = read_json("logs/topic-performance.json", {})
    cron_lines = get_cron_status()
    has_placeholder = check_placeholder()
    api_model  = get_api_model()
    articles   = sorted(Path(BASE / "articles").glob("20*.md"), reverse=True)[:5]
    cron_log   = read_text("logs/cron.log", 30)
    error_log  = read_text("logs/error.log", 20)
    knowledge  = read_text(".knowledge/posted-articles.md")

    skills_count = count_files(".claude/skills/*.md")
    hooks_count  = count_files(".claude/hooks/*.sh")
    agents_count = count_files(".claude/agents/*.md")

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # 狀態燈
    def badge(ok, yes_text="PASS", no_text="FAIL"):
        cls = "badge-green" if ok else "badge-red"
        return f'<span class="badge {cls}">{yes_text if ok else no_text}</span>'

    def warn_badge(text):
        return f'<span class="badge badge-yellow">{text}</span>'

    # 文章表格列
    article_rows = ""
    for a in articles:
        article_rows += f'<tr><td class="mono">{a.stem}</td><td>{a.stat().st_size // 1024} KB</td></tr>\n'

    # progress 記錄
    prog_rows = ""
    for p in reversed(progress[-5:]):
        status_cls = "badge-green" if p.get("status") == "reviewed" else "badge-yellow"
        prog_rows += f'''<tr>
            <td>{p.get("date","")}</td>
            <td class="title-cell">{p.get("title","")}</td>
            <td><span class="badge {status_cls}">{p.get("status","")}</span></td>
        </tr>\n'''

    # topic performance
    cats = perf.get("categories", {})
    perf_rows = ""
    for cat, data in cats.items():
        avg_up = data.get("avg_upvotes", 0)
        avg_co = data.get("avg_comments", 0)
        count  = data.get("count", 0)
        bar_w  = min(int(avg_up * 2), 100)
        perf_rows += f'''<tr>
            <td class="cat-label">{cat}</td>
            <td>{count} 篇</td>
            <td>
              <div class="bar-bg"><div class="bar-fill" style="width:{bar_w}%"></div></div>
              <span class="bar-num">{avg_up:.0f} upvotes</span>
            </td>
            <td>{avg_co:.0f} 則</td>
        </tr>\n'''

    # cron 狀態
    cron_html = ""
    for line in cron_lines:
        cron_html += f'<div class="mono cron-line">{line}</div>\n'
    if not cron_lines:
        cron_html = '<div class="warn-text">尚未設定排程</div>'

    # 日誌
    def log_block(content, cls=""):
        if not content.strip():
            return '<div class="log-empty">（無記錄）</div>'
        return f'<pre class="log-content {cls}">{content[-2000:]}</pre>'

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>AI 無人工廠 Dashboard</title>
<style>
:root {{
  --bg: #0f172a; --card: #1e293b; --border: #334155;
  --text: #e2e8f0; --muted: #94a3b8; --accent: #38bdf8;
  --green: #22c55e; --yellow: #eab308; --red: #ef4444;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; font-size: 14px; }}
.top-bar {{ background: var(--card); border-bottom: 1px solid var(--border);
  padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }}
.top-bar h1 {{ font-size: 18px; font-weight: 700; color: var(--accent); }}
.top-bar .ts {{ color: var(--muted); font-size: 12px; }}
.refresh-hint {{ color: var(--muted); font-size: 11px; margin-top: 2px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px; padding: 20px 24px; }}
.grid-wide {{ grid-column: 1 / -1; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px; }}
.card h2 {{ font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase;
  letter-spacing: .05em; margin-bottom: 14px; }}
.stat-row {{ display: flex; align-items: center; justify-content: space-between;
  padding: 6px 0; border-bottom: 1px solid var(--border); }}
.stat-row:last-child {{ border-bottom: none; }}
.stat-label {{ color: var(--muted); }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 600; }}
.badge-green {{ background: rgba(34,197,94,.15); color: var(--green); }}
.badge-red   {{ background: rgba(239,68,68,.15);  color: var(--red); }}
.badge-yellow{{ background: rgba(234,179,8,.15);  color: var(--yellow); }}
.badge-blue  {{ background: rgba(56,189,248,.15); color: var(--accent); }}
.big-num {{ font-size: 36px; font-weight: 800; color: var(--accent); }}
.big-label {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; }}
.stat-box {{ text-align: center; padding: 14px; background: var(--bg);
  border-radius: 8px; border: 1px solid var(--border); }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ color: var(--muted); font-weight: 500; text-align: left;
  padding: 6px 8px; border-bottom: 1px solid var(--border); font-size: 12px; }}
td {{ padding: 7px 8px; border-bottom: 1px solid rgba(51,65,85,.5); vertical-align: middle; }}
tr:last-child td {{ border-bottom: none; }}
.mono {{ font-family: monospace; font-size: 12px; }}
.title-cell {{ max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.bar-bg {{ background: var(--border); border-radius: 4px; height: 6px;
  width: 120px; display: inline-block; vertical-align: middle; }}
.bar-fill {{ background: var(--accent); border-radius: 4px; height: 6px; }}
.bar-num {{ color: var(--muted); font-size: 11px; margin-left: 6px; }}
.cat-label {{ font-weight: 700; color: var(--accent); width: 30px; }}
.cron-line {{ color: var(--green); font-size: 11px; background: var(--bg);
  padding: 6px 10px; border-radius: 6px; margin-bottom: 6px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.warn-text {{ color: var(--yellow); font-size: 12px; }}
.log-content {{ color: #94a3b8; font-size: 11px; background: var(--bg);
  border: 1px solid var(--border); border-radius: 6px; padding: 10px;
  max-height: 200px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }}
.log-content.error {{ color: var(--red); }}
.log-empty {{ color: var(--muted); font-size: 12px; font-style: italic; }}
.model-name {{ color: var(--green); font-weight: 700; font-size: 13px; }}
.placeholder-warn {{ background: rgba(234,179,8,.1); border: 1px solid rgba(234,179,8,.3);
  border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;
  color: var(--yellow); font-size: 13px; }}
.placeholder-warn strong {{ display: block; margin-bottom: 4px; }}
</style>
</head>
<body>
<div class="top-bar">
  <div>
    <h1>🏭 AI 無人工廠 Dashboard</h1>
    <div class="refresh-hint">每60秒自動重新整理</div>
  </div>
  <div class="ts">最後更新：{now}</div>
</div>

<div class="grid">

  {'<div class="grid-wide"><div class="placeholder-warn"><strong>⚠️ 待完成：填入 Whop 連結</strong>CLAUDE.md 中仍有 PLACEHOLDER_WHOP_* — 填入真實連結後系統才能在文章中放置正確的銷售連結。</div></div>' if has_placeholder else ''}

  <!-- 系統元件 -->
  <div class="card">
    <h2>系統元件</h2>
    <div class="stat-grid">
      <div class="stat-box">
        <div class="big-num">{skills_count}</div>
        <div class="big-label">Skills</div>
        {badge(skills_count >= 26)}
      </div>
      <div class="stat-box">
        <div class="big-num">{hooks_count}</div>
        <div class="big-label">Hooks</div>
        {badge(hooks_count >= 11)}
      </div>
      <div class="stat-box">
        <div class="big-num">{agents_count}</div>
        <div class="big-label">Agents</div>
        {badge(agents_count >= 11)}
      </div>
    </div>
  </div>

  <!-- API 狀態 -->
  <div class="card">
    <h2>API 狀態</h2>
    <div class="stat-row">
      <span class="stat-label">使用模型</span>
      <span class="model-name">{api_model}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Minimax 切換</span>
      {badge("MiniMax" in api_model, "已切換", "使用 Claude")}
    </div>
    <div class="stat-row">
      <span class="stat-label">Whop 連結</span>
      {warn_badge("待填入") if has_placeholder else badge(True, "已設定")}
    </div>
  </div>

  <!-- Cron 排程 -->
  <div class="card">
    <h2>Cron 排程</h2>
    <div class="stat-row" style="margin-bottom:10px">
      <span class="stat-label">排程數量</span>
      {badge(len(cron_lines) >= 2, f"{len(cron_lines)} 條", f"{len(cron_lines)} 條（需要2條）")}
    </div>
    {cron_html}
  </div>

  <!-- 文章歷史 -->
  <div class="card">
    <h2>文章歷史（最近5筆）</h2>
    <table>
      <tr><th>日期</th><th>標題</th><th>狀態</th></tr>
      {prog_rows if prog_rows else '<tr><td colspan="3" style="color:var(--muted);font-style:italic">尚無記錄</td></tr>'}
    </table>
  </div>

  <!-- 主題表現 -->
  <div class="card">
    <h2>主題類別表現</h2>
    <table>
      <tr><th>類</th><th>篇數</th><th>平均 Upvotes</th><th>平均留言</th></tr>
      {perf_rows if perf_rows else '<tr><td colspan="4" style="color:var(--muted);font-style:italic">尚無數據</td></tr>'}
    </table>
  </div>

  <!-- 最新文章 -->
  <div class="card">
    <h2>articles/ 最新檔案</h2>
    <table>
      <tr><th>檔名</th><th>大小</th></tr>
      {article_rows if article_rows else '<tr><td colspan="2" style="color:var(--muted);font-style:italic">尚無文章</td></tr>'}
    </table>
  </div>

  <!-- Cron 日誌 -->
  <div class="card grid-wide">
    <h2>Cron 執行日誌（最後30行）</h2>
    {log_block(cron_log)}
  </div>

  <!-- 錯誤日誌 -->
  <div class="card grid-wide">
    <h2>錯誤日誌</h2>
    {log_block(error_log, "error")}
  </div>

</div>
</body>
</html>"""

# ── HTTP Server ───────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        html = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(html))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, fmt, *args):
        pass  # 靜默 access log

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 3000))
    print(f"Dashboard 啟動：http://0.0.0.0:{port}")
    print("按 Ctrl+C 停止")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
