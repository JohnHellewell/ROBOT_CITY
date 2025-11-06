#example desktop shortcut
#Exec=env GTK_IM_MODULE=xim XDG_SESSION_TYPE=x11 XMODIFIERS= /usr/bin/python3 /home/john/ROBOT_CITY/game_master.py -gui

import pygame
import socket
import struct
import threading
import time
import platform
import math
import string
import json
from dotenv import load_dotenv
import os
import db_handler
import argparse
import sys
import signal
from LightClockHandler import LightClockHandler
import tkinter as tk
from tkinter import simpledialog, messagebox
from sound_effects import SoundEffects


pygame.init()
pygame.joystick.init()


controller_map_json_path = "controller_map.json"

def timer_stop_game():
    global killswitch_value
    with lock:
        killswitch_value = 0
    print("Game stopped (killswitch=0)")
    sound_effects.buzzer()

light_clock_handler = LightClockHandler(on_match_end=timer_stop_game)
sound_effects = SoundEffects()

CONTROLLER_MAP = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
}

REVERSE_MAP = {v: k for k, v in CONTROLLER_MAP.items()}

MAX_PLAYERS = 4
SEND_INTERVAL = 0.01  # seconds
DEAD_ZONE = 25

# global values
killswitch_value = 0
pairings = {}  # player_id -> RobotControllerThread
lock = threading.Lock()


# Platform dependent axis mapping for right stick and triggers
if platform.system() == "Linux":
    AXIS_X = 3 #3
    AXIS_Y = 1 #1
    AXIS_LEFT_TRIGGER = 2 #2
    AXIS_RIGHT_TRIGGER = 5 #5
    
else:
    AXIS_X = 2
    AXIS_Y = 3
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
    return db_handler.get_robot_info(robot_id)

def update_runtime_controller_map(json_file=controller_map_json_path):
    """
    Updates CONTROLLER_MAP to map letters → pygame indices using UIDs from JSON.
    """
    global CONTROLLER_MAP
    CONTROLLER_MAP = {}
    
    try:
        with open(json_file, "r") as f:
            letter_to_uid = json.load(f)
    except FileNotFoundError:
        print(f"No controller map JSON found at {json_file}. Using empty map.")
        return

    for i in range(pygame.joystick.get_count()):
        uid = get_unique_controller_id(i)
        for letter, mapped_uid in letter_to_uid.items():
            if uid == mapped_uid:
                CONTROLLER_MAP[letter] = i
                break

    print("Runtime CONTROLLER_MAP updated:", CONTROLLER_MAP)




update_runtime_controller_map() #run once on startup





def get_unique_controller_id(pygame_index):
    """
    Returns a unique identifier for the joystick at pygame_index.
    """
    joy = pygame.joystick.Joystick(pygame_index)
    joy.init()
    name = joy.get_name()
    guid = joy.get_guid()  # guaranteed unique per physical device
    return f"{name}_{guid}"


def calibrate_controller_order(num_controllers=8):
    reset()  # break all pairings first

    if pygame.joystick.get_count() < num_controllers:
        print(f"{num_controllers} controllers expected, only {pygame.joystick.get_count()} found. Operation cancelled")
        return
    elif pygame.joystick.get_count() > num_controllers:
        print(f"{num_controllers} controllers expected, {pygame.joystick.get_count()} found. Only the first {num_controllers} will be counted")

    joysticks = []
    unique_ids = []
    for i in range(min(num_controllers, pygame.joystick.get_count())):
        js = pygame.joystick.Joystick(i)
        js.init()
        joysticks.append(js)
        uid = get_unique_controller_id(i)
        unique_ids.append(uid)
        print(f"[{i}] {js.get_name()} | Serial={uid.split('_')[-1]}")  # show short serial

    print("\nPress A, B, X, or Y on each controller to assign A-H order...\n")

    new_order = []
    valid_buttons = {0, 1, 2, 3}  # A B X Y
    while len(new_order) < len(joysticks):
        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                js_index = event.joy
                btn = event.button
                uid = unique_ids[js_index]

                if uid not in new_order and btn in valid_buttons:
                    new_order.append(uid)
                    print(f"Controller {js_index + 1} set as {string.ascii_uppercase[len(new_order)-1]} ({uid})")

        pygame.time.wait(10)

    save_controller_map(new_order)
    load_controller_map()
    update_runtime_controller_map()


def save_controller_map(order, filename=controller_map_json_path):
    """Save the controller map as letters → unique IDs."""
    letters = list(string.ascii_uppercase[:len(order)])
    controller_map = {letters[i]: order[i] for i in range(len(order))}

    with open(filename, "w") as f:
        json.dump(controller_map, f, indent=4)

    print(f"\nController map saved to {filename}:")
    print(json.dumps(controller_map, indent=4))


def load_controller_map(filename=controller_map_json_path, num_controllers=8):
    """Load controller map from JSON file or set CONTROLLER_MAP to defaults using unique IDs."""
    global CONTROLLER_MAP, REVERSE_MAP

    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)

            if isinstance(data, dict) and all(k in string.ascii_uppercase for k in data.keys()):
                CONTROLLER_MAP = data
                REVERSE_MAP = {v: k for k, v in CONTROLLER_MAP.items()}
                print(f"Loaded controller map from {filename}:")
                print(json.dumps(CONTROLLER_MAP, indent=4))
                return
            else:
                print(f"Invalid format in {filename}, using default map.")
        else:
            print(f"No existing {filename}, using default map.")

    except Exception as e:
        print(f"Error loading {filename}: {e}")
        print("Using default map.")

    # fallback: map letters to first N controllers by index
    letters = list(string.ascii_uppercase[:num_controllers])
    CONTROLLER_MAP = {letters[i]: get_unique_controller_id(i) for i in range(min(num_controllers, pygame.joystick.get_count()))}
    REVERSE_MAP = {v: k for k, v in CONTROLLER_MAP.items()}


    
class RobotControllerThread(threading.Thread):
    def __init__(self, player_id, joystick, ip, port, inverts, bot_info, bot_id):
        super().__init__()
        self.player_id = player_id
        self.joystick = joystick
        self.ip = ip
        self.port = port
        self.inverts = inverts
        self.bot_info = bot_info
        self.bot_id = bot_id
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.01)  # short timeout for recvfrom
        self.daemon = True

    def run(self):
        global killswitch_value
        pressed = False  # For killswitch toggle logic (optional)
        while self.running:
            pygame.event.pump()

            raw_ch1 = self.joystick.get_axis(AXIS_X)
            raw_ch2 = self.joystick.get_axis(AXIS_Y)
            raw_ch3 = max(self.joystick.get_axis(AXIS_LEFT_TRIGGER), self.joystick.get_axis(AXIS_RIGHT_TRIGGER) )
            hat_x, hat_y = self.joystick.get_hat(0)
            #raw_ch4 = self.joystick.get_axis(AXIS_LEFT_TRIGGER)

            #account for "mode" being pressed
            if hat_y != 0:
                raw_ch2 = hat_y * -1

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

def pair(player_letter, robot_id):
    if player_letter not in CONTROLLER_MAP:
        print(f"Controller {player_letter} is not connected!")
        return

    joystick_index = CONTROLLER_MAP[player_letter]  # runtime index

    # Prevent duplicate robot pairing
    for thread in pairings.values():
        if thread.bot_id == robot_id:
            print(f"Robot {robot_id} is already paired to another controller.")
            return

    robot_info = get_robot_info(robot_id)
    if not robot_info:
        print(f"Robot ID '{robot_id}' not found in database.")
        return

    joystick = pygame.joystick.Joystick(joystick_index)
    joystick.init()
    ip, port, inverts, bot_info = robot_info
    thread = RobotControllerThread(player_letter, joystick, ip, port, inverts, bot_info, robot_id)
    pairings[player_letter] = thread
    thread.start()
    print(f"Paired controller {player_letter} to robot {robot_id} ({ip}:{port})")




def break_pair(player_id):
    thread = pairings.pop(player_id, None)
    if thread:
        thread.stop()
        print(f"Unpaired {player_id}")
    else:
        print(f"{player_id} not paired.")

def start_game():
    #sound_effects.chase_seq()
    light_clock_handler.start_match()
    #sound_effects.countdown_3sec()
    #time.sleep(3)
    global killswitch_value
    with lock:
        killswitch_value = 2
    print("Game started (killswitch=2)")

def stop_game():
    light_clock_handler.ko_match()
    global killswitch_value
    with lock:
        killswitch_value = 0
    print("Game stopped (killswitch=0)")

def pause_game():
    light_clock_handler.pause_match()
    global killswitch_value
    with lock:
        killswitch_value = 0
    print("game paused (killswitch=0)")

def resume_game():
    light_clock_handler.resume_match()
    global killswitch_value
    print("Game will resume after 3 2 1 countdown")
    time.sleep(3)
    with lock:
        killswitch_value = 2
    print("Game resumed (killswitch=2)")
    

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


def cleanup_and_exit():
    print("Cleaning up before exit...")
    try:
        reset()
        pygame.quit()
        light_clock_handler.stop()
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        try:
            # Safely destroy the Tkinter window if it exists
            if tk._default_root is not None:
                tk._default_root.destroy()
        except Exception:
            pass
        # Forcefully terminate the process
        os._exit(0)


class ArenaGUI:
    def __init__(self, root, start_fn, stop_fn, pause_fn, resume_fn, pair_fn, break_fn, reset_fn, controller_cal_fn):
        self.start_fn = start_fn
        self.stop_fn = stop_fn
        self.pause_fn = pause_fn
        self.resume_fn = resume_fn
        self.pair_fn = pair_fn
        self.break_fn = break_fn
        self.reset_fn = reset_fn
        self.controller_cal_fn = controller_cal_fn

        self.root = root
        self.root.title("Robot Arena Control")
        # Get screen dimensions
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # Maximize window to fill screen (still shows title bar)
        root.geometry(f"{screen_width}x{screen_height}+0+0")

        # Grid config (4 rows, 2 cols)
        self.root.grid_rowconfigure((0, 1, 2, 3), weight=1)
        self.root.grid_columnconfigure((0, 1), weight=1)

        # exit protocol
        self.root.protocol("WM_DELETE_WINDOW", cleanup_and_exit)


        # Top buttons
        self.start_btn = tk.Button(root, text="START", font=("Arial", 36),
                                    bg="green", fg="white", command=self.on_start)
        self.start_btn.grid(row=0, column=0, sticky="nsew")

        # --- New calibration button ---
        self.calibrate_btn = tk.Button(root, text="CALIBRATE\nCONTROLLERS", font=("Arial", 20, "bold"),
                                    bg="blue", fg="black", command=self.calibrate_controllers, wraplength=400)
        self.calibrate_btn.grid(row=0, column=1, sticky="nsew")

        # --- Existing STOP button (hidden by default) ---
        self.stop_btn = tk.Button(root, text="STOP", font=("Arial", 36),
                                    bg="red", fg="white", command=self.on_stop)
        self.stop_btn.grid(row=0, column=1, sticky="nsew")
        self.stop_btn.grid_remove()  # Hide STOP until a match starts

        self.pause_btn = tk.Button(root, text="PAUSE", font=("Arial", 36),
                                    bg="orange", fg="black", command=self.toggle_pause_resume)
        self.pause_btn.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # Bottom row: Pair / Break / Reset
        self.pair_btn = tk.Button(root, text="PAIR ROBOT", font=("Arial", 24),
                                    bg="purple", fg="white", command=self.pair_robot_popup)
        self.pair_btn.grid(row=3, column=0, sticky="nsew")

        self.break_btn = tk.Button(root, text="BREAK PAIR", font=("Arial", 24),
                                 bg="brown", fg="white", command=self.break_pair_popup)
        self.break_btn.grid(row=3, column=1, sticky="nsew")

        self.reset_btn = tk.Button(root, text="RESET ALL", font=("Arial", 24),
                                   bg="black", fg="white", command=self.reset_all_popup)
        self.reset_btn.grid(row=3, column=2, sticky="nsew")

        # Expand grid to 3 columns for bottom row
        self.root.grid_columnconfigure(2, weight=1)

    def on_stop(self, event=None):
        self.show_calibrate_button()
        self.stop_fn()
    
    def on_start(self, event=None):
        self.show_stop_button()
        self.start_fn()
    
    def calibrate_controllers(self, event=None):
        messagebox.showinfo(
            "Controller Calibration",
            "Press any [A B X Y] button on each controller from A to H. This will set the order.\n\n"
            "Make sure all controllers are plugged in before continuing."
        )

        try:
            self.controller_cal_fn()
            messagebox.showinfo("Calibration Complete", "Controllers calibrated successfully.")
        except Exception as e:
            messagebox.showerror("Calibration Failed", f"An error occurred:\n{e}")
    
    def reset_all_popup(self, event=None):
        """Popup confirmation when reset is triggered."""
        self.reset_fn()  # Call your actual reset function
        messagebox.showinfo("Reset All", "All pairings cleared.")
    
    def break_pair_popup(self, event=None):
        if not pairings:
            messagebox.showinfo("No Active Connections", "There are no active connections to break.")
            return

        popup = tk.Toplevel()
        popup.title("Break Pair")

        tk.Label(popup, text="Select Pairing to Break:").grid(row=0, column=0, padx=10, pady=10)

        pairing_display = []
        controllers = []

        # ✅ get full robot list ONCE (same info used in pair_robot_popup)
        robots = db_handler.get_robot_list()

        # ✅ build a dictionary: robot_id → "Type - Color"
        robot_lookup = {}
        for r in robots:
            # r is likely a dict with 'robot_id', 'robot_type', 'color'
            robot_lookup[r['robot_id']] = f"{r['robot_type']} - {r['color']}"

        # ✅ build the dropdown entries
        for thread in pairings.values():
            player_id = thread.player_id
            bot_id = thread.bot_id

            controller_label = REVERSE_MAP[player_id]   # e.g. A, B, C...
            robot_label = robot_lookup.get(bot_id, f"Robot {bot_id}")  # fallback just in case

            pairing_display.append(f"Controller {controller_label} → {robot_label}")
            controllers.append(player_id)

       
        pair_var = tk.StringVar(popup)
        pair_var.set(pairing_display[0])
        pair_menu = tk.OptionMenu(popup, pair_var, *pairing_display)
        pair_menu.grid(row=0, column=1, padx=10, pady=10)

        def on_break():
            idx = pairing_display.index(pair_var.get())
            controller_num = controllers[idx]
            self.break_fn(controller_num)
            popup.destroy()

        tk.Button(popup, text="Break", command=on_break,
                bg="red", fg="white").grid(row=1, column=0, columnspan=2, pady=15)
        popup.grab_set()



    
    def toggle_pause_resume(self):
        if self.pause_btn["text"] == "PAUSE":
            self.pause_fn()
            self.pause_btn.config(text="RESUME", bg="blue", fg="white")
        else:
            self.resume_fn()
            self.pause_btn.config(text="PAUSE", bg="orange", fg="black")
    
    def show_calibrate_button(self):
        self.stop_btn.grid_remove()
        self.calibrate_btn.grid()

    def show_stop_button(self):
        self.calibrate_btn.grid_remove()
        self.stop_btn.grid()

    def pair_robot_popup(self, event=None):
        # Gather already connected robots and controllers
        already_connected_bots = [thread.bot_id for thread in pairings.values()]
        already_connected_controllers = [thread.player_id for thread in pairings.values()]
        available_controllers = [
            letter for letter, num in CONTROLLER_MAP.items()
            if num not in already_connected_controllers
        ]

        # Fetch robots from DB
        robots = db_handler.get_robot_list(already_connected=already_connected_bots)
        if not robots:
            messagebox.showinfo("No Robots", "No available robots to pair.")
            return
        if len(available_controllers) <= 0:
            messagebox.showinfo("No Controllers", "No available controllers to pair. Break connections first")
            return

        # Robot display
        robot_display = [f"{r['robot_type']} - {r['color']}" for r in robots]

        popup = tk.Toplevel()
        popup.title("Pair Robot")

        

        tk.Label(popup, text="Select Controller:").grid(row=0, column=0, padx=10, pady=10)
        controller_var = tk.StringVar(popup)
        controller_var.set(available_controllers[0])
        controller_menu = tk.OptionMenu(popup, controller_var, *available_controllers)
        controller_menu.grid(row=0, column=1, padx=10, pady=10)

        tk.Label(popup, text="Select Robot:").grid(row=1, column=0, padx=10, pady=10)
        robot_var = tk.StringVar(popup)
        robot_var.set(robot_display[0])
        robot_menu = tk.OptionMenu(popup, robot_var, *robot_display)
        robot_menu.grid(row=1, column=1, padx=10, pady=10)

        def on_pair():
            controller = controller_var.get()
            selected_index = robot_display.index(robot_var.get())
            selected_robot_id = robots[selected_index]['robot_id']

            for thread in pairings.values():
                if thread.bot_id == selected_robot_id:
                    messagebox.showerror("Error", "That robot is already paired!")
                    return

            pair(CONTROLLER_MAP[controller], selected_robot_id)
            popup.destroy()

        tk.Button(popup, text="Pair", command=on_pair,
                  bg="green", fg="white").grid(row=2, column=0, columnspan=2, pady=15)
        popup.grab_set()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda sig, frame: cleanup_and_exit())
    parser = argparse.ArgumentParser(description="ROBOT CITY Game Manager")
    parser.add_argument("-gui", action="store_true", help="Run in GUI-only mode (no terminal)")
    args = parser.parse_args()

    load_controller_map()

    def launch_terminal_loop():
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
                elif cmd == "pause":
                    pause_game()
                elif cmd == "resume":
                    resume_game()
                elif cmd == "controller cal":
                    calibrate_controller_order()
                elif cmd == "exit":
                    reset()
                    cleanup_and_exit()
                elif cmd == "help":
                    print("Commands:")
                    print("\tGameplay: | pair playerX robot_id | break playerX | start | stop | reset | show pairings | exit |")
                    print("\tIndividual Robot Settings: | show robots | add robot | edit robot | remove robot |")
                    print("\tRobot Type Settings: | show types | edit type |")
                    print("\tCalibration: | Controller Cal |")
                else:
                    print("Unknown command.")
        except KeyboardInterrupt:
            cleanup_and_exit()

    # --- Tkinter GUI setup ---
    root = tk.Tk()
    gui = ArenaGUI(
        root,
        start_fn=start_game,
        stop_fn=stop_game,
        pause_fn=pause_game,
        resume_fn=resume_game,
        pair_fn=pair,
        break_fn=break_pair,
        reset_fn=reset,
        controller_cal_fn=calibrate_controller_order
    )

    if args.gui:
        # GUI-only: suppress terminal output
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    else:
        # Terminal + GUI: start terminal loop in background thread
        threading.Thread(target=launch_terminal_loop, daemon=True).start()

    # Tkinter must always run in main thread
    root.mainloop()

