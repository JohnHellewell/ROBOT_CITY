#ifndef HEAD_WIFI_H
#define HEAD_WIFI_H

#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include "secrets.h"

#define WIFI_LED_PIN 8
#define UDP_PORT 50001

WiFiUDP udp; // global UDP object

typedef void (*UdpValueCallback)(int32_t value);

// ---------------------- WiFi + OTA task ----------------------
static void wifiTask(void* parameter) {
  pinMode(WIFI_LED_PIN, OUTPUT);

  Serial.print("WiFi: connecting to network ");
  Serial.println(WIFI_SSID);

  IPAddress local_IP(192, 168, IP_group, IP_tail); 
  IPAddress gateway(192, 168, IP_group, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.config(local_IP, gateway, subnet);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  WiFi.setTxPower(WIFI_POWER_11dBm);

  bool ledState = false;

  while (WiFi.status() != WL_CONNECTED) {
    // Blink LED while connecting
    ledState = !ledState;
    digitalWrite(WIFI_LED_PIN, ledState);
    Serial.print(".");
    vTaskDelay(pdMS_TO_TICKS(250));
  }

  // Solid LED when connected
  digitalWrite(WIFI_LED_PIN, HIGH);

  Serial.println("\nWiFi: connected");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // ------------------- Setup OTA -------------------
  ArduinoOTA.setPassword(OTA_PASSWORD);

  ArduinoOTA
    .onStart([]() {
      String type = (ArduinoOTA.getCommand() == U_FLASH) ? "sketch" : "filesystem";
      Serial.println("OTA Start: " + type);
    })
    .onEnd([]() {
      Serial.println("\nOTA End");
    })
    .onProgress([](unsigned int progress, unsigned int total) {
      Serial.printf("OTA Progress: %u%%\r", (progress * 100 / total));
    })
    .onError([](ota_error_t error) {
      Serial.printf("OTA Error[%u]: ", error);
      if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
      else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
      else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
      else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
      else if (error == OTA_END_ERROR) Serial.println("End Failed");
    });

  ArduinoOTA.begin();
  Serial.println("OTA Ready");

  // ------------------- WiFi/OTA loop -------------------
  while (true) {
    ArduinoOTA.handle();
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// ------------------- UDP listener task -------------------
static void udpListenerTask(void* parameter) {
  UdpValueCallback callback = (UdpValueCallback)parameter;

  udp.begin(UDP_PORT);
  Serial.print("UDP: listening on port ");
  Serial.println(UDP_PORT);

  while (true) {
    int packetSize = udp.parsePacket();

    if (packetSize == sizeof(int32_t)) {
      int32_t value;
      int len = udp.read((uint8_t*)&value, sizeof(value));

      if (len == sizeof(value)) {
        value = ntohl(value);

        Serial.print("UDP received: ");
        Serial.println(value);

        if (callback) {
          callback(value);
        }
      }
    } else if (packetSize > 0) {
      Serial.print("UDP: invalid packet size ");
      Serial.println(packetSize);

      while (udp.available()) {
        udp.read();
      }
    }

    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// ------------------- Public API -------------------
inline void startWiFiAndOTA() {
  xTaskCreate(
    wifiTask,
    "WiFi+OTA",
    4096,
    NULL,
    1,
    NULL
  );
}

inline void startUDPListener(UdpValueCallback callback) {
  xTaskCreate(
    udpListenerTask,
    "UDPListener",
    4096,
    (void*)callback,
    1,
    NULL
  );
}

#endif // HEAD_WIFI_H