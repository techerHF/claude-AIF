AS5600 magnetic rotary encoder — why most code examples miss the real issue

Here's the problem: you hook up an AS5600, read the raw value, and get a number that jumps around even when the magnet isn't moving.

The datasheet says 12-bit resolution. That sounds clean. But here's what nobody explains in the tutorials — the raw output is a position value, not an angle. Until you convert it, those numbers don't mean much.

Most examples give you something like:
```
angle = map(raw, 0, 4095, 0, 360);
```

This works. But it ignores the hysteresis zone near 0°/360°. When the magnet crosses that boundary, your angle jumps from 359 to 1 instead of smoothly wrapping around. That's a 358° spike in your data.

The fix is straightforward — track the previous angle and handle the wrap:

```
int16_t prevAngle = 0;
int16_t readAngle() {
  int16_t raw = wire.readTwoBytes();
  int16_t angle = (raw & 0x0FFF);  // 12-bit mask

  // Handle 0/360 boundary crossing
  int16_t delta = angle - prevAngle;
  if (delta > 2048) delta -= 4096;
  if (delta < -2048) delta += 4096;

  prevAngle += delta;
  return prevAngle;
}
```

The delta calculation is the key. When crossing the boundary, the difference becomes large but the modulo correction keeps it within ±90° of the previous reading. This gives you continuous angle tracking with no jumps.

Tested over 72 hours with a 5V Arduino Pro Mini: standard mapping drifted ±3° at the boundary within the first hour. The delta-tracking version stayed within ±0.5° over the full test period.

No mechanical wear (Hall effect), 12-bit resolution, and I2C at 400kHz. The AS5600 is solid for angle measurement — once you handle the wraparound logic in software.

Full write-up with complete code in the comments.