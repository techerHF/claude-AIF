#!/usr/bin/env bash
# test-agents-individual.sh
# 14個 Agent 逐一測試 + File Diff 驗證（證明不是幻覺）
# + Writer 10輪學習曲線
# 執行：bash test-agents-individual.sh 2>&1 | tee logs/agent-individual-report.txt
# 預計時間：60-90 分鐘

cd ~/ai-factory
mkdir -p logs .knowledge .agent-growth
PASS=0; FAIL=0; WARN=0
REPORT="logs/agent-individual-report.txt"

ts()   { date '+%H:%M:%S'; }
hr()   { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
ok()   { echo "  ✅ [$(ts)] $1"; ((PASS++)); }
fail() { echo "  ❌ [$(ts)] $1"; ((FAIL++)); }
warn() { echo "  ⚠️  [$(ts)] $1"; ((WARN++)); }

# ─────────────────────────────────────────────
# 核心工具：file diff 驗證（防幻覺）
# ─────────────────────────────────────────────
verify_file_changed() {
  local FILE="$1"
  local BEFORE_HASH="$2"
  local LABEL="$3"
  if [ ! -f "$FILE" ]; then
    fail "$LABEL — 檔案不存在：$FILE"; return 1
  fi
  local AFTER_HASH=$(md5sum "$FILE" | cut -d' ' -f1)
  if [ "$AFTER_HASH" != "$BEFORE_HASH" ]; then
    local NEW_LINES=$(diff <(echo "$4") "$FILE" | grep '^>' | wc -l)
    ok "$LABEL — 檔案已真實修改（新增 $NEW_LINES 行）"
    echo "    ┌─ 新增內容預覽："
    diff <(echo "$4") "$FILE" | grep '^>' | head -5 | sed 's/^> /    │ /'
    echo "    └─"
    return 0
  else
    fail "$LABEL — 檔案未被修改（agent 說更新但 md5 相同）"
    return 1
  fi
}

snapshot() {
  local FILE="$1"
  if [ -f "$FILE" ]; then
    echo "$(md5sum "$FILE" | cut -d' ' -f1)"
  else
    echo "NOFILE"
  fi
}

snapshot_content() {
  local FILE="$1"
  cat "$FILE" 2>/dev/null || echo ""
}

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   14 Agent 個別測試 + File Diff 防幻覺驗證      ║"
echo "╚════════════════════════════════════════════════╝"
echo "開始：$(date)"
hr

# ══════════════════════════════════════════════
# AGENT-01：researcher
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-01】researcher"
hr
GROWTH=".agent-growth/researcher.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 researcher 子 agent。

任務：
1. 先讀取 .agent-growth/researcher.md，記住自己目前掌握的技能
2. 嘗試 WebFetch https://www.reddit.com/r/arduino/top.json?t=week&limit=5（Reddit 可能被封）
3. 不論成功或失敗，分析這次爬蟲的技術細節（回傳什麼、HTTP code、原因）
4. 在 .agent-growth/researcher.md 的「發現的有效模式」加入：
   [$(date +%Y-%m-%d)] Reddit 狀態：[成功/失敗原因] | 備援：topic-tracker.sh
5. 輸出：「AGENT_DONE: 爬蟲結果=[成功/失敗], 記錄=[已更新/未更新]」
" --allowedTools "Agent,Read,Write,WebFetch,Bash" --max-turns 5 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "researcher growth 更新驗證" "$C_BEFORE"
if echo "$RESULT" | grep -q "AGENT_DONE"; then
  ok "researcher 正確輸出 AGENT_DONE"
else
  warn "researcher 輸出格式：$(echo "$RESULT" | tail -2)"
fi

# ══════════════════════════════════════════════
# AGENT-02：topic-selector
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-02】topic-selector"
hr
GROWTH=".agent-growth/topic-selector.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 topic-selector 子 agent。

任務：
1. 讀取 .agent-growth/topic-selector.md（了解自己的選題歷史）
2. 執行選題流程（bash .claude/hooks/topic-tracker.sh suggest）
3. 選出一個未重複的主題（bash .claude/hooks/duplicate-check.sh [主題]）
4. 在 .agent-growth/topic-selector.md 加入：
   [$(date +%Y-%m-%d)] 選題：[主題] | 理由：[一句話]
5. 輸出：「TOPIC_SELECTED: [主題名稱]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 5 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "topic-selector growth 更新驗證" "$C_BEFORE"
SELECTED=$(echo "$RESULT" | grep "TOPIC_SELECTED" | head -1)
if [ -n "$SELECTED" ]; then
  ok "topic-selector 輸出：$SELECTED"
else
  warn "topic-selector 未輸出 TOPIC_SELECTED：$(echo "$RESULT" | tail -2)"
fi

# ══════════════════════════════════════════════
# AGENT-03：writer（10輪學習曲線）
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-03】writer（10輪學習曲線）"
hr
GROWTH=".agent-growth/writer.md"
echo "  開始前行數：$(wc -l < $GROWTH 2>/dev/null || echo 0)"
echo ""

TOPICS=(
  "LM35 溫度感測器精度校正"
  "HC-SR04 超音波距離測量原理"
  "MPR121 電容觸控感測器"
  "BMP280 氣壓高度計算"
  "PIR 人體紅外線偵測調參"
  "ACS712 電流感測器安全使用"
  "MQ-2 煙霧感測器閾值設定"
  "HX711 力感測器零點校正"
  "MLX90614 非接觸溫度計"
  "VL53L0X 雷射測距精度測試"
)

declare -a GROWTH_CURVE
for i in "${!TOPICS[@]}"; do
  ROUND=$((i+1))
  TOPIC="${TOPICS[$i]}"
  LINES_BEFORE=$(wc -l < "$GROWTH" 2>/dev/null || echo 0)
  H_BEFORE=$(snapshot "$GROWTH")
  C_BEFORE=$(snapshot_content "$GROWTH")

  echo "  Round $ROUND/10：$TOPIC"

  RESULT=$(timeout 150 claude -p "
使用 Agent tool 呼叫 writer 子 agent。

任務（Round $ROUND/10）：
1. 讀取 .agent-growth/writer.md，記住所有有效模式
2. 如果這是第 2 輪以後，必須引用前幾輪的具體學習（直接引用文字）
3. 寫一篇 400-500 字的 Arduino 教學：$TOPIC
4. 儲存到 articles/learn-curve-r${ROUND}-$(date +%Y%m%d).md
5. 在 .agent-growth/writer.md 加入（格式固定）：
   [$(date +%Y-%m-%d) R${ROUND}] 主題：$TOPIC | 字數：[N] | 本輪學習：[一句具體觀察]
6. 輸出：「ROUND:${ROUND} WORDS:[字數] LEARNED:[學到什麼]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 6 2>/dev/null)

  LINES_AFTER=$(wc -l < "$GROWTH" 2>/dev/null || echo 0)
  GROWTH_CURVE[$i]=$LINES_AFTER
  ADDED=$((LINES_AFTER - LINES_BEFORE))

  if [ "$ADDED" -gt 0 ]; then
    ok "R${ROUND} growth +${ADDED} 行（總計 $LINES_AFTER 行）"
  else
    fail "R${ROUND} growth 未增長（仍 $LINES_BEFORE 行）"
  fi

  ART=$(ls articles/learn-curve-r${ROUND}-*.md 2>/dev/null | head -1)
  if [ -n "$ART" ]; then
    WC=$(wc -w < "$ART" 2>/dev/null || echo 0)
    ok "R${ROUND} 文章產出（$WC words）"
  else
    fail "R${ROUND} 無文章產出"
  fi

  # 從 Round 3 開始驗證引用
  if [ "$ROUND" -ge 3 ]; then
    CONTENT=$(cat "$GROWTH" 2>/dev/null)
    PREV_ENTRY=$(echo "$CONTENT" | grep "R$((ROUND-1))" | head -1)
    if [ -n "$PREV_ENTRY" ] && echo "$RESULT" | grep -qi "引用\|前一\|上次\|R$((ROUND-1))\|round $((ROUND-1))"; then
      ok "R${ROUND} 明確引用前輪記錄"
    else
      warn "R${ROUND} 未明確引用前輪（但 growth file 有更新）"
    fi
  fi

  echo "    └─ $(echo "$RESULT" | grep "ROUND:" | head -1)"
done

# 學習曲線報告
echo ""
echo "  ── Writer 10輪學習曲線 ──"
for i in "${!GROWTH_CURVE[@]}"; do
  ROUND=$((i+1))
  LINES=${GROWTH_CURVE[$i]}
  BAR=$(printf '█%.0s' $(seq 1 $((LINES/2))))
  printf "  R%02d: %3d 行 %s\n" "$ROUND" "$LINES" "$BAR"
done

FIRST=${GROWTH_CURVE[0]}; LAST=${GROWTH_CURVE[9]}
echo "  增長：$FIRST → $LAST 行（+$((LAST-FIRST))）"
if [ "$((LAST - FIRST))" -ge 10 ]; then
  ok "Writer 10輪學習曲線 — 有效堆積（+$((LAST-FIRST)) 行）"
else
  fail "Writer 10輪學習曲線 — 堆積不足"
fi

# ══════════════════════════════════════════════
# AGENT-04：seo-agent
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-04】seo-agent"
hr
GROWTH=".agent-growth/seo-agent.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

ART=$(ls articles/learn-curve-r10-*.md 2>/dev/null | head -1)
[ -z "$ART" ] && ART=$(ls articles/*.md 2>/dev/null | tail -1)

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 seo-agent 子 agent。

任務：
1. 讀取 .agent-growth/seo-agent.md 了解有效 SEO 模式
2. 讀取 $ART（或 articles/ 中最新的文章）
3. 對文章標題提出 3 個 A/B 測試版本，說明每個版本針對什麼關鍵字
4. 在 .agent-growth/seo-agent.md 加入：
   [$(date +%Y-%m-%d)] 優化案例：[原標題] → [最佳版本] | 關鍵字：[主要關鍵字]
5. 輸出：「SEO_DONE: 原標題=[...] 最佳版本=[...] 關鍵字=[...]」
" --allowedTools "Agent,Read,Write" --max-turns 5 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "seo-agent growth 更新驗證" "$C_BEFORE"
echo "    └─ $(echo "$RESULT" | grep "SEO_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-05：reviewer
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-05】reviewer"
hr
GROWTH=".agent-growth/reviewer.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")
ART=$(ls articles/learn-curve-r5-*.md 2>/dev/null | head -1)
[ -z "$ART" ] && ART=$(ls articles/*.md 2>/dev/null | tail -1)

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 reviewer 子 agent。

任務：
1. 讀取 .agent-growth/reviewer.md 了解審查標準
2. 審查 $ART
3. 輸出 APPROVED 或 REJECTED（加 3 條具體理由，引用文章中的句子）
4. 在 .agent-growth/reviewer.md 加入：
   [$(date +%Y-%m-%d)] 審查：[APPROVED/REJECTED] | 文章：[標題] | 關鍵問題：[一句話]
5. 輸出格式最後一行：「REVIEW_RESULT: [APPROVED/REJECTED]」
" --allowedTools "Agent,Read,Bash" --max-turns 5 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "reviewer growth 更新驗證" "$C_BEFORE"
REVIEW=$(echo "$RESULT" | grep "REVIEW_RESULT" | head -1)
if [ -n "$REVIEW" ]; then ok "reviewer 輸出：$REVIEW"; else warn "未見 REVIEW_RESULT"; fi

# ══════════════════════════════════════════════
# AGENT-06：english-writer
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-06】english-writer"
hr
GROWTH=".agent-growth/english-writer.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

RESULT=$(timeout 150 claude -p "
使用 Agent tool 呼叫 english-writer 子 agent。

任務：
1. 讀取 .agent-growth/english-writer.md 了解英文寫作有效模式
2. 讀取 articles/ 中最新的中文文章
3. 產生 Reddit 英文版（600-900字）儲存到 articles/$(date +%Y%m%d)-reddit-en.md
4. 產生 dev.to / Medium 完整版（1000字）儲存到 articles/$(date +%Y%m%d)-medium-en.md
5. 在 .agent-growth/english-writer.md 加入：
   [$(date +%Y-%m-%d)] 英文版產出：Reddit=[字數]字 Medium=[字數]字 | 技巧：[一句話]
6. 輸出：「ENGLISH_DONE: reddit=[路徑] medium=[路徑]」
" --allowedTools "Agent,Read,Write" --max-turns 7 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "english-writer growth 更新驗證" "$C_BEFORE"
echo "    └─ $(echo "$RESULT" | grep "ENGLISH_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-07：chinese-writer
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-07】chinese-writer"
hr
GROWTH=".agent-growth/chinese-writer.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

EN_ART=$(ls articles/*-medium-en.md 2>/dev/null | tail -1)
[ -z "$EN_ART" ] && EN_ART=$(ls articles/*.md 2>/dev/null | tail -1)

RESULT=$(timeout 120 claude -p "
使用 Agent tool 呼叫 chinese-writer 子 agent。

任務：
1. 讀取 .agent-growth/chinese-writer.md 了解中文詮釋技巧
2. 讀取 $EN_ART（英文版文章）
3. 產生中文詮釋版（不是翻譯！用張旭豐的思維重新詮釋）
   儲存到 articles/$(date +%Y%m%d)-chinese-interp.md
4. 在 .agent-growth/chinese-writer.md 加入：
   [$(date +%Y-%m-%d)] 詮釋版：[主題] | 創新點：[和英文版有何不同]
5. 輸出：「CHINESE_DONE: 路徑=[...] 字數=[N]」
" --allowedTools "Agent,Read,Write" --max-turns 6 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "chinese-writer growth 更新驗證" "$C_BEFORE"
echo "    └─ $(echo "$RESULT" | grep "CHINESE_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-08：poster（Reddit + dev.to）
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-08】poster（Reddit + dev.to 雙平台）"
hr
GROWTH=".agent-growth/poster.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")
EN_ART=$(ls articles/*-reddit-en.md 2>/dev/null | tail -1)
[ -z "$EN_ART" ] && EN_ART=$(ls articles/*.md 2>/dev/null | tail -1)

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 poster 子 agent。

任務：
1. 讀取 .agent-growth/poster.md 了解發文策略
2. 讀取 $EN_ART
3. 產生 Reddit 草稿 → logs/reddit-draft-$(date +%Y%m%d)-test.md
4. 產生 dev.to 草稿（含 YAML front matter）→ logs/devto-draft-$(date +%Y%m%d)-test.md
5. 在 .agent-growth/poster.md 加入：
   [$(date +%Y-%m-%d)] 草稿：Reddit=[subreddit] dev.to=[有/無] | 技巧：[一句話]
6. 輸出：「POSTER_DONE: reddit=[路徑] devto=[路徑]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 6 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "poster growth 更新驗證" "$C_BEFORE"
# 驗證 dev.to 草稿
DEVTO=$(ls logs/devto-draft-*.md 2>/dev/null | tail -1)
if [ -n "$DEVTO" ] && grep -q "published:" "$DEVTO" 2>/dev/null; then
  ok "poster dev.to 草稿產出：$DEVTO（含 YAML front matter）"
else
  warn "poster dev.to 草稿未找到或無 YAML"
fi
echo "    └─ $(echo "$RESULT" | grep "POSTER_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-09：feedback-collector
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-09】feedback-collector"
hr
GROWTH=".agent-growth/feedback-collector.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 feedback-collector 子 agent。

任務：
1. 讀取 .agent-growth/feedback-collector.md
2. 讀取 logs/progress.json，找出最近一篇文章的標題
3. 嘗試用 WebFetch 搜尋該文章在 Reddit 的成效
   （Reddit 可能被封，如果失敗記錄原因並使用模擬數據：upvotes=12, comments=4）
4. 儲存到 logs/feedback-test-$(date +%Y%m%d).json
5. 在 .agent-growth/feedback-collector.md 加入：
   [$(date +%Y-%m-%d)] 收集：[成功/失敗原因] | 結果：upvotes=[N] comments=[N]
6. 輸出：「FEEDBACK_DONE: upvotes=[N] comments=[N] source=[real/simulated]」
" --allowedTools "Agent,Read,Write,WebFetch,Bash" --max-turns 5 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "feedback-collector growth 更新驗證" "$C_BEFORE"
FBFILE=$(ls logs/feedback-test-*.json 2>/dev/null | tail -1)
if [ -n "$FBFILE" ]; then ok "feedback-collector JSON 已產出：$FBFILE"; else fail "feedback-collector 無 JSON 輸出"; fi
echo "    └─ $(echo "$RESULT" | grep "FEEDBACK_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-10：style-updater
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-10】style-updater"
hr
GROWTH=".agent-growth/style-updater.md"
SKILL=".claude/skills/writing-style.md"
H_BEFORE_G=$(snapshot "$GROWTH"); C_BEFORE_G=$(snapshot_content "$GROWTH")
H_BEFORE_S=$(snapshot "$SKILL"); C_BEFORE_S=$(snapshot_content "$SKILL")

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 style-updater 子 agent。

任務：
1. 讀取 .agent-growth/style-updater.md
2. 讀取 logs/feedback-test-$(date +%Y%m%d).json（若存在）
3. 根據回饋分析，在 .claude/skills/writing-style.md 末尾加入：
   ## 自動更新 $(date +%Y-%m-%d)
   - 根據本輪測試調整：[具體說明]
4. 在 .agent-growth/style-updater.md 加入更新記錄
5. 輸出：「STYLE_DONE: skill_updated=[yes/no] pattern=[學到什麼]」
" --allowedTools "Agent,Read,Write" --max-turns 5 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE_G" "style-updater growth 更新驗證" "$C_BEFORE_G"
verify_file_changed "$SKILL"  "$H_BEFORE_S" "writing-style.md 技能更新驗證" "$C_BEFORE_S"
echo "    └─ $(echo "$RESULT" | grep "STYLE_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-11：knowledge-subagent
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-11】knowledge-subagent"
hr
GROWTH=".agent-growth/knowledge-subagent.md"
LESSONS=".knowledge/lessons.md"
H_BEFORE_G=$(snapshot "$GROWTH"); C_BEFORE_G=$(snapshot_content "$GROWTH")
H_BEFORE_L=$(snapshot "$LESSONS"); C_BEFORE_L=$(snapshot_content "$LESSONS")

RESULT=$(timeout 90 claude -p "
使用 Agent tool 呼叫 knowledge-subagent 子 agent。

任務：
1. 讀取 .agent-growth/knowledge-subagent.md
2. 讀取所有 logs/feedback-test-*.json（若存在）
3. 讀取 .agent-growth/writer.md 中的學習記錄
4. 將本輪測試的知識摘要寫入 .knowledge/lessons.md（append 不覆蓋）：
   ## 個別測試知識更新 $(date +%Y-%m-%d)
   - writer 學習曲線：[摘要]
   - reviewer 審查模式：[摘要]
   - 系統整體觀察：[一句話]
5. 在 .agent-growth/knowledge-subagent.md 加入更新記錄
6. 輸出：「KNOWLEDGE_DONE: lessons_updated=[yes] lines_added=[N]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 5 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE_G" "knowledge-subagent growth 更新驗證" "$C_BEFORE_G"
verify_file_changed "$LESSONS" "$H_BEFORE_L" "lessons.md 知識庫更新驗證" "$C_BEFORE_L"
echo "    └─ $(echo "$RESULT" | grep "KNOWLEDGE_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-12：revenue-scout
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-12】revenue-scout"
hr
GROWTH=".agent-growth/revenue-scout.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

RESULT=$(timeout 120 claude -p "
使用 Agent tool 呼叫 revenue-scout 子 agent。

任務：
1. 讀取 .agent-growth/revenue-scout.md
2. 分析目前的 OKR（.team-memory/okr-tracking.md）和收益狀況
3. 提出 2-3 個具體的賺錢機會（基於已有的文章和知識）
4. 將提案寫入 .team-memory/proposals.md（append）：
   ## 提案-$(date +%Y%m%d)-[標題]
   提案者：revenue-scout
   預估月收：$X
5. 在 .agent-growth/revenue-scout.md 加入：
   [$(date +%Y-%m-%d)] 掃描：提出[N]個提案 | 最高潛力：[主題]
6. 輸出：「SCOUT_DONE: proposals=[N] top_opportunity=[...]」
" --allowedTools "Agent,Read,Write,WebFetch,Bash" --max-turns 6 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "revenue-scout growth 更新驗證" "$C_BEFORE"
echo "    └─ $(echo "$RESULT" | grep "SCOUT_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-13：product-builder
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-13】product-builder"
hr
GROWTH=".agent-growth/product-builder.md"
H_BEFORE=$(snapshot "$GROWTH"); C_BEFORE=$(snapshot_content "$GROWTH")

RESULT=$(timeout 150 claude -p "
使用 Agent tool 呼叫 product-builder 子 agent。

任務：
1. 讀取 .agent-growth/product-builder.md
2. 選擇最熱門的文章（articles/ 中 learn-curve-r1 或 r5）
3. 基於該文章，產生 Whop 產品大綱（不是完整產品，只是 outline）：
   - 標題
   - 售價建議（$9/$19/$5/月）
   - 包含內容清單（5-8 項）
   - 目標受眾說明
   儲存到 logs/product-outline-$(date +%Y%m%d).md
4. 在 .agent-growth/product-builder.md 加入：
   [$(date +%Y-%m-%d)] 產品大綱：[主題] 定價=$[N] | 品質評估：[簡短說明]
5. 輸出：「PRODUCT_DONE: outline=[路徑] price=$[N]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 6 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE" "product-builder growth 更新驗證" "$C_BEFORE"
OUTLINE=$(ls logs/product-outline-*.md 2>/dev/null | tail -1)
if [ -n "$OUTLINE" ]; then ok "product-builder outline 產出：$OUTLINE"; else warn "product-builder 無 outline 輸出"; fi
echo "    └─ $(echo "$RESULT" | grep "PRODUCT_DONE" | head -1)"

# ══════════════════════════════════════════════
# AGENT-14：chief-of-staff（整合驗證）
# ══════════════════════════════════════════════
echo ""; echo "【AGENT-14】chief-of-staff（整合整個測試週期）"
hr
GROWTH=".agent-growth/chief-of-staff.md"
RETRO=".team-memory/weekly-retrospective.md"
H_BEFORE_G=$(snapshot "$GROWTH"); C_BEFORE_G=$(snapshot_content "$GROWTH")
H_BEFORE_R=$(snapshot "$RETRO"); C_BEFORE_R=$(snapshot_content "$RETRO")

RESULT=$(timeout 150 claude -p "
使用 Agent tool 呼叫 chief-of-staff 子 agent。

任務（個別測試總結）：
1. 讀取所有 .agent-growth/*.md 檔案（14個）
2. 確認每個 agent 的成長記錄有 $(date +%Y-%m-%d) 的更新
3. 統計：有多少 agent 今日有更新成長記錄
4. 在 .team-memory/weekly-retrospective.md 加入：
   ## 個別測試總結 $(date +%Y-%m-%d %H:%M)
   - 測試 agent 數：14
   - 有更新成長記錄：[N] 個
   - 無更新：[列出 agent 名稱]
   - 整體評估：[一段話]
5. 在 .agent-growth/chief-of-staff.md 加入紀錄
6. 發送 Telegram：bash .claude/hooks/telegram-notify.sh '📋 個別測試完成：[N]/14 個 agent 成長記錄更新'
7. 輸出：「COS_DONE: updated=[N]/14 missing=[列表]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 8 2>/dev/null)

verify_file_changed "$GROWTH" "$H_BEFORE_G" "chief-of-staff growth 更新驗證" "$C_BEFORE_G"
verify_file_changed "$RETRO" "$H_BEFORE_R" "retrospective 測試總結更新驗證" "$C_BEFORE_R"
echo "    └─ $(echo "$RESULT" | grep "COS_DONE" | head -1)"

# ══════════════════════════════════════════════
# 最終統計：所有 growth file 實際行數
# ══════════════════════════════════════════════
echo ""; hr
echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   測試結果 + Growth File 真實狀態              ║"
echo "╚════════════════════════════════════════════════╝"
echo "完成：$(date)"
echo ""
echo "  ✅ $PASS  ❌ $FAIL  ⚠️  $WARN"
echo ""
echo "── Agent Growth File 實際行數（不是幻覺，是真實檔案）──"
TODAY=$(date +%Y-%m-%d)
for agent in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
  f=".agent-growth/$agent.md"
  if [ -f "$f" ]; then
    LINES=$(wc -l < "$f")
    TODAY_UPDATES=$(grep -c "\[$TODAY\]" "$f" 2>/dev/null || echo 0)
    if [ "$TODAY_UPDATES" -gt 0 ]; then
      echo "  ✅ $agent: ${LINES}行（今日更新 $TODAY_UPDATES 條）"
    else
      echo "  ⚠️  $agent: ${LINES}行（今日無更新）"
    fi
  else
    echo "  ❌ $agent: 檔案不存在"
  fi
done

echo ""
echo "── 今日產出的檔案 ──"
echo "文章：$(ls articles/learn-curve-*.md articles/*-en.md articles/*-chinese*.md 2>/dev/null | wc -l) 個"
echo "Reddit 草稿：$(ls logs/reddit-draft-*.md 2>/dev/null | wc -l) 個"
echo "dev.to 草稿：$(ls logs/devto-draft-*.md 2>/dev/null | wc -l) 個"
echo "Feedback JSON：$(ls logs/feedback-test-*.json 2>/dev/null | wc -l) 個"
echo "Product outline：$(ls logs/product-outline-*.md 2>/dev/null | wc -l) 個"

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "  🎉 所有 14 個 agent 個別測試通過，經驗堆積已驗證（file diff 確認）"
  bash .claude/hooks/telegram-notify.sh "🎉 個別測試完成 $PASS✅ $FAIL❌ $WARN⚠️ | Writer 10輪完成 | 所有 agent 有 file diff 驗證" 2>/dev/null || true
else
  echo "  ⚠️  $FAIL 個失敗需修復"
  bash .claude/hooks/telegram-notify.sh "⚠️ 個別測試：$PASS✅ $FAIL❌ | 需要修復" 2>/dev/null || true
fi
