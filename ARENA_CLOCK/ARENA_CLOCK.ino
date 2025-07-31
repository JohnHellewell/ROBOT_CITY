#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include "secrets.h" //Wi-Fi credentials

// Define the 4 BCD input pins for DM7447AN
const int pinA[] = {12, 17, 1}; // LSB
const int pinB[] = {19, 10, 15};
const int pinC[] = {20, 9, 7}; //INSTEAD OF 46, 15
const int pinD[] = {13, 18, 2}; // MSB

// Other control pins
const int lampTestPin[] = {-1, -1, -1};  // LT
const int biPin[] = {14, 8, 5};        // BI/RBO (When LOW, turns off display)
const int rbiPin[] = {-1, -1, -1};      // RBI

const int fanPin = 35;
const int colonPin = 36;

unsigned long previousMillis = 0;
const long interval = 10000; // Check every 10 seconds
const unsigned int localPort = 4010;
WiFiUDP udp;
TaskHandle_t wifiMonitorTask = NULL;


void setup() {
  Serial.begin(115200);

  initializePins();

  connectToWiFi();

  setup_OTA();
  
}

void initializePins(){
  //setup fan
  pinMode(fanPin, OUTPUT);
  digitalWrite(fanPin, HIGH); //fan ON

  //setup colon
  pinMode(colonPin, OUTPUT);
  digitalWrite(colonPin, HIGH); //colon ON



  // Set BCD input pins and bi control pins as OUTPUT
  for(int i=0; i<3; i++){
    pinMode(pinA[i], OUTPUT);
    pinMode(pinB[i], OUTPUT);
    pinMode(pinC[i], OUTPUT);
    pinMode(pinD[i], OUTPUT);

    pinMode(biPin[i], OUTPUT);
    digitalWrite(biPin[i], HIGH); //set display to ON 
  }

  //Set all unneeded control pins to HIGH (except those that are already tied high, denoted by -1)
  for(int i=0; i<3; i++){
    if(lampTestPin[i] != -1){
      pinMode(lampTestPin[i], OUTPUT);
      digitalWrite(lampTestPin[i], HIGH);
    }

    if(rbiPin[i] != -1){
      pinMode(rbiPin[i], OUTPUT);
      digitalWrite(rbiPin[i], HIGH);
    }
  }

  Serial.println("Pins initialized successfully");
}

void displayDigits(int c, int b, int a){
  // Force RBI HIGH before writing any digits
  for(int i = 0; i < 3; i++) {
    if(rbiPin[i] != -1) {
      digitalWrite(rbiPin[i], HIGH);
    }
  }

  if(a < 0 || a >= 10){
    Serial.println("Digit out of range!! Must be 0-9");
    return;
  }
  if(b < 0 || b >= 10){
    Serial.println("Digit out of range!! Must be 0-9");
    return;
  }
  if(c < 0 || c >= 10){
    Serial.println("Digit out of range!! Must be 0-9");
    return;
  }

  int display[] = {a, b, c};

  for(int i=0; i<3; i++){
    // Set the binary value of i on pins A–D
    digitalWrite(pinA[i], bitRead(display[i], 0)); // Bit 0 (LSB)
    digitalWrite(pinB[i], bitRead(display[i], 1)); // Bit 1
    digitalWrite(pinC[i], bitRead(display[i], 2)); // Bit 2
    digitalWrite(pinD[i], bitRead(display[i], 3)); // Bit 3 (MSB)
  }
}

//connects to Wi-Fi and begins UDP
void connectToWiFi() { 
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  // Set lower WiFi transmit power (e.g., 10 dBm)
  //WiFi.setTxPower(WIFI_POWER_20dBm); //lower the transmitter power by 95%. If robots have connection issues, try raising this

  Serial.print("Connecting to WiFi Network ");
  Serial.print(WIFI_SSID);

  int attempts = 20;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if(attempts <= 0){
      ESP.restart();
    }
    attempts--;
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  udp.begin(localPort);
  Serial.println("UDP listening on port " + String(localPort));

  // Start WiFi monitor task on core 1
  xTaskCreatePinnedToCore(
    wifiMonitorTaskFunction,    // Task function
    "WiFi Monitor",     // Name
    4096,               // Stack size
    NULL,               // Parameters
    1,                  // Priority
    &wifiMonitorTask,
    1                   // Core 1 (can also be core 0)
  );

}

void wifiMonitorTaskFunction(void* parameter) {
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi disconnected. Reconnecting...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      // Wait a bit to allow reconnection
      for (int i = 0; i < 10 && WiFi.status() != WL_CONNECTED; i++) {
        delay(500);
      }
    }
    vTaskDelay(pdMS_TO_TICKS(10000)); // Check every 10 seconds
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

  ArduinoOTA.setPassword(OTA_PASSWORD); // No password. Put a string in here to add a password
  ArduinoOTA.begin();
  Serial.println("OTA Ready");
}

void loop() {
  ArduinoOTA.handle(); //checks for incoming OTA programming

  
  for (int i = 180; i >=0; i--) {
    //Serial.print("Testing digit ");
    //Serial.println(i);
    displayDigits(i/60, (i%60/10), i%10); // Show two 7s and one varying digit

    if(i%2==0){
      digitalWrite(8, LOW);
      digitalWrite(5, LOW);
      digitalWrite(14, LOW);
      digitalWrite(colonPin, LOW);
    } else {
      digitalWrite(8, HIGH);
      digitalWrite(5, HIGH);
      digitalWrite(14, HIGH);
      digitalWrite(colonPin, HIGH);
    }

    delay(1000);
  }
}

