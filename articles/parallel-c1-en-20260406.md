# SHT31 Calibration — Real Data From 6-Month Stability Test

Built a greenhouse controller with SHT31 last year. Datasheet claims 0.2°C accuracy. After calibration, I got 0.15°C. Here's what nobody tells you about keeping it accurate over time.

## The Drift Problem

Most tutorials stop at "wire it up and read values." Wrong. Self-heating from the microcontroller causes 2.8°C drift in sealed enclosures. But that's not the worst part — the drift changes over time.

I ran the SHT31 alongside a calibrated reference for 6 months. Here's what I found:

**Drift over 180 days:**
- Month 1-2: offset stayed within 0.1°C
- Month 3-4: offset drifted to 0.25°C
- Month 5-6: offset stabilized at 0.35°C

The calibration curve isn't linear. You need recalibration every 90 days minimum.

## Two-Point Calibration Method

1. Ice water bath (0°C reference) — stir 2 min, wait 5 min for stability
2. Record SHT31 vs reference, calculate offset
3. Ambient room temp (25°C) for second reference point
4. Average both offsets, store in EEPROM

```cpp
#include <Wire.h>
#include "Adafruit_SHT31.h"

Adafruit_SHT31 sht31 = Adafruit_SHT31();
float offset_temp = 0.0;
float offset_hum = 0.0;

void setup() {
  Serial.begin(115200);
  if (!sht31.begin(0x44)) while(1);
  sht31.heater(false); // Disable heater
}

void loop() {
  float t = sht31.readTemperature();
  float h = sht31.readHumidity();
  if (!isnan(t) && !isnan(h)) {
    Serial.print("Cal T: "); Serial.print(t + offset_temp, 2);
    Serial.print(" C | Cal H: "); Serial.print(h + offset_hum, 2);
    Serial.println(" %");
  }
  delay(1000);
}
```

## Key Numbers
- Pre-calibration error: 2.8°C at 25°C ambient
- Post-calibration accuracy: within 0.15°C of reference
- Humidity error: 8% before, 1.2% after
- Recalibration interval: every 90 days

Full write-up with complete annotated code in the comments.