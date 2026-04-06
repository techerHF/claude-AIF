# SHT31 高精度溫濕度感測器：為什麼你的數值差了 2-3 度？

去年做溫室控制系統，用了 SHT31，規格漂亮——0.2°C 精度、I2C 介面、一片不到 4 塊錢。但植物就是一直出問題，感測器卻說「環境完美」。兩週後才找到元兇。

## 規格是晶片自己的，不是你的系統

SHT31 原廠標 0.2°C 精度，那是晶片在理想實驗室條件下的數據。你接上 PCB、放在 Arduino 旁邊，或裝進任何塑膠殼裡，熱源一干擾，馬上偏離。我實測，一個密封的 Arduino 盒子常態下就高了 2.8°C。

多數教學只是接線、印數值。這個方法做出來的溫控系統，其實是在控制「一個偏差的錯誤溫度」。

## 為什麼 maker 值得學這個感測器

SHT31 是少數同時具備三個條件的感測器：精度夠高（0.2°C 等級）、價格低（不到 4 美元）、程式庫成熟（Adafruit 有完整驅動）。溫室、冷鏈、育雛箱、加濕控制——這些應用場景都需要「真正準確」的溫濕度數值，不是差不多就好。

而校正，是把「規格上的準」變成「實際上能用」的關鍵一步。

## 我的校正流程

材料：
- SHT31 模組（Adafruit 或相容版）
- Arduino Uno 或 ESP32
- 一支校正過的參考溫度計（實驗室等級，約 15 美元，不要去五金行買）
- 冰水與沸水（雙點校正：0°C 與 100°C 參考點）
- I2C 線路上若有需要，加 10kΩ 上拉電阻

關鍵原則：參考溫度計比 SHT31 本身更重要。你買再貴的感測器，參考點錯了，一切都錯。兩支感測器必須在同樣環境下熱平衡 30 分鐘以上，我才開始記錄數值。

## 程式碼（保持英文介面）

```cpp
#include <Wire.h>
#include "Adafruit_SHT31.h"

Adafruit_SHT31 sht31 = Adafruit_SHT31();

float offset_temp = 0.0;  // 溫度偏移量（儲存校正值）
float offset_hum = 0.0;   // 濕度偏移量

void setup() {
  Serial.begin(115200);
  if (!sht31.begin(0x44)) {
    Serial.println("找不到 SHT31，檢查接線");
    while (1);
  }
  sht31.heater(false);  // 關閉加熱器，否則影響濕度讀數
}

void loop() {
  float temp = sht31.readTemperature();
  float hum = sht31.readHumidity();

  if (!isnan(temp) && !isnan(hum)) {
    Serial.print("原始 T: "); Serial.print(temp, 2);
    Serial.print(" H: "); Serial.print(hum, 2);

    // 加上校正偏移，輸出實際溫度
    Serial.print(" | 校正 T: "); Serial.print(temp + offset_temp, 2);
    Serial.print(" C | 校正 H: "); Serial.print(hum + offset_hum, 2);
    Serial.println(" %");
  }
  delay(1000);
}
```

## 雙點校正做法

1. 冰水浴（0°C 參考）——攪拌 2 分鐘，等待數值穩定後記錄 SHT31 與參考溫度計的差值
2. 室溫環境（20-25°C 範圍）做第二個參考點
3. 計算：`offset_temp = 參考溫度 - SHT31 讀值`
4. 兩點平均後的偏移量寫入 EEPROM，系統重啟不會消失

我的結果：
- 校正前：室溫 25°C 環境下偏差 +2.8°C
- 校正後：與參考溫度計差距在 0.15°C 內
- 濕度從 8% 誤差壓到 1.2%

有問題歡迎留言。

---

想要完整程式碼與校正工具模板？[到 Whop 取得 SHT31 校正套件](PLACEHOLDER_WHOP_GUIDE)