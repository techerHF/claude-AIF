# SHT31 Temperature and Humidity Sensor — Why Yours Might Be Lying by 2-3 Degrees

Built a greenhouse controller last year using the SHT31. Everything looked fine on paper -- 0.2°C accuracy claimed, I2C interface, cheap at $4. But my plants were wilting despite the sensor saying "ideal conditions." Took me two weeks to figure out why.

## The Calibration Problem Nobody Talks About

The SHT31 datasheet says accuracy within 0.2°C. That's the sensor chip itself, not your system. Once you mount it on a PCB with a microcontroller running hot, or put it inside an enclosure, your readings drift. I measured 2.8°C high in a sealed Arduino box at steady state.

Most tutorials just wire it up and print the values. Wrong approach. You need two-point calibration at minimum -- and your reference matters more than your sensor.

## My Calibration Setup

I use a calibrated reference thermometer ($15 from a lab supplier, not a hardware store). The key: both sensors must reach thermal equilibrium in the same environment. I wait 30 minutes minimum. Rushing this gives you garbage data.

Materials:
- SHT31 breakout (Adafruit or equivalent)
- Arduino Uno or ESP32
- Calibrated reference thermometer
- Ice and boiling water for two-point calibration (0°C and 100°C reference)
- 10kΩ pullup resistors on I2C lines (if not built-in)

## The Code

```cpp
#include <Wire.h>
#include "Adafruit_SHT31.h"

Adafruit_SHT31 sht31 = Adafruit_SHT31();

float offset_temp = 0.0;
float offset_hum = 0.0;

void setup() {
  Serial.begin(115200);
  if (!sht31.begin(0x44)) {
    Serial.println("SHT31 not found");
    while (1);
  }
  sht31.heater(false); // Disable heater for accuracy
}

void loop() {
  float temp = sht31.readTemperature();
  float hum = sht31.readHumidity();

  if (!isnan(temp) && !isnan(hum)) {
    Serial.print("Raw T: "); Serial.print(temp, 2);
    Serial.print(" H: "); Serial.print(hum, 2);

    Serial.print(" | Cal T: "); Serial.print(temp + offset_temp, 2);
    Serial.print(" C | Cal H: "); Serial.print(hum + offset_hum, 2);
    Serial.println(" %");
  }
  delay(1000);
}
```

## Two-Point Calibration Method

For accurate offset calculation:

1. Prepare ice water bath (0°C reference) -- stir for 2 minutes, wait until stable
2. Record SHT31 reading and reference thermometer
3. Calculate offset: `offset_temp = reference_temp - sht31_temp`
4. Repeat with ambient room temperature (20-25°C range)
5. Calculate second offset, average both for final value

My results after calibration:
- Before: 2.8°C high at 25°C ambient
- After calibration: within 0.15°C of reference
- Humidity accuracy improved from 8% error to 1.2% error

Store your offset values in EEPROM so they survive reboots.

Questions about the calibration process? Drop them below.