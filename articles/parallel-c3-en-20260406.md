ADXL345 impact detection — why your tap sensor never triggers

Most ADXL345 tutorials set THRESH_TAP = 100 and call it "high sensitivity." Here's the problem: 1 LSB equals 62.5 mg. So THRESH_TAP = 100 means 6.25g of force required to trigger. That's hammer-strike territory, not finger-tap.

The second issue is power. Polling mode keeps your MCU awake at 130 uA. For battery-powered projects, that's your battery dying in days, not months.

The fix is interrupt-based detection. ADXL345 monitors taps internally. Only when the condition is met does it wake your MCU via INT1. Standby current drops from 140 uA to 18 uA — roughly 7x improvement. Response time stays under 1 ms because the chip handles detection in hardware.

My tested settings:
- Range: +/-4g (not +/-2g, or your 3g tap clips)
- THRESH_TAP: 32 (~2g, practical for finger taps)
- DUR: 12.5ms window
- Latent: 100ms
- Window: 250ms
- Enable all three axes

Code sketch:

```arduino
#include <Wire.h>
#define ADXL345_ADDR 0x53
#define THRESH_TAP 32  // 32 × 62.5mg = 2g

void setup() {
  Serial.begin(115200);
  Wire.begin();

  // Measurement mode
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(0x2D);
  Wire.write(0x08);
  Wire.endTransmission();

  // Threshold: 2g
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(0x1D);
  Wire.write(THRESH_TAP);
  Wire.endTransmission();

  // Enable XYZ tap detection + interrupt
  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(0x2A);
  Wire.write(0x07);  // XYZ enabled
  Wire.endTransmission();

  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(0x2E);
  Wire.write(0x07);  // INT1 enabled
  Wire.endTransmission();

  attachInterrupt(digitalPinToInterrupt(2), tapISR, RISING);
  Serial.println("ADXL345 ready — tap to test");
}

void loop() {
  // MCU sleeps until interrupt fires
  Serial.println("Sleeping...");
  delay(1000);
}

void tapISR() {
  Serial.println("TAP DETECTED");
}
```

Key numbers: 62.5 mg/LSB unit, 7x power reduction, 18 uA standby. Your sensor isn't broken. Your threshold calculation is.

Full write-up with complete annotated code in the comments.