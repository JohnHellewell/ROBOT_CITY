#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>

//Network credentials
const char* ssid = "Hellewell";
const char* password = "mac&cheese";

//UDP
WiFiUDP udp;
const unsigned int localPort = 4210;  // Arbitrary port
char incomingPacket[255];

int ch1 = 500; //500 is halfway between 0 and 1000
int ch2 = 500;
int ch3 = 0;
int killswitch = 0; //0 is OFF (as in robots should be off), 1 is LIMITED (drive enabled, weapon disabled), 2 is ARMED (battle mode)

Adafruit_MPU6050 mpu; //object
float z_offset = 2.5;  // Offset to calibrate Z axis. 2.5 is what's typically adjusted
float z_accel = 0.0;

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

  //calibrateZ(); //calibrate the Z axis

  connectToWiFi();

  setup_OTA();
}

void UDP_packet(){
  if (udp.parsePacket()) {
    uint8_t buf[4];
    int len = udp.read(buf, sizeof(buf));
    if (len == 4) {
      // Extract values
      int v1 = buf[0];
      int v2 = buf[1];
      int v3 = buf[2];
      int v4 = buf[3];

      Serial.printf("Received: [%d, %d, %d, %d]\n", v1, v2, v3, v4);

      
      float result = round(z_accel * 100) / 100; //rounds to two decimal places

      Serial.println(result);

      // Send back the result as float
      udp.beginPacket(udp.remoteIP(), udp.remotePort());
      udp.write((uint8_t*)&result, sizeof(result));
      udp.endPacket();
    }
  }
}

void setup_OTA(){
  ArduinoOTA
  .onStart([]() {
    String type;
    if (ArduinoOTA.getCommand() == U_FLASH)
      type = "sketch";
    else // U_SPIFFS
      type = "filesystem";
    Serial.println("Start updating " + type);
  })
  .onEnd([]() {
    Serial.println("\nEnd");
  })
  .onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
  })
  .onError([](ota_error_t error) {
    Serial.printf("Error[%u]: ", error);
    if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
    else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
    else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
    else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
    else if (error == OTA_END_ERROR) Serial.println("End Failed");
  });

  ArduinoOTA.setPassword("1234"); // No password. Put a string in here to add a password
  ArduinoOTA.begin();
  Serial.println("OTA Ready");
}

//connects to Wi-Fi and begins UDP
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

  udp.begin(localPort);
  Serial.println("UDP listening on port " + String(localPort));
}

void calibrateZ() {
  Serial.println("Calibrating... Please keep the board flat and still.");
  delay(2000);  // Give user time to settle the board

  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float current_z = a.acceleration.z;

  if(current_z > 5.0){
    z_offset = 10.0 - current_z; //I used 10.0 instead of 9.8 , since flipping it upside down tends to overestimate gravity's pull
  } else {
    Serial.println("Unable to calibrate");
  }

  Serial.print("Calibration complete. Applied Z offset: ");
  Serial.println(z_offset);
}

void loop() {
  ArduinoOTA.handle();

  UDP_packet();

  /* Get new sensor events with the readings */
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  z_accel = a.acceleration.z + z_offset;

  /* Print out the values */
  Serial.print("Acceleration X: ");
  Serial.print(a.acceleration.x);
  Serial.print(", Y: ");
  Serial.print(a.acceleration.y);
  Serial.print(", Z: ");
  Serial.print(a.acceleration.z);
  Serial.print(", corrected Z: ");
  Serial.print(z_accel);
  Serial.println(" m/s^2");
  Serial.print("Z axis offset: ");
  Serial.println(z_offset);


  Serial.print("Temperature: ");
  Serial.print(temp.temperature);
  Serial.println(" degC");

  Serial.println("");
  delay(2000);
}