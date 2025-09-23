import pygame
import socket
import struct
import threading
import time
import platform
import math
from dotenv import load_dotenv
import os
import db_handler
from LightClockHandler import LightClockHandler
import tkinter as tk
from tkinter import simpledialog, messagebox


pygame.init()
pygame.joystick.init()

def timer_stop_game():
    global killswitch_value
    with lock:
        killswitch_value = 0
    print("Game stopped (killswitch=0)")

light_clock_handler = LightClockHandler(on_match_end=timer_stop_game)



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
    AXIS_RIGHT_Y = 1
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
    return db_handler.get_robot_info(robot_id)
    
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
    
    # Check if robot is already paired
    for thread in pairings.values():
        if thread.bot_info[4] == robot_id:  # assuming bot_info[4] stores robot_id
            print(f"Robot {robot_id} is already paired to another controller.")
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
    light_clock_handler.start_match()
    time.sleep(3)
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




class ArenaGUI:
    def __init__(self, root, start_fn, stop_fn, pause_fn, resume_fn, pair_fn):
        self.start_fn = start_fn
        self.stop_fn = stop_fn
        self.pause_fn = pause_fn
        self.resume_fn = resume_fn
        self.pair_fn = pair_fn

        self.root = root
        self.root.title("Robot Arena Control")
        self.root.geometry("1024x600")
        self.root.attributes("-fullscreen", True)
        self.root.grid_rowconfigure((0,1,2,3), weight=1)
        self.root.grid_columnconfigure((0,1), weight=1)

        # Example existing buttons...
        self.start_btn = tk.Button(root, text="START", font=("Arial", 36), bg="green", fg="white", command=self.start_fn)
        self.start_btn.grid(row=0, column=0, sticky="nsew")
        self.stop_btn = tk.Button(root, text="STOP", font=("Arial", 36), bg="red", fg="white", command=self.stop_fn)
        self.stop_btn.grid(row=0, column=1, sticky="nsew")
        self.pause_btn = tk.Button(root, text="PAUSE", font=("Arial", 36), bg="orange", fg="black", command=self.toggle_pause_resume)
        self.pause_btn.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # Pair Robot button
        self.pair_btn = tk.Button(root, text="PAIR ROBOT", font=("Arial", 24), bg="purple", fg="white", command=self.pair_robot_popup)
        self.pair_btn.grid(row=2, column=0, columnspan=2, sticky="nsew")

    def toggle_pause_resume(self):
        if self.pause_btn["text"] == "PAUSE":
            self.pause_fn()
            self.pause_btn.config(text="RESUME", bg="blue", fg="white")
        else:
            self.resume_fn()
            self.pause_btn.config(text="PAUSE", bg="orange", fg="black")

    def pair_robot_popup(event=None):
        # Gather already connected robots
        already_connected = [thread.bot_info[4] for thread in pairings.values()]  # assuming bot_info[4] = robot_id

        # Fetch robots from database, excluding already connected ones
        robots = db_handler.db.get_robot_list(already_connected=already_connected)
        if not robots:
            messagebox.showinfo("No Robots", "No available robots to pair.")
            return

        # Map robots for display
        robot_display = [f"{r['color']} - {r['robot_type']}" for r in robots]

        popup = tk.Toplevel()
        popup.title("Pair Robot")

        tk.Label(popup, text="Select Controller:").grid(row=0, column=0, padx=10, pady=10)
        controller_var = tk.StringVar(popup)
        controller_var.set("A")  # default
        controller_menu = tk.OptionMenu(popup, controller_var, *list("ABCDEFGH"))
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

            # Quick safety: ensure robot isn't already paired
            for thread in pairings.values():
                if thread.bot_info[4] == selected_robot_id:
                    messagebox.showerror("Error", "That robot is already paired!")
                    return

            pair(controller, selected_robot_id)
            popup.destroy()

        tk.Button(popup, text="Pair", command=on_pair, bg="green", fg="white").grid(row=2, column=0, columnspan=2, pady=15)
        popup.grab_set()  # focus on this popup




if __name__ == "__main__":
    print("ROBOT CITY Game Manager")
    print("Type 'help' for a list of commands.")

    # Launch GUI in its own thread
    def launch_gui():
        root = tk.Tk()
        gui = ArenaGUI(
            root,
            start_fn=start_game,
            stop_fn=stop_game,
            pause_fn=pause_game,
            resume_fn=resume_game,
            pair_fn=pair
        )
        root.mainloop()

    gui_thread = threading.Thread(target=launch_gui, daemon=True)
    gui_thread.start()

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

