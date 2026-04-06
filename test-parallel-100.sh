#!/usr/bin/env bash
# test-parallel-100.sh v2
# 修正：改用單一 orchestrator 呼叫多個子 agent（不再多進程競爭 claude CLI）
# 加入：keepalive 防斷線 + 每輪自動 push GitHub
# 執行：bash test-parallel-100.sh 2>&1 | tee logs/parallel-report.txt

cd ~/ai-factory
mkdir -p logs .knowledge .agent-growth articles

TODAY=$(date +%Y-%m-%d)
TOTAL_PASS=0; TOTAL_FAIL=0; TOTAL_DONE=0
REPORT_FILE="logs/parallel-report.txt"
PROGRESS_FILE="logs/parallel-progress.json"

# ── 初始化進度檔 ──
echo '{"cycle":0,"total_done":0,"pass":0,"fail":0,"status":"running"}' > "$PROGRESS_FILE"

# ── Keepalive 防斷線（每 25 秒輸出一行） ──
keepalive_bg() {
  while true; do
    sleep 25
    echo "[⏱ $(date '+%H:%M:%S')] 後台運行中... cycle=${CURRENT_CYCLE:-0}/10 done=${TOTAL_DONE}/100"
  done
}
keepalive_bg &
KEEPALIVE_PID=$!
trap "kill $KEEPALIVE_PID 2>/dev/null; echo '測試中止'" EXIT

# ── 每輪自動 push GitHub ──
push_progress() {
  local CYCLE="$1"
  git add logs/ .agent-growth/ .knowledge/ articles/ 2>/dev/null
  git commit -m "Test progress: cycle ${CYCLE}/10 | ${TOTAL_PASS}✅ ${TOTAL_FAIL}❌" \
    --allow-empty 2>/dev/null
  git push origin master 2>/dev/null && echo "  [GitHub] Cycle ${CYCLE} 已推送" || echo "  [GitHub] Push 失敗（繼續測試）"
}

# ── 視覺化狀態板 ──
show_board() {
  local CYCLE="$1"
  echo ""
  echo "╔══════════════════════════════════════════════════════════╗"
  printf "║  🏭 AI 工廠 | Cycle %2d/10 | ✅%3d ❌%3d | 完成%3d/100  ║\n" \
    "$CYCLE" "$TOTAL_PASS" "$TOTAL_FAIL" "$TOTAL_DONE"
  echo "╠══════════════════════════════════════════════════════════╣"
  # 讀取每個 agent 今日更新數
  printf "║  %-16s %-5s %-16s %-5s %-10s ║\n" "Agent" "今日" "Agent" "今日" "Growth"
  echo "╠══════════════════════════════════════════════════════════╣"
  AGENTS_L=(researcher topic-selector writer seo-agent reviewer english-writer chinese-writer)
  AGENTS_R=(poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff)
  for i in "${!AGENTS_L[@]}"; do
    AL="${AGENTS_L[$i]}"; AR="${AGENTS_R[$i]:-}"
    CL=$(grep -c "\[$TODAY\]" ".agent-growth/${AL}.md" 2>/dev/null || echo 0)
    CR=$([ -n "$AR" ] && grep -c "\[$TODAY\]" ".agent-growth/${AR}.md" 2>/dev/null || echo "-")
    GL=$(wc -l < ".agent-growth/${AL}.md" 2>/dev/null || echo 0)
    printf "║  %-16s %-5s %-16s %-5s 行數:%-5s ║\n" "$AL" "${CL}次" "${AR:-}" "$CR次" "${GL}"
  done
  echo "╠══════════════════════════════════════════════════════════╣"
  LESSONS_LINES=$(wc -l < ".knowledge/lessons.md" 2>/dev/null || echo 0)
  ARTICLES=$(ls articles/parallel-c*.md 2>/dev/null | wc -l)
  REDDIT=$(ls logs/reddit-draft-c*.md 2>/dev/null | wc -l)
  DEVTO=$(ls logs/devto-draft-c*.md 2>/dev/null | wc -l)
  printf "║  📝 articles:%3d  📋 reddit:%3d  📰 devto:%3d  📚 lessons:%3d行 ║\n" \
    "$ARTICLES" "$REDDIT" "$DEVTO" "$LESSONS_LINES"
  echo "╚══════════════════════════════════════════════════════════╝"
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
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   100任務平行壓力測試 v2（修正：單 orchestrator）         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "開始：$(date)"
bash .claude/hooks/telegram-notify.sh "🏁 v2 測試開始｜單orchestrator多子agent｜keepalive已啟動" 2>/dev/null || true

# ════════════════════════════════════════════
# 主迴圈：10個 Cycle
# ════════════════════════════════════════════
for CYCLE in $(seq 1 10); do
  CURRENT_CYCLE=$CYCLE
  TOPIC="${TOPICS[$((CYCLE-1))]}"
  echo ""
  echo "══════ CYCLE ${CYCLE}/10：$TOPIC [$(date '+%H:%M:%S')] ══════"

  # ── BATCH A：researcher + revenue-scout（一個 orchestrator，兩個子 agent 平行）──
  echo "  [A] researcher + revenue-scout 平行..."
  BATCH_A_RESULT=$(timeout 180 claude -p "
你是主控 orchestrator。使用 Agent tool 同時呼叫以下兩個子 agent（可以連續呼叫，不需要等第一個完成才呼叫第二個）：

子 agent 1 — researcher：
任務：
1. 讀取 .agent-growth/researcher.md
2. 嘗試 WebFetch https://old.reddit.com/r/arduino/top.json?t=week&limit=3
3. 不論成功失敗，在 .agent-growth/researcher.md 加入（格式固定）：
   [$TODAY C${CYCLE}] 掃描：$TOPIC | Reddit:[成功/封鎖] | 備援:topic-tracker
4. 回報：RESEARCHER_DONE:C${CYCLE}

子 agent 2 — revenue-scout：
任務：
1. 讀取 .agent-growth/revenue-scout.md
2. 評估主題「$TOPIC」商業潛力（1-10分）
3. 在 .agent-growth/revenue-scout.md 加入：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力:[N]/10
4. 回報：SCOUT_DONE:C${CYCLE}

兩個都完成後，輸出：BATCH_A_DONE:C${CYCLE} R:[RESEARCHER_DONE/FAIL] S:[SCOUT_DONE/FAIL]
" --allowedTools "Agent,Read,Write,WebFetch,Bash" --max-turns 8 2>/dev/null)

  if echo "$BATCH_A_RESULT" | grep -q "BATCH_A_DONE"; then
    ok_count=$(echo "$BATCH_A_RESULT" | grep -o "DONE" | wc -l)
    echo "  ✅ Batch A 完成（$(echo "$BATCH_A_RESULT" | grep -o "BATCH_A_DONE.*" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    echo "  ❌ Batch A 失敗（輸出：$(echo "$BATCH_A_RESULT" | tail -2 | tr '\n' ' ')）"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi

  # ── BATCH B：topic-selector ──
  echo "  [B] topic-selector..."
  BATCH_B_RESULT=$(timeout 120 claude -p "
使用 Agent tool 呼叫 topic-selector 子 agent。
任務：
1. 讀取 .agent-growth/topic-selector.md
2. 本輪主題已定：$TOPIC
3. 執行重複檢查：bash .claude/hooks/duplicate-check.sh '${TOPIC:0:10}'
4. 在 .agent-growth/topic-selector.md 加入：
   [$TODAY C${CYCLE}] 選題：$TOPIC | 重複:[UNIQUE/DUPLICATE]
5. 輸出：BATCH_B_DONE:C${CYCLE} TOPIC_OK
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 2>/dev/null)

  if echo "$BATCH_B_RESULT" | grep -q "BATCH_B_DONE"; then
    echo "  ✅ Batch B 完成"
    TOTAL_PASS=$((TOTAL_PASS + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  else
    echo "  ❌ Batch B 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  fi

  # ── BATCH C：writer + english-writer + seo-agent 三路平行 ──
  echo "  [C] writer + english-writer + seo-agent 三路平行..."
  ART_PATH="articles/parallel-c${CYCLE}-$(date +%Y%m%d).md"
  EN_PATH="articles/parallel-c${CYCLE}-en-$(date +%Y%m%d).md"

  BATCH_C_RESULT=$(timeout 300 claude -p "
你是主控 orchestrator。依序呼叫以下三個子 agent（每個獨立，盡快呼叫全部）：

子 agent 1 — writer（最重要）：
1. 讀取 .agent-growth/writer.md，找出 [$TODAY C$((CYCLE-1))] 的記錄（上輪學習）
2. 寫 400-500 字 Arduino 教學：$TOPIC
3. 儲存到 $ART_PATH
4. 在 .agent-growth/writer.md 加入（格式固定，必須寫入）：
   [$TODAY C${CYCLE}] 主題：$TOPIC | 上輪引用：[是/否] | 字數：[N] | 本輪學習：[一句具體觀察]
5. 回報：WRITER_DONE:C${CYCLE} WORDS:[N]

子 agent 2 — english-writer：
1. 讀取 .agent-growth/english-writer.md
2. 寫英文 Reddit 版（300字），主題：$TOPIC，儲存到 $EN_PATH
3. 在 .agent-growth/english-writer.md 加入：
   [$TODAY C${CYCLE}] 英文版：$TOPIC | 字數:[N]
4. 回報：ENGLISH_DONE:C${CYCLE}

子 agent 3 — seo-agent：
1. 讀取 .agent-growth/seo-agent.md
2. 產生 3 個 SEO 標題，選出最佳版本
3. 在 .agent-growth/seo-agent.md 加入：
   [$TODAY C${CYCLE}] SEO：$TOPIC | 最佳標題：[版本]
4. 回報：SEO_DONE:C${CYCLE}

全部完成後輸出：BATCH_C_DONE:C${CYCLE} W:[DONE/FAIL] E:[DONE/FAIL] S:[DONE/FAIL]
" --allowedTools "Agent,Read,Write,Bash" --max-turns 20 2>/dev/null)

  if echo "$BATCH_C_RESULT" | grep -q "BATCH_C_DONE"; then
    echo "  ✅ Batch C 完成（$(echo "$BATCH_C_RESULT" | grep "BATCH_C_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  else
    echo "  ❌ Batch C 失敗（$(echo "$BATCH_C_RESULT" | tail -1)）"
    TOTAL_FAIL=$((TOTAL_FAIL + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  fi

  # ── BATCH D：reviewer + chinese-writer 平行 ──
  echo "  [D] reviewer + chinese-writer 平行..."
  BATCH_D_RESULT=$(timeout 240 claude -p "
你是主控 orchestrator。呼叫以下兩個子 agent：

子 agent 1 — reviewer：
1. 讀取 .agent-growth/reviewer.md
2. 讀取 $ART_PATH（若不存在，審查主題 $TOPIC 的標準描述）
3. 判斷 APPROVED 或 REJECTED，附 3 條理由
4. 在 .agent-growth/reviewer.md 加入（格式固定，必須寫入）：
   [$TODAY C${CYCLE}] 審查：$TOPIC | APPROVED/REJECTED | 主要問題：[一句]
5. 回報：REVIEWER_DONE:C${CYCLE} RESULT:[APPROVED/REJECTED]

子 agent 2 — chinese-writer：
1. 讀取 .agent-growth/chinese-writer.md
2. 讀取 $EN_PATH（若不存在，基於主題 $TOPIC 自行發揮）
3. 寫中文詮釋版（300字），儲存到 articles/parallel-c${CYCLE}-chi-$(date +%Y%m%d).md
4. 在 .agent-growth/chinese-writer.md 加入：
   [$TODAY C${CYCLE}] 詮釋：$TOPIC | 創新點：[和英文版差異]
5. 回報：CHINESE_DONE:C${CYCLE}

完成後輸出：BATCH_D_DONE:C${CYCLE} RV:[RESULT] CH:[DONE/FAIL]
" --allowedTools "Agent,Read,Write,Bash" --max-turns 10 2>/dev/null)

  REVIEW_RESULT=$(echo "$BATCH_D_RESULT" | grep -o "RESULT:[A-Z]*" | head -1 | cut -d: -f2)
  if echo "$BATCH_D_RESULT" | grep -q "BATCH_D_DONE"; then
    echo "  ✅ Batch D 完成 | 審查：${REVIEW_RESULT:-?}"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    echo "  ❌ Batch D 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi

  # ── BATCH E：poster + knowledge-subagent + feedback-collector 三路平行 ──
  echo "  [E] poster + knowledge-subagent + feedback-collector..."
  SIMULATED_UV=$((RANDOM % 50 + 5))
  SIMULATED_CM=$((RANDOM % 20 + 2))

  BATCH_E_RESULT=$(timeout 240 claude -p "
你是主控 orchestrator。呼叫以下三個子 agent：

子 agent 1 — poster：
1. 讀取 .agent-growth/poster.md
2. 產生 Reddit 草稿（r/arduino），儲存到 logs/reddit-draft-c${CYCLE}-$(date +%Y%m%d).md
3. 產生 dev.to 草稿（含 YAML front matter: title/published:false/tags），儲存到 logs/devto-draft-c${CYCLE}-$(date +%Y%m%d).md
4. 在 .agent-growth/poster.md 加入：
   [$TODAY C${CYCLE}] Reddit+devto：$TOPIC | 審查：${REVIEW_RESULT:-APPROVED}
5. 回報：POSTER_DONE:C${CYCLE}

子 agent 2 — knowledge-subagent：
1. 讀取 .agent-growth/knowledge-subagent.md
2. 讀取 .agent-growth/writer.md 的最後 3 行
3. 讀取 .agent-growth/reviewer.md 的最後 3 行
4. Append 到 .knowledge/lessons.md（建立檔案若不存在）：
   [$TODAY C${CYCLE}] $TOPIC | writer:$(grep "C${CYCLE}]" .agent-growth/writer.md 2>/dev/null | tail -1 | cut -c1-50) | reviewer:${REVIEW_RESULT:-?}
5. 在 .agent-growth/knowledge-subagent.md 加入：
   [$TODAY C${CYCLE}] 整合 writer+reviewer → lessons.md
6. 回報：KNOWLEDGE_DONE:C${CYCLE}

子 agent 3 — feedback-collector：
1. 讀取 .agent-growth/feedback-collector.md
2. 使用模擬數據：upvotes=$SIMULATED_UV comments=$SIMULATED_CM
3. 儲存到 logs/feedback-c${CYCLE}-$(date +%Y%m%d).json：{\"cycle\":$CYCLE,\"topic\":\"$TOPIC\",\"upvotes\":$SIMULATED_UV,\"comments\":$SIMULATED_CM,\"mode\":\"simulated\"}
4. 在 .agent-growth/feedback-collector.md 加入：
   [$TODAY C${CYCLE}] 回饋：$TOPIC | upvotes:$SIMULATED_UV comments:$SIMULATED_CM
5. 回報：FEEDBACK_DONE:C${CYCLE} UV:$SIMULATED_UV

完成後輸出：BATCH_E_DONE:C${CYCLE} P:[DONE/FAIL] K:[DONE/FAIL] F:[DONE/FAIL]
" --allowedTools "Agent,Read,Write,Bash" --max-turns 15 2>/dev/null)

  if echo "$BATCH_E_RESULT" | grep -q "BATCH_E_DONE"; then
    echo "  ✅ Batch E 完成（$(echo "$BATCH_E_RESULT" | grep "BATCH_E_DONE" | head -1)）"
    TOTAL_PASS=$((TOTAL_PASS + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  else
    echo "  ❌ Batch E 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 3)); TOTAL_DONE=$((TOTAL_DONE + 3))
  fi

  # ── BATCH F：style-updater + product-builder ──
  echo "  [F] style-updater + product-builder..."
  BATCH_F_RESULT=$(timeout 180 claude -p "
你是主控 orchestrator。呼叫以下兩個子 agent：

子 agent 1 — style-updater：
1. 讀取 .agent-growth/style-updater.md
2. 本輪回饋：upvotes=$SIMULATED_UV（${SIMULATED_UV} > 20 表現好）
3. 如果 upvotes > 20，在 .claude/skills/writing-style.md 末尾加一條觀察（## 自動更新 $TODAY C${CYCLE}）
4. 在 .agent-growth/style-updater.md 加入：
   [$TODAY C${CYCLE}] 分析：UV=$SIMULATED_UV | 風格更新：[有/無]
5. 回報：STYLE_DONE:C${CYCLE} ADJ:[yes/no]

子 agent 2 — product-builder：
1. 讀取 .agent-growth/product-builder.md
2. 評估「$TOPIC」做成 Whop 產品的可行性（1-10）
3. 在 .agent-growth/product-builder.md 加入：
   [$TODAY C${CYCLE}] 評估：$TOPIC | 潛力:[N]/10 | 決定:[做/跳過]
4. 如果潛力 ≥ 7，產生簡短產品大綱（3行）到 logs/product-c${CYCLE}.md
5. 回報：PRODUCT_DONE:C${CYCLE} SCORE:[N]

完成後輸出：BATCH_F_DONE:C${CYCLE} ST:[DONE/FAIL] PB:[DONE/FAIL]
" --allowedTools "Agent,Read,Write" --max-turns 10 2>/dev/null)

  if echo "$BATCH_F_RESULT" | grep -q "BATCH_F_DONE"; then
    echo "  ✅ Batch F 完成"
    TOTAL_PASS=$((TOTAL_PASS + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  else
    echo "  ❌ Batch F 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 2)); TOTAL_DONE=$((TOTAL_DONE + 2))
  fi

  # ── BATCH G：chief-of-staff 彙報 ──
  echo "  [G] chief-of-staff 彙報..."
  BATCH_G_RESULT=$(timeout 180 claude -p "
使用 Agent tool 呼叫 chief-of-staff 子 agent。
任務（第 $CYCLE/10 輪彙報）：
1. 讀取 .agent-growth/writer.md 最後 2 行
2. 讀取 .agent-growth/reviewer.md 最後 2 行
3. 在 .agent-growth/chief-of-staff.md 加入：
   [$TODAY C${CYCLE}] 第${CYCLE}輪：$TOPIC | UV:$SIMULATED_UV | 審查:${REVIEW_RESULT:-?} | 通過率:$((TOTAL_PASS * 100 / (TOTAL_DONE + 1)))%
4. 每 3 輪（第 3、6、9 輪）才發 Telegram，其他輪跳過：
   $([ $((CYCLE % 3)) -eq 0 ] && echo "執行：bash .claude/hooks/telegram-notify.sh '📊 第${CYCLE}/10輪完成｜✅${TOTAL_PASS} ❌${TOTAL_FAIL}｜UV:$SIMULATED_UV｜${TOPIC:0:15}'" || echo "本輪跳過 Telegram")
5. 最後輸出：BATCH_G_DONE:C${CYCLE} RATE:$((TOTAL_PASS * 100 / (TOTAL_DONE + 1)))%
" --allowedTools "Agent,Read,Write,Bash" --max-turns 5 2>/dev/null)

  if echo "$BATCH_G_RESULT" | grep -q "BATCH_G_DONE"; then
    RATE=$(echo "$BATCH_G_RESULT" | grep -o "RATE:[0-9]*%" | head -1)
    echo "  ✅ Batch G 完成 | ${RATE}"
    TOTAL_PASS=$((TOTAL_PASS + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  else
    echo "  ❌ Batch G 失敗"
    TOTAL_FAIL=$((TOTAL_FAIL + 1)); TOTAL_DONE=$((TOTAL_DONE + 1))
  fi

  # ── 更新進度 + push GitHub ──
  python3 -c "
import json,pathlib
f=pathlib.Path('$PROGRESS_FILE')
d={'cycle':$CYCLE,'total_done':$TOTAL_DONE,'pass':$TOTAL_PASS,'fail':$TOTAL_FAIL,'status':'running','topic':'$TOPIC'}
f.write_text(json.dumps(d,ensure_ascii=False))
" 2>/dev/null

  push_progress "$CYCLE"

  # ── 狀態板 ──
  show_board "$CYCLE"

  echo "  ── Cycle $CYCLE 完成 [$(date '+%H:%M:%S')] ✅${TOTAL_PASS} ❌${TOTAL_FAIL} 共${TOTAL_DONE}任務 ──"
done

# ════════════════════════════════════════════
# 最終報告
# ════════════════════════════════════════════
kill $KEEPALIVE_PID 2>/dev/null
trap - EXIT

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   100任務測試最終報告                                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "完成：$(date)"
FINAL_RATE=$(echo "scale=1; $TOTAL_PASS * 100 / ($TOTAL_DONE + 1)" | bc 2>/dev/null || echo "?")
echo "  總任務：$TOTAL_DONE  ✅$TOTAL_PASS  ❌$TOTAL_FAIL  通過率：${FINAL_RATE}%"
echo ""
echo "── Agent Growth 最終增長 ──"
for a in researcher topic-selector writer seo-agent reviewer english-writer chinese-writer \
         poster feedback-collector style-updater knowledge-subagent revenue-scout product-builder chief-of-staff; do
  S=${GROWTH_START[$a]:-0}
  E=$(wc -l < ".agent-growth/$a.md" 2>/dev/null || echo 0)
  TC=$(grep -c "\[$TODAY\]" ".agent-growth/$a.md" 2>/dev/null || echo 0)
  BAR=$(printf '▓%.0s' $(seq 1 $((TC > 20 ? 20 : TC))))
  [ "$TC" -ge 8 ] && ICON="✅" || { [ "$TC" -ge 3 ] && ICON="⚠️ " || ICON="❌"; }
  printf "  %s %-20s +%-3d行  今日:%2d次  %s\n" "$ICON" "$a" "$((E-S))" "$TC" "$BAR"
done

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
git commit -m "Test COMPLETE: ${TOTAL_PASS}✅ ${TOTAL_FAIL}❌ rate:${FINAL_RATE}% | 100-task parallel test" 2>/dev/null
git push origin master 2>/dev/null

bash .claude/hooks/telegram-notify.sh "🎯 100任務測試完成！通過率${FINAL_RATE}% | ✅${TOTAL_PASS} ❌${TOTAL_FAIL} | 14個agent全程運作 | logs在GitHub" 2>/dev/null || true
echo ""
echo "✅ 所有結果已推送到 GitHub，查看 logs/parallel-report.txt"
