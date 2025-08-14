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

pygame.init()
pygame.joystick.init()

MAX_PLAYERS = 4
SEND_INTERVAL = 0.01  # seconds
DEAD_ZONE = 25

# global values
killswitch_value = 0
pairings = {}  # player_id -> RobotControllerThread
lock = threading.Lock()

# Load environment variables for MySQL
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

def scale_axis(value, flip):
    if value < -1.0 or value > 1.0:
        print("Axis value out of range:", value)
        value = 0.0
    if flip:
        return 2000 - int((value + 1) * 500)
    else:
        return int((value + 1) * 500 + 1000)

def scale_axis_spinner(value, flip, weapon_scale=0.4):
    # Normalize trigger axis from [-1..1] to [0..1]
    if value < -1.0 or value > 1.0:
        print('CH3 OUT OF BOUNDS!')
        value = 0.0
    norm_val = (value + 1) / 2
    if flip:
        return 1500 - int(norm_val * 500 * weapon_scale)
    else:
        return 1500 + int(norm_val * 500 * weapon_scale)

def check_dead_zone(a, b):
    dist = math.sqrt((1500 - a) ** 2 + (1500 - b) ** 2)
    if dist <= DEAD_ZONE:
        return 1500, 1500
    return a, b

def get_robot_info(robot_id):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT local_ip, network_port, CH1_INVERT, CH2_INVERT, CH3_INVERT FROM robot WHERE robot_id = %s",
            (robot_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return (
                result['local_ip'],
                int(result['network_port']),
                [bool(result['CH1_INVERT']), bool(result['CH2_INVERT']), bool(result['CH3_INVERT'])]
            )
        else:
            return None
    except mysql.connector.Error as err:
        print("Database error:", err)
        return None

class RobotControllerThread(threading.Thread):
    def __init__(self, player_id, joystick, ip, port, inverts):
        super().__init__()
        self.player_id = player_id
        self.joystick = joystick
        self.ip = ip
        self.port = port
        self.inverts = inverts
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
            raw_ch4 = self.joystick.get_axis(AXIS_LEFT_TRIGGER)

            ch1 = scale_axis(raw_ch1, self.inverts[0])
            ch2 = scale_axis(raw_ch2, self.inverts[1])
            ch3 = scale_axis_spinner(raw_ch3, self.inverts[2])

            ch1, ch2 = check_dead_zone(ch1, ch2)

            with lock:
                ks = killswitch_value

            # Optional: toggle killswitch with left trigger press (if desired)
            # if not pressed and raw_ch4 > 0:
            #     pressed = True
            #     ks = 2 if ks == 0 else 0
            # elif pressed and raw_ch4 == -1.0:
            #     pressed = False

            #print(f"[{self.player_id}] Raw axes: X={raw_ch1:.2f} Y={raw_ch2:.2f} TRIG={raw_ch3:.2f} LT={raw_ch4:.2f}")
            #print(f"[{self.player_id}] Sending ch1={ch1}, ch2={ch2}, ch3={ch3}, ks={ks}")

            packet = struct.pack('HHHH', ch1, ch2, ch3, ks)
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
    ip, port, inverts = robot_info
    thread = RobotControllerThread(player_id, joystick, ip, port, inverts)
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

def remove_robot():
    robot_id = input("Enter robot ID to remove: ").strip()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM robot WHERE robot_id = %s", (robot_id,))
        if cursor.rowcount == 0:
            print(f"No robot found with ID '{robot_id}'.")
        else:
            conn.commit()
            print(f"Robot '{robot_id}' removed successfully.")
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error removing robot:", e)

def edit_robot():
    robot_id = input("Enter robot ID to edit: ").strip()
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM robot WHERE robot_id = %s", (robot_id,))
        robot = cursor.fetchone()
        if not robot:
            print(f"No robot found with ID '{robot_id}'.")
            cursor.close()
            conn.close()
            return

        print("Leave blank to keep current value.")
        new_ip = input(f"Current IP is {robot['local_ip']}. New IP: ").strip()
        new_port_input = input(f"Current port is {robot['network_port']}. New port: ").strip()
        new_ch1_inv = input(f"Current CH1 invert is {bool(robot['CH1_INVERT'])} (y/n): ").strip().lower()
        new_ch2_inv = input(f"Current CH2 invert is {bool(robot['CH2_INVERT'])} (y/n): ").strip().lower()
        new_ch3_inv = input(f"Current CH3 invert is {bool(robot['CH3_INVERT'])} (y/n): ").strip().lower()

        # If user left blank, keep old values
        ip = new_ip if new_ip else robot['local_ip']
        port = int(new_port_input) if new_port_input else robot['network_port']
        ch1_inv = robot['CH1_INVERT'] if new_ch1_inv == '' else (new_ch1_inv == 'y')
        ch2_inv = robot['CH2_INVERT'] if new_ch2_inv == '' else (new_ch2_inv == 'y')
        ch3_inv = robot['CH3_INVERT'] if new_ch3_inv == '' else (new_ch3_inv == 'y')

        cursor.execute("""
            UPDATE robot SET local_ip = %s, network_port = %s, CH1_INVERT = %s, CH2_INVERT = %s, CH3_INVERT = %s
            WHERE robot_id = %s
        """, (ip, port, ch1_inv, ch2_inv, ch3_inv, robot_id))

        conn.commit()
        print(f"Robot '{robot_id}' updated successfully.")
        cursor.close()
        conn.close()

    except Exception as e:
        print("Error editing robot:", e)

def show_robots():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT robot_id, local_ip, network_port, CH1_INVERT, CH2_INVERT, CH3_INVERT FROM robot")
        robots = cursor.fetchall()
        cursor.close()
        conn.close()

        if not robots:
            print("No robots found in database.")
            return

        print(f"{'Robot ID':<15} {'IP Address':<15} {'Port':<6} CH1_INV CH2_INV CH3_INV")
        print("-" * 60)
        for r in robots:
            print(f"{r['robot_id']:<15} {r['local_ip']:<15} {r['network_port']:<6}  {bool(r['CH1_INVERT']):<7} {bool(r['CH2_INVERT']):<7} {bool(r['CH3_INVERT']):<7}")

    except Exception as e:
        print("Error showing robots:", e)


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
                add_robot()
            elif cmd == "remove robot":
                remove_robot()
            elif cmd == "edit robot":
                edit_robot()
            elif cmd == "show robots":
                show_robots()
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
                print("  remove robot")
                print("  edit robot")
                print("  show robots")
                print("  exit")
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        print("\nExiting...")
        reset()
    finally:
        pygame.quit()
