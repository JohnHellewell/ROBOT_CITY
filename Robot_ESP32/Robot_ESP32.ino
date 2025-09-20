#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include "driver/ledc.h"
#include "secrets.h" //Wi-Fi credentials
#include "accel_handler.h"

#define SOFTWARE_VERSION "1.4.0" //latest change: verts can flip at just 90 degrees. Serial Plot is used to monitor accel data

enum RobotType {
  DRUM,
  HORIZ,
  VERT,
  LIFTER
};

//************************ Fill this section out for each individual robot *******************************
const unsigned int robot_id = 31;
ChipType chip = chip_MPU6050; //standard for first batch of boards
const bool PLOT_MODE = false; //set to false for normal use, set to true for reading accelerometer data
//********************************************************************************************************

unsigned int localPort = 4200 + robot_id;
bool BIDIRECTIONAL_WEAPON;
RobotType robotType;


#define SCL 6 
#define SDA 7 

//LED
#define ONBOARD_LED 8

//UDP
WiFiUDP udp;

char incomingPacket[255];

#define CH1_PIN 1 
#define CH2_PIN 2 
#define CH3_PIN 3 

unsigned long lastPacketReceived; //used to measure time
bool connected = false;
#define FAILSAFE_DISCONNECT 500 //how many milliseconds of time since no packets received to activate failsafe

// Channels
#define CH1_PWM LEDC_CHANNEL_1
#define CH2_PWM LEDC_CHANNEL_2
#define CH3_PWM LEDC_CHANNEL_3

#define PWM_FREQ_HZ     50  // 50 Hz = 20 ms period
#define PWM_RES_BITS    LEDC_TIMER_13_BIT  // 13-bit resolution
#define PWM_TIMER       LEDC_TIMER_0
#define PWM_MODE        LEDC_LOW_SPEED_MODE

int DEFAULT_PWM_RANGE[2] = {1000, 2000};
int SERVO_RANGE[2] = {500, 2500};

const bool SERVO_BOT = false; //true if bot is equipped with servo weapon, false if not

const int CH1_DEFAULT = 1500; 
const int CH2_DEFAULT = 1500;
int CH3_DEFAULT;

int ch1 = CH1_DEFAULT; 
int ch2 = CH2_DEFAULT;
int ch3; 
int killswitch = 0; //0 is OFF (as in robots should be off), 1 is LIMITED (drive enabled, weapon disabled), 2 is ARMED (battle mode)
int invert_for_steer = 0; //0 is off, 1 is on

//bool right_motor_reverse = false;
//bool left_motor_reverse = true;
//bool weapon_reverse = false;

const int SAFE_VARIANCE = 25; //in order to switch from kill switch mode 0 to 1 or 2, channels must be this close to the default range

//float z_offset = 2.5;  // Offset to calibrate Z axis. 2.5 is what's typically adjusted
//float z_accel = 0.0;

volatile bool flipped = false;
const double FLIPPED_Z_THRESHOLD = 5.0; //when the z acceleration goes above this threshold, bot is considered flipped or unflipped


AccelHandler* accelHandler;


void setup(void) {
  Serial.begin(115200);
  if(PLOT_MODE)
    Serial.println("X Y Z");

  if(!PLOT_MODE){
    Serial.print("Running software version ");
    Serial.println(SOFTWARE_VERSION);
  }

  

  switch(robot_id/10){
    case 1: { //drum bot
      BIDIRECTIONAL_WEAPON = true;
      robotType = DRUM;
      break;
    }
    case 2: {
      BIDIRECTIONAL_WEAPON = false;
      robotType = HORIZ;
      break;
    }
    case 3: { //vert bot
      BIDIRECTIONAL_WEAPON = true;
      robotType = VERT;
      break;
    }
    default: { //flipper
      BIDIRECTIONAL_WEAPON = false;
      robotType = LIFTER;
    }
  }

  if(BIDIRECTIONAL_WEAPON)
    CH3_DEFAULT = 1500;
  else
    CH3_DEFAULT = 1000;

  ch3 = CH3_DEFAULT;
  
  lastPacketReceived = millis();

  pinMode(ONBOARD_LED, OUTPUT);
  digitalWrite(ONBOARD_LED, LOW);

  setup_ESCs();
  
  setup_accelerometer();

  xTaskCreate(AccelerometerTask, "AccelMonitor", 4096, NULL, 1, NULL);

  connectToWiFi();

  setup_OTA();

  
}

// Utility to convert microseconds to 13-bit duty
uint32_t usToDuty(uint16_t pulse_us) {
  return (uint32_t)(((uint64_t)pulse_us * 8191) / 20000);
}

void setPWM(uint8_t channel, uint16_t pulse_us) {
  ledc_channel_t ch;
  switch (channel) {
    case 1: ch = CH1_PWM; break;
    case 2: ch = CH2_PWM; break;
    case 3: ch = CH3_PWM; break;
    default: return; // invalid channel
  }

  uint32_t duty = usToDuty(pulse_us);
  ledc_set_duty(PWM_MODE, ch, duty);
  ledc_update_duty(PWM_MODE, ch);
}


void setup_ESCs(){
  // Timer configuration
  ledc_timer_config_t timer_conf = {
    .speed_mode       = PWM_MODE,
    .duty_resolution  = PWM_RES_BITS,
    .timer_num        = PWM_TIMER,
    .freq_hz          = PWM_FREQ_HZ,
    .clk_cfg          = LEDC_AUTO_CLK
  };
  ledc_timer_config(&timer_conf);

  // Channel 1 setup
  ledc_channel_config_t ch1_conf = {
    .gpio_num       = CH1_PIN,
    .speed_mode     = PWM_MODE,
    .channel        = CH1_PWM,
    .intr_type      = LEDC_INTR_DISABLE,
    .timer_sel      = PWM_TIMER,
    .duty           = 0,
    .hpoint         = 0
  };
  ledc_channel_config(&ch1_conf);

  // Channel 2 setup
  ledc_channel_config_t ch2_conf = {
    .gpio_num       = CH2_PIN,
    .speed_mode     = PWM_MODE,
    .channel        = CH2_PWM,
    .intr_type      = LEDC_INTR_DISABLE,
    .timer_sel      = PWM_TIMER,
    .duty           = 0,
    .hpoint         = 0
  };
  ledc_channel_config(&ch2_conf);

  // Channel 3 setup
  ledc_channel_config_t ch3_conf = {
    .gpio_num       = CH3_PIN,
    .speed_mode     = PWM_MODE,
    .channel        = CH3_PWM,
    .intr_type      = LEDC_INTR_DISABLE,
    .timer_sel      = PWM_TIMER,
    .duty           = 0,
    .hpoint         = 0
  };
  ledc_channel_config(&ch3_conf);

  setPWM(1, CH1_DEFAULT);
  setPWM(2, CH2_DEFAULT);
  setPWM(3, CH3_DEFAULT);

  if(!PLOT_MODE)
    Serial.println("PWM channels started successfully");
}

void setup_accelerometer(){
  accelHandler = new AccelHandler(chip, SDA, SCL, !PLOT_MODE);
}


int classifyXZ(float x, float y, float z) {

  if(fabs(y) > FLIPPED_Z_THRESHOLD || fabs(x) + fabs(z) < FLIPPED_Z_THRESHOLD){ //don't flip when bot is on its side, or the readings are too weak
    return 0;
  }
  // Calculate angle in radians between vector (x, z) and Z-axis
  float angle = atan2(x, z);  // angle relative to Z axis
  
  // Convert to degrees
  float angleDeg = angle * 180.0 / PI;
  
  // Normalize to range -180, 180
  if (angleDeg < -180) angleDeg += 360;
  if (angleDeg > 180) angleDeg -= 360;

  // Check if within ±30° of 180° (Z-axis down)
  if (fabs(angleDeg) <= 15) {
    return 1;  // Z is flat
  }

  // Check if within ±30° of 90° (X-axis down)
  //if (fabs(angleDeg - 90) <= 30 || fabs(angleDeg + 90) <= 30) {
    if (fabs(angleDeg - 90) <= 15) {
    return -1; // X is flat
  }

  // Otherwise, not in range
  return 0;
}

void print_accel_values(double x, double y, double z){
  Serial.print(x);
  Serial.print(" ");
  Serial.print(y);
  Serial.print(" ");
  Serial.println(z);
}

void AccelerometerTask(void *pvParameters) { // task that constantly checks if bot is flipped over
  float readings[5][3] = {0};  // store last 5 readings (x,y,z)
  int index = 0;

  float x, y, z;

  while (true) {
    Values v = accelHandler->read();
    x = v.x;
    y = v.y;
    z = v.z;

    // store into circular buffer
    readings[index][0] = x;
    readings[index][1] = y;
    readings[index][2] = z;

    index++;
    if (index >= 5) index = 0;  // wrap around

    // compute average
    float sum[3] = {0.0, 0.0, 0.0};
    for (int i = 0; i < 5; i++) {
      sum[0] += readings[i][0];
      sum[1] += readings[i][1];
      sum[2] += readings[i][2];
    }

    float avg[3];
    avg[0] = sum[0] / 5.0; //x
    avg[1] = sum[1] / 5.0; //y
    avg[2] = sum[2] / 5.0; //z

    if(PLOT_MODE)
      print_accel_values(avg[0], avg[1], avg[2]);

    if(robotType == VERT){ //flip is calculated based on y and z axis
      switch(classifyXZ(avg[0], avg[1], avg[2])){ //use y and z
        case 1: { //right side up
          if(flipped){
            flipped = false;
            if(!PLOT_MODE)
              Serial.println("FLIPPED! Right side up");
          }
          break;
        }
        case -1: { //upside down
          if(!flipped){
            flipped = true;
            if(!PLOT_MODE)
              Serial.println("FLIPPED! Upside down");
          }
          break;
        }
        default: break;
      }
    } else { //flip is calculated based on Z axis alone
      if(flipped){//if bot is currently marked as upside down
        if(avg[2] < -FLIPPED_Z_THRESHOLD){
          flipped = false;
          if(!PLOT_MODE)
            Serial.println("FLIPPED! Right side up");
        }
      } else {//if bot is currently marked as right side up
        if(avg[2] > FLIPPED_Z_THRESHOLD){
          flipped = true;
          if(!PLOT_MODE)
            Serial.println("FLIPPED! Upside down");
        }
      }
    }

    vTaskDelay(50 / portTICK_PERIOD_MS);  // Wait 50ms
  }

}

int validate_range(int n, bool is_servo){
  int* range = DEFAULT_PWM_RANGE;
  if(is_servo){
    range = SERVO_RANGE;
  } 
  if(n >= range[0] && n<= range[1]){
    return n;
  } else if(n < range[0]){
    if(!PLOT_MODE){
      Serial.print("INVALID CHANNEL SIGNAL RECEIVED! received: ");
      Serial.println(n);
    }
    return range[0];
  } else {
    if(!PLOT_MODE){
      Serial.print("INVALID CHANNEL SIGNAL RECEIVED! received: ");
      Serial.println(n);
    }
    return range[1];
  }
}

bool is_safe_killswitch_change(int v1, int v2, int v3, int mode){
  if(mode==1 || mode==2){
    return abs(v1-CH1_DEFAULT)<=SAFE_VARIANCE && abs(v2-CH2_DEFAULT)<=SAFE_VARIANCE && (mode==1 || abs(v3-CH3_DEFAULT)<=SAFE_VARIANCE);
  } else {
    if(!PLOT_MODE){
      Serial.print("logic error: is_safe_killswitch_change was given this value as killswitch: ");
      Serial.println(mode);
    }
    return false;
  }
}

void mix_and_write(){
  int forward = ch2 - 1500;
  int turn = ch1 - 1500;
  int weapon;
  if(BIDIRECTIONAL_WEAPON){
    weapon = ch3 - 1500;
  } else {
    weapon = ch3 - 1000;
  }

 if(flipped){ 
    if(invert_for_steer==0){
      forward = -forward;
    } else {
      turn = -turn;
    }
    if(BIDIRECTIONAL_WEAPON){
        weapon = -weapon;
    }
  }


  // Mixed motor signals
  int left_motor = 1500 + forward + turn;
  int right_motor = 1500 + forward - turn;
  int weapon_motor;
  if(BIDIRECTIONAL_WEAPON){
    weapon_motor = 1500 + weapon;
  } else {
    weapon_motor = 1000 + weapon;
  }

  // Clamp to PWM range
  left_motor = constrain(left_motor, 1000, 2000);
  right_motor = constrain(right_motor, 1000, 2000);
  weapon_motor = constrain(weapon_motor, 1000, 2000);

  /*
  if(right_motor_reverse){
    right_motor = 2000 - (right_motor-1000);
  }

  if(left_motor_reverse){
    left_motor = 2000 - (left_motor-1000);
  }
  */
  if(!PLOT_MODE)
    Serial.printf("Motor output: [%d, %d]\n", right_motor, left_motor);

  setPWM(1, right_motor);
  setPWM(2, left_motor);
  setPWM(3, weapon_motor);
  
}

void execute_package(int v1, int v2, int v3, int v4, int v5){
  invert_for_steer = v5;
  
  if(v4 != 0 && v4 != 2 && v4 != 1){ //make sure valid killswitch signal is received. If not, activate killswitch and disable bot
      ch1 = CH1_DEFAULT;
      ch2 = CH2_DEFAULT;
      ch3 = CH3_DEFAULT;
      killswitch = 0;
      
      if(!PLOT_MODE){
        Serial.print("INVALID KILLSWITCH SIGNAL RECEIVED! received: ");
        Serial.println(v4);
      }
      return;
  }
  v1 = validate_range(v1, false);
  v2 = validate_range(v2, false);
  v3 = validate_range(v3, SERVO_BOT);

  switch(v4){
    case 0: { //killswitch is ON; robot should be immobile
      killswitch=0;
      ch1 = CH1_DEFAULT;
      ch2 = CH2_DEFAULT;
      ch3 = CH3_DEFAULT;
      break;
    }
    case 1: { //limited movement: robot can drive, but weapon is disabled
      if(killswitch == 0){
        //make sure robot is safe to start moving. 
        if(!is_safe_killswitch_change(v1, v2, v3, v4)){
          if(!PLOT_MODE)
            Serial.println("Robot will not move until drive joystick is at rest");
          return;
        }
        
      }
      killswitch = 1;
      ch1 = v1;
      ch2 = v2;
      ch3 = CH3_DEFAULT;
      break;
    }
    case 2: { //robot is enabled for battle mode
      if(killswitch == 0 || killswitch == 1){
        //make sure robot is safe to start moving. 
        if(!is_safe_killswitch_change(v1, v2, v3, v4)){
          if(!PLOT_MODE)
            Serial.println("Robot will not move until drive and weapon are at rest");
            Serial.println(v1);
            Serial.println(v2);
            Serial.println(v3);
            Serial.print("CH3_DEFAULT: ");
            Serial.println(CH3_DEFAULT);
          return;
        }
        killswitch = 2;
      }
      ch1 = v1;
      ch2 = v2;
      ch3 = v3;
      break;
    }
  }
}

void UDP_packet() {
  int len = 0;
  while (udp.parsePacket()) {
    len = udp.read((uint8_t*)incomingPacket, sizeof(incomingPacket));
  }

  if (len == 10) {
    lastPacketReceived = millis();

    if (!connected) {
      connected = true;
      if(!PLOT_MODE)
        Serial.println("Connection established; receiving packets");
    }

    uint16_t* values = (uint16_t*)incomingPacket;
    int v1 = values[0];
    int v2 = values[1];
    int v3 = values[2];
    int v4 = values[3];
    int v5 = values[4];

    execute_package(v1, v2, v3, v4, v5);
    mix_and_write();

    bool received = true;
    udp.beginPacket(udp.remoteIP(), udp.remotePort());
    udp.write((uint8_t*)&received, sizeof(received));
    udp.endPacket();
  } else if (connected && millis() - lastPacketReceived >= FAILSAFE_DISCONNECT) {
    connected = false;
    execute_package(CH1_DEFAULT, CH2_DEFAULT, CH3_DEFAULT, 0, 0);
    mix_and_write();
    if(!PLOT_MODE)
      Serial.println("Connection dropped! Failsafe enabled");
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
    
    if(!PLOT_MODE)
      Serial.println("Start updating " + type);
  })
  .onEnd([]() {
    if(!PLOT_MODE)
      Serial.println("\nEnd");
  })
  .onProgress([](unsigned int progress, unsigned int total) {
    if(!PLOT_MODE)
      Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
  })
  .onError([](ota_error_t error) {
    if(!PLOT_MODE){
      Serial.printf("Error[%u]: ", error);
      if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
      else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
      else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
      else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
      else if (error == OTA_END_ERROR) Serial.println("End Failed");
    }
  });

  ArduinoOTA.setPassword(OTA_PASSWORD); // No password. Put a string in here to add a password
  ArduinoOTA.begin();
  if(!PLOT_MODE)
    Serial.println("OTA Ready");
}

//connects to Wi-Fi and begins UDP
void connectToWiFi() { 
  IPAddress local_IP(192, 168, 8, robot_id);
  IPAddress gateway(192, 168, 8, 1);
  IPAddress subnet(255, 255, 255, 0);

  WiFi.config(local_IP, gateway, subnet);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  // Set lower WiFi transmit power (e.g., 10 dBm)
  WiFi.setTxPower(WIFI_POWER_20dBm); //lower the transmitter power by 95%. If robots have connection issues, try raising this

  if(!PLOT_MODE){
    Serial.print("Connecting to WiFi Network ");
    Serial.print(WIFI_SSID);
  }
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    if(!PLOT_MODE)
      Serial.print(".");
    pinMode(ONBOARD_LED, OUTPUT);
    digitalWrite(ONBOARD_LED, HIGH);
    delay(250);
    pinMode(ONBOARD_LED, OUTPUT);
    digitalWrite(ONBOARD_LED, LOW);
  }
  if(!PLOT_MODE){
    Serial.println("\nWiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  }

  udp.begin(localPort);
  if(!PLOT_MODE)
    Serial.println("UDP listening on port " + String(localPort));
}


void loop() {
  ArduinoOTA.handle(); //checks for incoming OTA programming

  UDP_packet(); //receive latest packet

  //map and write values
  
  delay(10); //power saving
}