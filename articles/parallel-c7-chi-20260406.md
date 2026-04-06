# MAX6675 熱電偶高溫量測：K-type 感測器入門首選，0–1023.75C 全範圍

熱電偶（Thermocouple）不是新東西，工業用了几十年。但 maker 社群長期被「冷接點補償」卡住——自己算誤差、自己接參考電路，做出來的東西數值飄來飄去，最後乾脆放棄。MAX6675 把這件事做進晶片裡，你只需要會 SPI 就能讀到準確的溫度。

## 為什麼高溫感測值得學

多數半導體感測器（DS18B20、SHT31）在 125C 以上就掛了。Maker 常見的高溫場景——窯燒、3D 列印熱塊、烤箱校正——這些你拿一般感測器根本量不了。K-type 熱電偶配上 MAX6675，0 到 1023.75C 全範圍，0.25C 解析度，+3C 典型誤差。這個組合是工業等級入門最便宜的方案，材料不到 200 元。

冷接點補償（Cold Junction Compensation）是關鍵。熱電偶量的是「兩端溫度差」，冷端在你板子上，室溫波動個 3 度，高溫讀數就差了 3 度。MAX6675 內建冷端溫度感測，自動幫你算好，直接吐數值。

## 程式碼實作

```
#include <SPI.h>

const int MAX6675_SO = 12;  // MISO 資料輸出
const int MAX6675_CS = 10;  // 晶片選擇
const int MAX6675_SCK = 13; // 時脈訊號

void setup() {
  Serial.begin(115200);
  pinMode(MAX6675_CS, OUTPUT);
  digitalWrite(MAX6675_CS, HIGH);
  SPI.begin();
}

double readThermocouple() {
  digitalWrite(MAX6675_CS, LOW);
  delayMicroseconds(1);
  uint16_t raw = SPI.transfer(0x00) << 8;
  raw |= SPI.transfer(0x00);
  digitalWrite(MAX6675_CS, HIGH);

  if (raw & 0x8002) {
    return NAN;  // 熱電偶斷線
  }

  raw >>= 3;
  return raw * 0.25;
}

void loop() {
  double temp = readThermocouple();
  Serial.print("Temperature: ");
  Serial.print(temp, 2);
  Serial.println(" C");
  delay(1000);
}
```

## 和直接讀電壓的差異

K-type 熱電偶靈敏度約 41 µV/度C。Arduino ADC 解析度不夠，你自己算補償還要查表對溫度——做出來只能用，不能用很久。MAX6675 12-bit 解析度，晶片內建所有補償演算法，SPI 輸出乾淨數值。這個差距就是「做出來放著會飄」和「做出來穩定跑一年」的差距。

## 應用場景

- 窯燒監控（陶藝、琉璃）
- 3D 列印機熱塊校正
- 烤箱或恆溫箱驗證
- 任何需要 125C 以上的場景

完整程式碼注解版本（包含常見問題 FAQ）：

[PLACEHOLDER_WHOP_GUIDE]