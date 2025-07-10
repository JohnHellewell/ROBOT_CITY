import pygame
import socket
import struct
import threading
import time
import math
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

pygame.init()
pygame.joystick.init()


MAX_PLAYERS = 4
SEND_INTERVAL = 0.01  # seconds
DEAD_ZONE = 25

# global values
killswitch_value = 0
pairings = {}  # player_id -> RobotControllerThread
lock = threading.Lock()

#load .env values
load_dotenv()
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
TARGET_DB = os.getenv("TARGET_DB")

def get_connection(database=None):
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=TARGET_DB
    )

def scale_axis(value, flip):
    temp = 1500
    if flip:
        temp = 2000-int((value + 1) * 500)
    else:
        temp = int((value + 1) * 500 + 1000)

    return temp

def get_robot_info(robot_id):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT local_ip, network_port, CH1_INVERT, CH2_INVERT, CH3_INVERT FROM robot WHERE robot_id = %s", (robot_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return result['local_ip'], int(result['network_port']), [bool(result['CH1_INVERT']), bool(result['CH2_INVERT']), bool(result['CH3_INVERT'])]
        else:
            return None
    except mysql.connector.Error as err:
        print("Database error:", err)
        return None

def check_dead_zone(a, b):
    a1 = abs(1500-a)
    b1 = abs(1500-b)

    if (math.sqrt(a1*a1 + b1*b1)<=DEAD_ZONE):
        return (1500, 1500)
    else:
        return (a, b)

# pairing thread
class RobotControllerThread(threading.Thread):
    def __init__(self, player_id, joystick, ip, port, inverts):
        super().__init__()
        

        self.player_id = player_id
        self.joystick = joystick

        self.ip = ip
        self.port = port
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.02)  
        self.daemon = True
        self.inverts = inverts

    def run(self):
        global killswitch_value
        while self.running:
            ch1 = scale_axis(self.joystick.get_axis(2), self.inverts[0])  # Right stick X
            ch2 = scale_axis(self.joystick.get_axis(3), self.inverts[1])  # Right stick Y
            ch3 = 1500  # Placeholder for now
            ch1, ch2 = check_dead_zone(ch1, ch2)

            with lock:
                ks = killswitch_value
            
            packet = struct.pack('HHHH', ch1, ch2, ch3, ks)
            self.sock.sendto(packet, (self.ip, self.port))

            time.sleep(SEND_INTERVAL)

    def stop(self):
        self.running = False

# game manager
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
    ip, port, ch_inverts  = robot_info
    thread = RobotControllerThread(player_id, joystick, ip, port, ch_inverts)
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

def add_robot():
    try:
        robot_id = input("Enter robot ID: ").strip()
        local_ip = input("Enter local IP address: ").strip()
        port = int(input("Enter network port: ").strip())
        ch1_inv = input("Invert CH1? (y/n): ").strip().lower() == 'y'
        ch2_inv = input("Invert CH2? (y/n): ").strip().lower() == 'y'
        ch3_inv = input("Invert CH3? (y/n): ").strip().lower() == 'y'

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO robot (robot_id, local_ip, network_port, CH1_INVERT, CH2_INVERT, CH3_INVERT)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (robot_id, local_ip, port, ch1_inv, ch2_inv, ch3_inv))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Robot '{robot_id}' added successfully.")
    except mysql.connector.IntegrityError:
        print("Error: Robot ID already exists.")
    except ValueError:
        print("Invalid number input.")
    except Exception as e:
        print("Error adding robot:", e)

# main
if __name__ == "__main__":
    
    print("ROBOT CITY Game Manager")
    print("Type 'help' for a list of commands.")

    while True:
        try:
            cmd = input("Command: ").strip().lower()
            if cmd.startswith("pair"):
                ignore, player_id, robot_id = cmd.split()
                pair(player_id, robot_id)
            elif cmd.startswith("break"):
                ignore, player_id = cmd.split()
                break_pair(player_id)
            elif cmd == "start":
                start_game()
            elif cmd == "stop":
                stop_game()
            elif cmd == "reset":
                reset()
            elif cmd == "show pairings":
                show_pairings()
            elif cmd == "add robot":
                add_robot()
            elif cmd == "exit":
                reset()
                break
            elif cmd == "help":
                print("Commands:")
                print("  pair playerX robot_id")
                print("  break playerX")
                print("  start")
                print("  stop")
                print("  reset")
                print("  show pairings")
                print("  add robot")
                print("  exit")
            else:
                print("Unknown command.")
        except Exception as e:
            print("Error:", e)
