#include "accel_handler.h"



AccelHandler::AccelHandler(ChipType chip, int SDA, int SCL) {
  chipType = chip;
  Wire.begin(SDA, SCL);

  switch (chip) {
    case MC3419: 
      // Start the sensor with I2C mode (bSpi = true), and I2C address = 0x4C (common for MC3419)
      if (!mc3419.start(true, 0x4C)) {
        Serial.println("Failed to initialize MC34X9 chip!");
        while (1);
      }
      Serial.println("MC34X9 initialized.");
      break;

    case MPU6050:
      //initialize mpu6050
      if (!mpu6050.begin()) {
        Serial.println("Failed to initialize MPU6050 chip!");
        while (1);
      }
      Serial.println("MPU6050 initialized.");

      //range options: 2_G, 4_G, 8_G, 16_G. Higher range sacrifices accuracy & power usage
      mpu6050.setAccelerometerRange(MPU6050_RANGE_4_G); 
      
      //range options: 250_DEG, 500_DEG, 1000_DEG, 2000_DEG
      mpu6050.setGyroRange(MPU6050_RANGE_500_DEG);
      
      //bandwidth options: 260_HZ, 184_HZ, 94_HZ, 44_HZ, 21_HZ, 10_HZ, 5_HZ
      mpu6050.setFilterBandwidth(MPU6050_BAND_21_HZ);

      break;

    default:
      Serial.println("wrong accelerometer selected!");
      while(1);
  }
}

Values AccelHandler::read() {
  float x = 0.0, y = 0.0, z = 0.0;

  switch (chipType) {
    case MPU6050: {
      sensors_event_t a, g, temp;
      mpu6050.getEvent(&a, &g, &temp);
      x = a.acceleration.x;
      y = a.acceleration.y;
      z = a.acceleration.z;
      break;
    }

    case MC3419: {
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

