#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <WiFi.h>

//Network credentials
const char* ssid = "Hellewell";
const char* password = "mac&cheese";

Adafruit_MPU6050 mpu; //object
float z_offset = 0;  // Offset to calibrate Z axis

void setup(void) {
  Serial.begin(115200);
  
  Wire.begin(1, 0); //GPIO pins for 6050 connection. (SDA, SCL)
  
  // Try to initialize!
  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip");
    while (1) {
      delay(10);
    }
  }
  Serial.println("MPU6050 Found!");

  //range options: 2_G, 4_G, 8_G, 16_G. Higher range sacrifices accuracy & power usage
  mpu.setAccelerometerRange(MPU6050_RANGE_4_G); 
  
  //range options: 250_DEG, 500_DEG, 1000_DEG, 2000_DEG
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  
  //bandwidth options: 260_HZ, 184_HZ, 94_HZ, 44_HZ, 21_HZ, 10_HZ, 5_HZ
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  calibrateZ(); //calibrate the Z axis

  connectToWiFi();
}

void connectToWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void calibrateZ() {
  Serial.println("Calibrating... Please keep the board flat and still.");
  delay(2000);  // Give user time to settle the board

  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float current_z = a.acceleration.z;

  if(current_z > 5.0){
    z_offset = 10.0 - current_z; //I used 10.0 instead of 9.8 
  } else {
    Serial.println("Unable to calibrate");
  }

  Serial.print("Calibration complete. Applied Z offset: ");
  Serial.println(z_offset);
}

void loop() {

  /* Get new sensor events with the readings */
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float z_corrected = a.acceleration.z + z_offset;

  /* Print out the values */
  Serial.print("Acceleration X: ");
  Serial.print(a.acceleration.x);
  Serial.print(", Y: ");
  Serial.print(a.acceleration.y);
  Serial.print(", Z: ");
  Serial.print(a.acceleration.z);
  Serial.print(", corrected Z: ");
  Serial.print(z_corrected);
  Serial.println(" m/s^2");
  Serial.print("Z axis offset: ");
  Serial.println(z_offset);


  Serial.print("Temperature: ");
  Serial.print(temp.temperature);
  Serial.println(" degC");

  Serial.println("");
  delay(500);
}