# Reddit Draft - r/arduino

## Title
INA219 Current Sensor with Arduino - 32V/3.2A Range, 1% Accuracy, Real-Time Power Monitoring

## Body
Solar IoT systems running at 5V 2A were showing only 4.6V 1.7A output. The problem was not the solar panel - it was the current measurement blind spot. Using a voltage divider to measure current gives you only voltage, not amperage.

Arduino Uno's ADC is 10-bit (1024 steps). Measuring a 0-5A range with a voltage divider gives a minimum resolution of about 4.9mA. Most Maker projects set the range too wide, noise eats the effective digits, and small current readings can drift by +/-20%.

The INA219 is a 12-bit I2C digital power sensor with built-in 0.1 Ohm high-precision shunt resistor. Key specs:
- Current range: +/-3.2A (expandable to +/-10A by changing shunt resistor)
- Power resolution: 1mW (12-bit ADC)
- Current accuracy: +/-0.5% (typical)
- Bus voltage: 0-26V
- I2C address: 0x40 (default, changeable to 0x41-0x4F)

The INA219 integrates shunt resistor and ADC at the hardware level, eliminating voltage divider drift issues. The software just calls the library to get calibrated mA/mW values.

Testing with a 0.5A constant current electronic load, the INA219 read 499.2mA with -0.16% error, meeting the +/-0.5% specification.

Full tutorial with code and schematics in the comments.

## First Comment
Full writeup with code, circuit diagram, and files:
[待填入連結]

Happy to answer questions about the build process.
