---
name: english-writing
description: 英文內容寫作規範，針對 Reddit 摘要版和 Medium 完整版的差異化規則
type: behavioral
---

# 英文內容寫作規範

## 目標讀者
Maker with Arduino basics, wants to understand design thinking, not just wiring.
Not a beginner. Not a researcher. Someone who's built things but hit a wall on a specific problem.

## 開場公式
不從「Today I'll show you...」開始
從設計問題開始：

「Here's the problem most tutorials don't address:
your sensor works, but your device doesn't respond the way you expect.
The issue isn't the hardware. It's the logic.」

「Most FSR tutorials stop at the wiring.
Here's what they don't cover: why threshold-based detection fails
when the user isn't a binary on/off input.」

## 句子結構
- 短句優先（15 字以內）
- 技術術語不解釋，但給上下文
- 主動語態：「The capacitor stores charge」不是「Charge is stored by the capacitor」
- 段落 3–4 句為上限

## 程式碼說明方式
每個區塊前一行說目的：
```
// Read raw ADC value — this is what your sensor actually outputs
int16_t raw = ads.readADC_SingleEnded(0);

// Convert to voltage — 0.1875mV per LSB at ±4.096V range
float voltage = raw * 0.1875 / 1000.0;
```

## 禁止句型
- In this tutorial, we will...
- First, ... Second, ... Finally, ...
- As you can see from the code above...
- I hope this helps!
- Feel free to ask questions in the comments!
- This is a great way to...
- Simply / Just / Easily（讓問題看起來比實際簡單）

## Reddit 版規範（摘要版）
長度：核心問題 + 核心解法 + 關鍵數據，600–900 字
結構：問題場景（1段）→ 為什麼現有方案失敗（1段）→ 解法概述（2段）→ 關鍵數據（1段）
結尾固定格式：「Full write-up with complete code in the comments.」
不放 Whop 連結

## Medium 版規範（完整版）
長度：1500 字以上（含程式碼）
結構：完整七層（writing-style.md 定義）
第七層放 Whop 連結
材料清單每個元件加 Amazon.co.jp 聯盟連結

## 標題規則（Reddit 英文標題）
格式：[主題] — [設計問題] + [關鍵數字]
長度：60–90 字元
範例：
「Capacitive pressure sensor with PDMS dielectric — 0 to 20 kPa range, $12 total, no calibration needed」
「5-finger flex sensor glove with ESP32 — reads 0-90° bend angles, under 20ms latency」

禁止：
- How to make a...
- DIY ... tutorial（太通用）
- Amazing/incredible/revolutionary（禁止詞）
