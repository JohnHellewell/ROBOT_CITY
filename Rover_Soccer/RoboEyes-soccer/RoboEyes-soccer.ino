#include <Arduino.h>
#include <Adafruit_SSD1306.h>
#include <FluxGarage_RoboEyes.h>
#include "head_wifi.h"

#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels
// Declaration for an SSD1306 display connected to I2C (SDA, SCL pins)
#define OLED_RESET     -1 // Reset pin # (or -1 if sharing Arduino reset pin)
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// create a RoboEyes instance using an Adafruit_SSD1306 display driver
RoboEyes<Adafruit_SSD1306> roboEyes(display); 

unsigned int elapsed = millis();
unsigned long next_mood_change = 10000 + elapsed; //10 sec
bool flicker = false;
unsigned long next_anim = 5000 + elapsed; //5 sec
int mood_weights[] = {4, 4, 6, 10}; //TIRED, ANGRY, HAPPY, DEFAULT

bool user_flag = false;
int user_mood = 0;



void setup() {
  Serial.begin(115200);
  Wire.begin(6, 7);   // SDA = 6, SCL = 7
  
  delay(100);
  startWiFiAndOTA(); 
  startUDPListener(user_command);

  // Startup OLED Display
  // SSD1306_SWITCHCAPVCC = generate display voltage from 3.3V internally
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { // Address 0x3C or 0x3D
    Serial.println(F("SSD1306 allocation failed"));
    for(;;); // Don't proceed, loop forever
  } else {
    Serial.println("SSD1306 allocation success");
  }
  display.setRotation(2); //rotate screen upside down

  // Startup robo eyes
  roboEyes.begin(SCREEN_WIDTH, SCREEN_HEIGHT, 60); // screen-width, screen-height, max framerate

  // Define some automated eyes behaviour
  roboEyes.setAutoblinker(ON, 3, 2); // Start auto blinker animation cycle -> bool active, int interval, int variation -> turn on/off, set interval between each blink in full seconds, set range for random interval variation in full seconds
  roboEyes.setIdleMode(ON, 2, 2); // Start idle animation cycle (eyes looking in random directions) -> turn on/off, set interval between each eye repositioning in full seconds, set range for random time interval variation in full seconds
  
  // Define eye shapes, all values in pixels
  roboEyes.setWidth(44, 44); // byte leftEye, byte rightEye //36 but i like 44
  roboEyes.setHeight(36, 36); // byte leftEye, byte rightEye //36
  roboEyes.setBorderradius(8, 8); // byte leftEye, byte rightEye //8
  roboEyes.setSpacebetween(10); // int space -> can also be negative //10

  // Define mood, curiosity and position
  //roboEyes.setMood(DEFAULT); // mood expressions, can be TIRED, ANGRY, HAPPY, DEFAULT
  //roboEyes.setPosition(DEFAULT); // cardinal directions, can be N, NE, E, SE, S, SW, W, NW, DEFAULT (default = horizontally and vertically centered)
  //roboEyes.setCuriosity(ON); // bool on/off -> when turned on, height of the outer eyes increases when moving to the very left or very right

  // Set horizontal or vertical flickering
  //roboEyes.setHFlicker(ON, 2); // bool on/off, byte amplitude -> horizontal flicker: alternately displacing the eyes in the defined amplitude in pixels
  //roboEyes.setVFlicker(ON, 2); // bool on/off, byte amplitude -> vertical flicker: alternately displacing the eyes in the defined amplitude in pixels

  // Play prebuilt oneshot animations
  //roboEyes.anim_confused(); // confused - eyes shaking left and right
  //roboEyes.anim_laugh(); // laughing - eyes shaking up and down

  //roboEyes.setCyclops(true); //(bool ON/OFF) -> if turned ON, robot has only on eye


  
} // end of setup

int random_weighted(int weights[], int count){
  int sum = 0;
  for(int i=0; i<count; i++){
    sum += weights[i];
  }

  int selection = random(sum);

  for(int i=0; i<count; i++){
    selection -= weights[i];
    if(selection < 0){
      return i;
    }
  }

  //should never reach this
  Serial.println("random weight out of bounds error");
  return 0;
}

void user_command(int32_t value){ //user sets a value for the eyes (0-3 inclusive)
  if(value >= 0 && value <= 3){
    user_mood = value;
    user_flag = true;
  }
}


void loop() {
  roboEyes.update(); // update eyes drawings
  // Dont' use delay() here in order to ensure fluid eyes animations.
  // Check the AnimationSequences example for common practices.

  //check for user input
  if(user_flag){
    user_flag = false; //set flag back to false
    roboEyes.setMood(user_mood);
    next_mood_change = millis() + 25000; //keep the user-specified mood for 25 seconds

    //flicker 
    flicker = true;
    roboEyes.setHFlicker(ON, 2);
    next_anim = millis() + 500; //500ms flicker time
  }

  //change mood
  if(millis() >= next_mood_change){
    roboEyes.setCuriosity(bool(random(2)));
    roboEyes.setMood(random_weighted(mood_weights, 4));
    next_mood_change = 10000 + random(5000) + millis(); //10-15 sec
  }

  if(millis() >= next_anim){
    if(!flicker){
      if(random(2)==0){
        roboEyes.setHFlicker(ON, 2);
        next_anim = millis() + random(250, 1000); //0.25 to 1 sec
        flicker = !flicker;
      } else { //laugh or confused
        if(random(2)==0){
          roboEyes.anim_laugh();
        } else {
          roboEyes.anim_confused();
        }
      }
    } else {
      roboEyes.setHFlicker(OFF, 2);
      next_anim = millis() + random(5000, 20000); //5-20 sec
      flicker = !flicker;
    }
    

  }
}
