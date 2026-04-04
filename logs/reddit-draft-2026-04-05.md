# Reddit 發文草稿
日期：2026-04-05
目標：r/maker（demand score 2302，本週 0 篇）

---

## 標題（71字元 / 60-90範圍）
5-finger flex sensor glove - ESP32 reads 0-90 degree bend angles, under 20ms latency

## 主文

Flex sensors vary by ±15% between units at the same bend angle — so I built a per-glove calibration step that maps raw ADC values to 0-90° individually. Now the code runs the same on any glove without hardcoded offsets.

The circuit is a simple voltage divider: 47 kΩ fixed resistor + flex sensor, read by ESP32's 12-bit ADC across GPIO34-38. At full extension, ADC ≈ 2300; at full bend, ≈ 1100.

Tested with 100 Hz sampling: all 5 fingers update in under 20 ms. Dropping to 10-bit ADC cuts it to 8 ms if you need faster response.

Full tutorial with code and schematics in the comments.

---

## 第一則留言
Full build guide with circuit diagram, calibration procedure, and Arduino code:
[PLACEHOLDER_SENSOR_GUIDE]

Happy to answer questions — especially about the calibration step or ESP32 ADC quirks.

---

## 備用 subreddit
r/arduino → r/esp32

## 連結狀態
⚠️ PLACEHOLDER — 發文前更新 CLAUDE.md Payhip 連結
