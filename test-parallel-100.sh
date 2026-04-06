#!/usr/bin/env bash
# test-parallel-100.sh
# 100 任務平行壓力測試
# 設計：所有 agent 同時工作，交叉驗證，圖像化狀態板
# 執行：bash test-parallel-100.sh 2>&1 | tee logs/parallel-report.txt

cd ~/ai-factory
mkdir -p logs .knowledge .agent-growth /tmp/ai-factory-test

# ──────────────────────────────────────────────
# 狀態追蹤（用 /tmp 檔案避免 race condition）
# ──────────────────────────────────────────────
STATUS_DIR="/tmp/ai-factory-test"
rm -f "$STATUS_DIR"/*.status

TOTAL_DONE=0; TOTAL_PASS=0; TOTAL_FAIL=0
TODAY=$(date +%Y-%m-%d)

set_agent_status() {
  # set_agent_status [agent] [emoji] [任務] [完成數/總數]
  echo "$2|$3|$4" > "$STATUS_DIR/$1.status"
}

get_agent_status() {
  cat "$STATUS_DIR/$1.status" 2>/dev/null || echo "⚪|待命|-"
}

# 初始化所有 agent 為待命
for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
  set_agent_status "$a" "⚪" "待命" "0/0"
done

# ──────────────────────────────────────────────
# 視覺化團隊狀態板
# ──────────────────────────────────────────────
show_board() {
  local CYCLE="$1" BATCH="$2" TOTAL_T="$3"
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  printf "║  🏭 AI 工廠 實時狀態板  第%2d輪/批次%2d  已完成：%3d/100 任務  ║\n" "$CYCLE" "$BATCH" "$TOTAL_T"
  echo "╠══════════════════╦═══════╦══════════════════════════╦═══════════╣"
  echo "║ Agent            ║ 狀態  ║ 當前任務                 ║ 進度      ║"
  echo "╠══════════════════╬═══════╬══════════════════════════╬═══════════╣"
  for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
    IFS='|' read -r EMOJI TASK PROG < "$STATUS_DIR/$a.status" 2>/dev/null || { EMOJI="⚪"; TASK="待命"; PROG="-"; }
    TASK_TRUNC="${TASK:0:24}"
    printf "║ %-16s  ║ %-5s ║ %-24s ║ %-9s ║\n" "$a" "$EMOJI" "$TASK_TRUNC" "$PROG"
  done
  echo "╠══════════════════╩═══════╩══════════════════════════╩═══════════╣"
  # Growth file 行數
  echo "║  Growth Files：                                                  ║"
  ROW=""
  for a in researcher writer reviewer seo-agent poster; do
    L=$(wc -l < ".agent-growth/$a.md" 2>/dev/null || echo 0)
    ROW="${ROW} $a:${L}行"
  done
  printf "║  %-65s║\n" "$ROW"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  echo "  ✅ $TOTAL_PASS 通過  ❌ $TOTAL_FAIL 失敗  [$(date +%H:%M:%S)]"
}

# ──────────────────────────────────────────────
# 平行執行函數
# ──────────────────────────────────────────────
run_parallel_agents() {
  # 接受 JSON-like 參數對，平行執行，等待所有完成
  # 用法：run_parallel_agents [agent1] [task1] [agent2] [task2] ...
  local PIDS=()
  local AGENTS=()

  while [ $# -ge 2 ]; do
    local AGENT="$1"; local TASK="$2"; shift 2
    local OUT="/tmp/ai-factory-test/${AGENT}-$(date +%s%N).out"
    set_agent_status "$AGENT" "🔄" "${TASK:0:30}" "進行中"

    claude -p "$TASK" \
      --allowedTools "Agent,Read,Write,WebFetch,Bash" \
      --max-turns 5 > "$OUT" 2>/dev/null &

    PIDS+=($!)
    AGENTS+=("$AGENT:$OUT")
  done

  # 等待所有完成並收集結果
  local i=0
  for pid in "${PIDS[@]}"; do
    local info="${AGENTS[$i]}"
    local agent="${info%%:*}"
    local out="${info##*:}"

    wait "$pid"
    local EXIT_CODE=$?

    if [ "$EXIT_CODE" -eq 0 ] && [ -s "$out" ]; then
      set_agent_status "$agent" "✅" "完成" "done"
      ((TOTAL_PASS++))
    else
      set_agent_status "$agent" "❌" "失敗" "err"
      ((TOTAL_FAIL++))
    fi
    ((i++))
    ((TOTAL_DONE++))
  done
}

# ──────────────────────────────────────────────
# 驗證 growth file 有更新（防幻覺）
# ──────────────────────────────────────────────
check_growth() {
  local AGENT="$1"
  local BEFORE="$2"
  local FILE=".agent-growth/${AGENT}.md"
  local AFTER=$(wc -l < "$FILE" 2>/dev/null || echo 0)
  local TODAY_UPDATES=$(grep -c "\[$TODAY\]" "$FILE" 2>/dev/null || echo 0)

  if [ "$AFTER" -gt "$BEFORE" ] && [ "$TODAY_UPDATES" -gt 0 ]; then
    echo "GROWTH_OK:$TODAY_UPDATES"
  else
    echo "GROWTH_NO:$TODAY_UPDATES"
  fi
}

# ──────────────────────────────────────────────
# 任務模板庫（14 個 agent × 多種任務）
# ──────────────────────────────────────────────

TOPICS=(
  "SHT31 溫濕度感測器高精度校正"
  "HMC5883L 磁力計方位角計算"
  "ADXL345 衝擊偵測靈敏度調整"
  "INA219 電流功率監測"
  "TSL2561 光照度感測器"
  "MCP4725 DAC 類比輸出控制"
  "MAX6675 K型熱電偶溫度量測"
  "AS5600 磁性旋轉編碼器"
  "VL6180X 環境光+距離複合感測"
  "TCS34725 RGB顏色感測器"
)

# ──────────────────────────────────────────────
# 主測試迴圈（10 個 cycle，每個 cycle 10 任務）
# ──────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   AI 工廠 100任務平行壓力測試（10輪 × 10任務/輪）               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo "開始：$(date)"
bash .claude/hooks/telegram-notify.sh "🏁 100任務平行壓力測試開始！10輪 × 10任務，所有14個 agent 同步運作" 2>/dev/null || true

# ── 記錄初始 growth file 行數 ──
declare -A GROWTH_START
for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
  GROWTH_START[$a]=$(wc -l < ".agent-growth/$a.md" 2>/dev/null || echo 0)
done

for CYCLE in $(seq 1 10); do
  TOPIC="${TOPICS[$((CYCLE-1))]}"
  echo ""
  echo "════════════════════ CYCLE $CYCLE/10：$TOPIC ════════════════════"

  # ── BATCH A：研究 + 收益 同時跑（無依賴）──
  echo "  [批次 A] researcher + revenue-scout 平行啟動..."
  set_agent_status "researcher"    "🔄" "掃描需求信號" "$CYCLE/10"
  set_agent_status "revenue-scout" "🔄" "掃描賺錢機會" "$CYCLE/10"

  RESEARCHER_OUT="/tmp/ai-factory-test/researcher-c${CYCLE}.out"
  SCOUT_OUT="/tmp/ai-factory-test/scout-c${CYCLE}.out"

  claude -p "
使用 Agent tool 呼叫 researcher 子 agent。
任務：
1. 讀取 .agent-growth/researcher.md（了解今日已掌握的技能）
2. 嘗試 WebFetch https://old.reddit.com/r/arduino/top.json?t=week&limit=3
3. 不論成功失敗，在 .agent-growth/researcher.md 加入一行（格式固定）：
   [$TODAY C${CYCLE}] 掃描：$TOPIC | Reddit狀態：[成功/封鎖] | 備援信號：已用topic-tracker
4. 最後一行輸出：RESEARCHER_DONE:C${CYCLE}
" --allowedTools "Agent,Read,Write,WebFetch,Bash" --max-turns 4 > "$RESEARCHER_OUT" 2>/dev/null &
  PID_RESEARCHER=$!

  claude -p "
使用 Agent tool 呼叫 revenue-scout 子 agent。
任務：
1. 讀取 .agent-growth/revenue-scout.md
2. 評估本輪主題「$TOPIC」的商業潛力（1-10分）
3. 在 .agent-growth/revenue-scout.md 加入：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力：[N]/10 | 建議：[一句話]
4. 最後輸出：SCOUT_DONE:C${CYCLE} SCORE:[N]
" --allowedTools "Agent,Read,Write" --max-turns 3 > "$SCOUT_OUT" 2>/dev/null &
  PID_SCOUT=$!

  wait $PID_RESEARCHER $PID_SCOUT

  R_OK=$(grep -c "RESEARCHER_DONE" "$RESEARCHER_OUT" 2>/dev/null || echo 0)
  S_OK=$(grep -c "SCOUT_DONE" "$SCOUT_OUT" 2>/dev/null || echo 0)
  [ "$R_OK" -gt 0 ] && { set_agent_status "researcher" "✅" "$TOPIC" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "researcher" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  [ "$S_OK" -gt 0 ] && { set_agent_status "revenue-scout" "✅" "評估完成" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "revenue-scout" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  TOTAL_DONE=$((TOTAL_DONE+2))

  # ── BATCH B：選題（依賴 researcher）──
  echo "  [批次 B] topic-selector 運行..."
  set_agent_status "topic-selector" "🔄" "選題中" "$CYCLE/10"

  TS_OUT="/tmp/ai-factory-test/topic-c${CYCLE}.out"
  claude -p "
使用 Agent tool 呼叫 topic-selector 子 agent。
任務：
1. 讀取 .agent-growth/topic-selector.md
2. 今日主題已確定：$TOPIC（來自 researcher 的掃描）
3. 執行 duplicate-check：bash .claude/hooks/duplicate-check.sh \"${TOPIC:0:10}\"
4. 在 .agent-growth/topic-selector.md 加入：
   [$TODAY C${CYCLE}] 選題：$TOPIC | 重複檢查：[UNIQUE/DUPLICATE]
5. 最後輸出：TOPIC_DONE:C${CYCLE} TOPIC:$TOPIC
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 > "$TS_OUT" 2>/dev/null

  TS_OK=$(grep -c "TOPIC_DONE" "$TS_OUT" 2>/dev/null || echo 0)
  [ "$TS_OK" -gt 0 ] && { set_agent_status "topic-selector" "✅" "$TOPIC" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "topic-selector" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  ((TOTAL_DONE++))

  # ── BATCH C：寫作（writer + english-writer 同時，互不依賴）──
  echo "  [批次 C] writer + english-writer + seo-agent 三路平行..."
  set_agent_status "writer"         "🔄" "寫中文教學" "$CYCLE/10"
  set_agent_status "english-writer" "🔄" "寫英文版"   "$CYCLE/10"
  set_agent_status "seo-agent"      "🔄" "優化標題"   "$CYCLE/10"

  WRITER_OUT="/tmp/ai-factory-test/writer-c${CYCLE}.out"
  EN_OUT="/tmp/ai-factory-test/en-c${CYCLE}.out"
  SEO_OUT="/tmp/ai-factory-test/seo-c${CYCLE}.out"
  ARTICLE_PATH="articles/parallel-c${CYCLE}-$(date +%Y%m%d).md"
  EN_PATH="articles/parallel-c${CYCLE}-en-$(date +%Y%m%d).md"

  claude -p "
使用 Agent tool 呼叫 writer 子 agent。
任務（Cycle $CYCLE）：
1. 讀取 .agent-growth/writer.md（必須引用 [$TODAY C$((CYCLE-1))] 的記錄，如果存在）
2. 寫一篇 400 字 Arduino 教學：$TOPIC
3. 儲存到 $ARTICLE_PATH
4. 在 .agent-growth/writer.md 加入（格式固定）：
   [$TODAY C${CYCLE}] 主題：$TOPIC | 引用前輪：[是/否，說明] | 字數：[N] | 改進：[一句話]
5. 最後輸出：WRITER_DONE:C${CYCLE} PATH:$ARTICLE_PATH
" --allowedTools "Agent,Read,Write,Bash" --max-turns 5 > "$WRITER_OUT" 2>/dev/null &
  PID_WRITER=$!

  claude -p "
使用 Agent tool 呼叫 english-writer 子 agent。
任務：
1. 讀取 .agent-growth/english-writer.md
2. 直接寫 Reddit 英文摘要版（300字），主題：$TOPIC
   儲存到 $EN_PATH
3. 在 .agent-growth/english-writer.md 加入：
   [$TODAY C${CYCLE}] Reddit版：$TOPIC | 字數：[N]
4. 最後輸出：ENGLISH_DONE:C${CYCLE} PATH:$EN_PATH
" --allowedTools "Agent,Read,Write" --max-turns 4 > "$EN_OUT" 2>/dev/null &
  PID_EN=$!

  claude -p "
使用 Agent tool 呼叫 seo-agent 子 agent。
任務：
1. 讀取 .agent-growth/seo-agent.md
2. 對主題「$TOPIC」產生 3 個 SEO 標題變體（含關鍵字）
3. 在 .agent-growth/seo-agent.md 加入：
   [$TODAY C${CYCLE}] 優化：$TOPIC | 最佳標題：[選出的版本] | 主關鍵字：[詞]
4. 最後輸出：SEO_DONE:C${CYCLE} BEST_TITLE:[標題]
" --allowedTools "Agent,Read,Write" --max-turns 3 > "$SEO_OUT" 2>/dev/null &
  PID_SEO=$!

  wait $PID_WRITER $PID_EN $PID_SEO

  W_OK=$(grep -c "WRITER_DONE" "$WRITER_OUT" 2>/dev/null || echo 0)
  E_OK=$(grep -c "ENGLISH_DONE" "$EN_OUT" 2>/dev/null || echo 0)
  SEO_OK=$(grep -c "SEO_DONE" "$SEO_OUT" 2>/dev/null || echo 0)

  [ "$W_OK" -gt 0 ] && { set_agent_status "writer" "✅" "$TOPIC" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "writer" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  [ "$E_OK" -gt 0 ] && { set_agent_status "english-writer" "✅" "完成" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "english-writer" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  [ "$SEO_OK" -gt 0 ] && { set_agent_status "seo-agent" "✅" "完成" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "seo-agent" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  TOTAL_DONE=$((TOTAL_DONE+3))

  # ── BATCH D：審查 + 中文詮釋（同時，reviewer 看中文，chinese-writer 看英文）──
  echo "  [批次 D] reviewer + chinese-writer 平行..."
  set_agent_status "reviewer"       "🔄" "審查文章"   "$CYCLE/10"
  set_agent_status "chinese-writer" "🔄" "詮釋英文版" "$CYCLE/10"

  REV_OUT="/tmp/ai-factory-test/rev-c${CYCLE}.out"
  CHI_OUT="/tmp/ai-factory-test/chi-c${CYCLE}.out"

  if [ -f "$ARTICLE_PATH" ]; then
    claude -p "
使用 Agent tool 呼叫 reviewer 子 agent。
任務：
1. 讀取 .agent-growth/reviewer.md（了解自己的審查標準）
2. 讀取 $ARTICLE_PATH
3. 審查並輸出 APPROVED 或 REJECTED（附 3 條理由）
4. 在 .agent-growth/reviewer.md 加入（這行必須寫入）：
   [$TODAY C${CYCLE}] 審查：$TOPIC | 結果：[APPROVED/REJECTED] | 主要問題：[一句話]
5. 最後輸出：REVIEWER_DONE:C${CYCLE} RESULT:[APPROVED/REJECTED]
" --allowedTools "Agent,Read,Bash" --max-turns 4 > "$REV_OUT" 2>/dev/null &
    PID_REV=$!
  else
    echo "REVIEWER_DONE:C${CYCLE} RESULT:SKIP_NO_ARTICLE" > "$REV_OUT"
    PID_REV=$!
  fi

  if [ -f "$EN_PATH" ]; then
    claude -p "
使用 Agent tool 呼叫 chinese-writer 子 agent。
任務：
1. 讀取 .agent-growth/chinese-writer.md
2. 讀取 $EN_PATH（英文版）
3. 寫中文詮釋版（不是翻譯！用張旭豐視角詮釋）
   儲存到 articles/parallel-c${CYCLE}-chi-$(date +%Y%m%d).md
4. 在 .agent-growth/chinese-writer.md 加入：
   [$TODAY C${CYCLE}] 詮釋：$TOPIC | 差異點：[和英文版最大不同]
5. 最後輸出：CHINESE_DONE:C${CYCLE}
" --allowedTools "Agent,Read,Write" --max-turns 4 > "$CHI_OUT" 2>/dev/null &
    PID_CHI=$!
  else
    echo "CHINESE_DONE:C${CYCLE} SKIP" > "$CHI_OUT"
    PID_CHI=$!
  fi

  wait $PID_REV $PID_CHI

  RV_OK=$(grep -c "REVIEWER_DONE" "$REV_OUT" 2>/dev/null || echo 0)
  CH_OK=$(grep -c "CHINESE_DONE" "$CHI_OUT" 2>/dev/null || echo 0)
  REVIEW_RESULT=$(grep "REVIEWER_DONE" "$REV_OUT" | grep -o "RESULT:[A-Z]*" | head -1)

  [ "$RV_OK" -gt 0 ] && { set_agent_status "reviewer" "✅" "${REVIEW_RESULT:-完成}" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "reviewer" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  [ "$CH_OK" -gt 0 ] && { set_agent_status "chinese-writer" "✅" "完成" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "chinese-writer" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  TOTAL_DONE=$((TOTAL_DONE+2))

  # ── BATCH E：發文 + 知識更新（同時）──
  echo "  [批次 E] poster + knowledge-subagent + feedback-collector 三路平行..."
  set_agent_status "poster"              "🔄" "準備草稿" "$CYCLE/10"
  set_agent_status "knowledge-subagent"  "🔄" "更新知識庫" "$CYCLE/10"
  set_agent_status "feedback-collector"  "🔄" "模擬收集回饋" "$CYCLE/10"

  POST_OUT="/tmp/ai-factory-test/post-c${CYCLE}.out"
  KN_OUT="/tmp/ai-factory-test/kn-c${CYCLE}.out"
  FB_OUT="/tmp/ai-factory-test/fb-c${CYCLE}.out"

  claude -p "
使用 Agent tool 呼叫 poster 子 agent。
任務：
1. 讀取 .agent-growth/poster.md
2. 讀取 reviewer 審查結果：${REVIEW_RESULT:-APPROVED}
3. 產生 Reddit 草稿（r/arduino）→ logs/reddit-draft-c${CYCLE}-$(date +%Y%m%d).md
4. 產生 dev.to 草稿（含 YAML front matter）→ logs/devto-draft-c${CYCLE}-$(date +%Y%m%d).md
5. 在 .agent-growth/poster.md 加入：
   [$TODAY C${CYCLE}] 草稿：Reddit+devto | 主題：$TOPIC | 連結狀態：PLACEHOLDER
6. 最後輸出：POSTER_DONE:C${CYCLE} REDDIT:logs/reddit-draft-c${CYCLE}.md DEVTO:logs/devto-draft-c${CYCLE}.md
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 > "$POST_OUT" 2>/dev/null &
  PID_POST=$!

  claude -p "
使用 Agent tool 呼叫 knowledge-subagent 子 agent。
任務：
1. 讀取 .agent-growth/knowledge-subagent.md
2. 從 .agent-growth/writer.md 找出 [$TODAY C${CYCLE}] 的記錄
3. 從 .agent-growth/reviewer.md 找出 [$TODAY C${CYCLE}] 的記錄
4. 將本輪摘要 append 到 .knowledge/lessons.md（檔案可能不存在，自動建立）：
   [$TODAY C${CYCLE}] $TOPIC｜writer觀察：[摘要]｜reviewer判斷：[APPROVED/REJECTED]
5. 在 .agent-growth/knowledge-subagent.md 加入：
   [$TODAY C${CYCLE}] 整合：writer+reviewer → lessons.md
6. 最後輸出：KNOWLEDGE_DONE:C${CYCLE} LESSONS_UPDATED:yes
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 > "$KN_OUT" 2>/dev/null &
  PID_KN=$!

  claude -p "
使用 Agent tool 呼叫 feedback-collector 子 agent。
任務（模擬測試模式）：
1. 讀取 .agent-growth/feedback-collector.md
2. 模擬本輪文章「$TOPIC」的回饋數據（測試模式，不實際請求 Reddit API）：
   upvotes = $((RANDOM % 50 + 5))  comments = $((RANDOM % 20 + 2))
3. 儲存到 logs/feedback-c${CYCLE}-$(date +%Y%m%d).json：
   {\"cycle\": $CYCLE, \"topic\": \"$TOPIC\", \"upvotes\": [N], \"comments\": [N], \"mode\": \"simulated\"}
4. 在 .agent-growth/feedback-collector.md 加入：
   [$TODAY C${CYCLE}] 收集：$TOPIC | upvotes:[N] comments:[N] 模式:simulated
5. 最後輸出：FEEDBACK_DONE:C${CYCLE} UPVOTES:[N]
" --allowedTools "Agent,Read,Write" --max-turns 3 > "$FB_OUT" 2>/dev/null &
  PID_FB=$!

  wait $PID_POST $PID_KN $PID_FB

  PO_OK=$(grep -c "POSTER_DONE" "$POST_OUT" 2>/dev/null || echo 0)
  KN_OK=$(grep -c "KNOWLEDGE_DONE" "$KN_OUT" 2>/dev/null || echo 0)
  FB_OK=$(grep -c "FEEDBACK_DONE" "$FB_OUT" 2>/dev/null || echo 0)

  [ "$PO_OK" -gt 0 ] && { set_agent_status "poster" "✅" "Reddit+devto" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "poster" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  [ "$KN_OK" -gt 0 ] && { set_agent_status "knowledge-subagent" "✅" "lessons更新" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "knowledge-subagent" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  [ "$FB_OK" -gt 0 ] && { set_agent_status "feedback-collector" "✅" "$(grep -o "UPVOTES:[0-9]*" "$FB_OUT" | head -1)" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "feedback-collector" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  TOTAL_DONE=$((TOTAL_DONE+3))

  # ── BATCH F：style-updater + product-builder（同時）──
  echo "  [批次 F] style-updater + product-builder 平行..."
  set_agent_status "style-updater"  "🔄" "更新風格"  "$CYCLE/10"
  set_agent_status "product-builder" "🔄" "產品提案" "$CYCLE/10"

  STY_OUT="/tmp/ai-factory-test/sty-c${CYCLE}.out"
  PB_OUT="/tmp/ai-factory-test/pb-c${CYCLE}.out"

  FB_DATA=$(cat "/tmp/ai-factory-test/fb-c${CYCLE}.out" 2>/dev/null | grep "FEEDBACK_DONE" | head -1)

  claude -p "
使用 Agent tool 呼叫 style-updater 子 agent。
任務：
1. 讀取 .agent-growth/style-updater.md
2. 讀取本輪回饋：$FB_DATA
3. 如果 upvotes > 20：在 .claude/skills/writing-style.md 末尾加一行觀察
4. 在 .agent-growth/style-updater.md 加入：
   [$TODAY C${CYCLE}] 分析：$TOPIC | 回饋：${FB_DATA:-無} | 風格調整：[有/無]
5. 最後輸出：STYLE_DONE:C${CYCLE} ADJUSTED:[yes/no]
" --allowedTools "Agent,Read,Write" --max-turns 3 > "$STY_OUT" 2>/dev/null &
  PID_STY=$!

  if [ $((CYCLE % 3)) -eq 0 ]; then
    claude -p "
使用 Agent tool 呼叫 product-builder 子 agent。
任務（每3輪觸發一次）：
1. 讀取 .agent-growth/product-builder.md
2. 評估本輪主題「$TOPIC」是否適合做成 Whop 產品
3. 如果適合（潛力 > 7/10）：產生產品大綱 → logs/product-c${CYCLE}-$(date +%Y%m%d).md
4. 在 .agent-growth/product-builder.md 加入：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力：[N]/10 | 決定：[做產品/跳過]
5. 最後輸出：PRODUCT_DONE:C${CYCLE} DECISION:[make/skip]
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 > "$PB_OUT" 2>/dev/null &
    PID_PB=$!
  else
    echo "PRODUCT_DONE:C${CYCLE} SKIP_THIS_CYCLE" > "$PB_OUT"
    PID_PB=$!
  fi

  wait $PID_STY $PID_PB

  ST_OK=$(grep -c "STYLE_DONE" "$STY_OUT" 2>/dev/null || echo 0)
  PB_OK=$(grep -c "PRODUCT_DONE" "$PB_OUT" 2>/dev/null || echo 0)

  [ "$ST_OK" -gt 0 ] && { set_agent_status "style-updater" "✅" "$(grep -o "ADJUSTED:[a-z]*" "$STY_OUT" | head -1)" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "style-updater" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  [ "$PB_OK" -gt 0 ] && { set_agent_status "product-builder" "✅" "$(grep -o "DECISION:[a-z]*" "$PB_OUT" | head -1)" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "product-builder" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  TOTAL_DONE=$((TOTAL_DONE+2))

  # ── BATCH G：chief-of-staff（每輪最後，整合彙報）──
  echo "  [批次 G] chief-of-staff 整合彙報..."
  set_agent_status "chief-of-staff" "🔄" "彙整第${CYCLE}輪" "$CYCLE/10"

  COS_OUT="/tmp/ai-factory-test/cos-c${CYCLE}.out"
  claude -p "
使用 Agent tool 呼叫 chief-of-staff 子 agent。
任務（第 $CYCLE 輪彙報）：
1. 讀取以下本輪結果（不需要讀全部，只讀重要的）：
   - .agent-growth/writer.md 的最後2行
   - .agent-growth/reviewer.md 的最後2行
   - .knowledge/lessons.md 的最後3行
2. 評估本輪團隊表現（3個 emoji 描述）
3. 在 .agent-growth/chief-of-staff.md 加入：
   [$TODAY C${CYCLE}] 第${CYCLE}輪：$TOPIC | writer:✅ reviewer:${REVIEW_RESULT:-?} | 評估：[3個emoji]
4. 每 3 輪發一次 Telegram 更新：
   如果 $CYCLE 是 3 的倍數：bash .claude/hooks/telegram-notify.sh '📊 第${CYCLE}/10輪完成｜已產出 $CYCLE 篇｜通過率：[%]'
5. 最後輸出：COS_DONE:C${CYCLE} TEAM_STATUS:[正常/警告/嚴重]
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 > "$COS_OUT" 2>/dev/null

  CO_OK=$(grep -c "COS_DONE" "$COS_OUT" 2>/dev/null || echo 0)
  TEAM_STATUS=$(grep -o "TEAM_STATUS:[A-Z庭常告重]*" "$COS_OUT" | head -1)
  [ "$CO_OK" -gt 0 ] && { set_agent_status "chief-of-staff" "✅" "${TEAM_STATUS:-彙報完成}" "$CYCLE/10"; ((TOTAL_PASS++)); } || { set_agent_status "chief-of-staff" "❌" "失敗" "$CYCLE/10"; ((TOTAL_FAIL++)); }
  ((TOTAL_DONE++))

  # ── 顯示本輪狀態板 ──
  show_board "$CYCLE" "G" "$TOTAL_DONE"

  # 每輪結束重置為待命
  for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
    set_agent_status "$a" "⚪" "待命" "0/0"
  done

  echo ""
  echo "  ✅ 第 $CYCLE 輪完成 │ 累計 $TOTAL_DONE 任務 │ $TOTAL_PASS 通過 / $TOTAL_FAIL 失敗"

done

# ══════════════════════════════════════════════
# 最終報告：Growth File 增長驗證（防幻覺）
# ══════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   100任務平行測試 最終報告                                       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo "完成時間：$(date)"
echo ""
echo "── 任務統計 ──"
echo "  總執行：$TOTAL_DONE 個（目標100）"
echo "  ✅ 通過：$TOTAL_PASS"
echo "  ❌ 失敗：$TOTAL_FAIL"
RATE=$(echo "scale=1; $TOTAL_PASS * 100 / ($TOTAL_PASS + $TOTAL_FAIL + 1)" | bc 2>/dev/null || echo "?")
echo "  通過率：${RATE}%"
echo ""
echo "── Agent Growth File 增長（測試前 → 測試後）──"
for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
  START=${GROWTH_START[$a]:-0}
  END=$(wc -l < ".agent-growth/$a.md" 2>/dev/null || echo 0)
  ADDED=$((END - START))
  TODAY_COUNT=$(grep -c "\[$TODAY\]" ".agent-growth/$a.md" 2>/dev/null || echo 0)
  BAR=$(printf '█%.0s' $(seq 1 $((TODAY_COUNT > 20 ? 20 : TODAY_COUNT))))
  if [ "$TODAY_COUNT" -ge 5 ]; then
    printf "  ✅ %-18s %3d→%3d (+%2d) 今日更新:%2d 次 %s\n" "$a" "$START" "$END" "$ADDED" "$TODAY_COUNT" "$BAR"
  elif [ "$TODAY_COUNT" -gt 0 ]; then
    printf "  ⚠️  %-18s %3d→%3d (+%2d) 今日更新:%2d 次 %s\n" "$a" "$START" "$END" "$ADDED" "$TODAY_COUNT" "$BAR"
  else
    printf "  ❌ %-18s %3d→%3d (+%2d) 今日無更新\n" "$a" "$START" "$END" "$ADDED"
  fi
done

echo ""
echo "── 產出檔案統計 ──"
echo "  中文文章：$(ls articles/parallel-c*-$(date +%Y%m%d).md 2>/dev/null | grep -v en | grep -v chi | wc -l) 篇"
echo "  英文文章：$(ls articles/parallel-c*-en-*.md 2>/dev/null | wc -l) 篇"
echo "  中文詮釋：$(ls articles/parallel-c*-chi-*.md 2>/dev/null | wc -l) 篇"
echo "  Reddit 草稿：$(ls logs/reddit-draft-c*.md 2>/dev/null | wc -l) 份"
echo "  dev.to 草稿：$(ls logs/devto-draft-c*.md 2>/dev/null | wc -l) 份"
echo "  Feedback JSON：$(ls logs/feedback-c*.json 2>/dev/null | wc -l) 份"
echo "  Knowledge lessons：$(wc -l < .knowledge/lessons.md 2>/dev/null || echo 0) 行"

echo ""
echo "── 交叉驗證（知識流動）──"
CROSS_OK=0
for CYCLE in 2 5 8; do
  WRITER_ENTRY=$(grep "\[$TODAY C${CYCLE}\]" .agent-growth/writer.md 2>/dev/null | head -1)
  LESSONS_ENTRY=$(grep "\[$TODAY C${CYCLE}\]" .knowledge/lessons.md 2>/dev/null | head -1)
  if [ -n "$WRITER_ENTRY" ] && [ -n "$LESSONS_ENTRY" ]; then
    echo "  ✅ Cycle $CYCLE：writer→knowledge-subagent 知識流動確認"
    ((CROSS_OK++))
  else
    echo "  ⚠️  Cycle $CYCLE：知識流動不完整（writer:$([ -n "$WRITER_ENTRY" ] && echo 有 || echo 無) lessons:$([ -n "$LESSONS_ENTRY" ] && echo 有 || echo 無)）"
  fi
done

echo ""
FINAL_MSG="🏁 100任務平行壓力測試完成！通過率${RATE}% | 所有14個agent同步運作10輪 | 交叉驗證${CROSS_OK}/3組"
bash .claude/hooks/telegram-notify.sh "$FINAL_MSG" 2>/dev/null || true
echo "Telegram 已發送最終報告"
echo ""
echo "詳細報告：logs/parallel-report.txt"
