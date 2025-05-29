import pygame
import socket
import struct
import threading
import csv
import time

pygame.init()
pygame.joystick.init()

# ========== CONFIG ==========
MAX_PLAYERS = 4
CSV_FILE = "robots.csv"
SEND_INTERVAL = 0.05  # seconds

# ========== GLOBALS ==========
killswitch_value = 0
pairings = {}  # player_id -> RobotControllerThread
robots = {}    # robot_id -> (ip, port)
lock = threading.Lock()

# ========== LOAD ROBOT INFO ==========
def load_robot_csv():
    global robots
    robots = {}
    with open(CSV_FILE, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            robot_id = row['robot_id']
            ip = row['local_ip']
            port = int(row['port'])
            robots[robot_id] = (ip, port)

# ========== UTILITIES ==========
def scale_axis(value):
    return int((value + 1) * 500 + 1000)

# ========== ROBOT THREAD ==========
class RobotControllerThread(threading.Thread):
    def __init__(self, player_id, joystick, ip, port):
        super().__init__()
        self.player_id = player_id
        self.joystick = joystick
        self.ip = ip
        self.port = port
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.daemon = True

    def run(self):
        global killswitch_value
        while self.running:
            ch1 = scale_axis(self.joystick.get_axis(2))  # Right stick X
            ch2 = scale_axis(self.joystick.get_axis(3))  # Right stick Y
            ch3 = 1500  # Placeholder for now
            with lock:
                ks = killswitch_value
            packet = struct.pack('HHHH', ch1, ch2, ch3, ks)
            self.sock.sendto(packet, (self.ip, self.port))
            time.sleep(SEND_INTERVAL)

    def stop(self):
        self.running = False

# ========== GAME MANAGER ==========
def pair(player_id, robot_id):
    if player_id in pairings:
        print(f"{player_id} is already paired. Break first.")
        return
    if robot_id not in robots:
        print(f"Robot ID '{robot_id}' not found.")
        return
    index = int(player_id[-1]) - 1
    if index >= pygame.joystick.get_count():
        print(f"No controller found for {player_id}.")
        return

    joystick = pygame.joystick.Joystick(index)
    joystick.init()
    ip, port = robots[robot_id]
    thread = RobotControllerThread(player_id, joystick, ip, port)
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

def show():
    if not pairings:
        print("No active pairings.")
        return
    for player, thread in pairings.items():
        print(f"{player} -> {thread.ip}:{thread.port}")

# ========== MAIN LOOP ==========
if __name__ == "__main__":
    load_robot_csv()
    print("Welcome to the Robot Game Manager")
    print("Type 'help' for a list of commands.")

    while True:
        try:
            cmd = input("Command > ").strip().lower()
            if cmd.startswith("pair"):
                _, player_id, robot_id = cmd.split()
                pair(player_id, robot_id)
            elif cmd.startswith("break"):
                _, player_id = cmd.split()
                break_pair(player_id)
            elif cmd == "start":
                start_game()
            elif cmd == "stop":
                stop_game()
            elif cmd == "reset":
                reset()
            elif cmd == "show":
                show()
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
                print("  show")
                print("  exit")
            else:
                print("Unknown command.")
        except Exception as e:
            print("Error:", e)
