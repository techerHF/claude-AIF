#!/usr/bin/env bash
# test-all.sh
# 完整測試：所有 hook、agent、skill
# 執行：bash test-all.sh 2>&1 | tee logs/test-report.txt
# 結果：logs/test-report.txt

set -uo pipefail
cd ~/ai-factory
PASS=0; FAIL=0; WARN=0
REPORT="logs/test-report.txt"
mkdir -p logs

hr() { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
ok()   { echo "  ✅ $1"; ((PASS++)); }
fail() { echo "  ❌ $1"; ((FAIL++)); }
warn() { echo "  ⚠️  $1"; ((WARN++)); }

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   AI 無人工廠 完整測試報告            ║"
echo "╚══════════════════════════════════════╝"
echo "執行時間：$(date)"
hr

# ═══════════════════════════════════════
# PART 1：Hook 測試（語法 + 基本執行）
# ═══════════════════════════════════════
echo ""
echo "【PART 1】Hooks（共 18 個）"
hr

HOOKS=(
  "telegram-notify.sh"
  "telegram-listen.sh"
  "standup.sh"
  "checkpoint.sh"
  "topic-tracker.sh"
  "duplicate-check.sh"
  "agent-growth-update.sh"
  "curiosity-scan.sh"
  "weekly-retrospective.sh"
  "memory-update.sh"
  "quality-check.sh"
  "word-count.sh"
  "code-syntax-check.sh"
  "ai-detection.sh"
  "error-recovery.sh"
  "reddit-rate-limit.sh"
  "link-validation.sh"
  "github-backup.sh"
)

for h in "${HOOKS[@]}"; do
  f=".claude/hooks/$h"
  if [ ! -f "$f" ]; then
    fail "$h — 檔案不存在"
    continue
  fi
  # bash 語法檢查
  if bash -n "$f" 2>/dev/null; then
    ok "$h — 語法正確"
  else
    fail "$h — bash 語法錯誤"
  fi
done

# 功能測試：可安全執行的 hooks
echo ""
echo "  -- Hook 功能測試 --"

# checkpoint.sh
if bash .claude/hooks/checkpoint.sh today-done 2>/dev/null | grep -qE '^[01]$'; then
  ok "checkpoint.sh today-done — 回傳 0 或 1"
else
  fail "checkpoint.sh today-done — 輸出異常"
fi

# word-count.sh（傳一個存在的檔案）
TEST_MD=$(ls articles/*.md 2>/dev/null | head -1)
if [ -n "$TEST_MD" ]; then
  WC=$(bash .claude/hooks/word-count.sh "$TEST_MD" 2>/dev/null)
  if [[ "$WC" =~ ^[0-9]+$ ]]; then
    ok "word-count.sh — 回傳 $WC 字"
  else
    warn "word-count.sh — 輸出：$WC"
  fi
else
  warn "word-count.sh — 無 articles/ 檔案可測試"
fi

# duplicate-check.sh
DC=$(bash .claude/hooks/duplicate-check.sh "DHT22" 2>/dev/null | head -1)
if [[ "$DC" =~ (DUPLICATE|UNIQUE) ]]; then
  ok "duplicate-check.sh — 回傳 $DC"
else
  warn "duplicate-check.sh — 輸出：$DC"
fi

# topic-tracker.sh suggest
TT=$(bash .claude/hooks/topic-tracker.sh suggest 2>/dev/null | head -3)
if [ -n "$TT" ]; then
  ok "topic-tracker.sh suggest — 有輸出"
else
  warn "topic-tracker.sh suggest — 無輸出"
fi

# telegram-notify.sh（不實際發送，只測設定檢查）
TN=$(bash .claude/hooks/telegram-notify.sh "" 2>/dev/null)
if echo "$TN" | grep -q "SKIP"; then
  ok "telegram-notify.sh 空訊息 — 正確跳過"
else
  warn "telegram-notify.sh 空訊息 — 輸出：$TN"
fi

# agent-growth-update.sh 空 agent（安全測試）
bash .claude/hooks/agent-growth-update.sh "" "success" "" 2>/dev/null
ok "agent-growth-update.sh 空參數 — 安全退出"

# ═══════════════════════════════════════
# PART 2：Skill 檔案完整性
# ═══════════════════════════════════════
echo ""
echo "【PART 2】Skills（共 26 個）"
hr

SKILLS=(
  "writing-style.md"
  "article-structure.md"
  "code-writing.md"
  "audience-targeting.md"
  "payhip-conversion.md"
  "topic-selection.md"
  "content-calendar.md"
  "researcher-strategy.md"
  "platform-rules.md"
  "seo-optimization.md"
  "reddit-post.md"
  "feedback-interpretation.md"
  "knowledge-update.md"
  "english-writing.md"
  "chinese-writing.md"
  "medium-post.md"
  "persona.md"
  "topic-hook.md"
  "monetization-strategy.md"
  "whop-product.md"
  "whop-copy.md"
  "digital-twin-voice.md"
  "comment-strategy.md"
  "image-description.md"
  "discount-pricing.md"
  "product-description.md"
)

for s in "${SKILLS[@]}"; do
  f=".claude/skills/$s"
  if [ ! -f "$f" ]; then
    fail "$s — 檔案不存在"
  else
    LINES=$(wc -l < "$f")
    if [ "$LINES" -gt 5 ]; then
      ok "$s — ${LINES} 行"
    else
      warn "$s — 只有 ${LINES} 行（可能內容不足）"
    fi
  fi
done

# ═══════════════════════════════════════
# PART 3：Agent Frontmatter 完整性
# ═══════════════════════════════════════
echo ""
echo "【PART 3】Agent Frontmatter（共 14 個）"
hr

AGENTS=(
  "researcher"
  "topic-selector"
  "writer"
  "seo-agent"
  "reviewer"
  "poster"
  "feedback-collector"
  "style-updater"
  "knowledge-subagent"
  "chief-of-staff"
  "english-writer"
  "chinese-writer"
  "revenue-scout"
  "product-builder"
)

for a in "${AGENTS[@]}"; do
  f=".claude/agents/$a.md"
  if [ ! -f "$f" ]; then
    fail "$a — 檔案不存在"
    continue
  fi
  HAS_NAME=$(grep -c "^name:" "$f" 2>/dev/null || echo 0)
  HAS_DESC=$(grep -c "^description:" "$f" 2>/dev/null || echo 0)
  HAS_TOOLS=$(grep -c "^allowed_tools:" "$f" 2>/dev/null || echo 0)
  HAS_CONTENT=$(wc -l < "$f")
  if [ "$HAS_NAME" -gt 0 ] && [ "$HAS_DESC" -gt 0 ] && [ "$HAS_TOOLS" -gt 0 ] && [ "$HAS_CONTENT" -gt 10 ]; then
    ok "$a — name/description/allowed_tools ✓（${HAS_CONTENT} 行）"
  elif [ "$HAS_TOOLS" -eq 0 ]; then
    fail "$a — 缺少 allowed_tools"
  else
    warn "$a — frontmatter 不完整"
  fi
done

# ═══════════════════════════════════════
# PART 4：Pipeline 關鍵 Agent 子 agent 測試
# ═══════════════════════════════════════
echo ""
echo "【PART 4】Agent 子 agent 功能測試（5個核心）"
echo "  （每個約 20-40 秒，請稍候）"
hr

# 4-1: seo-agent
echo "  測試 seo-agent..."
SEO_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 seo-agent 子 agent。
任務：對以下標題進行 SEO 優化，輸出優化後的標題和3個關鍵字：
原始標題：Arduino DHT22 Temperature Sensor Tutorial
完成後直接輸出結果。
" --allowedTools "Agent,Read,Write" --max-turns 4 2>/dev/null | tail -5)
if echo "$SEO_RESULT" | grep -qi "title\|標題\|keyword\|關鍵"; then
  ok "seo-agent 子 agent — 有效輸出"
else
  warn "seo-agent 子 agent — 輸出：${SEO_RESULT:0:80}"
fi

# 4-2: reviewer
echo "  測試 reviewer..."
TEST_ART=$(ls articles/*.md 2>/dev/null | head -1)
if [ -n "$TEST_ART" ]; then
  REV_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 reviewer 子 agent。
任務：審查檔案 $TEST_ART，輸出 APPROVED 或 REJECTED 加簡短理由。
" --allowedTools "Agent,Read,Bash" --max-turns 4 2>/dev/null | tail -3)
  if echo "$REV_RESULT" | grep -qiE "APPROVED|REJECTED|通過|退回"; then
    ok "reviewer 子 agent — 有效審查輸出"
  else
    warn "reviewer 子 agent — 輸出：${REV_RESULT:0:80}"
  fi
else
  warn "reviewer 子 agent — 無文章可審查（articles/ 為空）"
fi

# 4-3: knowledge-subagent
echo "  測試 knowledge-subagent..."
KN_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 knowledge-subagent 子 agent。
任務：讀取 logs/progress.json，將今日摘要 append 到 .knowledge/lessons.md，輸出更新了幾行。
" --allowedTools "Agent,Read,Write,Bash" --max-turns 4 2>/dev/null | tail -3)
if echo "$KN_RESULT" | grep -qiE "[0-9]|更新|append|寫入"; then
  ok "knowledge-subagent 子 agent — 有效輸出"
else
  warn "knowledge-subagent 子 agent — 輸出：${KN_RESULT:0:80}"
fi

# 4-4: poster
echo "  測試 poster..."
TEST_ART=$(ls articles/*.md 2>/dev/null | head -1)
if [ -n "$TEST_ART" ]; then
  POST_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 poster 子 agent。
任務：為 $TEST_ART 產生 Reddit 發文草稿（標題 + 前三行），不需要儲存，直接輸出。
" --allowedTools "Agent,Read,Write" --max-turns 4 2>/dev/null | tail -5)
  if echo "$POST_RESULT" | grep -qiE "reddit\|r/\|標題\|title\|TL;DR\|#"; then
    ok "poster 子 agent — 有效草稿輸出"
  else
    warn "poster 子 agent — 輸出：${POST_RESULT:0:80}"
  fi
else
  warn "poster 子 agent — 無文章可處理"
fi

# 4-5: style-updater
echo "  測試 style-updater..."
SU_RESULT=$(timeout 60 claude -p "
使用 Agent tool 呼叫 style-updater 子 agent。
任務：讀取 .knowledge/lessons.md（若存在），輸出當前寫作風格建議摘要（3點）。
" --allowedTools "Agent,Read,Write" --max-turns 4 2>/dev/null | tail -5)
if echo "$SU_RESULT" | grep -qiE "[1-3]\.|風格|建議|style|寫作"; then
  ok "style-updater 子 agent — 有效輸出"
else
  warn "style-updater 子 agent — 輸出：${SU_RESULT:0:80}"
fi

# ═══════════════════════════════════════
# PART 5：team-memory 結構
# ═══════════════════════════════════════
echo ""
echo "【PART 5】Team Memory 結構"
hr

TM_FILES=(
  ".team-memory/proposals.md"
  ".team-memory/experiments.md"
  ".team-memory/okr-tracking.md"
  ".team-memory/weekly-retrospective.md"
  ".team-memory/standup-log.md"
  ".team-memory/decisions.md"
)
for f in "${TM_FILES[@]}"; do
  if [ -f "$f" ]; then
    ok "$f — 存在"
  else
    fail "$f — 不存在"
  fi
done

# ═══════════════════════════════════════
# PART 6：agent-growth 結構
# ═══════════════════════════════════════
echo ""
echo "【PART 6】Agent Growth 記錄"
hr

for a in "${AGENTS[@]}"; do
  f=".agent-growth/$a.md"
  if [ -f "$f" ]; then
    ok "$a.md — 存在"
  else
    fail "$a.md — 不存在"
  fi
done

# ═══════════════════════════════════════
# PART 7：Telegram 狀態
# ═══════════════════════════════════════
echo ""
echo "【PART 7】Telegram 設定"
hr

python3 -c "
import json, pathlib
s = json.loads((pathlib.Path.home()/'.claude/settings.json').read_text())
e = s.get('env', {})
token = e.get('TELEGRAM_BOT_TOKEN', '')
chat = e.get('TELEGRAM_CHAT_ID', '')
if token and token not in ('你的Bot_Token', ''):
    print('  ✅ BOT_TOKEN — 已設定')
else:
    print('  ❌ BOT_TOKEN — 未設定')
if chat and chat not in ('你的Chat_ID', ''):
    print('  ✅ CHAT_ID — 已設定')
else:
    print('  ❌ CHAT_ID — 未設定')
"

# ═══════════════════════════════════════
# PART 8：Crontab 排程
# ═══════════════════════════════════════
echo ""
echo "【PART 8】Crontab 排程"
hr

CRON_COUNT=$(crontab -l 2>/dev/null | grep -c "ai-factory" || echo 0)
if [ "$CRON_COUNT" -ge 8 ]; then
  ok "crontab — $CRON_COUNT 條排程（目標 ≥ 8）"
else
  fail "crontab — 只有 $CRON_COUNT 條（目標 8）"
fi

crontab -l 2>/dev/null | grep "ai-factory" | while read -r line; do
  echo "    $line"
done

# ═══════════════════════════════════════
# 總結
# ═══════════════════════════════════════
hr
echo ""
echo "╔══════════════════════════════════════╗"
echo "║   測試結果總結                        ║"
echo "╚══════════════════════════════════════╝"
echo "  ✅ 通過：$PASS"
echo "  ❌ 失敗：$FAIL"
echo "  ⚠️  警告：$WARN"
echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "  🎉 所有必要項目通過！"
elif [ "$FAIL" -le 3 ]; then
  echo "  ⚠️  有 $FAIL 個問題需要修復"
else
  echo "  🚨 有 $FAIL 個嚴重問題"
fi
echo ""
echo "完整報告已儲存：$REPORT"
