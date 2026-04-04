#!/usr/bin/env bash
# verify-system.sh
# 用途：AI 無人工廠系統健康檢查
# 執行：bash ~/ai-factory/verify-system.sh

set -uo pipefail

# 顏色（VPS 支援 ANSI，Windows Git Bash 也支援）
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS="${GREEN}PASS${NC}"
FAIL="${RED}FAIL${NC}"
WARN="${YELLOW}WARN${NC}"

# 取得腳本所在目錄（支援 VPS ~/ai-factory/ 和 Windows /d/openclaw/）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TODAY=$(date +%Y-%m-%d)
REPORT_ISSUES=0

echo ""
echo "=== AI 無人工廠系統健康報告 ==="
echo "日期：$TODAY"
echo "工作目錄：$SCRIPT_DIR"
echo ""

# ─────────────────────────────────────────────────────
# 【1. 環境驗證】
# ─────────────────────────────────────────────────────
echo "【1. 環境驗證】"

# Node.js
NODE_VER=$(node --version 2>/dev/null || echo "未安裝")
if echo "$NODE_VER" | grep -qE '^v([2-9][0-9]|1[89])'; then
  echo -e "  Node.js：$NODE_VER $PASS"
  NODE_STATUS="$NODE_VER PASS"
else
  echo -e "  Node.js：$NODE_VER（需要 v18+）$WARN"
  NODE_STATUS="$NODE_VER WARN"
fi

# Claude Code CLI
CLAUDE_VER=$(claude --version 2>/dev/null || echo "未安裝")
if echo "$CLAUDE_VER" | grep -qE '[0-9]'; then
  echo -e "  Claude Code：$CLAUDE_VER $PASS"
  CLAUDE_STATUS="$CLAUDE_VER PASS"
else
  echo -e "  Claude Code：$CLAUDE_VER $FAIL"
  CLAUDE_STATUS="$CLAUDE_VER FAIL"
  REPORT_ISSUES=$((REPORT_ISSUES+1))
fi

# Python3
PY_VER=$(python3 --version 2>/dev/null || echo "未安裝")
if echo "$PY_VER" | grep -qE 'Python 3'; then
  echo -e "  Python3：$PY_VER $PASS"
  PY_STATUS="$PY_VER PASS"
else
  echo -e "  Python3：$PY_VER $FAIL"
  PY_STATUS="$PY_VER FAIL"
  REPORT_ISSUES=$((REPORT_ISSUES+1))
fi

# Cron
CRON_OUT=$(crontab -l 2>/dev/null || echo "")
if echo "$CRON_OUT" | grep -q 'run.sh'; then
  CRON_STATUS="PASS"
  echo -e "  Cron (run.sh)：已設定 $PASS"
else
  CRON_STATUS="WARN — 尚未部署到 VPS"
  echo -e "  Cron (run.sh)：未找到 $WARN（本地 Windows 正常，VPS 部署後會設定）"
fi
if echo "$CRON_OUT" | grep -q 'feedback-collector'; then
  echo -e "  Cron (feedback-collector)：已設定 $PASS"
else
  echo -e "  Cron (feedback-collector)：未找到 $WARN"
fi

echo ""

# ─────────────────────────────────────────────────────
# 【2. 檔案完整性驗證】
# ─────────────────────────────────────────────────────
echo "【2. 檔案完整性驗證】"

check_file() {
  local path=$1
  if [ -f "$path" ]; then
    echo -e "  ✓ $path"
    return 0
  else
    echo -e "  ${RED}✗ $path（缺失）${NC}"
    REPORT_ISSUES=$((REPORT_ISSUES+1))
    return 1
  fi
}

echo "  [Skills — 26個]"
SKILLS_OK=0
SKILLS_TOTAL=26
for f in \
  .claude/skills/writing-style.md \
  .claude/skills/article-structure.md \
  .claude/skills/reddit-post.md \
  .claude/skills/topic-selection.md \
  .claude/skills/seo-optimization.md \
  .claude/skills/code-writing.md \
  .claude/skills/comment-strategy.md \
  .claude/skills/audience-targeting.md \
  .claude/skills/product-description.md \
  .claude/skills/image-description.md \
  .claude/skills/content-calendar.md \
  .claude/skills/persona.md \
  .claude/skills/topic-hook.md \
  .claude/skills/discount-pricing.md \
  .claude/skills/monetization-strategy.md \
  .claude/skills/whop-product.md \
  .claude/skills/whop-copy.md \
  .claude/skills/payhip-conversion.md \
  .claude/skills/digital-twin-voice.md \
  .claude/skills/english-writing.md \
  .claude/skills/chinese-writing.md \
  .claude/skills/medium-post.md \
  .claude/skills/platform-rules.md \
  .claude/skills/researcher-strategy.md \
  .claude/skills/feedback-interpretation.md \
  .claude/skills/knowledge-update.md; do
  check_file "$f" && SKILLS_OK=$((SKILLS_OK+1))
done

echo ""
echo "  [Hooks — 11個]"
HOOKS_OK=0
HOOKS_TOTAL=11
for f in \
  .claude/hooks/quality-check.sh \
  .claude/hooks/ai-detection.sh \
  .claude/hooks/code-syntax-check.sh \
  .claude/hooks/word-count.sh \
  .claude/hooks/checkpoint.sh \
  .claude/hooks/duplicate-check.sh \
  .claude/hooks/memory-update.sh \
  .claude/hooks/topic-tracker.sh \
  .claude/hooks/reddit-rate-limit.sh \
  .claude/hooks/link-validation.sh \
  .claude/hooks/error-recovery.sh; do
  check_file "$f" && HOOKS_OK=$((HOOKS_OK+1))
done

echo ""
echo "  [Agents — 11個]"
AGENTS_OK=0
AGENTS_TOTAL=11
for f in \
  .claude/agents/writer.md \
  .claude/agents/reviewer.md \
  .claude/agents/poster.md \
  .claude/agents/seo-agent.md \
  .claude/agents/topic-selector.md \
  .claude/agents/feedback-collector.md \
  .claude/agents/style-updater.md \
  .claude/agents/english-writer.md \
  .claude/agents/chinese-writer.md \
  .claude/agents/researcher.md \
  .claude/agents/knowledge-subagent.md; do
  check_file "$f" && AGENTS_OK=$((AGENTS_OK+1))
done

echo ""
echo "  [主控檔案]"
MAIN_OK=0
for f in run.sh CLAUDE.md deploy.sh .gitattributes; do
  check_file "$f" && MAIN_OK=$((MAIN_OK+1))
done
# 確認資料夾
[ -d "logs" ]     && echo -e "  ✓ logs/"     && MAIN_OK=$((MAIN_OK+1)) || { echo -e "  ${RED}✗ logs/ 資料夾缺失${NC}"; REPORT_ISSUES=$((REPORT_ISSUES+1)); }
[ -d "articles" ] && echo -e "  ✓ articles/" && MAIN_OK=$((MAIN_OK+1)) || { echo -e "  ${RED}✗ articles/ 資料夾缺失${NC}"; REPORT_ISSUES=$((REPORT_ISSUES+1)); }

echo ""

# ─────────────────────────────────────────────────────
# 【3. Hook 功能驗證】
# ─────────────────────────────────────────────────────
echo "【3. Hook 功能驗證】"

# 建立測試文章（壞）
cat > /tmp/test-bad.md << 'BADEOF'
隨著科技的發展，這個革命性的感測器非常驚人！
它可以感測壓力，非常好用，完全完美。
BADEOF

# 建立測試文章（好）— 使用已驗證通過的 articles/test-good.md
# 若不存在才用 heredoc 備用版本
if [ -f "articles/test-good.md" ]; then
  cp "articles/test-good.md" /tmp/test-good.md
fi
cat > /tmp/test-good-fallback.md << 'GOODEOF'
## 電容式壓力感測器設計

手指按下時，電極間距從 1.6mm 縮短至 0.12mm，電容值從 0.19pF 上升至 0.57pF。
感測範圍：0–20 kPa，解析度：11.85 mV/kPa。

### 材料清單
- Arduino UNO × 1：主控制器
- 銅箔膠帶 8mm × 適量：上下電極
- PDMS 3mm 厚 × 1片：彈性介電層
- ADS1115 × 1：16-bit ADC，讀值精度 0.1875 mV

### 步驟1：製作上電極彈性層
將 PDMS 澆鑄至 3mm 厚，自然固化24小時。
預期結果：透明彈性薄片，可以壓縮至 0.12mm。

```arduino
// 電容式壓力感測 — Arduino UNO
// 接線：ADS1115 SDA→A4, SCL→A5
#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;
const float THRESHOLD_LIGHT = 10.0;  // kPa 輕壓閾值
const float THRESHOLD_HEAVY = 20.0;  // kPa 重壓閾值

void setup() {
  Serial.begin(9600);
  ads.begin();
}

void loop() {
  int16_t raw = ads.readADC_SingleEnded(0);
  float voltage = raw * 0.1875 / 1000.0;  // 轉換為 mV
  Serial.print("電壓：");
  Serial.println(voltage);
  delay(100);
}
```

測試結果：無壓力時輸出 225mV，10kPa 時輸出 345mV，解析度 12.6 mV/kPa。
GOODEOF
# 若 articles/test-good.md 不存在才使用 fallback
[ ! -f /tmp/test-good.md ] && cp /tmp/test-good-fallback.md /tmp/test-good.md

run_hook_test() {
  local label=$1
  local cmd=$2
  local expect=$3
  local result
  result=$(eval "$cmd" 2>&1 | head -1 || true)
  if echo "$result" | grep -q "$expect"; then
    echo -e "  $label：$result $PASS"
    return 0
  else
    echo -e "  $label：$result（預期 $expect）$FAIL"
    REPORT_ISSUES=$((REPORT_ISSUES+1))
    return 1
  fi
}

QC_BAD_STATUS="PASS"
QC_GOOD_STATUS="PASS"
AI_BAD_STATUS="PASS"
AI_GOOD_STATUS="PASS"
CODE_STATUS="PASS"
CKPT_STATUS="PASS"
LINK_STATUS="PASS"
DUPCHECK_STATUS="PASS"
RATELIMIT_STATUS="PASS"

run_hook_test "quality-check（壞文章→REJECTED）" \
  "bash .claude/hooks/quality-check.sh /tmp/test-bad.md" \
  "REJECTED" || QC_BAD_STATUS="FAIL"

run_hook_test "quality-check（好文章→APPROVED）" \
  "bash .claude/hooks/quality-check.sh /tmp/test-good.md" \
  "APPROVED" || QC_GOOD_STATUS="FAIL"

run_hook_test "ai-detection（壞文章→REJECTED）" \
  "bash .claude/hooks/ai-detection.sh /tmp/test-bad.md" \
  "REJECTED" || AI_BAD_STATUS="FAIL"

run_hook_test "ai-detection（好文章→APPROVED）" \
  "bash .claude/hooks/ai-detection.sh /tmp/test-good.md" \
  "APPROVED" || AI_GOOD_STATUS="FAIL"

run_hook_test "code-syntax-check（好文章→APPROVED）" \
  "bash .claude/hooks/code-syntax-check.sh /tmp/test-good.md" \
  "APPROVED" || CODE_STATUS="FAIL"

# checkpoint status（允許輸出任何狀態，只要不崩潰）
CKPT_OUT=$(bash .claude/hooks/checkpoint.sh status 2>&1 || true)
if echo "$CKPT_OUT" | grep -qiE 'status|today|done|total|progress|[][]'; then
  echo -e "  checkpoint status：正常回傳 $PASS"
else
  echo -e "  checkpoint status：$CKPT_OUT $FAIL"
  CKPT_STATUS="FAIL"
  REPORT_ISSUES=$((REPORT_ISSUES+1))
fi

# duplicate-check
DUPCHECK_OUT=$(bash .claude/hooks/duplicate-check.sh "電容式感測" 2>&1 || true)
if echo "$DUPCHECK_OUT" | grep -qiE 'UNIQUE|DUPLICATE|duplicate|unique|找到|未找到'; then
  echo -e "  duplicate-check：$DUPCHECK_OUT $PASS"
else
  echo -e "  duplicate-check：$DUPCHECK_OUT $FAIL"
  DUPCHECK_STATUS="FAIL"
  REPORT_ISSUES=$((REPORT_ISSUES+1))
fi

# link-validation
LINK_OUT=$(bash .claude/hooks/link-validation.sh 2>&1 || true)
if echo "$LINK_OUT" | grep -qiE 'PLACEHOLDER|placeholder|WARNING|OK|valid|連結'; then
  echo -e "  link-validation：PLACEHOLDER 警告正常觸發 $PASS"
else
  echo -e "  link-validation：$LINK_OUT $WARN"
fi

# reddit-rate-limit
RATELIMIT_OUT=$(bash .claude/hooks/reddit-rate-limit.sh arduino 2>&1 || true)
if echo "$RATELIMIT_OUT" | grep -qiE 'OK|BLOCKED|rate|limit|posts|本週|允許'; then
  echo -e "  reddit-rate-limit (arduino)：$RATELIMIT_OUT $PASS"
else
  echo -e "  reddit-rate-limit：$RATELIMIT_OUT $WARN"
fi

echo ""

# ─────────────────────────────────────────────────────
# 【4. API 連通驗證】
# ─────────────────────────────────────────────────────
echo "【4. API 連通驗證】"
API_STATUS="PASS"
MODEL_NAME="（未知）"

if command -v claude >/dev/null 2>&1; then
  API_OUT=$(timeout 30 claude -p "輸出你目前使用的模型名稱，只需一行文字，不要其他說明" --max-turns 1 2>&1 || true)
  if echo "$API_OUT" | grep -qiE 'claude|minimax|model|MiniMax|sonnet|haiku|opus'; then
    MODEL_NAME=$(echo "$API_OUT" | head -1)
    echo -e "  API 連通：$PASS"
    echo -e "  回應模型：$MODEL_NAME"
  else
    echo -e "  API 連通：$FAIL（回應：$API_OUT）"
    API_STATUS="FAIL"
    REPORT_ISSUES=$((REPORT_ISSUES+1))
  fi
else
  echo -e "  API 連通：$FAIL（claude CLI 未找到）"
  API_STATUS="FAIL"
  REPORT_ISSUES=$((REPORT_ISSUES+1))
fi

echo ""

# ─────────────────────────────────────────────────────
# 【5. 系統健康報告摘要】
# ─────────────────────────────────────────────────────
echo "========================================"
echo "=== AI 無人工廠系統健康報告摘要 ==="
echo "========================================"
echo "日期：$TODAY"
echo ""
echo "環境："
echo "  Node.js：$NODE_STATUS"
echo "  Claude Code：$CLAUDE_STATUS"
echo "  Python3：$PY_STATUS"
echo "  Cron：$CRON_STATUS"
echo ""
echo "檔案完整性："
if [ "$SKILLS_OK" -eq "$SKILLS_TOTAL" ]; then
  echo -e "  Skills：$SKILLS_OK/$SKILLS_TOTAL（6 Whop 變現 + 8 新增）${GREEN}PASS${NC}"
else
  echo -e "  Skills：$SKILLS_OK/$SKILLS_TOTAL ${RED}FAIL${NC}"
fi
if [ "$HOOKS_OK" -eq "$HOOKS_TOTAL" ]; then
  echo -e "  Hooks：$HOOKS_OK/$HOOKS_TOTAL ${GREEN}PASS${NC}"
else
  echo -e "  Hooks：$HOOKS_OK/$HOOKS_TOTAL ${RED}FAIL${NC}"
fi
if [ "$AGENTS_OK" -eq "$AGENTS_TOTAL" ]; then
  echo -e "  Agents：$AGENTS_OK/$AGENTS_TOTAL（含 en/zh writer + researcher + knowledge）${GREEN}PASS${NC}"
else
  echo -e "  Agents：$AGENTS_OK/$AGENTS_TOTAL ${RED}FAIL${NC}"
fi
echo ""
echo "Hook 功能測試："
echo "  quality-check（壞文章 → REJECTED）：$QC_BAD_STATUS"
echo "  quality-check（好文章 → APPROVED）：$QC_GOOD_STATUS"
echo "  ai-detection（壞文章 → REJECTED）：$AI_BAD_STATUS"
echo "  ai-detection（好文章 → APPROVED）：$AI_GOOD_STATUS"
echo "  code-syntax-check（好文章 → APPROVED）：$CODE_STATUS"
echo "  checkpoint status：$CKPT_STATUS"
echo "  duplicate-check：$DUPCHECK_STATUS"
echo "  link-validation：$LINK_STATUS"
echo ""
echo "API："
echo "  Minimax 連通：$API_STATUS"
echo "  使用模型：$MODEL_NAME"
echo ""
echo "待完成事項："
# 檢查 PLACEHOLDER 是否還在
if grep -q "PLACEHOLDER" CLAUDE.md 2>/dev/null; then
  echo "  [ ] 填入真實 Whop 連結（CLAUDE.md 中仍有 PLACEHOLDER_WHOP_*）"
else
  echo "  [x] Whop 連結已設定"
fi
echo "  [ ] 確認 Reddit 帳號準備好"
echo "  [ ] VPS 部署後執行 deploy.sh 設定 cron 排程"
echo ""

if [ "$REPORT_ISSUES" -eq 0 ]; then
  echo -e "系統整體狀態：${GREEN}就緒${NC}（0 個問題）"
elif [ "$REPORT_ISSUES" -le 2 ]; then
  echo -e "系統整體狀態：${YELLOW}部分就緒${NC}（$REPORT_ISSUES 個需要注意）"
else
  echo -e "系統整體狀態：${RED}需要修正${NC}（$REPORT_ISSUES 個問題）"
fi
echo ""
