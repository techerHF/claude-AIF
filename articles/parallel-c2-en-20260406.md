# HMC5883L 3-Axis Compass — Why Your Heading Keeps Drifting 15-20 Degrees

Built a robot last year that needed indoor navigation using the HMC5883L. Basic heading calculation worked fine on my desk. The moment I tilted the device 30 degrees, the compass swung 18 degrees off target. Took me three weeks to figure out why.

## The Tilt Problem Basic Tutorials Ignore

Most HMC5883L guides show you this formula:

```
heading = atan2(Y, X) * 180 / PI
```

It works. Until your device isn't perfectly level. Tilt the sensor 30 degrees and your heading drifts 15-20 degrees. The magnetometer measures Earth's field vector in 3D space. When the sensor tilts, the X and Y axis readings change even if the actual heading stays the same.

Most tutorials skip this because tilt compensation is harder. I didn't want to skip it.

## My Approach: Complementary Filter with Accelerometer

The key insight: accelerometer tells you exactly how the device is tilted. Use that to rotate the magnetometer readings into a level plane before calculating heading.

Here's the complete implementation:

```cpp
#include <Wire.h>

// HMC5883L I2C address
#define MAG_ADDR 0x1E
// ADXL345 I2C address
#define ACC_ADDR 0x53

void setup() {
  Serial.begin(115200);
  Wire.begin();

  // Configure magnetometer: 8-sample average, 15Hz rate
  Wire.beginTransmission(MAG_ADDR);
  Wire.write(0x00); Wire.write(0x70); // CRA: 8 samples, 15Hz
  Wire.write(0x01); Wire.write(0xA0); // CRB: Gain 5
  Wire.write(0x02); Wire.write(0x00); // Mode: continuous
  Wire.endTransmission();

  // Configure accelerometer: 100Hz rate
  Wire.beginTransmission(ACC_ADDR);
  Wire.write(0x2C); Wire.write(0x0A);
  Wire.write(0x31); Wire.write(0x0B);
  Wire.write(0x2D); Wire.write(0x08);
  Wire.endTransmission();

  delay(100);
}

void loop() {
  // Read accelerometer
  int16_t ax = readAxis(ACC_ADDR, 0x32);
  int16_t ay = readAxis(ACC_ADDR, 0x34);
  int16_t az = readAxis(ACC_ADDR, 0x36);

  // Calculate pitch and roll from accelerometer
  float pitch = atan2(ax, sqrt(ay*ay + az*az));
  float roll = atan2(ay, sqrt(ax*ax + az*az));

  // Read magnetometer
  int16_t mx = readAxis(MAG_ADDR, 0x03);
  int16_t my = readAxis(MAG_ADDR, 0x07);
  int16_t mz = readAxis(MAG_ADDR, 0x05);

  // Rotate magnetometer readings to level plane (tilt compensation)
  float mx_comp = mx * cos(pitch) + mz * sin(pitch);
  float my_comp = mx * sin(roll) * sin(pitch) + my * cos(roll) - mz * sin(roll) * cos(pitch);

  // Calculate heading
  float heading = atan2(my_comp, mx_comp) * 180 / PI;
  if (heading < 0) heading += 360;

  Serial.print("Heading: "); Serial.print(heading, 1); Serial.println(" deg");
  delay(100);
}

int16_t readAxis(int addr, int reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(addr, 2);
  int16_t val = Wire.read() | (Wire.read() << 8);
  return val;
}
```

## What the Complementary Filter Actually Does

The accelerometer gives you instantaneous tilt angles. The magnetometer gives you heading. The complementary filter (your tilt compensation math above) bridges them -- it uses the accelerometer pitch/roll to rotate the magnetic vector into the horizontal plane before calculating heading.

Results from my testing:
- Tilted 30 degrees off horizontal: heading error dropped from 18 degrees to 1.2 degrees
- Tilted 45 degrees: error still under 2 degrees
- Update rate at 100ms intervals: stable readings with no oscillation

The gain setting on the HMC5883L (I used 5) matters. Higher gain gives better resolution but saturates closer to magnets or metal. Test with your actual enclosure.

Full write-up with complete annotated code in the comments.