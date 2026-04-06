#!/usr/bin/env bash
# test-parallel-100.sh v3
# 修正：
#   1. 大幅減少 --max-turns（防 API 超限）
#   2. 加入 sleep 20 每輪間隔
#   3. 修正 grep 模式（$TODAY → 不含後括號）
#   4. agent 思考展示 + 中文身份標籤
#   5. Message Board 側向溝通機制
#   6. GitHub push token 恢復
#   7. 緊急停止機制（touch ~/ai-factory/.stop-test）

cd ~/ai-factory
mkdir -p logs .knowledge .agent-growth articles

TODAY=$(date +%Y-%m-%d)
TOTAL_PASS=0; TOTAL_FAIL=0; TOTAL_DONE=0
REPORT_FILE="logs/parallel-report-v3.txt"
PROGRESS_FILE="logs/parallel-progress.json"
MSG_BOARD=".knowledge/msg-board.md"
STOP_FILE=".stop-test"   # 緊急停止旗標

# ── 清除舊的停止旗標（若存在）──
rm -f "$STOP_FILE"

# ── 緊急停止檢查函數 ──
check_stop() {
  if [ -f "$STOP_FILE" ]; then
    echo ""
    echo "🛑 ════════════════════════════════════════════════════════"
    echo "🛑  偵測到停止旗標（.stop-test）— 立即中止測試"
    echo "🛑  已完成：Cycle ${CURRENT_CYCLE:-0}/10 | ✅${TOTAL_PASS} ❌${TOTAL_FAIL} | 共${TOTAL_DONE}任務"
    echo "🛑 ════════════════════════════════════════════════════════"
    # 儲存中止狀態
    python3 -c "
import json,pathlib
f=pathlib.Path('$PROGRESS_FILE')
f.write_text(json.dumps({'cycle':${CURRENT_CYCLE:-0},'total_done':$TOTAL_DONE,'pass':$TOTAL_PASS,'fail':$TOTAL_FAIL,'status':'stopped_by_user'},ensure_ascii=False))
" 2>/dev/null
    git add -A 2>/dev/null
    git commit -m "Test STOPPED at cycle ${CURRENT_CYCLE:-0}: ✅${TOTAL_PASS} ❌${TOTAL_FAIL}" --allow-empty 2>/dev/null
    git push origin master 2>/dev/null
    bash .claude/hooks/telegram-notify.sh "🛑 測試手動中止｜Cycle ${CURRENT_CYCLE:-0}/10｜✅${TOTAL_PASS} ❌${TOTAL_FAIL}" 2>/dev/null || true
    rm -f "$STOP_FILE"
    kill $KEEPALIVE_PID 2>/dev/null
    exit 0
  fi
}

# ── 初始化 Message Board（agent 側向溝通用）──
[ ! -f "$MSG_BOARD" ] && printf "# Agent Message Board — AI 無人工廠\n創建於 %s\n\n" "$TODAY" > "$MSG_BOARD"

# ── 初始化進度檔 ──
echo "{\"cycle\":0,\"total_done\":0,\"pass\":0,\"fail\":0,\"status\":\"running\"}" > "$PROGRESS_FILE"

# ── Keepalive 防斷線（每 25 秒，從進度檔讀取 — 修正 subshell 無法讀父變數的問題）──
keepalive_bg() {
  local PF="$1"
  while true; do
    sleep 25
    if [ -f "$PF" ]; then
      PROG=$(python3 -c "
import json,sys
try:
  d=json.load(open('$PF'))
  print(f\"cycle={d.get('cycle',0)}/10 done={d.get('total_done',0)}/100 \u2705{d.get('pass',0)} \u274c{d.get('fail',0)}\")
except: print('讀取中...')
" 2>/dev/null)
    else
      PROG="初始化中..."
    fi
    echo "[⏱ $(date '+%H:%M:%S')] 🏭 後台運行中... ${PROG}"
  done
}
keepalive_bg "$PROGRESS_FILE" &
KEEPALIVE_PID=$!
trap "kill $KEEPALIVE_PID 2>/dev/null; echo '測試中止'" EXIT

# ── GitHub push（帶 token 恢復）──
push_progress() {
  local CYCLE="$1"
  # 依優先順序讀取 GitHub token：.env → settings.json → 環境變數
  local GHTOKEN=""
  if [ -f .env ]; then
    GHTOKEN=$(grep "^GITHUB_TOKEN=" .env | cut -d= -f2 | tr -d '"' | tr -d "'")
  fi
  if [ -z "$GHTOKEN" ]; then
    GHTOKEN=$(python3 -c "
import json,pathlib
try:
  s=json.loads((pathlib.Path.home()/'.claude/settings.json').read_text())
  print(s.get('env',{}).get('GITHUB_TOKEN',''))
except: print('')
" 2>/dev/null)
  fi
  if [ -z "$GHTOKEN" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
    GHTOKEN="$GITHUB_TOKEN"
  fi
  if [ -n "$GHTOKEN" ]; then
    GHREPO=$(git remote get-url origin 2>/dev/null | sed 's|https://[^@]*@||' | sed 's|https://||')
    git remote set-url origin "https://${GHTOKEN}@${GHREPO}" 2>/dev/null
  fi
  git add logs/ .agent-growth/ .knowledge/ articles/ 2>/dev/null
  git commit -m "v3 cycle ${CYCLE}/10 | ✅${TOTAL_PASS} ❌${TOTAL_FAIL} | $(date '+%H:%M')" \
    --allow-empty 2>/dev/null
  git push origin master 2>/dev/null \
    && echo "  [GitHub ✅] Cycle ${CYCLE} 已推送" \
    || echo "  [GitHub ⚠️ ] Push 失敗（token: ${GHTOKEN:+已設定，檢查權限}${GHTOKEN:-未設定}）"
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
  check_stop   # ← 每輪開始前檢查緊急停止旗標
  TOPIC="${TOPICS[$((CYCLE-1))]}"
  echo ""
  echo "══════ CYCLE ${CYCLE}/10：$TOPIC [$(date '+%H:%M:%S')] ══════"
  echo "       讀取留言板... $(grep -c "^\\[" "$MSG_BOARD" 2>/dev/null || echo 0) 則待讀訊息"
  echo "       緊急停止：touch ~/ai-factory/.stop-test"

  # ── 讀取留言板 + 所有 agent 歷史（bash層注入，不靠agent自己讀）──
  LAST_MSGS=$(tail -8 "$MSG_BOARD" 2>/dev/null || echo "（留言板空）")

  # 預讀各 agent 成長記錄（最後5條有效記錄，確保 prompt 有真實歷史）
  _hist() { grep "\[20" ".agent-growth/$1.md" 2>/dev/null | tail -5 || echo "（$1 尚無記錄，第一次執行）"; }
  H_RESEARCHER=$(_hist researcher)
  H_SCOUT=$(_hist revenue-scout)
  H_SELECTOR=$(_hist topic-selector)
  H_WRITER=$(_hist writer)
  H_EN=$(_hist english-writer)
  H_SEO=$(_hist seo-agent)
  H_REVIEWER=$(_hist reviewer)
  H_CHINESE=$(_hist chinese-writer)
  H_POSTER=$(_hist poster)
  H_KNOW=$(_hist knowledge-subagent)
  H_FEEDBACK=$(_hist feedback-collector)
  H_STYLE=$(_hist style-updater)
  H_PRODUCT=$(_hist product-builder)
  H_CHIEF=$(_hist chief-of-staff)

  # ── BATCH A：【研究員】+【營收偵察員】平行 ──
  echo ""
  echo "  ┌─ BATCH A：【研究員】研究 + 【營收偵察員】評估"
  echo "  │  正在喚醒 2 個 agent..."
  _TMP_A_OUT=$(mktemp); _TMP_A_ERR=$(mktemp)
  timeout 120 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10）

留言板最新動態：
${LAST_MSGS}

─── 呼叫以下兩個子 agent ───

## 子 agent 1：researcher（研究員）

【研究員的歷史記錄（這是他的真實記憶，必須引用）】：
${H_RESEARCHER}

在呼叫前，先輸出：
「【研究員 🔍】根據歷史記錄，上次[引用一條具體記錄]。這次我要做的不一樣是：[具體說明]。開始掃描 $TOPIC...」

任務：
1. 評估歷史記錄中的失敗模式（若有），調整本次策略
2. 嘗試 WebFetch https://old.reddit.com/r/arduino/top.json?t=week&limit=3
3. 在 .agent-growth/researcher.md append 一行（直接用 Bash echo，格式固定，不能跳過）：
   [$TODAY C${CYCLE}] 掃描：$TOPIC | Reddit:[成功/封鎖] | 策略調整:[和上次相比的改變] | 發現:[一句重點]
4. 在 $MSG_BOARD append：
   [$TODAY C${CYCLE}][研究員→全隊] $TOPIC：[一句具體市場觀察，給 writer 的切入建議]
5. 回報：RESEARCHER_DONE:C${CYCLE}

## 子 agent 2：revenue-scout（營收偵察員）

【營收偵察員的歷史記錄】：
${H_SCOUT}

在呼叫前，先輸出：
「【營收偵察員 💰】歷史顯示[引用記錄]。這次評估 $TOPIC 時我會特別注意：[基於歷史的具體重點]。」

任務：
1. 基於歷史中的成功評估案例，調整本次評分方式
2. 評估「$TOPIC」商業潛力（1-10分），說明評分邏輯
3. 在 .agent-growth/revenue-scout.md append（用 Bash echo，不能跳過）：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力:[N]/10 | 評分邏輯:[一句] | 歷史參考:[引用的上次記錄]
4. 在 $MSG_BOARD append：
   [$TODAY C${CYCLE}][營收偵察員→秘書長] $TOPIC 潛力:[N]/10，基於[一句評估根據]
5. 回報：SCOUT_DONE:C${CYCLE}

兩個都完成後，輸出：
「✅ BATCH_A_DONE:C${CYCLE} R:[RESEARCHER_DONE/FAIL] S:[SCOUT_DONE/FAIL]」
" --allowedTools "Agent,Read,Write,WebFetch,Bash" --max-turns 6 >"$_TMP_A_OUT" 2>"$_TMP_A_ERR"
  BATCH_A_RESULT=$(cat "$_TMP_A_OUT")

  if echo "$BATCH_A_RESULT" | grep -q "BATCH_A_DONE"; then
    echo "$BATCH_A_RESULT" | grep -E "【(研究員|營收偵察員)" | head -4 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch A 完成（$(echo "$BATCH_A_RESULT" | grep "BATCH_A_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    _ERR_OUT=$(tail -8 "$_TMP_A_OUT" 2>/dev/null | tr '\n' ' ')
    _ERR_ERR=$(tail -3 "$_TMP_A_ERR" 2>/dev/null | tr '\n' ' ')
    _REASON="${_ERR_OUT:-$_ERR_ERR}"
    echo "  └─ ❌ Batch A 失敗：${_REASON:0:150}"
    echo "[$TODAY C${CYCLE}][診斷] Batch A 失敗：${_REASON:0:100}" >> "$MSG_BOARD"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi
  # Fallback：確保記憶一定被更新（agent 沒寫時 bash 補寫）
  grep -q "C${CYCLE}" ".agent-growth/researcher.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 掃描：$TOPIC | bash-fallback | Batch A $(echo "$BATCH_A_RESULT" | grep -q "RESEARCHER_DONE" && echo "成功" || echo "未完成")" >> ".agent-growth/researcher.md"
  grep -q "C${CYCLE}" ".agent-growth/revenue-scout.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 評估：$TOPIC | bash-fallback | $(echo "$BATCH_A_RESULT" | grep -q "SCOUT_DONE" && echo "成功" || echo "未完成")" >> ".agent-growth/revenue-scout.md"
  rm -f "$_TMP_A_OUT" "$_TMP_A_ERR"

  # ── BATCH B：【選題師】──
  echo ""
  echo "  ┌─ BATCH B：【選題師】確認主題"
  _TMP_B_OUT=$(mktemp); _TMP_B_ERR=$(mktemp)
  # 讀取研究員剛才在留言板的發現
  RES_LATEST=$(grep "研究員→全隊.*C${CYCLE}" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "（本輪研究員未留言）")
  timeout 90 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch B）

使用 Agent tool 呼叫 topic-selector 子 agent。

【選題師的歷史記錄】：
${H_SELECTOR}

【研究員本輪留言】：
${RES_LATEST}

在呼叫前輸出：
「【選題師 🎯】歷史顯示[引用一條記錄，說明哪類選題成功/失敗]。本輪研究員說：${RES_LATEST}。我的確認策略：[基於歷史+研究員建議的具體判斷]。」

任務：
1. 基於歷史記錄，評估 $TOPIC 是否符合過去成功模式
2. 執行重複檢查：bash .claude/hooks/duplicate-check.sh '${TOPIC:0:10}'（若腳本不存在直接輸出 UNIQUE）
3. 在 .agent-growth/topic-selector.md append（Bash echo，不能跳過）：
   [$TODAY C${CYCLE}] 選題：$TOPIC | 重複:[UNIQUE/DUPLICATE] | 歷史對比:[和過去相比的評估] | 研究員建議:[已採納/忽略，原因]
4. 在 $MSG_BOARD append：
   [$TODAY C${CYCLE}][選題師→撰稿人] 主題確認：$TOPIC。切入建議：[基於研究員觀察的具體寫作方向，不是泛泛而談]
5. 輸出：BATCH_B_DONE:C${CYCLE} TOPIC_CONFIRMED
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 >"$_TMP_B_OUT" 2>"$_TMP_B_ERR"
  BATCH_B_RESULT=$(cat "$_TMP_B_OUT")

  if echo "$BATCH_B_RESULT" | grep -q "BATCH_B_DONE"; then
    echo "$BATCH_B_RESULT" | grep "【選題師" | head -2 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch B 完成"
    TOTAL_PASS=$((TOTAL_PASS + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  else
    _ERR_OUT=$(tail -8 "$_TMP_B_OUT" 2>/dev/null | tr '\n' ' ')
    _ERR_ERR=$(tail -3 "$_TMP_B_ERR" 2>/dev/null | tr '\n' ' ')
    echo "  └─ ❌ Batch B 失敗：${_ERR_OUT:-$_ERR_ERR}"
    echo "[$TODAY C${CYCLE}][診斷] Batch B 失敗：${_ERR_OUT:0:100}" >> "$MSG_BOARD"
    TOTAL_FAIL=$((TOTAL_FAIL + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  fi
  grep -q "C${CYCLE}" ".agent-growth/topic-selector.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 選題：$TOPIC | bash-fallback | Batch B $(echo "$BATCH_B_RESULT" | grep -q "BATCH_B_DONE" && echo "成功" || echo "未完成")" >> ".agent-growth/topic-selector.md"
  rm -f "$_TMP_B_OUT" "$_TMP_B_ERR"

  # ── BATCH C：【撰稿人】+【英文作家】+【SEO師】三路平行 ──
  echo ""
  echo "  ┌─ BATCH C：【撰稿人】+【英文作家】+【SEO師】三路平行"
  ART_PATH="articles/parallel-c${CYCLE}-$(date +%Y%m%d).md"
  EN_PATH="articles/parallel-c${CYCLE}-en-$(date +%Y%m%d).md"
  SEL_MSG=$(grep "選題師→撰稿人" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "（無留言）")
  RES_MSG=$(grep "研究員→全隊" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "（無留言）")

  _TMP_C_OUT=$(mktemp); _TMP_C_ERR=$(mktemp)
  timeout 240 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch C）

【選題師→撰稿人留言】：$SEL_MSG
【研究員→全隊留言】：$RES_MSG

請呼叫三個子 agent。

## 子 agent 1：writer（撰稿人）★最重要★

【撰稿人的歷史記錄（過去的心得，必須引用）】：
${H_WRITER}

在呼叫前輸出：
「【撰稿人 ✍️】歷史記錄顯示：[引用最近一條記錄，說明上次心得]。這次根據選題師建議（${SEL_MSG:0:50}），我的寫作策略調整是：[具體說明和上次不同的地方]。開始寫 $TOPIC...」

任務：
1. 基於歷史心得調整寫作策略，寫 400-500 字 Arduino 教學：$TOPIC
2. 儲存到 $ART_PATH
3. 在 .agent-growth/writer.md append（Bash echo，必須執行）：
   [$TODAY C${CYCLE}] 主題：$TOPIC | 採納建議:[選題師/研究員的哪個建議] | 字數:[N] | 本輪心得:[一句具體觀察，不是空話]
4. 在 $MSG_BOARD append：
   [$TODAY C${CYCLE}][撰稿人→審稿人] 完成初稿：$TOPIC。最不確定的是：[具體說明一個疑問點]
5. 回報：WRITER_DONE:C${CYCLE} WORDS:[N]

## 子 agent 2：english-writer（英文作家）

【英文作家的歷史記錄】：
${H_EN}

在呼叫前輸出：
「【英文作家 🌍】歷史顯示：[引用記錄]。這次我要改進的是：[基於歷史的具體調整]。」

任務：
1. 基於歷史經驗選擇最合適的語氣（conversational/technical）
2. 寫英文 Reddit 版（300字），主題：$TOPIC，儲存到 $EN_PATH
3. 在 .agent-growth/english-writer.md append（Bash echo）：
   [$TODAY C${CYCLE}] 英文版：$TOPIC | 字數:[N] | 語氣:[選擇原因] | 和上次差異:[一句]
4. 回報：ENGLISH_DONE:C${CYCLE}

## 子 agent 3：seo-agent（SEO師）

【SEO師的歷史記錄】：
${H_SEO}

在呼叫前輸出：
「【SEO師 📊】過去記錄顯示：[引用哪種標題格式效果好]。這次我選擇格式：[理由]。」

任務：
1. 基於歷史標題效果，產生 3 個候選標題，選最佳
2. 在 .agent-growth/seo-agent.md append（Bash echo）：
   [$TODAY C${CYCLE}] SEO：$TOPIC | 最佳標題:[標題] | 選擇理由:[基於歷史的判斷]
3. 在 $MSG_BOARD append：
   [$TODAY C${CYCLE}][SEO師→發文師] 建議標題：[最佳標題]
4. 回報：SEO_DONE:C${CYCLE}

全部完成後輸出：
「BATCH_C_DONE:C${CYCLE} W:[DONE/FAIL] E:[DONE/FAIL] S:[DONE/FAIL]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 12 >"$_TMP_C_OUT" 2>"$_TMP_C_ERR"
  BATCH_C_RESULT=$(cat "$_TMP_C_OUT")

  if echo "$BATCH_C_RESULT" | grep -q "BATCH_C_DONE"; then
    echo "$BATCH_C_RESULT" | grep -E "【(撰稿人|英文作家|SEO師)" | head -6 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch C 完成（$(echo "$BATCH_C_RESULT" | grep "BATCH_C_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  else
    _ERR_OUT=$(tail -8 "$_TMP_C_OUT" 2>/dev/null | tr '\n' ' ')
    _ERR_ERR=$(tail -3 "$_TMP_C_ERR" 2>/dev/null | tr '\n' ' ')
    echo "  └─ ❌ Batch C 失敗：${_ERR_OUT:-$_ERR_ERR}"
    echo "[$TODAY C${CYCLE}][診斷] Batch C 失敗：${_ERR_OUT:0:100}" >> "$MSG_BOARD"
    TOTAL_FAIL=$((TOTAL_FAIL + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  fi
  # Fallback 寫入
  grep -q "C${CYCLE}" ".agent-growth/writer.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 主題：$TOPIC | bash-fallback | $(echo "$BATCH_C_RESULT" | grep -q "WRITER_DONE" && echo "文章已產出" || echo "未完成")" >> ".agent-growth/writer.md"
  grep -q "C${CYCLE}" ".agent-growth/english-writer.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 英文版：$TOPIC | bash-fallback" >> ".agent-growth/english-writer.md"
  grep -q "C${CYCLE}" ".agent-growth/seo-agent.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] SEO：$TOPIC | bash-fallback" >> ".agent-growth/seo-agent.md"
  rm -f "$_TMP_C_OUT" "$_TMP_C_ERR"

  # ── BATCH D：【審稿人】+【中文詮釋師】平行 ──
  echo ""
  echo "  ┌─ BATCH D：【審稿人】審查 + 【中文詮釋師】詮釋"

  WRITER_MSG=$(grep "撰稿人→審稿人" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "無")

  _TMP_D=$(mktemp)
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
" --allowedTools "Agent,Read,Write,Bash" --max-turns 8 2>"$_TMP_D")

  REVIEW_RESULT=$(echo "$BATCH_D_RESULT" | grep -o "RESULT:[A-Z]*" | head -1 | cut -d: -f2)
  if echo "$BATCH_D_RESULT" | grep -q "BATCH_D_DONE"; then
    echo "$BATCH_D_RESULT" | grep -E "【(審稿人|中文詮釋師)" | head -4 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch D 完成 | 審查：${REVIEW_RESULT:-?}"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    _ERR=$(cat "$_TMP_D" 2>/dev/null | tail -3 | tr '\n' ' ')
    [ -z "$_ERR" ] && _ERR=$(echo "$BATCH_D_RESULT" | tail -3 | tr '\n' ' ')
    echo "  └─ ❌ Batch D 失敗：${_ERR:-（timeout 3分鐘）}"
    echo "[$TODAY C${CYCLE}][診斷] Batch D 失敗：${_ERR:0:80}" >> "$MSG_BOARD"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi
  rm -f "$_TMP_D"

  # ── BATCH E：【發文師】+【知識管家】+【回饋偵察員】三路平行 ──
  echo ""
  echo "  ┌─ BATCH E：【發文師】+【知識管家】+【回饋偵察員】三路平行"
  SIMULATED_UV=$((RANDOM % 50 + 5))
  SIMULATED_CM=$((RANDOM % 20 + 2))
  SEO_MSG=$(grep "SEO師→發文師" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "（無SEO建議）")

  _TMP_E_OUT=$(mktemp); _TMP_E_ERR=$(mktemp)
  timeout 180 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch E）

## 子 agent 1：poster（發文師）

【發文師的歷史記錄】：
${H_POSTER}

在呼叫前輸出：
「【發文師 📢】SEO師建議標題：${SEO_MSG:0:50}。歷史顯示[引用記錄]。這次我調整：[具體做法]。」

任務：
1. 基於 SEO 師建議和歷史記錄，產生 Reddit 草稿（r/arduino），儲存到 logs/reddit-draft-c${CYCLE}-$(date +%Y%m%d).md
2. 產生 dev.to 草稿（含 YAML front matter），儲存到 logs/devto-draft-c${CYCLE}-$(date +%Y%m%d).md
3. 在 .agent-growth/poster.md append（Bash echo）：
   [$TODAY C${CYCLE}] 發布：$TOPIC | 審查:${REVIEW_RESULT:-APPROVED} | SEO採納:[是/否] | 和上次差異:[一句]
4. 回報：POSTER_DONE:C${CYCLE}

## 子 agent 2：knowledge-subagent（知識管家）

【知識管家的歷史記錄】：
${H_KNOW}

在呼叫前輸出：
「【知識管家 📚】歷史顯示[引用記錄]。本輪留言板有[N]條新訊息，我要整合的關鍵是：[具體說明]。」

任務：
1. 計算本輪留言板有多少條 C${CYCLE} 的訊息
2. 把本輪最重要的 3 個學習 append 到 .knowledge/lessons.md：
   [$TODAY C${CYCLE}] $TOPIC | 審查:${REVIEW_RESULT:-?} | UV:$SIMULATED_UV | 最重要的團隊學習:[一句具體教訓]
3. 在 .agent-growth/knowledge-subagent.md append（Bash echo）：
   [$TODAY C${CYCLE}] 整合 C${CYCLE} | 留言板:[N]條 | 核心學習:[一句精華]
4. 回報：KNOWLEDGE_DONE:C${CYCLE}

## 子 agent 3：feedback-collector（回饋偵察員）

【回饋偵察員的歷史記錄】：
${H_FEEDBACK}

在呼叫前輸出：
「【回饋偵察員 📡】歷史顯示[引用一條記錄中的規律]。UV=$SIMULATED_UV，和歷史平均相比：[判斷]。」

任務：
1. 模擬數據：upvotes=$SIMULATED_UV comments=$SIMULATED_CM
2. 基於歷史判斷這次表現是 好/普通/差（要說明判斷標準）
3. 儲存到 logs/feedback-c${CYCLE}-$(date +%Y%m%d).json
4. 在 .agent-growth/feedback-collector.md append（Bash echo）：
   [$TODAY C${CYCLE}] 回饋：$TOPIC | UV:$SIMULATED_UV | 評級:[基於歷史的判斷] | 發現規律:[一句]
5. 在 $MSG_BOARD append：
   [$TODAY C${CYCLE}][回饋偵察員→風格調音師] UV=$SIMULATED_UV（歷史對比:[評級]），建議：[具體行動]
6. 回報：FEEDBACK_DONE:C${CYCLE} UV:$SIMULATED_UV

完成後輸出：
「BATCH_E_DONE:C${CYCLE} P:[DONE/FAIL] K:[DONE/FAIL] F:[DONE/FAIL]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 10 >"$_TMP_E_OUT" 2>"$_TMP_E_ERR"
  BATCH_E_RESULT=$(cat "$_TMP_E_OUT")

  if echo "$BATCH_E_RESULT" | grep -q "BATCH_E_DONE"; then
    echo "$BATCH_E_RESULT" | grep -E "【(發文師|知識管家|回饋偵察員)" | head -6 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch E 完成（$(echo "$BATCH_E_RESULT" | grep "BATCH_E_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  else
    _ERR_OUT=$(tail -8 "$_TMP_E_OUT" 2>/dev/null | tr '\n' ' ')
    _ERR_ERR=$(tail -3 "$_TMP_E_ERR" 2>/dev/null | tr '\n' ' ')
    echo "  └─ ❌ Batch E 失敗：${_ERR_OUT:-$_ERR_ERR}"
    echo "[$TODAY C${CYCLE}][診斷] Batch E 失敗：${_ERR_OUT:0:100}" >> "$MSG_BOARD"
    TOTAL_FAIL=$((TOTAL_FAIL + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  fi
  grep -q "C${CYCLE}" ".agent-growth/poster.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 發布：$TOPIC | bash-fallback" >> ".agent-growth/poster.md"
  grep -q "C${CYCLE}" ".agent-growth/knowledge-subagent.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 整合 C${CYCLE} | bash-fallback" >> ".agent-growth/knowledge-subagent.md"
  grep -q "C${CYCLE}" ".agent-growth/feedback-collector.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 回饋：$TOPIC | UV:$SIMULATED_UV | bash-fallback" >> ".agent-growth/feedback-collector.md"
  rm -f "$_TMP_E_OUT" "$_TMP_E_ERR"

  # ── BATCH F：【風格調音師】+【產品建構師】平行 ──
  echo ""
  echo "  ┌─ BATCH F：【風格調音師】調整 + 【產品建構師】評估"
  FB_MSG=$(grep "回饋偵察員→風格調音師" "$MSG_BOARD" 2>/dev/null | tail -1 || echo "（無回饋）")

  _TMP_F_OUT=$(mktemp); _TMP_F_ERR=$(mktemp)
  timeout 150 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch F）

## 子 agent 1：style-updater（風格調音師）

【風格調音師的歷史記錄】：
${H_STYLE}

在呼叫前輸出：
「【風格調音師 🎵】回饋偵察員說：${FB_MSG:0:60}。歷史記錄顯示[引用上次的規則更新]。這次決定：[有/無需調整，理由]。」

任務：
1. 基於回饋和歷史，判斷是否需要更新寫作風格（不是每次都更新，要有根據）
2. 如果 UV > 25，在 .claude/skills/writing-style.md 末尾加一條有數據支撐的觀察
3. 在 .agent-growth/style-updater.md append（Bash echo）：
   [$TODAY C${CYCLE}] UV:$SIMULATED_UV | 更新:[有/無] | 決策邏輯:[基於歷史+回饋的具體判斷]
4. 回報：STYLE_DONE:C${CYCLE} ADJ:[yes/no]

## 子 agent 2：product-builder（產品建構師）

【產品建構師的歷史記錄】：
${H_PRODUCT}

在呼叫前輸出：
「【產品建構師 🛠️】歷史顯示[引用過去的評估記錄]。評估 $TOPIC 時，我對比歷史案例的判斷是：[具體預期分數範圍和原因]。」

任務：
1. 基於歷史評估記錄，評估「$TOPIC」做成 Whop 產品（1-10分），必須引用至少一個歷史案例對比
2. 在 .agent-growth/product-builder.md append（Bash echo）：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力:[N]/10 | 歷史對比:[引用哪個過去案例] | 決定:[做/跳過]
4. 如果潛力 ≥ 7，產生產品大綱到 logs/product-c${CYCLE}.md（3行：名稱+內容+定價）
5. 在留言板加入：
   [$TODAY C${CYCLE}][產品建構師→秘書長] $TOPIC 產品潛力:[N]/10，$([ $(( RANDOM % 10 )) -ge 7 ] && echo '建議立即提案' || echo '暫緩')
6. 回報：PRODUCT_DONE:C${CYCLE} SCORE:[N]

完成後輸出：
「BATCH_F_DONE:C${CYCLE} ST:[DONE/FAIL] PB:[DONE/FAIL]」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 8 >"$_TMP_F_OUT" 2>"$_TMP_F_ERR"
  BATCH_F_RESULT=$(cat "$_TMP_F_OUT")

  if echo "$BATCH_F_RESULT" | grep -q "BATCH_F_DONE"; then
    echo "$BATCH_F_RESULT" | grep -E "【(風格調音師|產品建構師)" | head -4 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch F 完成"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    _ERR_OUT=$(tail -8 "$_TMP_F_OUT" 2>/dev/null | tr '\n' ' ')
    _ERR_ERR=$(tail -3 "$_TMP_F_ERR" 2>/dev/null | tr '\n' ' ')
    echo "  └─ ❌ Batch F 失敗：${_ERR_OUT:-$_ERR_ERR}"
    echo "[$TODAY C${CYCLE}][診斷] Batch F 失敗：${_ERR_OUT:0:100}" >> "$MSG_BOARD"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi
  grep -q "C${CYCLE}" ".agent-growth/style-updater.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] UV:$SIMULATED_UV | bash-fallback" >> ".agent-growth/style-updater.md"
  grep -q "C${CYCLE}" ".agent-growth/product-builder.md" 2>/dev/null || \
    echo "[$TODAY C${CYCLE}] 評估：$TOPIC | bash-fallback" >> ".agent-growth/product-builder.md"
  rm -f "$_TMP_F_OUT" "$_TMP_F_ERR"

  # ── BATCH G：【秘書長】真正診斷（FIX-4）──
  echo ""
  echo "  ┌─ BATCH G：【秘書長】診斷全輪"
  ALL_MSGS=$(tail -20 "$MSG_BOARD" 2>/dev/null || echo "（無）")
  THIS_RATE=$(( TOTAL_PASS * 100 / (TOTAL_DONE > 0 ? TOTAL_DONE : 1) ))
  FAIL_LOG=$(grep "\[診斷\].*C${CYCLE}" "$MSG_BOARD" 2>/dev/null | tr '\n' ';' || echo "本輪無失敗診斷記錄")
  # 歷史通過率（比較是否在下降）
  PREV_RATE=$(grep "通過率" ".agent-growth/chief-of-staff.md" 2>/dev/null | tail -2 | grep -o "[0-9]*%" | head -1 || echo "?")

  _TMP_G_OUT=$(mktemp); _TMP_G_ERR=$(mktemp)
  timeout 120 claude -p "
# AI 無人工廠 — Orchestrator（Cycle ${CYCLE}/10 Batch G）

先輸出：
「【秘書長 👔】本輪通過率 ${THIS_RATE}%，上輪 ${PREV_RATE}。失敗記錄：${FAIL_LOG:0:100}。我要分析模式...」

使用 Agent tool 呼叫 chief-of-staff 子 agent。

【秘書長的歷史診斷記錄】：
${H_CHIEF}

【本輪所有 agent 留言板記錄】：
${ALL_MSGS}

【本輪失敗診斷（來自 msg-board）】：
${FAIL_LOG}

═══ 重要：你是診斷者，不是播報機。以下格式是強制的。═══

任務：

1. 對比歷史記錄（H_CHIEF），判斷本輪失敗是「首次出現」還是「重複模式」

2. 分析失敗原因類型：
   - 如果錯誤訊息包含 timeout → 是任務太重，需要降低 max-turns
   - 如果錯誤訊息包含 rate_limit → API 超限，需要增加冷卻時間
   - 如果錯誤訊息是空的 → agent 執行完但沒有輸出正確格式，需要修改 prompt
   - 如果同一 batch 在不同 cycle 都失敗 → 系統性問題

3. 在 .agent-growth/chief-of-staff.md append（Bash echo，必須執行，格式如下）：
   [$TODAY C${CYCLE}] 通過率:${THIS_RATE}%(前:${PREV_RATE}) | 失敗Batch:[列出] | 失敗類型:[timeout/rate_limit/格式/系統性] | 留言板互動:[N]條 | 下輪指示:[一句具體行動]

4. 輸出正式診斷報告（寫入 .team-memory/standup-log.md，建立若不存在）：
   【第${CYCLE}輪診斷報告 $(date '+%H:%M')】
   通過率：${THIS_RATE}%（前輪：${PREV_RATE}）

   [失敗分析]
   $([ -n "$FAIL_LOG" ] && echo "- 本輪失敗：${FAIL_LOG:0:150}" || echo "- 本輪無失敗")
   失敗類型判斷：[根據錯誤訊息分析]
   是否為重複模式：[對比歷史後的判斷]

   [團隊狀態]
   - 最活躍 agent：[誰的留言最有價值，說明原因]
   - 需要改善 agent：[誰的記錄顯示有問題]

   [秘書長決定]（不需老闆批准的自主行動）
   - [具體行動1]

   [升報老闆]（需要決策的問題）
   - $([ $THIS_RATE -lt 60 ] && echo "通過率低於60%，建議老闆審查 Batch 設計" || echo "無需升報")

5. 在 $MSG_BOARD append：
   [$TODAY C${CYCLE}][秘書長→全隊] 診斷：通過率${THIS_RATE}%，失敗原因:[類型]。下輪注意：[具體指示]

6. $([ $((CYCLE % 3)) -eq 0 ] && echo "執行：bash .claude/hooks/telegram-notify.sh '📊 第${CYCLE}輪診斷｜${THIS_RATE}%｜失敗原因:[類型]'" || echo "本輪跳過 Telegram")

7. 輸出：BATCH_G_DONE:C${CYCLE} RATE:${THIS_RATE}% DIAGNOSIS:[一句核心發現]
" --allowedTools "Agent,Read,Write,Bash" --max-turns 7 >"$_TMP_G_OUT" 2>"$_TMP_G_ERR"
  BATCH_G_RESULT=$(cat "$_TMP_G_OUT")

  if echo "$BATCH_G_RESULT" | grep -q "BATCH_G_DONE"; then
    RATE=$(echo "$BATCH_G_RESULT" | grep -o "RATE:[0-9]*%" | head -1)
    DIAG=$(echo "$BATCH_G_RESULT" | grep -o "DIAGNOSIS:.*" | head -1 | sed 's/DIAGNOSIS://')
    echo "$BATCH_G_RESULT" | grep "【秘書長" | head -2 | sed 's/^/  │  /'
    echo "  └─ ✅ Batch G 完成 | ${RATE} | ${DIAG:-（診斷已寫入 standup-log.md）}"
    TOTAL_PASS=$((TOTAL_PASS + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  else
    _ERR_OUT=$(tail -8 "$_TMP_G_OUT" 2>/dev/null | tr '\n' ' ')
    _ERR_ERR=$(tail -3 "$_TMP_G_ERR" 2>/dev/null | tr '\n' ' ')
    echo "  └─ ❌ Batch G 失敗：${_ERR_OUT:-$_ERR_ERR}"
    # 秘書長失敗時 bash 直接寫入基本記錄
    echo "[$TODAY C${CYCLE}] 通過率:${THIS_RATE}% | bash-fallback（秘書長未完成）" >> ".agent-growth/chief-of-staff.md"
    TOTAL_FAIL=$((TOTAL_FAIL + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  fi
  rm -f "$_TMP_G_OUT" "$_TMP_G_ERR"

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
