#ifndef BATTERY_MANAGER_H
#define BATTERY_MANAGER_H

#include <Arduino.h>

#define VOLTAGE_PIN 0              // ADC input pin
#define NUM_SAMPLES 10             // Number of readings to average
#define R1 51000.0                 // Upper resistor (ohms)
#define R2 10000.0                 // Lower resistor (ohms)
#define ADC_MAX 4095.0             // 12-bit ADC resolution for ESP32
#define ADC_REF_VOLTAGE 3.3        // Reference voltage (V)

inline float get_voltage_level() {
    int raw_adc = analogRead(VOLTAGE_PIN);

    // Convert ADC reading to voltage at the pin
    float pin_voltage = (raw_adc / ADC_MAX) * ADC_REF_VOLTAGE;

    // Scale up based on voltage divider ratio
    float battery_voltage = pin_voltage * ((R1 + R2) / R2);

    return battery_voltage;
}

#endif