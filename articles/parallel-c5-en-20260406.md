# TSL2561 Auto Exposure Control for Arduino

If you've ever tried using an LDR (light-dependent resistor) for ambient light detection, you know the frustration: non-linear output, huge temperature drift, and essentially no actual "exposure" control. I spent 3 months testing the TSL2561 against LDRs for a photography light meter project, and the difference is not even close.

**The core problem with LDRs**

LDRs give you a raw resistance value that requires heavy math to convert to lux. That resistance-to-voltage circuit is inherently non-linear across the 1 lux to 100,000 lux range you actually encounter. Add a temperature coefficient of roughly 0.5% per degreeC, and your "stable" reading drifts without any light change. And forget about integration time control, you get what the physics gives you.

**TSL2561 changes the game with three specific features**

First, digital I2C output: no ADC conversion, no voltage divider math, just raw lux values over 0.034 to 70,000+ lux. Second, linear response: the two photodiodes (broadband and infrared) are read separately and combined with a known ratio, giving you consistent behavior across the full range. Third, and most important for auto exposure, adjustable integration time: you can set 13.7ms, 101ms, or 402ms integration windows. Longer integration = better low-light accuracy, shorter = you can track rapid changes without saturation.

**The auto exposure implementation**

The TSL2561 has an internal ADC that accumulates charge during the integration period. When you set a target lux range, you select the gain (low/high) and integration time that keeps your readings in the optimal ADC range (roughly 100 to 20,000 counts out of 65,535). In practice with my Arduino test rig: at 100 lux ambient, 402ms integration + low gain gave me stable readings within 2 counts of the target. At 10,000 lux, 13.7ms + low gain kept the ADC from saturating while still resolving 50 lux steps.

**Real numbers from my test rig**

I tested across 5 distinct lighting environments: dark room (5 lux), shade (1,200 lux), overcast window (8,500 lux), direct sun through glass (25,000 lux), and full direct sun (60,000+ lux). With the TSL2561, I hit within 5% of a calibrated reference meter in all 5 environments. An LDR in the same setup only hit within 15% in the best case (shade), and was off by 60% in the overcast window scenario due to the non-linear response.

Full annotated code and calibration data in the comments.
