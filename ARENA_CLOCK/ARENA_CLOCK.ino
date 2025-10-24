#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include "secrets.h" //Wi-Fi credentials

#define UDP_PORT 50001
WiFiUDP udp;

// Define the 4 BCD input pins for DM7447AN
const int pinA[] = {12, 17, 1}; // LSB
const int pinB[] = {19, 10, 15};
const int pinC[] = {20, 9, 7}; //INSTEAD OF 46, 15
const int pinD[] = {13, 18, 2}; // MSB

// Other control pins
const int biPin[] = {14, 8, 5};        // BI/RBO (When LOW, turns off display)

const int fanPin = 35;
const int colonPin = 36;

//WiFiUDP udp;
TaskHandle_t wifiMonitorTask = NULL;
TaskHandle_t otaTask = NULL;
TaskHandle_t udpTaskHandle;

enum ClockState {
  WAITING,
  PAUSED,
  COUNTING,
  KO
};
volatile uint32_t current_ms = 0;

volatile ClockState currentState = WAITING;

void setup() {
  Serial.begin(115200);

  initializePins();

  connectToWiFi();

  setup_OTA();
  
  waiting();
}

void initializePins(){
  //setup fan
  pinMode(fanPin, OUTPUT);
  digitalWrite(fanPin, HIGH); //fan ON

  //setup colon
  pinMode(colonPin, OUTPUT);
  digitalWrite(colonPin, LOW); //colon OFF initially

  // Set BCD input pins and bi control pins as OUTPUT
  for(int i=0; i<3; i++){
    pinMode(pinA[i], OUTPUT);
    pinMode(pinB[i], OUTPUT);
    pinMode(pinC[i], OUTPUT);
    pinMode(pinD[i], OUTPUT);

    pinMode(biPin[i], OUTPUT);
    digitalWrite(biPin[i], LOW); //set display to OFF 
  }
  Serial.println("Pins initialized successfully");
}

void blankDisplay(bool blank){ //turns the whole display on or off
  if(blank){
    for(int i = 0; i < 3; i++) {
      if(biPin[i] != -1) {
        digitalWrite(biPin[i], LOW);
      }
    }
  } else {
    for(int i = 0; i < 3; i++) {
      if(biPin[i] != -1) {
        digitalWrite(biPin[i], HIGH);
      }
    }
  }
}

void displayDigits(int a, int b, int c, bool aOn, bool bOn, bool cOn){
  // Force BI HIGH before writing any digits
  for(int i = 0; i < 3; i++) {
    if(biPin[i] != -1) {
      digitalWrite(biPin[i], HIGH);
    }
  }

  if(a < 0 || a >= 10){
    //Serial.println("Digit out of range!! Must be 0-9. Received arg a with: ");
    //Serial.print(a);
    return;
  }
  if(b < 0 || b >= 10){
    //Serial.println("Digit out of range!! Must be 0-9. Received arg b with: ");
    //Serial.print(b);
    return;
  }
  if(c < 0 || c >= 10){
    //Serial.println("Digit out of range!! Must be 0-9. Received arg c with: ");
    //Serial.print(c);
    return;
  }

  int display[] = {a, b, c};
  int toggle[] = {aOn, bOn, cOn};

  for(int i=0; i<3; i++){
    //first, toggle the display where needed
    if(!toggle[i]){
      digitalWrite(biPin[2-i], LOW);
    } else {
      digitalWrite(biPin[2-i], HIGH);
    }

    // Set the binary value of digit on pins A–D
    digitalWrite(pinA[i], bitRead(display[2-i], 0)); // Bit 0 (LSB)
    digitalWrite(pinB[i], bitRead(display[2-i], 1)); // Bit 1
    digitalWrite(pinC[i], bitRead(display[2-i], 2)); // Bit 2
    digitalWrite(pinD[i], bitRead(display[2-i], 3)); // Bit 3 (MSB)
  }
}

//connects to Wi-Fi and begins UDP
void connectToWiFi() { 

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to WiFi Network ");
  Serial.print(WIFI_SSID);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED) {
    wiFiConnectingEffect(attempts);
    delay(500);
    Serial.print(".");
    if(attempts > 21){
      ESP.restart();
    }
    attempts++;
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // Start WiFi monitor task on core 0
  xTaskCreatePinnedToCore(
    wifiMonitorTaskFunction,    // Task function
    "WiFi Monitor",     // Name
    4096,               // Stack size
    NULL,               // Parameters
    1,                  // Priority
    &wifiMonitorTask,
    0                   // Core 0 (can also be core 1)
  );

  xTaskCreatePinnedToCore(
    [](void* param) { handleUDPControl(); }, // task function
    "UDPListener",                          // name
    4096,                                   // stack size
    NULL,                                   // task param
    1,                                      // priority
    &udpTaskHandle,                         // task handle
    0                                       // core 0
  );

}

void handleUDPControl() {
  udp.begin(UDP_PORT);
  while (true) {
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
      Serial.printf("Packet received, size: %d\n", packetSize);
      if (packetSize == 4) {  // 2 bytes command + 2 bytes time_ds
        uint8_t buffer[4];
        int len = udp.read(buffer, sizeof(buffer));
        if (len == 4) {
          uint16_t command;
          uint16_t time_ds; // time in deciseconds (ms / 100)

          memcpy(&command, buffer, 2);
          memcpy(&time_ds, buffer + 2, 2);

          // Convert from network byte order (big endian) to host order
          command = ntohs(command);
          time_ds = ntohs(time_ds);

          // Convert deciseconds back to milliseconds
          uint32_t time_ms = time_ds * 100;

          Serial.print("Command: "); Serial.println(command);
          Serial.print("Time (ms): "); Serial.println(time_ms);

          executeCommand(command, time_ms);
        }
      } else {
        Serial.printf("Received invalid packet size: %d\n", packetSize);
      }
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}


void wiFiConnectingEffect(int attempts){ //delays are done in the wifi function
  colonToggle(false);
  if(attempts%3==0){
    displayDigits(0, 0, 0, true, false, false);
  } else if(attempts%3==1){
    displayDigits(0, 0, 0, false, true, false);
  } else {
    displayDigits(0, 0, 0, false, false, true);
  }
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

  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.begin();

  Serial.println("OTA Ready");

  // Create OTA handler task
  xTaskCreatePinnedToCore(
    otaTaskFunction,   // Task function
    "OTA Task",        // Name of task
    4096,              // Stack size
    NULL,              // Parameters
    1,                 // Priority
    &otaTask,          // Task handle
    0                  // Core 0
  );
}

void otaTaskFunction(void* parameter) {
  while (true) {
    ArduinoOTA.handle();
    vTaskDelay(pdMS_TO_TICKS(50)); // Check every 100 ms
  }
}

void colonToggle(bool on){
  if(on){
    digitalWrite(colonPin, HIGH);
  } else {
    digitalWrite(colonPin, LOW);
  }
}

void effect321(){
  colonToggle(false);
  for(int i=3; i>0; i--){
    displayDigits(0, i, 0, false, true, false);
    delay(500);
    displayDigits(0, i, 0, false, false, false);
    delay(500);
  }
}

void displaySeconds(uint32_t time){
  colonToggle(true);
  
  // Round up seconds by adding 999 ms before dividing
  int totalSeconds = (time + 999) / 1000;

  int min = totalSeconds / 60;
  int sec = totalSeconds % 60;

  int tens = sec / 10;
  int ones = sec % 10;

  if (min == 0) {
    displayDigits(min, tens, ones, false, true, true); // blank leading zero
  } else {
    displayDigits(min, tens, ones, true, true, true);
  }
}

void displayMillis(uint32_t time){
  colonToggle(true);
  int j = time;
  int s = j/1000;
  int ten_ms = j%1000/100;
  int ms = j%100/10;

  if(s==0){
    displayDigits(s, ten_ms, ms, false, true, true);
  } else {
    displayDigits(s, ten_ms, ms, true, true, true);
  }
}

void effectKO(){
  displaySeconds(current_ms);

  for(int j=0; j<3; j++){
    blankDisplay(false);
    colonToggle(true);
    delay(1000);
    blankDisplay(true);
    colonToggle(false);
    delay(1000);
  }
}

void executeCommand(uint32_t command, uint32_t time_ms){
  switch (command) {
    case 0: { //reset clock
      current_ms = time_ms;
      currentState = WAITING;
      break;
    }
    case 1: { //start countdown
      current_ms = time_ms;
      currentState = COUNTING;
      break;
    } 
    case 2: { //pause
      current_ms = time_ms;
      currentState = PAUSED;
      break;
    }
    case 3: { //Resume
      current_ms = time_ms;
      currentState = COUNTING;
      break;
    }
    case 4: { //add time
      current_ms = time_ms;
      break;            
    }
    case 5: { //KO
      current_ms = time_ms;
      currentState = KO;
      break;
    }
    default: {
      break;
    }
  }
}

void counting(){
  //do the 321 effect, then start counting
  effect321();

  uint32_t time_start = millis();
  uint32_t original_time = current_ms;
  while(currentState == COUNTING && current_ms > 0){
    //current_ms = millis() - time_start; //decrease current_ms by how many ms have actually passed
    current_ms = original_time - (millis() - time_start);

    //decide whether to display seconds or ms:
    /*
    if(current_ms < 1000*10){ //under ten seconds
      displayMillis(current_ms);
    } else { //normal
      displaySeconds(current_ms);
    }*/
    //no special effects, just continue counting down to 0
    displaySeconds(current_ms);

    delay(10);
  }

  switch(currentState){
    case WAITING: { //cancels whole thing
      waiting();
      break;
    }
    case PAUSED: {
      paused();
      break;
    }
    case KO: {
      ko();
      break;
    }
    default: {
      ko(); 
      break;
    }
  }
  
}

void ko(){
  effectKO();
  currentState = WAITING;
  waiting();
}

void paused(){
  int interval = 1000; //how often it blinks / unblinks
  unsigned long start = millis();
  while(currentState == PAUSED){
    unsigned long waiting = millis() - start;
    if((waiting/interval)%2==0){
      blankDisplay(true);
      colonToggle(false);
    } else {
      displaySeconds(current_ms);
      blankDisplay(false);
      colonToggle(true);
    }
    delay(20);
  }

  switch(currentState){
    case WAITING: { 
      waiting();
      break;
    }
    case COUNTING: {
      counting();
      break;
    }
    case KO: {
      ko();
      break;
    }
    default: {
      waiting(); 
      break;
    }
  }
}

void waiting(){
  //blank screen
  blankDisplay(true);
  colonToggle(false);

  unsigned long waiting_start = millis();
  while(currentState == WAITING){ //prevents millis() from overflow by restarting if left waiting for 8hrs
    if(millis() - waiting_start > 1000*60*60*8){
      ESP.restart();
    }
    delay(20);
  }

  switch(currentState){
    case PAUSED: { //shouldn't go from waiting to paused. ignore command
      waiting();
      break;
    }
    case COUNTING: {
      counting();
      break;
    }
    default: {
      waiting(); 
      break;
    }
  }

}

void loop() {
  
}

