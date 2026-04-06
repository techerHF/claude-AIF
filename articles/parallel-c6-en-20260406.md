# MCP4725 DAC: Generating Clean Analog Waveforms Without PWM Workarounds

If you've been faking analog voltages with PWM plus a low-pass filter, the MCP4725 12-bit DAC is a direct upgrade worth considering. Unlike PWM, this chip outputs a true DC voltage that doesn't need filtering.

## Why PWM Falls Short

PWM模拟DAC有两个致命问题。第一，你需要自己做低通滤波器——截断频率算不对，波形就糊了。第二，输出阻抗高（ typically 10kΩ+），驱动能力弱。实测我用 Arduino Uno 的 PWM 输出 2.5V，实际测出来在 2.3V 到 2.7V 之间跳动，纹波峰值 200mV。

## Enter the MCP4725

The MCP4725 is a 12-bit I2C DAC. It outputs 0-5V with 4096 steps (0.0012V resolution). No filter needed, clean DC output.

**Key specs:**
- 12-bit resolution (4096 levels)
- I2C at 400kHz (Fast Mode)
- Built-in 2.048V reference (or use VCC as reference)
- 2.7-5.5V operation

## The I2C Speed Bottleneck

Here's the catch: at 400kHz I2C, sending a DAC update takes roughly 100μs. That gives you a maximum update rate of about **10kHz**. For audio or high-frequency waveforms, this is your limiting factor.

For a sine wave lookup table, I precompute 256 values and send them in a loop:

```cpp
#include <Wire.h>
#include <math.h>

#define DAC_ADDR 0x60
const int TABLE_SIZE = 256;

// Precomputed sine table (0-255 mapped to 0-4095 DAC values)
uint16_t sineTable[TABLE_SIZE];

void generateSineTable() {
  for (int i = 0; i < TABLE_SIZE; i++) {
    float sineVal = sin(2.0 * PI * i / TABLE_SIZE); // -1 to 1
    sineTable[i] = (uint16_t)((sineVal + 1.0) * 2047.5); // 0-4095
  }
}

void setup() {
  Wire.begin();
  Serial.begin(115200);
  generateSineTable();
}

void writeDAC(uint16_t value) {
  Wire.beginTransmission(DAC_ADDR);
  Wire.write(0x40); // Write DAC register
  Wire.write(value >> 4); // Upper 8 bits
  Wire.write((value & 0x0F) << 4); // Lower 4 bits
  Wire.endTransmission();
}

void loop() {
  static int index = 0;
  writeDAC(sineTable[index]);
  index = (index + 1) % TABLE_SIZE;
  // At 100μs per update, one cycle = 256 * 100μs = 25.6ms
  // ≈ 39Hz sine wave output
}
```

## Real-World Results

I tested this with an oscilloscope comparing PWM+filter vs MCP4725:
- PWM+filter: 40mV ripple at 1kHz
- MCP4725: < 2mV ripple (undetectable)

For function generators, audio amplitude control, or anywhere you need clean DC voltages, the MCP4725 wins. The tradeoff is speed—at 10kHz max update rate, it's fine for low-frequency waveforms but won't replace a true high-speed DAC for audio.

What waveforms are you planning to generate? I've got square and triangle wave examples in my full write-up.
