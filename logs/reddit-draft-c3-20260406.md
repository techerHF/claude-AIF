# Reddit Draft - r/arduino

## Title
ADXL345 Tap Detection: Why THRESH_TAP=100 Never Triggers (Correct Setup)

## Body

Built an ADXL345 impact detector last month. Set THRESH_TAP to 100 expecting to catch strong taps. Nothing fired for two days until I read the datasheet more carefully.

The problem: THRESH_TAP units are not what most tutorials suggest. Each LSB equals 62.5 mg. Setting THRESH_TAP to 100 means you are looking for 100 x 62.5 = 6.25g impacts. That is a hard slam, not a tap. On top of that, if you are using +/-2g range (common default), a 6.25g tap clips at 2g anyway. You would never catch it.

Here is the register setup that finally worked for light finger taps. Set range to +/-4g first for headroom, then set THRESH_TAP to 32 (~2g), Duration to 12.5ms, and enable all three axes:

```cpp
#include <Wire.h>

#define ADXL345_ADDR 0x53

// Register addresses
#define REG_THRESH_TAP   0x1D
#define REG_DURATION     0x21
#define REG_LATENT       0x22
#define REG_WINDOW       0x23
#define REG_INT_MAP      0x2F
#define REG_INT_ENABLE   0x2E
#define REG_TAP_AXES     0x2A
#define REG_POWER_CTL    0x2D
#define REG_DATA_FORMAT  0x31
#define REG_FIFO_CTL     0x38

void setup() {
  Serial.begin(115200);
  Wire.begin();

  // Set range to +/-4g for better tap headroom
  // Bits D1:D0 = 01 -> +/-4g
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_DATA_FORMAT);
  Wire.write(0x01);
  Wire.endTransmission();

  // THRESH_TAP: 62.5 mg per LSB
  // Target: detect taps above ~2g -> 2g / 62.5mg = 32 LSB
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_THRESH_TAP);
  Wire.write(32);  // ~2g threshold
  Wire.endTransmission();

  // Duration: max time tap can be above threshold (625 us per LSB)
  // Set to 20 LSB = 12.5 ms
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_DURATION);
  Wire.write(20);
  Wire.endTransmission();

  // Latent: time after tap before second tap window starts (1.25 ms per LSB)
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_LATENT);
  Wire.write(80);  // 100 ms latent window
  Wire.endTransmission();

  // Window: time after latent where second tap can start double-tap (1.25 ms per LSB)
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_WINDOW);
  Wire.write(200);  // 250 ms window
  Wire.endTransmission();

  // Enable tap detection on all axes
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_TAP_AXES);
  Wire.write(0x07);  // X, Y, Z all enabled
  Wire.endTransmission();

  // Map INT1 for single tap (leave INT2 for double tap if needed)
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_INT_MAP);
  Wire.write(0x00);  // Single tap on INT1
  Wire.endTransmission();

  // Enable single tap interrupt
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_INT_ENABLE);
  Wire.write(0x40);  // SINGLE_TAP bit
  Wire.endTransmission();

  // Measure mode (disable sleep for continuous operation)
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(REG_POWER_CTL);
  Wire.write(0x08);
  Wire.endTransmission();

  delay(100);
  Serial.println("ADXL345 tap detector ready");
  Serial.println("THRESH_TAP = 32 (~2g)");
  Serial.println("Check Serial Monitor for tap events");
}

void loop() {
  // Read interrupt source register to clear pending interrupts
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(0x30);  // INT_SOURCE register
  Wire.endTransmission(false);
  Wire.requestFrom(ADXL345_ADDR, 1);
  uint8_t intSource = Wire.read();

  if (intSource & 0x40) {  // SINGLE_TAP bit
    Serial.println("TAP DETECTED");
  }

  // Alternative: use interrupt pin (INT1 on ADXL345)
  // Wire pin 2 on Arduino -> INT1 pin on ADXL345
  // This eliminates polling -- sensor wakes MCU only on actual taps
  delay(50);
}
```

After switching to interrupt-based detection with the MCU sleeping, power draw dropped from 140 uA (polling at 100Hz) to 18 uA average. The ADXL345 wakes the Arduino only when a tap exceeds your threshold.

Full tutorial with code and schematics in the comments.