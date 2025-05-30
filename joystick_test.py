import pygame
import sys

import pygame
import socket
import struct
import time

# --- UDP Setup ---
ESP32_IP = "192.168.1.7"
PORT = 4210
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.01)

# --- Stick Drift Correction ---
dead_zone = 40

# killswitch
ks = 0


def send_and_receive(values):
    assert len(values) == 4
    packet = struct.pack('HHHH', *values)
    sock.sendto(packet, (ESP32_IP, PORT))
    try:
        data, _ = sock.recvfrom(1024)
        result = struct.unpack('?', data[:1])[0]
        #print("Received bool:", result)
        return result
    except socket.timeout:
        print("No response (timeout)")

# --- Gamepad Setup ---
pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No joystick connected.")
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print(f"Using joystick: {joystick.get_name()}")

# --- Axis to RC Conversion ---
def scale_axis(value, flip):
    temp = 1500
    if flip:
        temp = 2000-int((value + 1) * 500)
    else:
        temp = int((value + 1) * 500 + 1000)
    
    if abs(1500-temp) <= dead_zone:
        return 1500
    else:
        return temp




# --- Main Loop ---
try:
    pressed = True
    while True:
        pygame.event.pump()

        # Read axis 4 and 5 (right stick typically)
        raw_ch1 = joystick.get_axis(2)  # Right stick horizontal
        raw_ch2 = joystick.get_axis(3)  # Right stick vertical
        raw_ch4 = joystick.get_axis(4)  # Left trigger: killswitch


        ch1 = scale_axis(raw_ch1, False) 
        ch2 = scale_axis(raw_ch2, True) 


        if not pressed and raw_ch4 > 0:
            pressed = True
            if ks == 0:
                ks = 2
            else:
                ks = 0
        elif pressed and raw_ch4 == -1.0:
            pressed = False
        
        
        print(f"ch1: {ch1}, ch2: {ch2}, ks: {ks}, left trig: {raw_ch4}")

            
        # Send ch1 and ch2, set ch3 = 1500, ch4 = 0
        send_and_receive([ch1, ch2, 1500, ks])

        time.sleep(0.01)  

except KeyboardInterrupt:
    print("\nExiting...")
finally:
    pygame.quit()
