#include "accel_handler.h"



AccelHandler::AccelHandler(ChipType chip, int SDA, int SCL) {
  chipType = chip;
  Wire.begin(SDA, SCL);

  switch (chip) {
    case chip_MC3419: 
      // Start the sensor with I2C mode (bSpi = true), and I2C address = 0x4C (common for MC3419)
      if (!mc3419.start(true, 0x4C)) {
        Serial.println("Failed to initialize MC34X9 chip!");
        while (1);
      }
      Serial.println("MC34X9 initialized.");
      break;

    case chip_MPU6050:
      mpu6050.initialize();
      if (!mpu6050.testConnection()) {
        Serial.println("Failed to initialize MPU6050 chip!");
        while (1);
      } else {
        Serial.println("MPU6050 initialized.");

        // Set accelerometer range to ±4g
        mpu6050.setFullScaleAccelRange(MPU6050_ACCEL_FS_4);

        // Set gyroscope range to ±500 deg/s
        mpu6050.setFullScaleGyroRange(MPU6050_GYRO_FS_500);

        // Note: Filter bandwidth configuration is not directly supported in this library
      }

      break;

    default:
      Serial.println("wrong accelerometer selected!");
      while(1);
  }
}

Values AccelHandler::read() {
  float x = 0.0, y = 0.0, z = 0.0;

  switch (chipType) {
    case chip_MPU6050: {
      int16_t ax, ay, az;
      mpu6050.getAcceleration(&ax, &ay, &az);

      // Convert raw values to g using sensitivity for ±4g: 8192 LSB/g
      // Change divisor if using a different range
      x = ax / 819.20;
      y = ay / 819.20;
      z = az / 819.20;
      break;
    }

    case chip_MC3419: {
      MC34X9_acc_t accData = mc3419.readRawAccel();
      x = accData.XAxis_g;
      y = accData.YAxis_g;
      z = accData.ZAxis_g;
      break;
    }

    default:
      break;
  }

  return {x, y, z};
}


