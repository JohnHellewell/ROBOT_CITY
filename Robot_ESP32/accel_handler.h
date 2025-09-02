#ifndef ACCEL_HANDLER_H
#define ACCEL_HANDLER_H

//#include <Arduino>
//#include <Adafruit_MPU6050.h>
//#include <Adafruit_Sensor.h>
#include <MPU6050.h>
#include "MC34X9.h"



enum ChipType {
  chip_MPU6050,
  chip_MC3419
};

struct Values {
  float x;
  float y;
  float z;
};

class AccelHandler {
  private:
  ChipType chipType;
  MPU6050 mpu6050;
  MC34X9 mc3419;

  public:
  AccelHandler(ChipType chip, int SDA, int SCL, bool doPrint);

  //bool start();
  virtual Values read();
};

#endif