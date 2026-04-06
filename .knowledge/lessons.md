# 踩坑記錄（遇到問題就立刻記）

## 格式
```
YYYY-MM-DD 踩坑：[問題描述]
原因：[根本原因]
解法：[怎麼修]
下次避免：[預防措施]
```

---

## 記錄

[2026-04-06 C1] SHT31 高精度溫濕度感測校正 | 審查:REJECTED | UV模擬:48 | 留言板互動:6條

[2026-04-06 C2] HMC5883L 磁力計三軸方位計算 | 審查:? | UV模擬:30 | 留言板互動:11條

[2026-04-06 C3] ADXL345 衝擊偵測靈敏度設定 | 審查:? | UV模擬:41 | 留言板互動:37條

2026-04-04 踩坑：quality-check.sh 在文章無數字時 pipefail 中止整個腳本
原因：`set -euo pipefail` 下，`grep -oE '[0-9]...'` 找不到匹配時 exit 1，導致 pipeline 失敗，腳本靜默退出
解法：改用 `{ grep -oE '...' || true; }` 包裹，確保 pipeline 永遠回傳 0
下次避免：所有用 grep 計數的 command substitution 都要加 `|| true` 保護

2026-04-04 踩坑：duplicate-check.sh / reddit-rate-limit.sh 硬編碼 ~/ai-factory/ 路徑在 Windows Git Bash 失效
原因：`~/ai-factory/` 在 Windows Git Bash 解析為 `/c/Users/FN/ai-factory/`，Python 無法開啟此虛擬路徑
解法：改用 CWD 相對路徑 `logs/progress.json`，搭配 `[ -d "logs" ]` 判斷環境
下次避免：所有硬編碼 `~/ai-factory/` 的腳本都改用相對路徑，VPS 上 CWD = ~/ai-factory/ 時自然正確

2026-04-04 踩坑：verify-system.sh 的 test-good.md heredoc 缺少必要關鍵字導致 quality-check 回 REJECTED
原因：verify 腳本自訂的 test-good 內容沒有 `問題|場景` 和 `原理|機制` 關鍵字，但 quality-check 要求這些
解法：改為直接 cp 已驗證通過的 articles/test-good.md，heredoc 只作 fallback
下次避免：verify 腳本的測試文章要用已通過 hook 的真實文章，不要重新寫 inline 版本

[2026-04-06 C1] SHT31 高精度溫濕度感測校正 | 審查:REJECTED | UV:22 | 最重要的團隊學習:鹽溶液24-48小時靜置對Maker環境不可行，改用飽和水杯+濕度計對照更實際；AI文句「此外」殘留是REJECTED主因
