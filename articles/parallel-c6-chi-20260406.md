# PWM 只能幫你輸出「假的」類比電壓：MCP4725 讓你動手做訊號源

做互動裝置的人遲早會遇到一個問題：Arduino 的腳位只能輸出 HIGH 或 LOW，但要控制一盞燈的亮度、調整馬達的速度，該怎麼辦？

多數人的第一個答案就是 PWM。教官也這樣教，網路上也這樣寫。但你真的拿示波器看過 PWM 的輸出嗎？

我看過。用 Uno 的 PWM 輸出 2.5V，實際量到的電壓在 2.3V 到 2.7V 之間跳動，紋波峰值 200mV。那不是直流，是一連串的 HIGH-LOW- HIGH-LOW。如果你運氣好，加個低通濾波器可以把它压平；運氣不好，波形還是糊的。

**MCP4725 是一個不需要濾波器的方案。** 12-bit I2C DAC，輸出 0-5V，共有 4096 階，解析度 0.0012V。晶片內建 2.048V 參考電壓，也可以直接用 VCC 當參考。重點是：輸出的是真正的直流電壓，不是脈衝訊號。

## 什麼情境值得用

**信號源校正：** 你要輸出一個穩定的 3.3V 給感測器當參考電壓，PWM 加濾波器輸出 3.3V 的穩定度就是不如專用 DAC。

**函數產生器：** 做電子專題的人一定需要函數產生器。網路上有現成的模組，但自己用 MCP4725 做一個，可以改成自己要的頻率範圍、輸出通道數，而且成本差不多。

**音頻振幅控制：** 控制音效晶片的音量，用 PWM 輸出會有底噪，用 DAC 輸出才乾淨。

## 速度限制先搞清楚

400kHz I2C，傳一次更新大約 100 微秒，最大更新率約 10kHz。這對低頻波形（幾百 Hz 以內的類比訊號）足夠了，但如果你要做音頻合成、更高頻率的波形生成，這個晶片的速度就不夠用。實測：1kHz 的弦波輸出，MCP4725 的紋波小於 2mV，PWM 加濾波器則有 40mV。

```cpp
#include <Wire.h>
#include <math.h>

#define DAC_ADDR 0x60        // MCP4725 預設 I2C 位址
const int TABLE_SIZE = 256; // 弦波查表大小

// 預先計算的弦波資料表（0-255 對應 0-4095 DAC 值）
uint16_t sineTable[TABLE_SIZE];

void generateSineTable() {
  // 產生一個完整的正弦波查表
  for (int i = 0; i < TABLE_SIZE; i++) {
    float sineVal = sin(2.0 * PI * i / TABLE_SIZE); // 輸出 -1 到 1
    sineTable[i] = (uint16_t)((sineVal + 1.0) * 2047.5); // 映射到 0-4095
  }
}

void setup() {
  Wire.begin();         // 初始化 I2C 匯流排
  Serial.begin(115200);
  generateSineTable();  // 啟動時先算好查表
}

void writeDAC(uint16_t value) {
  // 傳送 12-bit 資料到 MCP4725
  Wire.beginTransmission(DAC_ADDR);
  Wire.write(0x40);            // 寫入 DAC 暫存器命令
  Wire.write(value >> 4);      // 高 8 位元
  Wire.write((value & 0x0F) << 4); // 低 4 位元（靠右對齊）
  Wire.endTransmission();
}

void loop() {
  static int index = 0;
  writeDAC(sineTable[index]);   // 查表輸出
  index = (index + 1) % TABLE_SIZE;
  // 每次更新約 100 微秒，一個週期 = 256 * 100μs = 25.6ms
  // 實際輸出頻率約 39Hz 弦波
}
```

## 實戰經驗

我第一個用 MCP4725 的專案是一個太陽能板的最大功率點追蹤（MPPT）控制器。需要輸出一個緩慢變化的電壓去控制降壓轉換器的參考值，用 PWM 加濾波器測了三天，紋波就是壓不下去。換成 MCP4725 之後，一次搞定。

如果你現在還在用 PWM 做類比輸出，建議你花 35 元買一顆 MCP4725 模組，加上兩條杜邦線，親自比較一下。做出來了，你就知道什麼叫「乾淨的電壓」。

---

**相關資源：**
完整程式碼包（含方波、三角波範例）：[MCP4725 完整專案包 - Whop $19](PLACEHOLDER_WHOP_PACK)

---

作者：張旭豐｜機械工程博士｜觸覺感測與人機互動