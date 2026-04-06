#!/usr/bin/env bash
# test-parallel-100.sh v3
# 修正：
#   1. 大幅減少 --max-turns（防 API 超限）
#   2. 加入 sleep 20 每輪間隔
#   3. 修正 grep 模式（$TODAY → 不含後括號）
#   4. agent 思考展示 + 中文身份標籤
#   5. Message Board 側向溝通機制
#   6. GitHub push token 恢復

cd ~/ai-factory
mkdir -p logs .knowledge .agent-growth articles

TODAY=$(date +%Y-%m-%d)
TOTAL_PASS=0; TOTAL_FAIL=0; TOTAL_DONE=0
REPORT_FILE="logs/parallel-report-v3.txt"
PROGRESS_FILE="logs/parallel-progress.json"
MSG_BOARD=".knowledge/msg-board.md"

# ── 初始化 Message Board（agent 側向溝通用）──
[ ! -f "$MSG_BOARD" ] && printf "# Agent Message Board — AI 無人工廠\n創建於 %s\n\n" "$TODAY" > "$MSG_BOARD"

# ── 初始化進度檔 ──
echo "{\"cycle\":0,\"total_done\":0,\"pass\":0,\"fail\":0,\"status\":\"running\"}" > "$PROGRESS_FILE"

# ── Keepalive 防斷線（每 25 秒）──
keepalive_bg() {
  while true; do
    sleep 25
    echo "[⏱ $(date '+%H:%M:%S')] 🏭 後台運行中... cycle=${CURRENT_CYCLE:-0}/10 done=${TOTAL_DONE}/100 ✅${TOTAL_PASS} ❌${TOTAL_FAIL}"
  done
}
keepalive_bg &
KEEPALIVE_PID=$!
trap "kill $KEEPALIVE_PID 2>/dev/null; echo '測試中止'" EXIT

# ── GitHub push（帶 token 恢復）──
push_progress() {
  local CYCLE="$1"
  # 嘗試從 .env 讀取 token
  if [ -f .env ]; then
    GHTOKEN=$(grep "^GITHUB_TOKEN=" .env | cut -d= -f2 | tr -d '"' | tr -d "'")
    GHREPO=$(git remote get-url origin 2>/dev/null | sed 's|https://[^@]*@||' | sed 's|https://||')
    if [ -n "$GHTOKEN" ] && [ -n "$GHREPO" ]; then
      git remote set-url origin "https://${GHTOKEN}@${GHREPO}" 2>/dev/null
    fi
  fi
  git add logs/ .agent-growth/ .knowledge/ articles/ 2>/dev/null
  git commit -m "v3 cycle ${CYCLE}/10 | ✅${TOTAL_PASS} ❌${TOTAL_FAIL} | $(date '+%H:%M')" \
    --allow-empty 2>/dev/null
  git push origin master 2>/dev/null \
    && echo "  [GitHub ✅] Cycle ${CYCLE} 已推送" \
    || echo "  [GitHub ⚠️ ] Push 失敗（token 未設定？繼續測試）"
}

# ── Agent 中文名對照 ──
declare -A AGENT_ZH
AGENT_ZH[researcher]="研究員"
AGENT_ZH[topic-selector]="選題師"
AGENT_ZH[writer]="撰稿人"
AGENT_ZH[seo-agent]="SEO 師"
AGENT_ZH[reviewer]="審稿人"
AGENT_ZH[english-writer]="英文作家"
AGENT_ZH[chinese-writer]="中文詮釋師"
AGENT_ZH[poster]="發文師"
AGENT_ZH[knowledge-subagent]="知識管家"
AGENT_ZH[feedback-collector]="回饋偵察員"
AGENT_ZH[style-updater]="風格調音師"
AGENT_ZH[product-builder]="產品建構師"
AGENT_ZH[revenue-scout]="營收偵察員"
AGENT_ZH[chief-of-staff]="秘書長"

# ── 視覺化狀態板（修正 grep 模式）──
show_board() {
  local CYCLE="$1"
  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  printf "║  🏭 AI 無人工廠 | Cycle %2d/10 | ✅%3d ❌%3d | 完成 %3d/100  ║\n" \
    "$CYCLE" "$TOTAL_PASS" "$TOTAL_FAIL" "$TOTAL_DONE"
  echo "╠══════════════════════════════════════════════════════════════╣"
  printf "║  %-22s %-5s  %-22s %-5s ║\n" "Agent" "今日" "Agent" "今日"
  echo "╠══════════════════════════════════════════════════════════════╣"
  AGENTS_L=(researcher topic-selector writer seo-agent reviewer english-writer chinese-writer)
  AGENTS_R=(poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff)
  for i in "${!AGENTS_L[@]}"; do
    AL="${AGENTS_L[$i]}"; AR="${AGENTS_R[$i]:-}"
    # 修正：grep "$TODAY" 而非 "\[$TODAY\]"，才能匹配 [2026-04-06 C1] 格式
    CL=$(grep -c "$TODAY" ".agent-growth/${AL}.md" 2>/dev/null || echo 0)
    CR=$([ -n "$AR" ] && grep -c "$TODAY" ".agent-growth/${AR}.md" 2>/dev/null || echo "-")
    ZHL="${AGENT_ZH[$AL]:-$AL}"
    ZHR="${AGENT_ZH[$AR]:-$AR}"
    printf "║  %-13s(%-8s)%2s次  %-13s(%-8s)%2s次 ║\n" \
      "$AL" "$ZHL" "${CL}" "${AR:-}" "$ZHR" "${CR}"
  done
  echo "╠══════════════════════════════════════════════════════════════╣"
  MSG_COUNT=$(grep -c "^\[" "$MSG_BOARD" 2>/dev/null || echo 0)
  LESSONS_LINES=$(wc -l < ".knowledge/lessons.md" 2>/dev/null || echo 0)
  ARTICLES=$(ls articles/parallel-c*.md 2>/dev/null | wc -l)
  printf "║  📝文章:%3d  📚lessons:%3d行  💬留言板:%3d條            ║\n" \
    "$ARTICLES" "$LESSONS_LINES" "$MSG_COUNT"
  echo "╚══════════════════════════════════════════════════════════════╝"
}

# ── 記錄初始狀態 ──
declare -A GROWTH_START
for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer \
         poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
  GROWTH_START[$a]=$(wc -l < ".agent-growth/$a.md" 2>/dev/null || echo 0)
done

TOPICS=(
  "SHT31 高精度溫濕度感測校正"
  "HMC5883L 磁力計三軸方位計算"
  "ADXL345 衝擊偵測靈敏度設定"
  "INA219 電流功率精準監測"
  "TSL2561 光照度自動曝光控制"
  "MCP4725 DAC 類比輸出波形生成"
  "MAX6675 熱電偶高溫量測補償"
  "AS5600 磁性旋轉角度讀取"
  "VL6180X 近距離光學感測融合"
  "TCS34725 RGB顏色辨識與校色"
)

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   100任務平行壓力測試 v3                                      ║"
echo "║   修正：API限制 / 身份展示 / 側向溝通 / Grep修正               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo "開始：$(date)"
bash .claude/hooks/telegram-notify.sh "🏁 v3 測試開始｜API節流+身份展示+留言板｜$(date '+%H:%M')" 2>/dev/null || true

# ════════════════════════════════════════════
# 主迴圈：10個 Cycle
# ════════════════════════════════════════════
for CYCLE in $(seq 1 10); do
  CURRENT_CYCLE=$CYCLE
  TOPIC="${TOPICS[$((CYCLE-1))]}"
  echo ""
  echo "══════ CYCLE ${CYCLE}/10：$TOPIC [$(date '+%H:%M:%S')] ══════"
  echo "       讀取留言板... $(grep -c "^\\[" "$MSG_BOARD" 2>/dev/null || echo 0) 則待讀訊息"

  # ── 讀取留言板給 orchestrator 參考 ──
  LAST_MSGS=$(tail -5 "$MSG_BOARD" 2>/dev/null || echo "（留言板空）")

  # ── BATCH A：【研究員】+【營收偵察員】平行 ──
  echo ""
  echo "  ┌─ BATCH A：【研究員】研究 + 【營收偵察員】評估"
  echo "  │  正在喚醒 2 個 agent..."
  BATCH_A_RESULT=$(timeout 120 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10）

你正在協調 AI 無人工廠的兩位 agent 執行任務。
請展示每個 agent 的思考過程（用中文標籤格式）。

留言板最新動態：
${LAST_MSGS}

─── 請依序呼叫以下兩個子 agent，每個都必須在開始前輸出思考展示 ───

## 子 agent 1：researcher（研究員）
在呼叫前，先輸出：
「【研究員 🔍】思考中：準備掃描 $TOPIC 的市場熱度...」

任務：
1. 讀取 .agent-growth/researcher.md（了解自己的歷史）
2. 嘗試 WebFetch https://old.reddit.com/r/arduino/top.json?t=week&limit=3
3. 在 .agent-growth/researcher.md 加入一行（格式固定）：
   [$TODAY C${CYCLE}] 掃描：$TOPIC | Reddit:[成功/封鎖] | 發現:[一句重點]
4. 在留言板 $MSG_BOARD 加入一行：
   [$TODAY C${CYCLE}][研究員→全隊] $TOPIC 趨勢：[一句觀察，給 writer 的建議]
5. 回報：RESEARCHER_DONE:C${CYCLE}

## 子 agent 2：revenue-scout（營收偵察員）
在呼叫前，先輸出：
「【營收偵察員 💰】思考中：評估 $TOPIC 的商業潛力...」

任務：
1. 讀取 .agent-growth/revenue-scout.md
2. 讀取留言板最後 3 行（了解研究員觀察）
3. 評估「$TOPIC」商業潛力（1-10分），說明理由
4. 在 .agent-growth/revenue-scout.md 加入：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力:[N]/10 | 理由:[一句]
5. 在留言板加入：
   [$TODAY C${CYCLE}][營收偵察員→秘書長] $TOPIC 潛力:[N]/10
6. 回報：SCOUT_DONE:C${CYCLE}

兩個都完成後，輸出：
「✅ BATCH_A_DONE:C${CYCLE} R:[RESEARCHER_DONE/FAIL] S:[SCOUT_DONE/FAIL]」
" --allowedTools "Agent,Read,Write,WebFetch" --max-turns 6 2>/dev/null)

  if echo "$BATCH_A_RESULT" | grep -q "BATCH_A_DONE"; then
    # 提取並顯示 agent 思考
    echo "$BATCH_A_RESULT" | grep -E "【(研究員|營收偵察員)" | head -4 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch A 完成（$(echo "$BATCH_A_RESULT" | grep "BATCH_A_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    echo "  └─ ❌ Batch A 失敗（$(echo "$BATCH_A_RESULT" | tail -2 | tr '\n' ' ')）"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi

  # ── BATCH B：【選題師】──
  echo ""
  echo "  ┌─ BATCH B：【選題師】確認主題"
  BATCH_B_RESULT=$(timeout 90 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch B）

輸出：「【選題師 🎯】思考中：確認主題是否與上一輪不重複...」

使用 Agent tool 呼叫 topic-selector 子 agent。

任務：
1. 讀取 .agent-growth/topic-selector.md（了解歷史選題）
2. 讀取留言板最後 3 行（研究員的發現）
3. 本輪主題已定：$TOPIC
4. 執行重複檢查：bash .claude/hooks/duplicate-check.sh '${TOPIC:0:10}'（若不存在直接略過）
5. 在 .agent-growth/topic-selector.md 加入：
   [$TODAY C${CYCLE}] 選題：$TOPIC | 重複:[UNIQUE/DUPLICATE] | 研究員建議:[已讀/未讀]
6. 在留言板加入：
   [$TODAY C${CYCLE}][選題師→撰稿人] 主題確認：$TOPIC，請重點著墨[研究員建議的切入點]
7. 輸出：BATCH_B_DONE:C${CYCLE} TOPIC_CONFIRMED
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 2>/dev/null)

  if echo "$BATCH_B_RESULT" | grep -q "BATCH_B_DONE"; then
    echo "$BATCH_B_RESULT" | grep "【選題師" | head -2 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch B 完成"
    TOTAL_PASS=$((TOTAL_PASS + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  else
    echo "  └─ ❌ Batch B 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  fi

  # ── BATCH C：【撰稿人】+【英文作家】+【SEO師】三路平行 ──
  echo ""
  echo "  ┌─ BATCH C：【撰稿人】+【英文作家】+【SEO師】三路平行"
  ART_PATH="articles/parallel-c${CYCLE}-$(date +%Y%m%d).md"
  EN_PATH="articles/parallel-c${CYCLE}-en-$(date +%Y%m%d).md"

  # 讀最新留言
  SEL_MSG=$(grep "選題師→撰稿人" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "無留言")
  RES_MSG=$(grep "研究員→全隊" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "無留言")

  BATCH_C_RESULT=$(timeout 240 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch C）

留言板訊息：
- $SEL_MSG
- $RES_MSG

請呼叫三個子 agent，每個呼叫前展示思考。

## 子 agent 1：writer（撰稿人）★最重要★
在呼叫前輸出：
「【撰稿人 ✍️】思考中：讀取上輪學習記錄，整合選題師和研究員的建議，開始寫作...」

任務：
1. 讀取 .agent-growth/writer.md（找上輪 C$((CYCLE-1)) 的學習記錄）
2. 根據研究員和選題師的建議，寫 400-500 字 Arduino 教學：$TOPIC
3. 儲存到 $ART_PATH
4. 在 .agent-growth/writer.md 加入（必須寫入）：
   [$TODAY C${CYCLE}] 主題：$TOPIC | 引用留言板:[是/否] | 字數:[N] | 本輪心得:[一句]
5. 在留言板加入：
   [$TODAY C${CYCLE}][撰稿人→審稿人] 完成初稿，請重點審查[最不確定的部分]
6. 回報：WRITER_DONE:C${CYCLE} WORDS:[N]

## 子 agent 2：english-writer（英文作家）
在呼叫前輸出：
「【英文作家 🌍】思考中：根據中文稿件方向，寫符合 Reddit 語氣的英文版...」

任務：
1. 讀取 .agent-growth/english-writer.md
2. 寫英文 Reddit 版（300字），主題：$TOPIC，儲存到 $EN_PATH
3. 在 .agent-growth/english-writer.md 加入：
   [$TODAY C${CYCLE}] 英文版：$TOPIC | 字數:[N] | 語氣:[conversational/technical]
4. 回報：ENGLISH_DONE:C${CYCLE}

## 子 agent 3：seo-agent（SEO師）
在呼叫前輸出：
「【SEO師 📊】思考中：分析 $TOPIC 的關鍵字競爭度，產生 3 個標題方案...」

任務：
1. 讀取 .agent-growth/seo-agent.md
2. 產生 3 個 SEO 標題，分析關鍵字，選最佳版本
3. 在 .agent-growth/seo-agent.md 加入：
   [$TODAY C${CYCLE}] SEO：$TOPIC | 最佳標題:[標題] | 關鍵字:[2個]
4. 在留言板加入：
   [$TODAY C${CYCLE}][SEO師→發文師] 建議標題：[最佳標題]
5. 回報：SEO_DONE:C${CYCLE}

全部完成後輸出：
「BATCH_C_DONE:C${CYCLE} W:[DONE/FAIL] E:[DONE/FAIL] S:[DONE/FAIL]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 12 2>/dev/null)

  if echo "$BATCH_C_RESULT" | grep -q "BATCH_C_DONE"; then
    echo "$BATCH_C_RESULT" | grep -E "【(撰稿人|英文作家|SEO師)" | head -6 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch C 完成（$(echo "$BATCH_C_RESULT" | grep "BATCH_C_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  else
    echo "  └─ ❌ Batch C 失敗（$(echo "$BATCH_C_RESULT" | tail -1)）"
    TOTAL_FAIL=$((TOTAL_FAIL + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  fi

  # ── BATCH D：【審稿人】+【中文詮釋師】平行 ──
  echo ""
  echo "  ┌─ BATCH D：【審稿人】審查 + 【中文詮釋師】詮釋"

  WRITER_MSG=$(grep "撰稿人→審稿人" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "無")

  BATCH_D_RESULT=$(timeout 180 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch D）

留言板：撰稿人留給審稿人的訊息：$WRITER_MSG

## 子 agent 1：reviewer（審稿人）
在呼叫前輸出：
「【審稿人 🔎】思考中：讀取撰稿人的留言，重點審查其不確定的部分...」

任務：
1. 讀取 .agent-growth/reviewer.md（了解過去審稿標準）
2. 讀取 $ART_PATH（若不存在，審查主題 $TOPIC 的通用標準）
3. 判斷 APPROVED 或 REJECTED，附 3 條具體理由
4. 在 .agent-growth/reviewer.md 加入（必須寫入）：
   [$TODAY C${CYCLE}] 審查：$TOPIC | APPROVED/REJECTED | 主要問題:[一句] | 給writer建議:[一句]
5. 在留言板加入：
   [$TODAY C${CYCLE}][審稿人→撰稿人] 審查結果:[APPROVED/REJECTED]，下輪請注意:[一句建議]
6. 回報：REVIEWER_DONE:C${CYCLE} RESULT:[APPROVED/REJECTED]

## 子 agent 2：chinese-writer（中文詮釋師）
在呼叫前輸出：
「【中文詮釋師 🌸】思考中：不只翻譯，而是用張旭豐的視角重新詮釋這個主題...」

任務：
1. 讀取 .agent-growth/chinese-writer.md
2. 讀取 $EN_PATH（若不存在，基於 $TOPIC 自行發揮）
3. 寫中文詮釋版（300字，強調「為什麼這個感測器值得學」），儲存到 articles/parallel-c${CYCLE}-chi-$(date +%Y%m%d).md
4. 在 .agent-growth/chinese-writer.md 加入：
   [$TODAY C${CYCLE}] 詮釋：$TOPIC | 創新點:[和英文版最大差異]
5. 回報：CHINESE_DONE:C${CYCLE}

完成後輸出：
「BATCH_D_DONE:C${CYCLE} RV:[RESULT] CH:[DONE/FAIL]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 8 2>/dev/null)

  REVIEW_RESULT=$(echo "$BATCH_D_RESULT" | grep -o "RESULT:[A-Z]*" | head -1 | cut -d: -f2)
  if echo "$BATCH_D_RESULT" | grep -q "BATCH_D_DONE"; then
    echo "$BATCH_D_RESULT" | grep -E "【(審稿人|中文詮釋師)" | head -4 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch D 完成 | 審查：${REVIEW_RESULT:-?}"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    echo "  └─ ❌ Batch D 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi

  # ── BATCH E：【發文師】+【知識管家】+【回饋偵察員】三路平行 ──
  echo ""
  echo "  ┌─ BATCH E：【發文師】+【知識管家】+【回饋偵察員】三路平行"
  SIMULATED_UV=$((RANDOM % 50 + 5))
  SIMULATED_CM=$((RANDOM % 20 + 2))
  SEO_MSG=$(grep "SEO師→發文師" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "無SEO建議")

  BATCH_E_RESULT=$(timeout 180 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch E）

## 子 agent 1：poster（發文師）
在呼叫前輸出：
「【發文師 📢】思考中：整合 SEO師建議（$SEO_MSG），準備 Reddit + dev.to 草稿...」

任務：
1. 讀取 .agent-growth/poster.md
2. 產生 Reddit 草稿（r/arduino），儲存到 logs/reddit-draft-c${CYCLE}-$(date +%Y%m%d).md
3. 產生 dev.to 草稿（含 YAML front matter），儲存到 logs/devto-draft-c${CYCLE}-$(date +%Y%m%d).md
4. 在 .agent-growth/poster.md 加入：
   [$TODAY C${CYCLE}] 發布：$TOPIC | 審查:${REVIEW_RESULT:-APPROVED} | Reddit+devto草稿完成
5. 回報：POSTER_DONE:C${CYCLE}

## 子 agent 2：knowledge-subagent（知識管家）
在呼叫前輸出：
「【知識管家 📚】思考中：整合本輪所有 agent 的學習，歸納知識精華...」

任務：
1. 讀取 .agent-growth/knowledge-subagent.md
2. 讀取留言板最後 5 行（本輪 agent 互動記錄）
3. Append 到 .knowledge/lessons.md：
   [$TODAY C${CYCLE}] $TOPIC | 審查:${REVIEW_RESULT:-?} | UV模擬:$SIMULATED_UV | 留言板互動:[N]條
4. 在 .agent-growth/knowledge-subagent.md 加入：
   [$TODAY C${CYCLE}] 整合 C${CYCLE} 知識 | agent留言:[N]條 → lessons.md
5. 回報：KNOWLEDGE_DONE:C${CYCLE}

## 子 agent 3：feedback-collector（回饋偵察員）
在呼叫前輸出：
「【回饋偵察員 📡】思考中：收集模擬回饋數據，分析受眾反應...」

任務：
1. 讀取 .agent-growth/feedback-collector.md
2. 模擬數據：upvotes=$SIMULATED_UV comments=$SIMULATED_CM
3. 儲存到 logs/feedback-c${CYCLE}-$(date +%Y%m%d).json：
   {\"cycle\":$CYCLE,\"topic\":\"$TOPIC\",\"upvotes\":$SIMULATED_UV,\"comments\":$SIMULATED_CM,\"mode\":\"simulated\"}
4. 在 .agent-growth/feedback-collector.md 加入：
   [$TODAY C${CYCLE}] 回饋：$TOPIC | UV:$SIMULATED_UV CM:$SIMULATED_CM | 評級:[好/普通/差]
5. 在留言板加入：
   [$TODAY C${CYCLE}][回饋偵察員→風格調音師] UV=$SIMULATED_UV，建議$([ $SIMULATED_UV -gt 25 ] && echo '維持現有風格' || echo '調整切入角度')
6. 回報：FEEDBACK_DONE:C${CYCLE} UV:$SIMULATED_UV

完成後輸出：
「BATCH_E_DONE:C${CYCLE} P:[DONE/FAIL] K:[DONE/FAIL] F:[DONE/FAIL]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 10 2>/dev/null)

  if echo "$BATCH_E_RESULT" | grep -q "BATCH_E_DONE"; then
    echo "$BATCH_E_RESULT" | grep -E "【(發文師|知識管家|回饋偵察員)" | head -6 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch E 完成（$(echo "$BATCH_E_RESULT" | grep "BATCH_E_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  else
    echo "  └─ ❌ Batch E 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  fi

  # ── BATCH F：【風格調音師】+【產品建構師】平行 ──
  echo ""
  echo "  ┌─ BATCH F：【風格調音師】調整 + 【產品建構師】評估"
  FB_MSG=$(grep "回饋偵察員→風格調音師" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "無回饋")

  BATCH_F_RESULT=$(timeout 150 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch F）

## 子 agent 1：style-updater（風格調音師）
在呼叫前輸出：
「【風格調音師 🎵】思考中：讀取回饋偵察員的訊息（$FB_MSG），決定是否調整寫作風格...」

任務：
1. 讀取 .agent-growth/style-updater.md
2. 分析：upvotes=$SIMULATED_UV（>25 = 好，<15 = 差）
3. 如果 UV > 25，在 .claude/skills/writing-style.md 末尾加觀察：
   ## 自動更新 $TODAY C${CYCLE}：UV=$SIMULATED_UV，維持現有寫作節奏
4. 在 .agent-growth/style-updater.md 加入：
   [$TODAY C${CYCLE}] 分析：UV=$SIMULATED_UV | 風格更新:[有/無] | 決策根據:[回饋偵察員留言]
5. 回報：STYLE_DONE:C${CYCLE} ADJ:[yes/no]

## 子 agent 2：product-builder（產品建構師）
在呼叫前輸出：
「【產品建構師 🛠️】思考中：評估 $TOPIC 的產品化可行性，考慮 Whop 市場定位...」

任務：
1. 讀取 .agent-growth/product-builder.md
2. 評估「$TOPIC」做成 Whop 產品（1-10分）
3. 在 .agent-growth/product-builder.md 加入：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力:[N]/10 | 決定:[做/跳過] | 預估定價:[$N]
4. 如果潛力 ≥ 7，產生產品大綱到 logs/product-c${CYCLE}.md（3行：名稱+內容+定價）
5. 在留言板加入：
   [$TODAY C${CYCLE}][產品建構師→秘書長] $TOPIC 產品潛力:[N]/10，$([ $(( RANDOM % 10 )) -ge 7 ] && echo '建議立即提案' || echo '暫緩')
6. 回報：PRODUCT_DONE:C${CYCLE} SCORE:[N]

完成後輸出：
「BATCH_F_DONE:C${CYCLE} ST:[DONE/FAIL] PB:[DONE/FAIL]」
" --allowedTools "Agent,Read,Write" --max-turns 8 2>/dev/null)

  if echo "$BATCH_F_RESULT" | grep -q "BATCH_F_DONE"; then
    echo "$BATCH_F_RESULT" | grep -E "【(風格調音師|產品建構師)" | head -4 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch F 完成"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    echo "  └─ ❌ Batch F 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi

  # ── BATCH G：【秘書長】彙報 + 讀取留言板 ──
  echo ""
  echo "  ┌─ BATCH G：【秘書長】彙報全輪"
  ALL_MSGS=$(tail -10 "$MSG_BOARD" 2>/dev/null || echo "（無）")

  BATCH_G_RESULT=$(timeout 120 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch G）

輸出：「【秘書長 👔】思考中：讀取本輪所有 agent 的留言板訊息，準備向老闆彙報...」

使用 Agent tool 呼叫 chief-of-staff 子 agent。

本輪留言板記錄（agent 之間的溝通）：
${ALL_MSGS}

任務（第 ${CYCLE}/10 輪彙報）：
1. 讀取 .agent-growth/chief-of-staff.md
2. 統計本輪表現：✅${TOTAL_PASS} ❌${TOTAL_FAIL} 通過率約$(( TOTAL_PASS * 100 / (TOTAL_DONE > 0 ? TOTAL_DONE : 1) ))%
3. 在 .agent-growth/chief-of-staff.md 加入（必須寫入）：
   [$TODAY C${CYCLE}] 第${CYCLE}輪：$TOPIC | UV:$SIMULATED_UV | 審查:${REVIEW_RESULT:-?} | agent留言:[N]條 | 通過率:$(( TOTAL_PASS * 100 / (TOTAL_DONE > 0 ? TOTAL_DONE : 1) ))%
4. 在留言板加入：
   [$TODAY C${CYCLE}][秘書長→全隊] 第${CYCLE}輪結束，通過率$(( TOTAL_PASS * 100 / (TOTAL_DONE > 0 ? TOTAL_DONE : 1) ))%，下輪重點：[一句指示]
5. 每 3 輪才發 Telegram（第 3、6、9 輪）：
   $([ $((CYCLE % 3)) -eq 0 ] && echo "執行：bash .claude/hooks/telegram-notify.sh '📊 第${CYCLE}/10輪｜✅${TOTAL_PASS} ❌${TOTAL_FAIL}｜UV:$SIMULATED_UV｜留言板活躍'" || echo "本輪跳過 Telegram")
6. 輸出：BATCH_G_DONE:C${CYCLE} RATE:$(( TOTAL_PASS * 100 / (TOTAL_DONE > 0 ? TOTAL_DONE : 1) ))%
" --allowedTools "Agent,Read,Write,Bash" --max-turns 5 2>/dev/null)

  if echo "$BATCH_G_RESULT" | grep -q "BATCH_G_DONE"; then
    RATE=$(echo "$BATCH_G_RESULT" | grep -o "RATE:[0-9]*%" | head -1)
    echo "$BATCH_G_RESULT" | grep "【秘書長" | head -2 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch G 完成 | ${RATE}"
    TOTAL_PASS=$((TOTAL_PASS + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  else
    echo "  └─ ❌ Batch G 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  fi

  # ── 更新進度檔 ──
  python3 -c "
import json,pathlib
f=pathlib.Path('$PROGRESS_FILE')
d={'cycle':$CYCLE,'total_done':$TOTAL_DONE,'pass':$TOTAL_PASS,'fail':$TOTAL_FAIL,'status':'running','topic':'$TOPIC','msg_count':$(grep -c '^\\[' "$MSG_BOARD" 2>/dev/null || echo 0)}
f.write_text(json.dumps(d,ensure_ascii=False))
" 2>/dev/null

  push_progress "$CYCLE"
  show_board "$CYCLE"

  echo "  ── Cycle ${CYCLE}/10 完成 [$(date '+%H:%M:%S')] ✅${TOTAL_PASS} ❌${TOTAL_FAIL} 共${TOTAL_DONE}任務 ──"
  echo "     留言板本輪新增：$(grep "C${CYCLE}]" "$MSG_BOARD" 2>/dev/null | wc -l) 條"

  # ── 輪間冷卻（節省 API 配額）──
  if [ "$CYCLE" -lt 10 ]; then
    echo "  [冷卻 20 秒，避免 API 超限...]"
    sleep 20
  fi
done

# ════════════════════════════════════════════
# 最終報告
# ════════════════════════════════════════════
kill $KEEPALIVE_PID 2>/dev/null
trap - EXIT

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   100任務測試 v3 最終報告                                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo "完成：$(date)"
FINAL_RATE=$(echo "scale=1; $TOTAL_PASS * 100 / ($TOTAL_DONE > 0 ? $TOTAL_DONE : 1)" | bc 2>/dev/null || echo "?")
echo "  總任務：$TOTAL_DONE  ✅$TOTAL_PASS  ❌$TOTAL_FAIL  通過率：${FINAL_RATE}%"
echo ""

echo "── Agent 成長與活躍度 ──"
for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer \
         poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
  S=${GROWTH_START[$a]:-0}
  E=$(wc -l < ".agent-growth/$a.md" 2>/dev/null || echo 0)
  TC=$(grep -c "$TODAY" ".agent-growth/$a.md" 2>/dev/null || echo 0)
  ZH="${AGENT_ZH[$a]:-$a}"
  BAR=$(python3 -c "print('▓' * min($TC, 20))" 2>/dev/null || printf '▓%.0s' $(seq 1 $(( TC > 20 ? 20 : TC ))))
  [ "$TC" -ge 8 ] && ICON="✅" || { [ "$TC" -ge 3 ] && ICON="⚠️ " || ICON="❌"; }
  printf "  %s %-14s(%-10s) +%-3d行  今日:%2d次  %s\n" \
    "$ICON" "$a" "$ZH" "$((E-S))" "$TC" "$BAR"
done

echo ""
echo "── 留言板統計 ──"
echo "  總訊息數：$(grep -c '^\\[' "$MSG_BOARD" 2>/dev/null || echo 0) 條"
echo "  最活躍 sender：$(grep -o '\\[[^]]*\\]\\[[^→]*→' "$MSG_BOARD" 2>/dev/null | sort | uniq -c | sort -rn | head -1)"

echo ""
echo "── 產出統計 ──"
echo "  文章(中)：$(ls articles/parallel-c*-$(date +%Y%m%d).md 2>/dev/null | grep -v en | grep -v chi | wc -l) 篇"
echo "  文章(英)：$(ls articles/parallel-c*-en-*.md 2>/dev/null | wc -l) 篇"
echo "  文章(詮)：$(ls articles/parallel-c*-chi-*.md 2>/dev/null | wc -l) 篇"
echo "  Reddit：$(ls logs/reddit-draft-c*.md 2>/dev/null | wc -l) 份"
echo "  dev.to：$(ls logs/devto-draft-c*.md 2>/dev/null | wc -l) 份"
echo "  lessons：$(wc -l < .knowledge/lessons.md 2>/dev/null || echo 0) 行"

# 最終 push
git add -A 2>/dev/null
git commit -m "v3 COMPLETE: ✅${TOTAL_PASS} ❌${TOTAL_FAIL} rate:${FINAL_RATE}% | 留言板:$(grep -c '^\\[' "$MSG_BOARD" 2>/dev/null || echo 0)條" 2>/dev/null
git push origin master 2>/dev/null && echo "✅ 最終結果已推送 GitHub" || echo "⚠️  Push 失敗"

bash .claude/hooks/telegram-notify.sh "🎯 v3測試完成！通過率${FINAL_RATE}%｜✅${TOTAL_PASS} ❌${TOTAL_FAIL}｜留言板$(grep -c '^\\[' "$MSG_BOARD" 2>/dev/null || echo 0)條｜14agent全程運作" 2>/dev/null || true
echo ""
echo "✅ 查看 GitHub: logs/parallel-report-v3.txt + .knowledge/msg-board.md"
