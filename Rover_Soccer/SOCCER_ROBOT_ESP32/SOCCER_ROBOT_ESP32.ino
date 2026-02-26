#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
//#include <ESPmDNS.h>
#include "driver/ledc.h"
#include "secrets.h" //Wi-Fi credentials

#define SOFTWARE_VERSION "0.1.0" //latest change: test code for soccer robot


//************************ Fill this section out for each individual robot *******************************
//const unsigned int robot_id = 80;
//********************************************************************************************************

unsigned int localPort = 4200 + IP_tail;

#define SCL 6 
#define SDA 7 

//LED
#define ONBOARD_LED 8

//UDP
WiFiUDP udp;

char incomingPacket[255];

#define CH1_PIN 4 
#define CH2_PIN 2 
#define CH3_PIN 1 
#define CH4_PIN 3 

unsigned long lastPacketReceived; //used to measure time
bool connected = false;
#define FAILSAFE_DISCONNECT 500 //how many milliseconds of time since no packets received to activate failsafe

// Channels
#define CH1_PWM LEDC_CHANNEL_0
#define CH2_PWM LEDC_CHANNEL_1
#define CH3_PWM LEDC_CHANNEL_2
#define CH4_PWM LEDC_CHANNEL_3

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

enum TxMode {
  TX_LOW,
  TX_MED,
  TX_HIGH
};

TxMode currentTxMode = TX_LOW;

//********************************

void setup(void) {
  Serial.begin(115200);
  
  Serial.print("Running software version ");
  Serial.println(SOFTWARE_VERSION);
  
  lastPacketReceived = millis();

  pinMode(ONBOARD_LED, OUTPUT);
  digitalWrite(ONBOARD_LED, LOW);

  setup_ESCs();

  delay(1000); //give ESCs time to arm

  connectToWiFi();

  setup_OTA();
}

void setTxMode(TxMode newMode) {
  if (newMode == currentTxMode) 
    return;

  if (newMode == TX_LOW) {
    WiFi.setTxPower(WIFI_POWER_8_5dBm);
    Serial.println("WiFi TX power: LOW");
    return;
  } 
  if(newMode == TX_MED) {
    WiFi.setTxPower(WIFI_POWER_13dBm);
    Serial.println("WiFi TX power: MEDIUM");
  } else {
    WiFi.setTxPower(WIFI_POWER_17dBm);
    Serial.println("WiFi TX power: HIGH");
  }

  currentTxMode = newMode;
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
    case 4: ch = CH4_PWM; break;
    default: return; // invalid channel
  }
  uint32_t duty = usToDuty(pulse_us);
  ledc_set_duty(PWM_MODE, ch, duty);
  ledc_update_duty(PWM_MODE, ch);
}


void setup_ESCs() {
    // Timer configuration (high-speed)
    ledc_timer_config_t timer_conf = {
        .speed_mode       = PWM_MODE,
        .duty_resolution  = PWM_RES_BITS,
        .timer_num        = PWM_TIMER,
        .freq_hz          = PWM_FREQ_HZ,
        .clk_cfg          = LEDC_AUTO_CLK
    };
    ledc_timer_config(&timer_conf);

    // Configure all channels on the same high-speed timer
    ledc_channel_config_t channels[4] = {
        {CH1_PIN, PWM_MODE, CH1_PWM, LEDC_INTR_DISABLE, PWM_TIMER, 0, 0},
        {CH2_PIN, PWM_MODE, CH2_PWM, LEDC_INTR_DISABLE, PWM_TIMER, 0, 0},
        {CH3_PIN, PWM_MODE, CH3_PWM, LEDC_INTR_DISABLE, PWM_TIMER, 0, 0},
        {CH4_PIN, PWM_MODE, CH4_PWM, LEDC_INTR_DISABLE, PWM_TIMER, 0, 0},
    };

    for (int i = 0; i < 4; i++) {
        ledc_channel_config(&channels[i]);
    }

    // Set default ESC values
    setPWM(1, CH1_DEFAULT);
    setPWM(2, CH2_DEFAULT);
    setPWM(3, CH3_DEFAULT);
    setPWM(4, CH4_DEFAULT);

    Serial.println("PWM channels configured successfully");
}


void apply_motor_values(int values[]){
    for(int i=1; i<=4; i++){
        setPWM(i, values[i-1]);
    }
}

void mix_mecanum(int strafe, int forward, int rotate, int out[4])
{
  forward = constrain(forward, 1000, 2000);
  strafe = constrain(strafe, 1000, 2000);
  rotate = constrain(rotate, 1000, 2000);

  int f = forward - 1500;
  int s = strafe  - 1500;
  int r = rotate  - 1500;

  out[0] = 1500 - (f + s + r);
  out[1] = 1500 + (f - s - r);
  out[2] = 1500 - (f - s + r);
  out[3] = 1500 + (f + s - r);

  for (int i = 0; i < 4; i++) {
    out[i] = constrain(out[i], 1000, 2000);
  }


}


void execute_package(int v1, int v2, int v3, int v4){
  
  if(v4 != 0 && v4 != 2 && v4 != 1){ //make sure valid killswitch signal is received. If not, activate killswitch and disable bot
      ch1 = CH1_DEFAULT;
      ch2 = CH2_DEFAULT;
      ch3 = CH3_DEFAULT;
      killswitch = 0;
      
      Serial.print("INVALID KILLSWITCH SIGNAL RECEIVED! received: ");
      Serial.println(v4);
      return;
  }

  switch(v4){
    case 0: { //killswitch is ON; robot should be immobile
      killswitch=0;
      ch1 = CH1_DEFAULT;
      ch2 = CH2_DEFAULT;
      ch3 = CH3_DEFAULT;

      setTxMode(TX_LOW); //low, robot is inactive
      break;
    }
    case 1: { //limited movement: robot can drive, but weapon is disabled
      killswitch = 1;
      ch1 = v1;
      ch2 = v2;
      ch3 = CH3_DEFAULT;
      break;
    }
    case 2: { //robot is enabled for battle mode
      if(killswitch == 0 || killswitch == 1){
        killswitch = 2;
        setTxMode(TX_HIGH); //high, robot is active
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

  if (len == 8) {
    lastPacketReceived = millis();

    if (!connected) {
      connected = true;
      Serial.println("Connection established; receiving packets");
    }

    uint16_t* values = (uint16_t*)incomingPacket;
    int v1 = values[0];
    int v2 = values[1];
    int v3 = values[2];
    int v4 = values[3];

    execute_package(v1, v2, v3, v4);
    int motor_vals[4];
    mix_mecanum(ch1, ch2, ch3, motor_vals);
    apply_motor_values(motor_vals);

    bool received = true;
    udp.beginPacket(udp.remoteIP(), udp.remotePort());
    udp.write((uint8_t*)&received, sizeof(received));
    udp.endPacket();
  } else if (connected && millis() - lastPacketReceived >= FAILSAFE_DISCONNECT) {
    connected = false;

    execute_package(CH1_DEFAULT, CH2_DEFAULT, CH3_DEFAULT, 0);
    int motor_vals[4];
    mix_mecanum(ch1, ch2, ch3, motor_vals);
    apply_motor_values(motor_vals);
    
    Serial.println("Connection dropped! Failsafe enabled");

    //attempt to establish better WiFi connection
    if(millis() - lastPacketReceived >= 60000){ //if disconnected for over a minute, reduce power a bit
      setTxMode(TX_MED);
    } else { //if disconnected for under a minute, try hard
      setTxMode(TX_HIGH); 
    }
  } else { //not connected
    setTxMode(TX_MED); 
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
    
    setTxMode(TX_HIGH); //establish good connection
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

  ArduinoOTA.setPassword(OTA_PASSWORD); 
  ArduinoOTA.begin();
  
  Serial.println("OTA Ready");
}

//connects to Wi-Fi and begins UDP
void connectToWiFi() { 
  IPAddress local_IP(192, 168, IP_group, IP_tail);
  IPAddress gateway(192, 168, IP_group, 1);
  IPAddress subnet(255, 255, 255, 0);

  WiFi.config(local_IP, gateway, subnet);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  // Set lower WiFi transmit power (e.g., 10 dBm)
  WiFi.setTxPower(WIFI_POWER_17dBm); //high for connecting initially

  Serial.print("Connecting to WiFi Network ");
  Serial.print(WIFI_SSID);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
    pinMode(ONBOARD_LED, OUTPUT);
    digitalWrite(ONBOARD_LED, HIGH);
    delay(250);
    pinMode(ONBOARD_LED, OUTPUT);
    digitalWrite(ONBOARD_LED, LOW);
  }

  //WiFi connected
  WiFi.setTxPower(WIFI_POWER_8_5dBm); //low 
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  

  udp.begin(localPort);
  Serial.println("UDP listening on port " + String(localPort));
}


void loop() {
  ArduinoOTA.handle(); //checks for incoming OTA programming

  UDP_packet(); //receive latest packet

  //map and write values
  
  delay(10); //power saving
}