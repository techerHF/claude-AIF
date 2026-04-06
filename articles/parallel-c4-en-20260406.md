# INA219: I2C Power Monitor with 1% Accuracy

Wiring two multimeters just to measure current and voltage at the same time? The INA219 handles both through I2C, no manual range switching.

## The Problem

A standard multimeter shows one value at a time. Measure voltage or current, never both simultaneously. And if your project draws 3A peaks under load, a cheap meter at the $10 range is guessing.

Generic voltage sensors lack calibration and cannot measure current without breaking the circuit.

## The INA219 Solution

The INA219 from Texas Instruments is a high-precision power monitor with I2C interface. It measures three values simultaneously:

- Bus voltage: 0V to 32V
- Shunt voltage: 320mV range
- Calculated current: up to 3.2A with built-in 0.1 ohm resistor

**Accuracy: 1%** across the full range. No manual calibration.

The key advantage: this sensor never breaks your circuit. Install it inline between power supply and load, report readings continuously. Your Arduino logs power consumption, detects anomalies, or shuts down if current exceeds a threshold.

## Wiring (4 connections)

Arduino A4 (SDA) to INA219 SDA, A5 (SCL) to INA219 SCL, 3.3V to VCC, GND to GND. The INA219 does the math. You get current in amps and power in watts directly.

## Real Test Results

On a 12V LED strip: INA219 reported 0.85A at startup with a 1.2A peak lasting 200ms during LED turn-on. A budget multimeter showed a flat 0.9A throughout. The INA219 caught the inrush current spike that would have tripped thermal shutdown on a smaller supply.

At roughly $2 per breakout board module, the INA219 is the practical choice for power monitoring in any battery-powered or IoT project.

Full write-up with complete annotated code in the comments.