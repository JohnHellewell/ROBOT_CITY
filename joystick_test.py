import pygame
import sys
import math
import socket
import struct
import time
import platform

# --- UDP Setup ---
BODY_IP = "192.168.1.80"
BODY_PORT = 4280
HEAD_IP = "192.168.1.90"
HEAD_PORT = 50001

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.01)

# --- Stick Drift Correction ---
dead_zone = 30

# --- killswitch ---
ks = 0

# --- weapon scaling ---
weapon_scale = 1.0  # must be between 0.0 and 1.0

# --- Joystick axis mapping ---
if platform.system() == "Linux":
    AXIS_RIGHT_X = 3
    AXIS_RIGHT_Y = 4
    AXIS_LEFT_TRIGGER = 2
    AXIS_RIGHT_TRIGGER = 5
else:
    # Assume Windows fallback
    AXIS_RIGHT_X = 2
    AXIS_RIGHT_Y = 3
    AXIS_LEFT_X = 0
    AXIS_LEFT_Y = 1
    AXIS_LEFT_TRIGGER = 4
    AXIS_RIGHT_TRIGGER = 5

# --- XYAB button indices (verify with your controller) ---
BUTTON_X = 2
BUTTON_Y = 3
BUTTON_A = 0
BUTTON_B = 1

prev_button_state = [False] * 4  # track previous XYAB states

# --- Helper functions ---
def send_only(values):
    """Send 4-channel packet to the body."""
    packet = struct.pack('HHHH', *values)
    sock.sendto(packet, (BODY_IP, BODY_PORT))
    # Print for debugging
    #print(f"Body packet sent -> CH1: {values[0]}, CH2: {values[1]}, CH3: {values[2]}, KS: {values[3]}")

def send_head(button_id):
    """Send a single integer to the head board (edge-triggered)."""
    if button_id == 2:
        button_id = 1
    elif button_id == 1:
        button_id = 2
    packet = struct.pack('!I', button_id)  # network byte order
    sock.sendto(packet, (HEAD_IP, HEAD_PORT))
    print(f"Head packet sent -> Button ID: {button_id}")

def scale_axis(value, flip=False):
    """Scale joystick axis (-1..1) to 1000-2000 PWM values."""
    if flip:
        return 2000 - int((value + 1) * 500)
    else:
        return int((value + 1) * 500 + 1000)

def check_dead_zone(a, b):
    """Apply circular dead zone to two axes."""
    a1 = abs(1500 - a)
    b1 = abs(1500 - b)
    if math.sqrt(a1 * a1 + b1 * b1) <= dead_zone:
        return 1500, 1500
    else:
        return a, b

# --- Initialize joystick ---
pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No joystick connected.")
    sys.exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print(f"Using joystick: {joystick.get_name()}")

# --- Main loop ---
try:
    pressed = False  # tracks killswitch trigger state

    while True:
        pygame.event.pump()

        # --- Read axes ---
        raw_ch1 = joystick.get_axis(AXIS_LEFT_X)
        raw_ch2 = joystick.get_axis(AXIS_LEFT_Y)
        raw_ch3 = joystick.get_axis(AXIS_RIGHT_X)
        raw_ch4 = joystick.get_axis(AXIS_LEFT_TRIGGER)

        ch1 = scale_axis(raw_ch1, False)
        ch2 = scale_axis(raw_ch2, True)
        ch3 = scale_axis(raw_ch3, False)
        ch1, ch2 = check_dead_zone(ch1, ch2)

        # --- Handle killswitch toggle ---
        if not pressed and raw_ch4 > 0:
            pressed = True
            ks = 2 if ks == 0 else 0
        elif pressed and raw_ch4 == -1.0:
            pressed = False

        # --- Handle XYAB button presses (edge detection) ---
        for idx, button in enumerate([BUTTON_A, BUTTON_B, BUTTON_X, BUTTON_Y]):
            is_pressed = joystick.get_button(button)
            if is_pressed and not prev_button_state[idx]:
                send_head(idx)  # send packet once per press
            prev_button_state[idx] = is_pressed

        # --- Send body control packet ---
        send_only([ch1, ch2, ch3, ks])

        # --- Small delay ---
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    pygame.quit()