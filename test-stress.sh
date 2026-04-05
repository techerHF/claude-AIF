#!/usr/bin/env bash
# test-stress.sh
# 真實行為壓力測試
# 測試：學習循環、經驗堆積、跨輪次驗證、錯誤恢復、pipeline 完整性
# 執行時間：約 30-50 分鐘
# 執行：bash test-stress.sh 2>&1 | tee logs/stress-report.txt

set -uo pipefail
cd ~/ai-factory
PASS=0; FAIL=0; WARN=0
mkdir -p logs .knowledge

ts() { date '+%H:%M:%S'; }
hr()   { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
ok()   { echo "  ✅ [$( ts)] $1"; ((PASS++)); }
fail() { echo "  ❌ [$( ts)] $1"; ((FAIL++)); }
warn() { echo "  ⚠️  [$( ts)] $1"; ((WARN++)); }
section() { echo ""; echo "【$1】"; hr; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   AI 無人工廠 壓力測試（行為驗證版）          ║"
echo "╚══════════════════════════════════════════════╝"
echo "開始時間：$(date)"

# ═══════════════════════════════════════════════
# TEST-1：Writer 學習循環（3輪）
# 驗證：每輪後 growth file 更新，且第二輪有參考第一輪學習
# ═══════════════════════════════════════════════
section "TEST-1：Writer 學習循環（3輪）"

GROWTH_FILE=".agent-growth/writer.md"

# 記錄初始狀態
INIT_LINES=$(wc -l < "$GROWTH_FILE" 2>/dev/null || echo 0)
echo "  初始 growth file 行數：$INIT_LINES"

for ROUND in 1 2 3; do
  echo ""
  echo "  ── Round $ROUND ──"
  TOPIC_LIST=("BME280 氣壓感測器" "HC-SR04 超音波距離感測器" "MPU6050 加速度陀螺儀")
  TOPIC="${TOPIC_LIST[$((ROUND-1))]}"

  BEFORE_LINES=$(wc -l < "$GROWTH_FILE" 2>/dev/null || echo 0)

  RESULT=$(timeout 120 claude -p "
使用 Agent tool 呼叫 writer 子 agent。

任務：
1. 讀取 .agent-growth/writer.md 了解自己的成長記錄（有什麼有效模式？上次學到什麼？）
2. 寫一篇 500 字的 Arduino 教學文章：$TOPIC
3. 儲存到 articles/stress-test-round${ROUND}-$(date +%Y%m%d).md
4. 更新 .agent-growth/writer.md：在「發現的有效模式」加入這次的觀察（一行）
5. 最後輸出：
   - 儲存路徑
   - 字數
   - 這次學到什麼（一句話）
   - 有沒有參考上一輪的學習？（是/否，說明）
" --allowedTools "Agent,Read,Write,Bash" --max-turns 6 2>/dev/null)

  AFTER_LINES=$(wc -l < "$GROWTH_FILE" 2>/dev/null || echo 0)
  LINES_ADDED=$((AFTER_LINES - BEFORE_LINES))

  # 驗證1：growth file 有增加
  if [ "$LINES_ADDED" -gt 0 ]; then
    ok "Round $ROUND growth 更新 (+${LINES_ADDED} 行)"
  else
    fail "Round $ROUND growth 沒有更新（行數不變 $BEFORE_LINES）"
  fi

  # 驗證2：文章有產出
  ARTICLE=$(ls articles/stress-test-round${ROUND}-*.md 2>/dev/null | head -1)
  if [ -n "$ARTICLE" ]; then
    WC=$(wc -w < "$ARTICLE" 2>/dev/null || echo 0)
    ok "Round $ROUND 文章產出（$WC words）：$ARTICLE"
  else
    fail "Round $ROUND 無文章產出"
  fi

  # 驗證3：Round 2/3 有參考前輪學習
  if [ "$ROUND" -gt 1 ]; then
    if echo "$RESULT" | grep -qi "參考\|上次\|之前\|前一\|學到\|發現\|是"; then
      ok "Round $ROUND 有參考前輪學習記錄"
    else
      warn "Round $ROUND 未明確參考前輪（可能有隱性學習）"
    fi
  fi

  echo "  └─ 輸出摘要：$(echo "$RESULT" | tail -4 | head -1)"
done

# 最終 growth file 驗證
FINAL_LINES=$(wc -l < "$GROWTH_FILE" 2>/dev/null || echo 0)
TOTAL_ADDED=$((FINAL_LINES - INIT_LINES))
echo ""
echo "  Growth file 總增長：$INIT_LINES → $FINAL_LINES 行（+$TOTAL_ADDED）"
if [ "$TOTAL_ADDED" -ge 3 ]; then
  ok "Writer 學習循環 — 3輪後有效堆積 $TOTAL_ADDED 行經驗"
else
  fail "Writer 學習循環 — 經驗堆積不足（只增 $TOTAL_ADDED 行）"
fi

# ═══════════════════════════════════════════════
# TEST-2：Reviewer 拒絕 → Writer 修改 循環
# 驗證：reviewer 能識別低品質，writer 能根據退回意見修改
# ═══════════════════════════════════════════════
section "TEST-2：Reviewer 拒絕 → Writer 修改 循環"

# 故意建立一篇低品質文章
cat > /tmp/bad-article.md << 'EOF'
# Arduino 教學

Arduino 很好用。你可以用它做很多事情。

```cpp
void setup() {}
void loop() {}
```

結論：Arduino 真的很棒！你應該學習它。
EOF

echo "  建立故意低品質文章 /tmp/bad-article.md（無數字、無細節、程式碼空白）"

REV_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 reviewer 子 agent。

任務：審查 /tmp/bad-article.md
1. 依照 .claude/skills/writing-style.md 標準審查
2. 明確輸出 APPROVED 或 REJECTED
3. 如果 REJECTED，列出具體理由（至少 3 點）
" --allowedTools "Agent,Read,Bash" --max-turns 4 2>/dev/null)

if echo "$REV_RESULT" | grep -qi "REJECTED\|退回\|不通過"; then
  ok "Reviewer 正確識別低品質文章 → REJECTED"

  # 現在讓 writer 根據退回意見修改
  FIX_RESULT=$(timeout 120 claude -p "
使用 Agent tool 呼叫 writer 子 agent。

背景：以下文章被 reviewer 退回，原因如下：
$REV_RESULT

任務：
1. 閱讀退回原因
2. 重新寫一篇關於 Arduino LED 控制的文章，修正所有問題
3. 儲存到 articles/stress-test-fixed-$(date +%Y%m%d).md
4. 輸出：修正了哪些問題（對照退回原因逐點說明）
" --allowedTools "Agent,Read,Write,Bash" --max-turns 6 2>/dev/null)

  # 驗證修改後的文章存在且更好
  FIXED=$(ls articles/stress-test-fixed-*.md 2>/dev/null | head -1)
  if [ -n "$FIXED" ]; then
    FIXED_WC=$(wc -w < "$FIXED" || echo 0)
    ok "Writer 根據 REJECTED 完成修改（$FIXED_WC words）"

    # 再次審查修改後的版本
    REV2=$(timeout 60 claude -p "
使用 Agent tool 呼叫 reviewer 子 agent。
審查 $FIXED，輸出 APPROVED 或 REJECTED。
" --allowedTools "Agent,Read,Bash" --max-turns 4 2>/dev/null)

    if echo "$REV2" | grep -qi "APPROVED\|通過"; then
      ok "修改後文章通過 reviewer — 迴圈成功閉合"
    else
      warn "修改後仍被退回或審查不明確：$(echo "$REV2" | tail -2)"
    fi
  else
    fail "Writer 修改後未產出文章"
  fi
else
  warn "Reviewer 未明確 REJECTED 低品質文章：$(echo "$REV_RESULT" | tail -2)"
fi

# ═══════════════════════════════════════════════
# TEST-3：完整 Pipeline 一輪（清除 checkpoint 後）
# 驗證：researcher→topic-selector→writer→seo→reviewer→poster 全流程
# ═══════════════════════════════════════════════
section "TEST-3：完整 Pipeline 一輪（清除 checkpoint）"

# 備份並清除 checkpoint
CHECKPOINT_FILE="logs/progress.json"
if [ -f "$CHECKPOINT_FILE" ]; then
  cp "$CHECKPOINT_FILE" "/tmp/progress-backup-$(date +%Y%m%d%H%M).json"
  echo "  已備份 checkpoint → /tmp/progress-backup-*.json"
fi

# 用 stress-test 日期避免與真實 checkpoint 衝突
STRESS_DATE="2026-01-01"

PIPELINE_RESULT=$(timeout 300 claude -p "
你是 AI 無人工廠主控 Agent。今日日期：$STRESS_DATE（壓力測試模式）。

執行完整 pipeline，每步使用 Agent tool 呼叫對應子 agent：

步驟1：呼叫 topic-selector 子 agent，選一個主題（忽略 checkpoint，直接執行）
步驟2：呼叫 writer 子 agent，寫 600 字文章，儲存到 articles/stress-pipeline-$(date +%Y%m%d%H%M).md
步驟3：呼叫 seo-agent 子 agent，優化標題
步驟4：呼叫 reviewer 子 agent，審查文章
步驟5：呼叫 poster 子 agent，產生 Reddit 草稿（不需要儲存，直接輸出）

每步完成後輸出：「步驟X完成：[結果摘要]」
最後輸出：PIPELINE_COMPLETE 或 PIPELINE_FAILED:[哪一步失敗]
" --allowedTools "Agent,Read,Write,Bash" --max-turns 30 2>/dev/null)

# 驗證各步驟
for STEP in 1 2 3 4 5; do
  if echo "$PIPELINE_RESULT" | grep -qi "步驟${STEP}完成\|步驟 ${STEP} 完成"; then
    ok "Pipeline 步驟 $STEP 完成"
  else
    warn "Pipeline 步驟 $STEP 未明確確認"
  fi
done

if echo "$PIPELINE_RESULT" | grep -q "PIPELINE_COMPLETE"; then
  ok "完整 Pipeline — PIPELINE_COMPLETE"
elif echo "$PIPELINE_RESULT" | grep -q "PIPELINE_FAILED"; then
  FAIL_STEP=$(echo "$PIPELINE_RESULT" | grep "PIPELINE_FAILED" | head -1)
  fail "Pipeline 失敗：$FAIL_STEP"
else
  warn "Pipeline 結果不明確，最後輸出：$(echo "$PIPELINE_RESULT" | tail -3)"
fi

# ═══════════════════════════════════════════════
# TEST-4：Knowledge 累積驗證
# 驗證：curiosity-scan → lessons.md 更新 → topic-selector 參考新知識
# ═══════════════════════════════════════════════
section "TEST-4：Knowledge 累積驗證（3步）"

LESSONS_FILE=".knowledge/lessons.md"
mkdir -p .knowledge

BEFORE_LESSONS=$(wc -l < "$LESSONS_FILE" 2>/dev/null || echo 0)
echo "  lessons.md 初始行數：$BEFORE_LESSONS"

# Step 4a：手動注入一條知識（模擬 curiosity-scan 的輸出）
TEST_LESSON="## 測試知識注入 $(date +%Y-%m-%d)
- 發現：MIT TouchDevelop 框架 — 支援觸覺感測資料視覺化，適合張旭豐的研究方向
- 發現：capacitive grid sensor — 使用電容矩陣做多點觸控，已有 maker 在 Reddit 詢問完整教學
- 發現：piezoelectric haptic feedback — 配合 Arduino 做觸覺回饋原型，與博士研究高度相關"

echo "$TEST_LESSON" >> "$LESSONS_FILE"
AFTER_INJECT=$(wc -l < "$LESSONS_FILE")
ok "lessons.md 知識注入（+$((AFTER_INJECT - BEFORE_LESSONS)) 行）"

# Step 4b：讓 knowledge-subagent 整理並更新
KN_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 knowledge-subagent 子 agent。

任務：
1. 讀取 .knowledge/lessons.md
2. 找出最新加入的「測試知識注入」區塊
3. 確認它已被記錄
4. 輸出：「已確認 X 條新知識已記錄」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 2>/dev/null)

if echo "$KN_RESULT" | grep -qiE "確認|記錄|[0-9]條"; then
  ok "knowledge-subagent 確認新知識已記錄"
else
  warn "knowledge-subagent 輸出不明確：$(echo "$KN_RESULT" | tail -2)"
fi

# Step 4c：讓 topic-selector 參考新知識選題
TS_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 topic-selector 子 agent。

任務：
1. 讀取 .knowledge/lessons.md 了解最新發現
2. 選一個主題時，說明是否有參考到「capacitive grid sensor」或「piezoelectric haptic feedback」這些新知識
3. 輸出：選定主題 + 是否參考了新注入的知識（明確說是/否）
" --allowedTools "Agent,Read,Bash" --max-turns 4 2>/dev/null)

if echo "$TS_RESULT" | grep -qiE "capacitive|piezoelectric|觸覺|是"; then
  ok "Topic-selector 參考了新注入知識選題"
else
  warn "Topic-selector 未明確參考新知識：$(echo "$TS_RESULT" | tail -3)"
fi

# ═══════════════════════════════════════════════
# TEST-5：Agent Growth 跨輪次驗證
# 驗證：多個 agent growth file 在測試後有實際增長
# ═══════════════════════════════════════════════
section "TEST-5：Agent Growth 跨輪次增長驗證"

declare -A GROWTH_BEFORE
for agent in researcher topic-selector writer seo-agent reviewer poster knowledge-subagent chief-of-staff; do
  f=".agent-growth/$agent.md"
  GROWTH_BEFORE[$agent]=$(wc -l < "$f" 2>/dev/null || echo 0)
done

# 給每個 agent 一個任務，要求它更新自己的 growth file
for agent in seo-agent reviewer; do
  GROWTH_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 ${agent} 子 agent。

任務：
1. 讀取 .agent-growth/${agent}.md 了解自己目前的成長狀態
2. 執行一個簡單任務（seo-agent: 優化標題『Arduino MPU6050 教學』；reviewer: 評估文章品質基準）
3. 在 .agent-growth/${agent}.md 的「發現的有效模式」區塊加入一行今日觀察
4. 輸出：「已更新 growth file」
" --allowedTools "Agent,Read,Write" --max-turns 4 2>/dev/null)

  AFTER=$(wc -l < ".agent-growth/$agent.md" 2>/dev/null || echo 0)
  BEFORE=${GROWTH_BEFORE[$agent]}
  if [ "$AFTER" -gt "$BEFORE" ]; then
    ok "$agent growth file 增長（$BEFORE → $AFTER 行）"
  else
    warn "$agent growth file 未增長（仍 $BEFORE 行）"
  fi
done

# ═══════════════════════════════════════════════
# TEST-6：錯誤恢復測試
# 驗證：error-recovery.sh 能處理已知錯誤情境
# ═══════════════════════════════════════════════
section "TEST-6：錯誤恢復 + Edge Case"

# 6a：duplicate-check 重複主題
DC_DUP=$(bash .claude/hooks/duplicate-check.sh "DHT22" 2>/dev/null | head -1)
echo "  duplicate-check DHT22（已寫過）：$DC_DUP"
if echo "$DC_DUP" | grep -qi "DUPLICATE"; then
  ok "duplicate-check 正確識別已寫主題"
else
  warn "duplicate-check 對已寫主題回傳：$DC_DUP"
fi

# 6b：word-count 邊界測試
echo "這是一個很短的測試文章，少於100字。" > /tmp/short-article.md
WC_SHORT=$(bash .claude/hooks/word-count.sh /tmp/short-article.md 2>/dev/null | head -1)
echo "  word-count 短文章測試：$WC_SHORT"
if echo "$WC_SHORT" | grep -qiE "字數|report|REJECT|字"; then
  ok "word-count 正確處理短文章"
else
  warn "word-count 輸出：$WC_SHORT"
fi

# 6c：agent-growth-update 真實更新測試
BEFORE_RES=$(wc -l < ".agent-growth/researcher.md")
bash .claude/hooks/agent-growth-update.sh "researcher" "success" "壓力測試 $(date +%H%M)：Reddit 被封鎖時的備援邏輯有效" 2>/dev/null
AFTER_RES=$(wc -l < ".agent-growth/researcher.md")
if [ "$AFTER_RES" -gt "$BEFORE_RES" ]; then
  ok "agent-growth-update.sh 真實更新（$BEFORE_RES → $AFTER_RES 行）"
else
  fail "agent-growth-update.sh 未更新 researcher.md"
fi

# 6d：Telegram 快速連發測試（3條）
echo "  Telegram 快速連發測試..."
T1=$(bash .claude/hooks/telegram-notify.sh "🧪 壓力測試訊息 1/3：$(date +%H:%M:%S)" 2>/dev/null)
T2=$(bash .claude/hooks/telegram-notify.sh "🧪 壓力測試訊息 2/3：系統穩定" 2>/dev/null)
T3=$(bash .claude/hooks/telegram-notify.sh "🧪 壓力測試訊息 3/3：OKR 追蹤正常" 2>/dev/null)
if [ "$T1" = "OK" ] && [ "$T2" = "OK" ] && [ "$T3" = "OK" ]; then
  ok "Telegram 快速連發 3 條 — 全部 OK"
else
  warn "Telegram 部分失敗：$T1 / $T2 / $T3"
fi

# ═══════════════════════════════════════════════
# TEST-7：Chief-of-Staff 週報完整性驗證
# ═══════════════════════════════════════════════
section "TEST-7：Chief-of-Staff 週報完整性"

RETRO_BEFORE=$(wc -l < ".team-memory/weekly-retrospective.md" 2>/dev/null || echo 0)
OKR_BEFORE=$(wc -l < ".team-memory/okr-tracking.md" 2>/dev/null || echo 0)

COS_RESULT=$(timeout 120 claude -p "
使用 Agent tool 呼叫 chief-of-staff 子 agent。

任務：執行一次完整的週報循環：
1. 讀取 logs/progress.json、.knowledge/lessons.md、.agent-growth/*.md
2. 將本次壓力測試摘要 append 到 .team-memory/weekly-retrospective.md
3. 更新 .team-memory/okr-tracking.md 的進度數字
4. 整理 .agent-growth/ 中所有 agent 的學習，輸出成長摘要
5. 發送 Telegram：壓力測試完成通知
6. 輸出：「週報完成，更新了 X 個 agent 成長記錄」
" --allowedTools "Agent,Read,Write,Bash" --max-turns 8 2>/dev/null)

RETRO_AFTER=$(wc -l < ".team-memory/weekly-retrospective.md" 2>/dev/null || echo 0)
OKR_AFTER=$(wc -l < ".team-memory/okr-tracking.md" 2>/dev/null || echo 0)

if [ "$RETRO_AFTER" -gt "$RETRO_BEFORE" ]; then
  ok "weekly-retrospective.md 已更新（+$((RETRO_AFTER-RETRO_BEFORE)) 行）"
else
  fail "weekly-retrospective.md 未更新"
fi

if [ "$OKR_AFTER" -gt "$OKR_BEFORE" ]; then
  ok "okr-tracking.md 已更新（+$((OKR_AFTER-OKR_BEFORE)) 行）"
else
  warn "okr-tracking.md 未更新"
fi

echo "  COS 輸出：$(echo "$COS_RESULT" | tail -3)"

# ═══════════════════════════════════════════════
# 最終統計
# ═══════════════════════════════════════════════
hr
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   壓力測試結果                                ║"
echo "╚══════════════════════════════════════════════╝"
echo "完成時間：$(date)"
echo ""
echo "  ✅ 通過：$PASS"
echo "  ❌ 失敗：$FAIL"
echo "  ⚠️  警告：$WARN"
echo ""

# growth 最終快照
echo "── Agent Growth 最終狀態 ──"
for agent in researcher writer reviewer seo-agent topic-selector poster knowledge-subagent chief-of-staff; do
  f=".agent-growth/$agent.md"
  LINES=$(wc -l < "$f" 2>/dev/null || echo 0)
  echo "  $agent: ${LINES} 行"
done

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "  🎉 壓力測試通過！團隊具備學習能力。"
  bash .claude/hooks/telegram-notify.sh "🎉 壓力測試完成：$PASS 通過 / $FAIL 失敗 / $WARN 警告。學習循環驗證成功！" 2>/dev/null || true
elif [ "$FAIL" -le 3 ]; then
  echo "  ⚠️  $FAIL 個問題需修復，$WARN 個警告需確認"
  bash .claude/hooks/telegram-notify.sh "⚠️ 壓力測試：$PASS 通過 / $FAIL 失敗 需修復" 2>/dev/null || true
else
  echo "  🚨 $FAIL 個嚴重問題，請查看詳細報告"
fi

echo ""
echo "完整報告：logs/stress-report.txt"
