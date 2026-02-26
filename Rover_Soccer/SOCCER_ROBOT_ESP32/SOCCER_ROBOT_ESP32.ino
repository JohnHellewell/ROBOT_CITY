#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include "driver/ledc.h"
#include "secrets.h" //Wi-Fi credentials

#define SOFTWARE_VERSION "0.1.0" //latest change: test code for soccer robot



//************************ Fill this section out for each individual robot *******************************
const unsigned int robot_id = 80;
//ChipType chip = chip_MPU6050; //standard for first batch of boards
const bool PLOT_MODE = false; //set to false for normal use, set to true for reading accelerometer data
//********************************************************************************************************

unsigned int localPort = 4200 + robot_id;

#define SCL 6 
#define SDA 7 

//LED
#define ONBOARD_LED 8

//UDP
WiFiUDP udp;

char incomingPacket[255];

#define CH1_PIN 2 //1
#define CH2_PIN 3 //2
#define CH3_PIN 4 //3
#define CH4_PIN 1 //4

unsigned long lastPacketReceived; //used to measure time
bool connected = false;
#define FAILSAFE_DISCONNECT 500 //how many milliseconds of time since no packets received to activate failsafe

// Channels
#define CH1_PWM LEDC_CHANNEL_1
#define CH2_PWM LEDC_CHANNEL_2
#define CH3_PWM LEDC_CHANNEL_3
#define CH4_PWM LEDC_CHANNEL_4

#define PWM_FREQ_HZ     50  // 50 Hz = 20 ms period
#define PWM_RES_BITS    LEDC_TIMER_13_BIT  // 13-bit resolution
#define PWM_TIMER       LEDC_TIMER_0
#define PWM_MODE        LEDC_LOW_SPEED_MODE

int DEFAULT_PWM_RANGE[2] = {1000, 2000};

const int CH1_DEFAULT = 1500; 
const int CH2_DEFAULT = 1500;
const int CH3_DEFAULT = 1500;
const int CH4_DEFAULT = 1500;

int ch1 = CH1_DEFAULT; 
int ch2 = CH2_DEFAULT;
int ch3 = CH3_DEFAULT; 
int ch4 = CH4_DEFAULT; 
int killswitch = 0; //0 is OFF (as in robots should be off), 1 is LIMITED (drive enabled, weapon disabled), 2 is ARMED (battle mode)

const int SAFE_VARIANCE = 25; //in order to switch from kill switch mode 0 to 1 or 2, channels must be this close to the default range

void setup(void) {
  Serial.begin(115200);
  //randomSeed(analogRead(A0)); //seed the random number generator with the analog read of noise from pin 0. 
  if(PLOT_MODE)
    Serial.println("X Y Z");

  if(!PLOT_MODE){
    Serial.print("Running software version ");
    Serial.println(SOFTWARE_VERSION);
  }

  lastPacketReceived = millis();

  pinMode(ONBOARD_LED, OUTPUT);
  digitalWrite(ONBOARD_LED, LOW);

  setup_ESCs();

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

  // Channel 4 setup
  ledc_channel_config_t ch4_conf = {
    .gpio_num       = CH4_PIN,
    .speed_mode     = PWM_MODE,
    .channel        = CH4_PWM,
    .intr_type      = LEDC_INTR_DISABLE,
    .timer_sel      = PWM_TIMER,
    .duty           = 0,
    .hpoint         = 0
  };
  ledc_channel_config(&ch4_conf);

  setPWM(1, CH1_DEFAULT);
  setPWM(2, CH2_DEFAULT);
  setPWM(3, CH3_DEFAULT);
  setPWM(4, CH4_DEFAULT);

  if(!PLOT_MODE)
    Serial.println("PWM channels started successfully");
}



int validate_range(int n, bool is_servo){
  int* range = DEFAULT_PWM_RANGE;
  
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
    return abs(v1-CH1_DEFAULT)<=SAFE_VARIANCE && abs(v2-CH2_DEFAULT)<=SAFE_VARIANCE && abs(v3-CH3_DEFAULT)<=SAFE_VARIANCE;
  } else {
    if(!PLOT_MODE){
      Serial.print("logic error: is_safe_killswitch_change was given this value as killswitch: ");
      Serial.println(mode);
    }
    return false;
  }
}

void mix_and_write(){ //in future, mixing will be done by server. For now, only forward and strafe are being sent, not turn. Turn set to 1500
  int forward = ch2 - 1500; //forward positive
  int turn = 1500; //Clockwise positive ---FOR NOW ALWAYS OFF, FIXME---
  int strafe = ch1 - 1500; //Right Positive
  
  float motor1 = forward + strafe + turn; //Front Left
  float motor2 = forward - strafe - turn; //Front Right
  float motor3 = forward - strafe + turn; //Rear Left
  float motor4 = forward + strafe - turn; //Rear Right
  
  //left_motor = 1500 + forward + turn;
  //right_motor = 1500 + forward - turn;

  float maxVal = 500;
  maxVal = max(maxVal, abs(motor1));
  maxVal = max(maxVal, abs(motor2));
  maxVal = max(maxVal, abs(motor3));
  maxVal = max(maxVal, abs(motor4));

  motor1 = (motor1/maxVal) + 1500;
  motor2 = (motor2/maxVal) + 1500;
  motor3 = (motor3/maxVal) + 1500;
  motor4 = (motor4/maxVal) + 1500;

  
  setPWM(1, (int)(motor1));
  setPWM(2, (int)(motor2));
  setPWM(3, (int)(motor3));
  setPWM(4, (int)(motor4));
  
}

void execute_package(int v1, int v2, int v3, int v4, int v5){
  
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
  v3 = validate_range(v3, false);

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