#include <Wire.h>
#include "MC34X9.h"

MC34X9 MC34X9_acc;

void setup() {
  Serial.begin(115200);
  delay(1000); // Give time for Serial monitor to open

  // Start I2C using custom SDA and SCL pins (SDA = 8, SCL = 9)
  Wire.begin(5, 6);

  // Start the sensor with I2C mode (bSpi = true), and I2C address = 0x4C (common for MC3419)
  if (!MC34X9_acc.start(true, 0x4C)) {
    Serial.println("Failed to initialize MC34X9 sensor!");
    while (1);
  }

  Serial.println("MC34X9 initialized.");
}

void loop() {
  MC34X9_acc_t accData = MC34X9_acc.readRawAccel();

  Serial.print("Z-Axis (raw): ");
  Serial.print(accData.ZAxis);
  Serial.print("   Z-Axis (g): ");
  Serial.println(accData.ZAxis_g, 4);

  delay(20);
}
