This is all the code needed to run the robots & arena at Robot City

![Diagram](arena_robots_server_diagram.jpg)

The robots each have an ESP32 acting as a WiFi receiver. These can be reprogrammed wirelessly using the Arduino OTA protocol. Password is "1234". Code for the robots is found in the "Robot_ESP32" folder
Each robot will have the following programmed functionalities:
- The ability to send/receive packets over the WiFi network, used to drive the robots and toggle the killswitch. In the future, LED lights will be controlled in this manner as well
- Each robot can be reprogrammed when turned on and connected to the WiFi
- Each robot has an accelerometer, and will be able to invert drive controls when flipped upside down

A computer sitting under the arena will read inputs from the 4 controllers, and send the WiFi packets to each of the robots in the arena. This will be coded in python scripts
The computer will do the following:
- read inputs from each of the 4 controllers. They will be distinct from each other
- receive killswitch data. Manual input, also sensor from the door (possibly a ESP32 device that sends data over WiFi)
- translate the user inputs into packets for each robot. Send to robots via WiFi router. Measure ping with each robot
- Run a program with a screen for the employee and customers to watch. This program can:
  - Allow the employee can "scan" each robot before the match (assigning a robot to players 1-4)
  - Start the match, pause it. (Allow robots to drive to starting squares with weapons disabled). When employee hits start, bots are disabled during the "3, 2, 1..." countdown
  - Display a battle timer clock
  - Display points for each team, and a "winner" screen
  - Controls lights in arena
**At first, the UI will be text-based. In the future, it will be GUI & sensor-based

  
In the future, I will add a vpn capability to the computer, so I can repair things from anywhere, even uploading code to the robots.
