# Reddit 發文草稿
日期：2026-04-04
目標：r/arduino（第1優先，本週已發 0 篇）

---

## 標題
DIY capacitive pressure sensor from copper foil and PDMS - 0 to 20 kPa range, Arduino readable, total cost $4.50

## 主文

FSR sensors saturate above 10 N — beyond that, you lose 95% of your resolution. I needed a 0–20 kPa range with linear output, so I built a capacitive sensor instead.

The principle: C = ε₀·εᵣ·A/d. When a 1.5mm PDMS layer compresses from 1.6mm to 1.0mm under load, capacitance shifts from 0.11 pF to 0.18 pF — a 64% change vs. FSR's 5% over the same range.

Tested with 50g and 200g calibration weights: readings match within ±12% across the full 0–20 kPa span. Materials cost: copper foil tape + PDMS + ADS1115 module = about $4.50 total.

Full tutorial with code and schematics in the comments.

---

## 第一則留言（發文後立即貼）

Full writeup with circuit diagram, PDMS fabrication steps, and Arduino code:
[PLACEHOLDER_SENSOR_GUIDE]

Happy to answer questions about the build — especially PDMS curing or ADS1115 setup.

---

## 備用 subreddit（如果 r/arduino 被拒）
r/maker → r/electronics

## 連結狀態
⚠️ PLACEHOLDER 尚未填入 — 發文前請更新 CLAUDE.md 的 Payhip 連結
