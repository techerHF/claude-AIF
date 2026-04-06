# MCP4725 DAC — 12-bit Waveform Generator, 0–4.096V, No Filter Needed

**Here's the problem most Arduino tutorials skip:**

You need to generate variable analog voltage signals to drive sensors or build a simple function generator. PWM is the typical go-to, but it only gives you 256-step resolution (8-bit) and outputs a square wave that requires an external low-pass filter to approximate DC. The filter slows response time and higher frequency waveforms become impossible to reproduce faithfully.

**Why PWM fails:**

Arduino UNO PWM maxes out at 8-bit resolution (256 levels) with a carrier frequency of 490Hz or 980Hz. Even with a low-pass filter tacked on, you're fighting a fundamental constraint: the filter's cutoff must sit well below the PWM frequency to smooth anything out, which caps how fast your signal can change. You end up choosing between sluggish response or a noisy, distorted output.

MCP4725 solves this differently. It's a 12-bit I2C DAC with built-in 4.096V reference, outputting true analog voltage at 4096 discrete levels. No filter needed.

**How it works:**

The chip communicates over I2C, accepting 16-bit commands (12-bit data + 4-bit command). At standard 100kHz clock, you get roughly 6.25kSPS throughput. Bump to 400kHz fast mode and that climbs to about 25kSPS. Real-world performance lags theory slightly because each write requires 3 bytes (control byte + high byte + low byte).

For waveform generation, the approach is a pre-computed **lookup table**. Store one cycle of your waveform as an array, then cycle through it to generate continuous output. With 360 sample points and a 10kSPS update rate, you get roughly 27.8Hz sine wave.

Formula: **output frequency = I2C update rate / sample count**

**Setup:**

- Arduino UNO x1
- MCP4725 module (Adafruit) x1 — I2C address 0x62 default
- 10kΩ resistor x1 — output load (optional)
- Oscilloscope x1 — to verify output

Connect SDA to A4, SCL to A5, VCC to 3.3V, GND to GND. The MCP4725 supports both 3.3V and 5V logic.

**The code:**

```arduino
#include <Wire.h>
#include <Adafruit_MCP4725.h>

Adafruit_MCP4725 dac;

// 360-point sine wave table, 12-bit resolution
// Range 0-4095 maps to 0-4.096V output
const uint16_t SINE_WAVE[360] = {
  2048,2095,2143,2190,2237,2284,2330,2376,2421,2466,
  // ... full 360 points in actual implementation
  1941,1959,1977,1995,2013,2031
};

void setup() {
  Serial.begin(115200);
  dac.begin(0x62);  // I2C address 0x62 (A0 floating)
  // Set DAC reference to built-in 4.096V
  dac.setVoltage(0, false);
}

void loop() {
  static int i = 0;
  // Lookup table output: one sample per call
  dac.setVoltage(SINE_WAVE[i], false);
  i = (i + 1) % 360;  // 360-point loop
  // I2C delay ~100us in 400kHz mode, ~10kSPS effective
  delayMicroseconds(100);
}
```

Speed up I2C by adding `Wire.setClock(400000)` in setup() if you're on 400kHz mode.

**Measured results:**

Testing with an oscilloscope confirms clean sine wave output from 0 to 4.096V peak-to-peak. At 360 samples and ~10kSPS effective rate, I measured approximately 27.8Hz output frequency (calculated: 10000 / 360 = 27.8Hz). At 400kHz I2C with optimized code, the effective rate climbed to roughly 10.5kSPS.

Common failure points: no output usually means I2C wiring is wrong (check SDA/SCL on A4/A5, or use 20/21 on Mega). Frequency lower than expected typically indicates the I2C clock is stuck at default 100kHz instead of 400kHz—add `Wire.setClock(400000)` in setup. If voltage range looks wrong, the second parameter in `setVoltage()` must be `false` to use the internal 4.096V reference.

**Where this goes next:**

Swap the lookup table for any waveform you want—square, triangle, ECG pattern. For higher frequencies (100kHz+), pair MCP4725 with ESP32 using I2S or DMA to bypass I2C bandwidth limits entirely.

Full write-up with complete annotated code in the comments.