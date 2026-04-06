# INA219 Current and Power Monitoring: Solar, Battery, and Power Supply Projects

Ever tried to measure current or power consumption in your Arduino project and ended up guessing? I have. Spent way too long wondering if my solar setup was actually charging or just idling. The INA219 broke that pattern for me.

## The Problem with Basic Current Sensing

Most Arduino current measurements rely on Ohm's law with a shunt resistor and ADC. Sounds simple until you realize the ADC on an Arduino Uno has only 10-bit resolution across 5V -- that's 4.9mV per step. For a project running at 20mA with a 0.1-ohm shunt, your "measurement" is just 2mV of signal sitting inside ADC noise. Not great.

## Enter the INA219

The INA219 from Texas Instruments solves this with a dedicated 12-bit ADC, built-in shunt resistor (typically 0.1 ohms), and I2C interface. It measures bus voltage (up to 26V), shunt voltage, and calculates current and power directly. No math required on your microcontroller.

Key specs:
- Bus voltage: 0-26V
- Current resolution: 0.8mA (with built-in shunt)
- Power resolution: 20mW
- I2C address: selectable (0x40-0x4F)

## Arduino I2C Setup

```cpp
#include <Wire.h>
#include <Adafruit_INA219.h>

Adafruit_INA219 ina219;

void setup() {
  Serial.begin(115200);
  if (!ina219.begin()) {
    Serial.println("INA219 not found");
    while (1);
  }
  ina219.setCalibration_32V_1A(); // Good for most projects
}

void loop() {
  float shunt_v = ina219.getShuntVoltage_mV();
  float bus_v = ina219.getBusVoltage_V();
  float current_mA = ina219.getCurrent_mA();
  float power_mW = ina219.getPower_mW();

  Serial.print("Bus: "); Serial.print(bus_v); Serial.println(" V");
  Serial.print("Current: "); Serial.print(current_mA); Serial.println(" mA");
  Serial.print("Power: "); Serial.print(power_mW); Serial.println(" mW");
  delay(500);
}
```

## Calibration for Better Accuracy

The default calibration works, but you can improve accuracy by calibrating to your specific shunt. For a 0.1-ohm external shunt handling up to 3A:

```cpp
void setup() {
  ina219.begin();
  ina219.setCalibration_32V_2A();
  ina219.setCalibration(0.1, 3.0); // shunt ohms, max expected amps
}
```

## Real Numbers from My Solar Monitor

After calibration, my outdoor solar project showed consistent readings:
- Charging current: 340mA in direct sunlight (measured with INA219)
- Night leakage: 0.8mA (previously invisible with basic ADC)
- Battery drain rate: calculated automatically, no manual math

The INA219 let me catch a faulty USB solar controller that was drawing 50mA even at night. Paid for itself in one weekend.

Works great with ESP32 too -- the 3.3V I2C is fully compatible.
