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



def scale_axis_drive(value, flip, limit):
    if value < -1.0 or value > 1.0:
        print("Axis value out of range:", value)
        value = 0.0
    if flip:
        return 2000 - int((value + 1) * 500 * limit)
    else:
        return int((value + 1) * 500 * limit) + 1000

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
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT local_ip, network_port, robot_type, color, CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE, " \
            "steering_limit, forward_limit, weapon_limit, bidirectional_weapon FROM robot " \
            "JOIN robot_type ON robot.robot_type = robot_type.bot_type WHERE robot_id = %s",
            (robot_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return (
                result['local_ip'],
                int(result['network_port']),
                [bool(result['CH1_INVERT']), bool(result['CH2_INVERT']), bool(result['CH3_INVERT']), bool(result['INVERT_DRIVE'])],
                [float(result['steering_limit']), float(result['forward_limit']), float(result['weapon_limit']), bool(result['bidirectional_weapon'])]
            )
        else:
            return None
    except mysql.connector.Error as err:
        print("Database error:", err)
        return None
    


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
            raw_ch4 = self.joystick.get_axis(AXIS_LEFT_TRIGGER)

            ch1 = scale_axis_drive(raw_ch1, self.inverts[0], self.bot_info[0])
            ch2 = scale_axis_drive(raw_ch2, self.inverts[1], self.bot_info[1])
            ch3 = scale_axis_spinner(raw_ch3, self.inverts[2], self.bot_info[2], self.bot_info[3])

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

def add_robot():
    try:
        robot_id = input("Enter robot ID: ").strip()
        local_ip = input("Enter local IP address: ").strip()
        port = int(input("Enter network port: ").strip())
        ch1_inv = input("Invert CH1? (y/n): ").strip().lower() == 'y'
        ch2_inv = input("Invert CH2? (y/n): ").strip().lower() == 'y'
        ch3_inv = input("Invert CH3? (y/n): ").strip().lower() == 'y'
        invert_drive = input("Invert drive? (y/n): ").strip().lower() == 'y'
        robot_type = input("Enter robot type: ").strip()
        color = input("Enter color: ").strip()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO robot (robot_id, local_ip, network_port, CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE, robot_type, color)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (robot_id, local_ip, port, ch1_inv, ch2_inv, ch3_inv, invert_drive, robot_type, color))
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
        new_robot_type = input(f"Current bot type is {robot['robot_type']}. New bot type: ").strip()
        new_color = input(f"Current color is {robot['color']}. New color: ").strip()
        new_invert_drive = input(f"Current invert_drive is {bool(robot['invert_drive'])}. Only change this if robot turns when supposed to go forward. (y/n): ").strip().lower()
        new_ch1_inv = input(f"Current CH1 invert is {bool(robot['CH1_INVERT'])} (y/n): ").strip().lower()
        new_ch2_inv = input(f"Current CH2 invert is {bool(robot['CH2_INVERT'])} (y/n): ").strip().lower()
        new_ch3_inv = input(f"Current CH3 invert is {bool(robot['CH3_INVERT'])} (y/n): ").strip().lower()

        # If user left blank, keep old values
        ip = new_ip if new_ip else robot['local_ip']
        port = int(new_port_input) if new_port_input else robot['network_port']
        robot_type = new_robot_type if new_robot_type else robot['robot_type']
        color = new_color if new_color else robot['color']
        invert_drive = robot['invert_drive'] if new_invert_drive == '' else (new_invert_drive == 'y')
        ch1_inv = robot['CH1_INVERT'] if new_ch1_inv == '' else (new_ch1_inv == 'y')
        ch2_inv = robot['CH2_INVERT'] if new_ch2_inv == '' else (new_ch2_inv == 'y')
        ch3_inv = robot['CH3_INVERT'] if new_ch3_inv == '' else (new_ch3_inv == 'y')

        cursor.execute("""
            UPDATE robot
            SET local_ip = %s,
                network_port = %s,
                robot_type = %s,
                color = %s,
                INVERT_DRIVE = %s,
                CH1_INVERT = %s,
                CH2_INVERT = %s,
                CH3_INVERT = %s
            WHERE robot_id = %s
        """, (ip, port, robot_type, color, invert_drive, ch1_inv, ch2_inv, ch3_inv, robot_id))

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

        cursor.execute("""
            SELECT 
                robot_id, local_ip, network_port, robot_type, color,
                CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE,
                steering_limit, forward_limit, weapon_limit, bidirectional_weapon
            FROM robot
            JOIN robot_type ON robot.robot_type = robot_type.bot_type
        """)

        robots = cursor.fetchall()
        cursor.close()
        conn.close()

        if not robots:
            print("No robots found in database.")
            return

        # Map database columns to shorter display names
        display_map = {
            'robot_id': 'ID',
            'local_ip': 'IP',
            'network_port': 'Port',
            'robot_type': 'Type',
            'color': 'Color',
            'CH1_INVERT': 'ch1_inv',
            'CH2_INVERT': 'ch2_inv',
            'CH3_INVERT': 'ch3_inv',
            'INVERT_DRIVE': 'inv_drv',
            'steering_limit': 'steer_lim',
            'forward_limit': 'for_lim',
            'weapon_limit': 'wpn_lim',
            'bidirectional_weapon': 'bi_dir_wpn'
        }

        # Set maximum column widths
        max_widths = {
            'robot_id': 6,
            'local_ip': 15,
            'network_port': 5,
            'robot_type': 12,
            'color': 8,
            'CH1_INVERT': 5,
            'CH2_INVERT': 5,
            'CH3_INVERT': 5,
            'INVERT_DRIVE': 5,
            'steering_limit': 6,
            'forward_limit': 6,
            'weapon_limit': 6,
            'bidirectional_weapon': 5
        }

        # Print header
        header = ""
        for col in display_map:
            header += display_map[col].ljust(max_widths[col]+2)
        print(header)
        print("-" * len(header))

        # Print rows
        for r in robots:
            row_str = ""
            for col, width in max_widths.items():
                val = r[col]
                # convert booleans to True/False
                if isinstance(val, bool) or col in ['CH1_INVERT','CH2_INVERT','CH3_INVERT','INVERT_DRIVE','bidirectional_weapon']:
                    val = str(bool(val))
                val = str(val)
                # truncate if too long
                if len(val) > width:
                    val = val[:width-3] + "..."
                row_str += val.ljust(width+2)
            print(row_str)

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
