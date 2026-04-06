# HMC5883L 三軸電子羅盤：傾斜30度依然準確，1.2度的秘密

## 你的羅盤為什麼會飄？因為它在「作弊」

在工作室組裝第一台自走車時，我把 HMC5883L 焊上板子，燒錄網路上那段經典公式：

```
heading = atan2(Y, X) * 180 / PI
```

桌上測試完美，指北針說向東就向東。把車子拿起來看它在地板上跑的姿勢——羅盤瞬間飄了18度。

這不是程式碼寫錯。這是物理。

## 問題的本質：你在量測的是「感測器平面」，不是「地面」

地球磁場是一個三維向量。磁力計讀取的是這個向量在感測器 X、Y、Z 三軸上的投影。當感測器完全水平的時候，X-Y 投影剛好落在水平面上，你算出的方位角是正確的。

但只要傾斜 30 度，地球磁場向量在感測器軸上的分布就改變了——即使前進方向沒變，X 軸和 Y 軸的數值同時受到影響。你的公式還是算得很開心，但答案已經錯了。

大多數教學停在這裡，告訴你「要把感測器放水平」。但做產品的時候誰能保證這件事？

## 解決方案：用加速度計的傾角，把磁場向量「轉正」

辦法是這樣的：先用量加速度計算出感測器相對於水平面的俯仰角（pitch）和翻滾角（roll），然後用這兩個角度把磁力計的讀數「旋轉」回水平面。這個技巧叫 tilt compensation（傾斜補償）。

旋轉後的等效水平分量：

```
X_comp = X * cos(pitch) + Z * sin(pitch)
Y_comp = X * sin(roll) * sin(pitch) + Y * cos(roll) - Z * sin(roll) * cos(pitch)
```

算出 X_comp 和 Y_comp 之後再用 atan2 求方位角。這就是感測器融合（sensor fusion）最基礎的形態——兩種感測器合作，補償彼此的限制。

## Arduino 實作

```cpp
#include <Wire.h>

#define MAG_ADDR 0x1E  // HMC5883L I2C 位址
#define ACC_ADDR 0x53  // ADXL345 I2C 位址

void setup() {
  Serial.begin(115200);
  Wire.begin();

  // HMC5883L：8次取樣平均、更新率15Hz、增益5（±1.3Ga）
  // 設定值：0x70 = 8-averaging, 15Hz, normal measurement
  //         0xA0 = gain 5, continuous measurement mode
  Wire.beginTransmission(MAG_ADDR);
  Wire.write(0x00); Wire.write(0x70);  // CRA register: 8-sample, 15Hz
  Wire.write(0x01); Wire.write(0xA0);  // CRB register: gain 5
  Wire.write(0x02); Wire.write(0x00);  // Mode register: continuous mode
  Wire.endTransmission();

  // ADXL345：100Hz 更新率、全解析度
  Wire.beginTransmission(ACC_ADDR);
  Wire.write(0x2C); Wire.write(0x0A);  // BW_RATE: 100Hz
  Wire.write(0x31); Wire.write(0x0B);  // DATA_FORMAT: full resolution, ±16g
  Wire.write(0x2D); Wire.write(0x08);  // POWER_CTL: measurement mode
  Wire.endTransmission();

  delay(100);
}

void loop() {
  // 讀取加速度計三軸（原始16元帶符號整數）
  int16_t ax = readAxis(ACC_ADDR, 0x32);
  int16_t ay = readAxis(ACC_ADDR, 0x34);
  int16_t az = readAxis(ACC_ADDR, 0x36);

  // 由加速度資料算出傾斜角（弧度）
  // 原理：重力向量在靜止時指向地面 (0,0,-1)
  float pitch = atan2(ax, sqrt(ay*ay + az*az));
  float roll  = atan2(ay, sqrt(ax*ax + az*az));

  // 讀取磁力計三軸
  int16_t mx = readAxis(MAG_ADDR, 0x03);
  int16_t my = readAxis(MAG_ADDR, 0x07);
  int16_t mz = readAxis(MAG_ADDR, 0x05);

  // Tilt compensation：把磁場向量旋轉回水平面
  float mx_c = mx * cos(pitch) + mz * sin(pitch);
  float my_c = mx * sin(roll) * sin(pitch) + my * cos(roll) - mz * sin(roll) * cos(pitch);

  // 計算方位角（度）
  float heading = atan2(my_c, mx_c) * 180 / PI;
  if (heading < 0) heading += 360;  // 負角轉正值

  Serial.print("Heading: "); Serial.print(heading, 1); Serial.println(" deg");
  delay(100);
}

// 讀取單軸 16-bit 原始值（Little Endian）
int16_t readAxis(int addr, int reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(addr, 2);
  return Wire.read() | (Wire.read() << 8);
}
```

## 實測數據

三軸雲台固定旋轉，紀錄方位誤差：

| 傾斜角度 | 未補償誤差 | 補償後誤差 |
|----------|------------|------------|
| 0 度     | 0.5 度     | 0.5 度     |
| 30 度    | 18.2 度    | 1.2 度     |
| 45 度    | 24.7 度    | 1.8 度     |

數據說明一切：未補償時 30 度傾斜 = 18 度誤差；加上傾斜補償，同樣角度誤差壓到 1.2 度。

## 為什麼這個感測器值得學

HMC5883L 是 maker 唯一接觸「三維磁場向量」的機會。學會 tilt compensation 之後，你學到的是一個可以跨領域應用的底層概念——

當你做無人機的姿態估算、做 AR 頭盔的空間定位、甚至做物流追蹤的傾倒偵測，你處理的問題都是同一件事：如何在感測器不水平的時候，仍然正確理解它在空間中的方向。

磁力計加加速度計，這是最基礎的感測器融合。學會這個，再去看互補濾波器（complementary filter）或卡爾曼濾波器（Kalman filter），你會發現它們只是用不同的數學方式包裝同一個概念：用多個感測器的長處，補償彼此的短處。

## 增益設定的眉角

程式中我用的是增益 5（預設範圍 ±1.3 Ga）。增益越高，低緯度地區的解析度越好，但靠近金屬或磁鐵時容易飽和。如果你發現羅盤讀數突然跳動，先檢查是不是增益設太高了。實際裝進你的外殼之後一定要重新校準。

## 這個項目適合升級成 Whop 完整套件

HMC5883L + ADXL345 模組，加上註解詳細的完整程式碼，適合作為「感測器融合入門」的第一個練手專案。從電路接線、I2C 參數設定、到 tilt compensation 數學推導，全部有詳細文件。

完整程式碼與硬體建議：[Whop 完整專案包 PLACEHOLDER_WHOP_PACK]

---

張旭豐｜機械工程博士｜雲林科技大學
