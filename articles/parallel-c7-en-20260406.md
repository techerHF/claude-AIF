# MAX6675 Thermocouple High-Temperature Measurement with Cold Junction Compensation

If you have ever tried reading a K-type thermocouple directly with an Arduino, you know the headache. Raw thermocouple voltage is in the millivolt range, and the readings drift all over the place unless you handle cold junction compensation. The MAX6675 solves exactly this, and it does it on-chip.

## The Problem: "Cold" Junction Is Not Cold

A thermocouple produces voltage based on the temperature difference between its two junctions. One junction goes into your kiln or heat source (the hot junction), and the other end sits at your board (the cold junction). Here is the catch: that "cold" junction is often at room temperature, and it fluctuates. Without compensation, your 800C reading might report 25C off because the cold end changed by a few degrees.

You could hand-roll compensation using a separate ambient temperature sensor and do the math yourself, but the MAX6675 bakes all of that into the chip. It measures the cold junction temperature internally and adds the compensation automatically over SPI.

## How It Works

The MAX6675 reads the K-type thermocouple and outputs a 12-bit digital value with 0.25C resolution over SPI. The math is handled inside, and you get a clean temperature value. No manual compensation, no lookup tables for ambient drift.

```
#include <SPI.h>

const int MAX6675_SO = 12;  // MISO
const int MAX6675_CS = 10;  // Chip Select
const int MAX6675_SCK = 13; // Clock

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
    return NAN;  // Thermocouple disconnected
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

## Why Not Just Read Raw Voltage?

You can technically read raw K-type thermocouple voltage with an Arduino ADC, but you are looking at about 41 microvolts per degree Celsius. The Arduino ADC steps are too coarse for useful accuracy, and you still have to handle compensation yourself. The MAX6675 gives you 0.25C resolution out of the box with no additional math.

## Real Numbers

- Range: 0 to 1023.75C
- Resolution: 0.25C (12-bit)
- Accuracy: +/- 3C typical
- Interface: SPI (3 wires + power)
- Power: 5V compatible

## Where This Shows Up

K-type thermocouples with the MAX6675 are the go-to for monitoring kiln temperatures, ceramic oven elements, 3D printer heat blocks, and refinery instrumentation. The combination of high range and decent accuracy at low cost makes it the standard entry point for any project above 125C, which is where most semiconductor temperature sensors give up.

Full write-up with complete annotated code in the comments.
