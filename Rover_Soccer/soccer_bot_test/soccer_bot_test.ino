#include <Arduino.h>
#include "driver/ledc.h"

// ===== CONFIG =====
#define PWM_MODE        LEDC_LOW_SPEED_MODE
#define PWM_RES_BITS    LEDC_TIMER_12_BIT  // 12-bit is more stable at 50 Hz
#define PWM_FREQ_HZ     50
#define PWM_TIMER       LEDC_TIMER_0

// Pins
#define CH1_PIN 4
#define CH2_PIN 2
#define CH3_PIN 1
#define CH4_PIN 3

// Channels
#define CH1_PWM LEDC_CHANNEL_0
#define CH2_PWM LEDC_CHANNEL_1
#define CH3_PWM LEDC_CHANNEL_2
#define CH4_PWM LEDC_CHANNEL_3

// Default ESC pulse widths (us)
const int CH1_DEFAULT = 1500;
const int CH2_DEFAULT = 1500;
const int CH3_DEFAULT = 1500;
const int CH4_DEFAULT = 1500;

// ===== HELPER FUNCTIONS =====

// Convert microseconds to 13-bit duty (0-8191)
uint32_t usToDuty(uint16_t pulse_us) {
    return (uint32_t)(((uint64_t)pulse_us * ((1 << PWM_RES_BITS) - 1)) / 20000);
}

// Write PWM to a channel
void setPWM(uint8_t channel, uint16_t pulse_us) {
    ledc_channel_t ch;
    switch(channel) {
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

// ===== SETUP ESCs =====
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
}

// ===== SETUP =====
void setup() {
    Serial.begin(115200);
    setup_ESCs();
    delay(2000); // Give ESCs time to arm
}

void apply_motor_values(int values[]){
    for(int i=1; i<=4; i++){
        setPWM(i, values[i-1]);
    }
}

void mix_mecanum(int strafe, int forward, int rotate, int out[4])
{
  int f = forward - 1500;
  int s = strafe  - 1500;
  int r = rotate  - 1500;

  f = constrain(f, 1000, 2000);
  s = constrain(s, 1000, 2000);
  r = constrain(r, 1000, 2000);

  out[0] = 1500 - (f + s + r);
  out[1] = 1500 + (f - s - r);
  out[2] = 1500 - (f - s + r);
  out[3] = 1500 + (f + s - r);

  for (int i = 0; i < 4; i++) {
    out[i] = constrain(out[i], 1000, 2000);
  }
}


// ===== LOOP =====
void loop() {
    int stopped[4];
    int motor_vals[4];
    mix_mecanum(1500,1500,1500, stopped);
    
    apply_motor_values(stopped);
    delay(10000); //10s

    mix_mecanum(1500,1800,1500, motor_vals); //forward
    apply_motor_values(motor_vals);
    delay(500); //500ms

    apply_motor_values(stopped);
    delay(1000); //1s

    mix_mecanum(1500,1200,1500, motor_vals); //backward
    apply_motor_values(motor_vals);
    delay(500); //500ms

    apply_motor_values(stopped);
    delay(1000); //1s

    mix_mecanum(1800,1500,1500, motor_vals); //strafe right
    apply_motor_values(motor_vals);
    delay(750); //500ms

    apply_motor_values(stopped);
    delay(1000); //1s

    mix_mecanum(1200,1500,1500, motor_vals); //strafe left
    apply_motor_values(motor_vals);
    delay(750); //500ms

    apply_motor_values(stopped);
    delay(1000); //1s

    mix_mecanum(1500,1500,1800, motor_vals); //rotate CW
    apply_motor_values(motor_vals);
    delay(500); //500ms

    apply_motor_values(stopped);
    delay(1000); //1s

    mix_mecanum(1500,1500,1200, motor_vals); //rotate CCW
    apply_motor_values(motor_vals);
    delay(500); //500ms
    
}
