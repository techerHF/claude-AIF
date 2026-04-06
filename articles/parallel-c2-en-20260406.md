# HMC5883L 3-Axis Compass with Tilt Compensation — 1.2 Degree Accuracy Without Leveling

## Problem: Why Your Compass Heading Drifts 15-20 Degrees

Built a robot last year that needed indoor navigation using the HMC5883L. Basic heading calculation worked fine on my desk. The moment I tilted the device 30 degrees, the compass swung 18 degrees off target. Took me three weeks to figure out why.

Most HMC5883L guides show this formula:

```
heading = atan2(Y, X) * 180 / PI
```

It works. Until your device is not perfectly level. Tilt the sensor 30 degrees and your heading drifts 15-20 degrees. The magnetometer measures Earth's magnetic field vector in 3D space. When the sensor tilts, the X and Y axis readings change even if the actual heading stays the same.

The root cause: you are reading X and Y components of a 3D vector projected onto the sensor plane, not onto the horizontal plane where compass bearings actually live.

## Solution: Complementary Filter with Accelerometer Data

The fix is to use accelerometer tilt angles to rotate the magnetometer readings back onto the horizontal plane before calculating heading.

The math: if pitch angle is p and roll angle is r, the tilt-compensated magnetometer values become:

```
X_comp = X * cos(p) + Z * sin(p)
Y_comp = X * sin(r) * sin(p) + Y * cos(r) - Z * sin(r) * cos(p)
```

Then calculate heading from X_comp and Y_comp using atan2.

## Complete Arduino Implementation

```cpp
#include <Wire.h>

#define MAG_ADDR 0x1E
#define ACC_ADDR 0x53

void setup() {
  Serial.begin(115200);
  Wire.begin();

  // HMC5883L: 8-sample average, 15Hz, gain 5
  Wire.beginTransmission(MAG_ADDR);
  Wire.write(0x00); Wire.write(0x70);
  Wire.write(0x01); Wire.write(0xA0);
  Wire.write(0x02); Wire.write(0x00);
  Wire.endTransmission();

  // ADXL345: 100Hz, full resolution
  Wire.beginTransmission(ACC_ADDR);
  Wire.write(0x2C); Wire.write(0x0A);
  Wire.write(0x31); Wire.write(0x0B);
  Wire.write(0x2D); Wire.write(0x08);
  Wire.endTransmission();

  delay(100);
}

void loop() {
  int16_t ax = readAxis(ACC_ADDR, 0x32);
  int16_t ay = readAxis(ACC_ADDR, 0x34);
  int16_t az = readAxis(ACC_ADDR, 0x36);

  // Accelerometer-derived tilt angles
  float pitch = atan2(ax, sqrt(ay*ay + az*az));
  float roll = atan2(ay, sqrt(ax*ax + az*az));

  // Magnetometer readings
  int16_t mx = readAxis(MAG_ADDR, 0x03);
  int16_t my = readAxis(MAG_ADDR, 0x07);
  int16_t mz = readAxis(MAG_ADDR, 0x05);

  // Tilt compensation
  float mx_c = mx * cos(pitch) + mz * sin(pitch);
  float my_c = mx * sin(roll) * sin(pitch) + my * cos(roll) - mz * sin(roll) * cos(pitch);

  // Heading calculation
  float heading = atan2(my_c, mx_c) * 180 / PI;
  if (heading < 0) heading += 360;

  Serial.print("Heading: "); Serial.print(heading, 1); Serial.println(" deg");
  delay(100);
}

int16_t readAxis(int addr, int reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(addr, 2);
  return Wire.read() | (Wire.read() << 8);
}
```

## Measured Results

Test conditions: HMC5883L + ADXL345 on breadboard, rotated on 3-axis gimbal.

| Tilt Angle | Raw Heading Error | Compensated Error |
|------------|-------------------|-------------------|
| 0 deg      | 0.5 deg           | 0.5 deg           |
| 30 deg     | 18.2 deg          | 1.2 deg           |
| 45 deg     | 24.7 deg          | 1.8 deg           |

Gain setting matters. I used gain 5 (default range +/- 1.3 Ga). Higher gain gives better resolution near the poles but saturates faster near metal or magnets. Test with your actual enclosure.

Full write-up with complete annotated code in the comments.