# 程式碼撰寫規範

## 基本要求
- 每篇文章必須有完整可執行的程式碼
- 不能省略、不能用「...」代替任何部分
- 必須在 Arduino IDE 或指定環境直接執行

## Arduino 程式碼規範

### 結構要求
```arduino
// 檔案說明：[功能描述]
// 作者：HF Chang
// 硬體：[列出使用的元件和型號]
// 接線：[簡短說明接線]

// 函式庫引用（必要時）
#include <Wire.h>

// 常數定義（數值不能寫死在程式裡）
const int SENSOR_PIN = A0;
const float THRESHOLD_LIGHT = 10.0;  // kPa，輕壓閾值
const float THRESHOLD_HEAVY = 20.0;  // kPa，重壓閾值

// 全域變數
float pressureValue = 0;

void setup() {
  Serial.begin(9600);
  // 說明：9600 baud，配合 Serial Monitor 使用
}

void loop() {
  // 讀取感測器
  pressureValue = readPressure();

  // 判斷壓力等級
  if (pressureValue < THRESHOLD_LIGHT) {
    Serial.println("輕壓");
  } else if (pressureValue < THRESHOLD_HEAVY) {
    Serial.println("重壓");
  }

  delay(100);  // 100ms 採樣間隔
}

float readPressure() {
  // 讀取 ADC 值並轉換為 kPa
  int rawValue = analogRead(SENSOR_PIN);
  return (rawValue / 1023.0) * 25.0;  // 0-25 kPa 範圍
}
```

### 注解規則
- 每個函式有說明
- 每個常數說明單位
- 非直覺的數值說明計算方式
- 接線資訊寫在檔案開頭

### 禁止
- 魔術數字（直接寫 1023 而不說明）
- 無注解的複雜運算
- 未說明的延遲時間
- 省略 include 或 define

## Python 程式碼規範（ESP32/Raspberry Pi）
```python
#!/usr/bin/env python3
"""
功能描述
硬體：[元件列表]
執行方式：python3 script.py
"""

import time
import board  # 說明：Adafruit CircuitPython board 模組

# 常數
SAMPLE_RATE = 0.1  # 秒，採樣頻率

def read_sensor():
    """讀取感測器並回傳 kPa 值"""
    # 實作內容
    pass

def main():
    """主程式迴圈"""
    while True:
        value = read_sensor()
        print(f"壓力：{value:.2f} kPa")
        time.sleep(SAMPLE_RATE)

if __name__ == "__main__":
    main()
```

## 程式碼後說明（必須附上）
1. 上傳方式：使用哪個環境、哪個版本
2. 預期輸出：Serial Monitor 應該顯示什麼
3. 常見錯誤：編譯失敗常見原因
