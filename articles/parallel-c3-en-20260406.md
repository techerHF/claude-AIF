# ADXL345 Tap Detection — Why Your Threshold Is Probably Wrong

Built a impact detector last month with the ADXL345. Set THRESH_TAP to 100 expecting to catch "strong" taps. Nothing happened. Took me two days to realize the datasheet units were lying to me in a way I didn't expect.

## The Unit Confusion That Breaks Every DIY Tap Detector

Most guides tell you THRESH_TAP is a "sensitivity" value. Higher number = more sensitive. That's technically true but useless without the conversion: each LSB equals 62.5 mg. So setting THRESH_TAP to 100 means you're looking for taps at 100 * 62.5 = 6.25g. That's a pretty hard slam, not a tap.

The ADXL345 range setting complicates this further. If you're using +/-2g range, a 6.25g tap would saturate the sensor anyway. You'd never catch it. Most DIY projects set the range to +/-2g for sensitivity, then wonder why tap detection doesn't work -- because a 6.25g threshold in a +/-2g range clips everything.

Here's the register setup I ended up using for a tap detector that actually responds to light finger taps:

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

## The Power Saving Case for Interrupt-Based Detection

Here's what changed my approach: polling the ADXL345 at 100Hz draws about 140 uA. Interrupt-driven detection? You can sleep the Arduino and let the ADXL345 wake it only when a tap occurs -- dropping average current to under 20 uA on a 3.3V Arduino setup. That's a 7x power reduction.

The interrupt pin (INT1) on the ADXL345 fires when any threshold is exceeded. Your MCU can sleep. The sensor handles the monitoring.

Key numbers from my bench test:
- Polling at 100Hz: 140 uA average draw
- Interrupt-driven with MCU sleep: 18 uA average draw
- THRESH_TAP conversion: 1 LSB = 62.5 mg (documented, but easy to forget)
- Setting THRESH_TAP to 32 = approximately 2g sensitivity
- Duration register: 1 LSB = 625 us (not 62.5 mg -- different register)

## Quick Reference for Common Threshold Values

| THRESH_TAP | Actual g-force |
|------------|----------------|
| 16         | 1g             |
| 32         | 2g             |
| 64         | 4g             |
| 128        | 8g             |

If your sensor clips or gives erratic readings, check your DATA_FORMAT register range setting. +/-2g clips at 2g. +/-4g gives you headroom up to 4g. Set range first, then calibrate threshold.

Full write-up with complete annotated code in the comments.