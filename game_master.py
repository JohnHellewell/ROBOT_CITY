import pygame
import socket
import struct
import threading
import time
import platform
import math
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os
import db_handler

pygame.init()
pygame.joystick.init()

MAX_PLAYERS = 4
SEND_INTERVAL = 0.01  # seconds
DEAD_ZONE = 25

# global values
killswitch_value = 0
pairings = {}  # player_id -> RobotControllerThread
lock = threading.Lock()


# Platform dependent axis mapping for right stick and triggers
if platform.system() == "Linux":
    AXIS_RIGHT_X = 3
    AXIS_RIGHT_Y = 4
    AXIS_LEFT_TRIGGER = 2
    AXIS_RIGHT_TRIGGER = 5
else:
    AXIS_RIGHT_X = 2
    AXIS_RIGHT_Y = 3
    AXIS_LEFT_TRIGGER = 4
    AXIS_RIGHT_TRIGGER = 5



def scale_axis_drive(value, flip, limit):
    if value < -1.0 or value > 1.0:
        print("Axis value out of range:", value)
        value = 0.0
    if flip:
        #return 2000 - int((value + 1) * 500 * limit)
        return int((-value) * 500 * limit) + 1500
    else:
        #return int((value + 1) * 500 * limit) + 1000
        return int(value * 500 * limit) + 1500

def scale_axis_spinner(value, ch3_invert, weapon_scale, bidirectional):
    # Normalize trigger axis from [-1..1] to [0..1]
    if value < -1.0 or value > 1.0:
        print('CH3 OUT OF BOUNDS!')
        value = 0.0
    norm_val = (value + 1) / 2

    if ch3_invert:
        if(bidirectional):
            return 1500 - int(norm_val * 500 * weapon_scale)
        else:
            return 2000 - int(norm_val * 1000 * weapon_scale)
    else:
        if(bidirectional):
            return 1500 + int(norm_val * 500 * weapon_scale)
        else:
            return 1000 + int(norm_val * 1000 * weapon_scale)

def check_dead_zone(a, b):
    dist = math.sqrt((1500 - a) ** 2 + (1500 - b) ** 2)
    if dist <= DEAD_ZONE:
        return 1500, 1500
    return a, b

def get_robot_info(robot_id):
    db_handler.get_robot_info()
    
class RobotControllerThread(threading.Thread):
    def __init__(self, player_id, joystick, ip, port, inverts, bot_info):
        super().__init__()
        self.player_id = player_id
        self.joystick = joystick
        self.ip = ip
        self.port = port
        self.inverts = inverts
        self.bot_info = bot_info
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.01)  # short timeout for recvfrom
        self.daemon = True

    def run(self):
        global killswitch_value
        pressed = False  # For killswitch toggle logic (optional)
        while self.running:
            pygame.event.pump()

            raw_ch1 = self.joystick.get_axis(AXIS_RIGHT_X)
            raw_ch2 = self.joystick.get_axis(AXIS_RIGHT_Y)
            raw_ch3 = self.joystick.get_axis(AXIS_RIGHT_TRIGGER)
            #raw_ch4 = self.joystick.get_axis(AXIS_LEFT_TRIGGER)

            if(self.inverts[3]): #swap steer and for/back channels
                ch2 = scale_axis_drive(raw_ch1, self.inverts[0], self.bot_info[0])
                ch1 = scale_axis_drive(raw_ch2, self.inverts[1], self.bot_info[1])
            else: #normal operation
                ch1 = scale_axis_drive(raw_ch1, self.inverts[0], self.bot_info[0])
                ch2 = scale_axis_drive(raw_ch2, self.inverts[1], self.bot_info[1])
            
            ch3 = scale_axis_spinner(raw_ch3, self.inverts[2], self.bot_info[2], self.bot_info[3])

            ch1, ch2 = check_dead_zone(ch1, ch2)

            with lock:
                ks = killswitch_value


            packet = struct.pack('HHHHH', ch1, ch2, ch3, ks, self.inverts[3])
            try:
                self.sock.sendto(packet, (self.ip, self.port))
                data, _ = self.sock.recvfrom(1024)
                ack = struct.unpack('?', data[:1])[0]
                # print(f"[{self.player_id}] Received ack: {ack}")
            except socket.timeout:
                #print(f"[{self.player_id}] No response (timeout)")
                #print("")
                pass

            time.sleep(SEND_INTERVAL)

    def stop(self):
        self.running = False
        self.sock.close()

def pair(player_id, robot_id):
    if player_id in pairings:
        print(f"{player_id} is already paired. Break first.")
        return

    robot_info = get_robot_info(robot_id)
    if not robot_info:
        print(f"Robot ID '{robot_id}' not found in database.")
        return

    index = int(player_id[-1]) - 1
    if index >= pygame.joystick.get_count():
        print(f"No controller found for {player_id}.")
        return

    joystick = pygame.joystick.Joystick(index)
    joystick.init()
    ip, port, inverts, bot_info = robot_info
    thread = RobotControllerThread(player_id, joystick, ip, port, inverts, bot_info)
    pairings[player_id] = thread
    thread.start()
    print(f"Paired {player_id} to {robot_id} ({ip}:{port})")

def break_pair(player_id):
    thread = pairings.pop(player_id, None)
    if thread:
        thread.stop()
        print(f"Unpaired {player_id}")
    else:
        print(f"{player_id} not paired.")

def start_game():
    global killswitch_value
    with lock:
        killswitch_value = 2
    print("Game started (killswitch=2)")

def stop_game():
    global killswitch_value
    with lock:
        killswitch_value = 0
    print("Game stopped (killswitch=0)")

def reset():
    global pairings
    for player_id in list(pairings.keys()):
        break_pair(player_id)
    pairings = {}
    print("All pairings cleared.")

def show_pairings():
    if not pairings:
        print("No active pairings.")
        return
    for player, thread in pairings.items():
        print(f"{player} -> {thread.ip}:{thread.port}")


if __name__ == "__main__":
    print("ROBOT CITY Game Manager")
    print("Type 'help' for a list of commands.")

    try:
        while True:
            cmd = input("Command: ").strip().lower()
            if cmd.startswith("pair"):
                parts = cmd.split()
                if len(parts) == 3:
                    _, player_id, robot_id = parts
                    pair(player_id, robot_id)
                else:
                    print("Usage: pair playerX robot_id")
            elif cmd.startswith("break"):
                parts = cmd.split()
                if len(parts) == 2:
                    _, player_id = parts
                    break_pair(player_id)
                else:
                    print("Usage: break playerX")
            elif cmd == "start":
                start_game()
            elif cmd == "stop":
                stop_game()
            elif cmd == "reset":
                reset()
            elif cmd == "show pairings":
                show_pairings()
            elif cmd == "add robot":
                db_handler.add_robot()
            elif cmd == "remove robot":
                db_handler.remove_robot()
            elif cmd == "edit robot":
                db_handler.edit_robot()
            elif cmd == "show robots":
                db_handler.show_robots()
            elif cmd == "show types":
                db_handler.show_types()
            elif cmd == "edit type":
                db_handler.edit_type()
            elif cmd == "exit":
                reset()
                break
            elif cmd == "help":
                print("Commands:")
                print("\tGameplay: | pair playerX robot_id | break playerX | start | stop | reset | show pairings | exit |")
                print("\tIndividual Robot Settings: | show robots | add robot | edit robot | remove robot |")
                print("\tRobot Type Settings (edit all robots of a certain type): | show types | edit type | ")
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        print("\nExiting...")
        reset()
    finally:
        pygame.quit()
