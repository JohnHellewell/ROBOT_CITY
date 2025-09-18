import socket
import struct
import time
import threading

from lighting_control import LightingController

#Lights
lights = LightingController()

# UDP config
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip = '192.168.8.7'  # your ESP32 IP
port = 50001

# Constants
MATCH_DURATION_MS = 180000  # 3 minutes
ANIMATION_BUFFER_MS = 8000  # delay before match starts (5s chase seq, 3s red flash)

# Match state
match_start_time = None
match_end_time = None
remaining_ms = MATCH_DURATION_MS
current_state = "waiting"

def send_command(command, time_ms):
    data = struct.pack('!HH', command, time_ms // 100)  # time in deciseconds
    sock.sendto(data, (ip, port))
    print(f"Sent command {command} with time {time_ms} ms")

def get_elapsed_time():
    if match_start_time is None:
        return 0
    elapsed = int(time.time() * 1000) - match_start_time - ANIMATION_BUFFER_MS
    return max(0, elapsed)

def get_remaining_time():
    if current_state == "counting":
        now = int(time.time() * 1000)
        return max(0, match_end_time - now)
    else:
        return remaining_ms

def start_match():
    global match_start_time, match_end_time, remaining_ms, current_state
    if current_state != "waiting":
        print("Match already started or in progress.")
        return
    remaining_ms = MATCH_DURATION_MS
    match_start_time = int(time.time() * 1000)
    match_end_time = match_start_time + remaining_ms + ANIMATION_BUFFER_MS
    current_state = "counting"


    lights.battle_start() #lights

    send_command(1, remaining_ms)
    


def pause_match():
    global remaining_ms, current_state, match_end_time
    remaining_ms = get_remaining_time()
    current_state = "paused"
    lights.pause() # lights
    send_command(2, remaining_ms)

def resume_match():
    global match_start_time, match_end_time, current_state
    match_start_time = int(time.time() * 1000)
    match_end_time = match_start_time + remaining_ms + ANIMATION_BUFFER_MS
    current_state = "counting"
    lights.battle_start(chase = False)
    send_command(3, remaining_ms)

def add_time(new_time_ms):
    global remaining_ms, match_start_time, match_end_time
    remaining_ms = new_time_ms
    match_start_time = int(time.time() * 1000)
    match_end_time = match_start_time + remaining_ms + ANIMATION_BUFFER_MS
    send_command(4, remaining_ms)

def ko_match():
    global remaining_ms, current_state, match_start_time
    remaining_ms = get_remaining_time()
    current_state = "waiting"
    match_start_time = None
    lights.wait()
    send_command(5, remaining_ms)
    print("Match ended with KO. Returning to waiting state.")

def winner(winner):
    global current_state, match_start_time, remaining_ms
    current_state = "waiting"
    lights.celebrate(winner)
    send_command(5, remaining_ms)
    match_start_time = None
    print(f"{winner} team won!")

def parse_time_input(time_str):
    try:
        m, s = map(int, time_str.split(":"))
        return (m * 60 + s) * 1000
    except ValueError:
        print("Invalid time format. Use mm:ss")
        return None

def monitor_timer():
    global current_state, remaining_ms, match_start_time, match_end_time
    while True:
        if current_state == "counting":
            if get_remaining_time() <= 0:
                print("Match timer ended.")
                current_state = "waiting"
                remaining_ms = MATCH_DURATION_MS
                match_start_time = None
                match_end_time = None
                lights.off() #lights
        time.sleep(0.1)



def main():
    global current_state, match_start_time

    threading.Thread(target=monitor_timer, daemon=True).start()

    print("Welcome to the Combat Robot Timer Control")
    print("Commands: | start | pause | resume | add | ko | winner | exit |")

    while True:
        # Check if match time has expired
        if current_state == "counting" and get_remaining_time() <= 0:
            print("Match timer ended.")
            current_state = "waiting"
            remaining_ms = MATCH_DURATION_MS
            match_start_time = None
            match_end_time = None

        cmd = input(f"[{current_state}] Enter command: ").strip().lower()

        if cmd == "start":
            if current_state == "waiting":
                start_match()
            else:
                print("Match already started or in progress.")

        elif cmd == "pause":
            if current_state == "counting":
                pause_match()
            else:
                print("Can only pause while counting.")

        elif cmd == "resume":
            if current_state == "paused":
                resume_match()
            else:
                print("Can only resume from paused state.")

        elif cmd == "add":
            if current_state == "paused":
                time_input = input("Enter new time (mm:ss): ").strip()
                new_time = parse_time_input(time_input)
                if new_time is not None:
                    add_time(new_time)
            else:
                print("Can only add time while paused.")

        elif cmd == "ko":
            if current_state in ("counting", "paused"):
                ko_match()
            else:
                print("KO command can only be used during a match.")
        
        elif cmd == "winner":
            winner_input = input("Ender team that won: YELLOW, BLUE, ORANGE, GREEN: ").strip().upper()
            while winner_input not in ("YELLOW", "ORANGE", "BLUE", "GREEN"):
                winner_input = input("Ender team that won: YELLOW, BLUE, ORANGE, GREEN: ").strip().upper()
            winner(winner_input)
            

        elif cmd == "exit":
            print("Exiting timer control.")
            lights.off()
            break

        else:
            print("Unknown command. Valid commands: start, pause, resume, add, ko, exit.")

if __name__ == "__main__":
    # Start OLA loop in main thread
    import threading
    import sys

    # Start monitor and wait loops
    threading.Thread(target=monitor_timer, daemon=True).start()
    lights.wait()  # starts the background _wait_loop thread

    # Start main control loop in main thread
    # But OLA needs its event loop running:
    from ola.ClientWrapper import ClientWrapper
    lights.wrapper.Run()  # BLOCKS main thread, safe