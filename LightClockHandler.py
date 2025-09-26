import socket
import struct
import time
import threading

from lighting_control import LightingController


class LightClockHandler:
    def __init__(self, ip="192.168.8.7", port=50001, match_duration_ms=180000, animation_buffer_ms=3000, on_match_end=None):
        # Lights
        self.lights = LightingController()

        # UDP config
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ip = ip
        self.port = port

        #parent function call
        self.on_match_end = on_match_end

        # Constants
        self.MATCH_DURATION_MS = match_duration_ms
        self.ANIMATION_BUFFER_MS = animation_buffer_ms

        # Match state
        self.match_start_time = None
        self.match_end_time = None
        self.remaining_ms = self.MATCH_DURATION_MS
        self.current_state = "waiting"

        # Stop flag for monitor thread
        self._stop_event = threading.Event()

        # Start monitoring thread
        threading.Thread(target=self._monitor_timer, daemon=True).start()

        # Start lights in waiting mode in a separate thread (non-blocking)
        threading.Thread(target=self.lights.wait, daemon=True).start()

    # --------------------------
    # Helper methods
    # --------------------------
    def _send_command(self, command, time_ms):
        data = struct.pack("!HH", command, time_ms // 100)  # time in deciseconds
        self.sock.sendto(data, (self.ip, self.port))
        print(f"Sent command {command} with time {time_ms} ms")

    def _get_elapsed_time(self):
        if self.match_start_time is None:
            return 0
        elapsed = int(time.time() * 1000) - self.match_start_time - self.ANIMATION_BUFFER_MS
        return max(0, elapsed)

    def get_remaining_time(self):
        if self.current_state == "counting":
            now = int(time.time() * 1000)
            return max(0, self.match_end_time - now)
        else:
            return self.remaining_ms

    # --------------------------
    # Match controls
    # --------------------------
    def start_match(self):
        if self.current_state != "waiting":
            print("Match already started or in progress.")
            return
        self.remaining_ms = self.MATCH_DURATION_MS
        self.match_start_time = int(time.time() * 1000)
        self.match_end_time = self.match_start_time + self.remaining_ms + self.ANIMATION_BUFFER_MS
        self.current_state = "counting"

        self.lights.battle_start()
        self._send_command(1, self.remaining_ms)

        

    def pause_match(self):
        if self.current_state != "counting":
            print("Can only pause while counting.")
            return
        self.remaining_ms = self.get_remaining_time()
        self.current_state = "paused"
        self.lights.pause()
        self._send_command(2, self.remaining_ms + 5000)

    def resume_match(self):
        if self.current_state != "paused":
            print("Can only resume from paused state.")
            return
        self.match_start_time = int(time.time() * 1000)
        self.match_end_time = self.match_start_time + self.remaining_ms + self.ANIMATION_BUFFER_MS
        self.current_state = "counting"

        self.lights.battle_start(chase=False)
        self._send_command(3, self.remaining_ms + 5000)

    def add_time(self, new_time_ms):
        self.remaining_ms = new_time_ms
        self.match_start_time = int(time.time() * 1000)
        self.match_end_time = self.match_start_time + self.remaining_ms + self.ANIMATION_BUFFER_MS
        self._send_command(4, self.remaining_ms)

    def ko_match(self):
        self.remaining_ms = self.get_remaining_time()
        self.current_state = "waiting"
        self.match_start_time = None
        self.match_end_time = None
        self._send_command(5, self.remaining_ms + 5000)
        print("Match ended with KO. Returning to waiting state.")
        self.lights.battle_end(5)

    def winner(self, winner):
        self.current_state = "waiting"
        self.lights.celebrate(winner)
        self._send_command(5, self.remaining_ms)
        self.match_start_time = None
        self.match_end_time = None
        print(f"{winner} team won!")

    # --------------------------
    # Background monitor
    # --------------------------
    def _monitor_timer(self):
        while not self._stop_event.is_set():
            if self.current_state == "counting" and self.get_remaining_time() <= 0:
                print("Match timer ended.")
                self.current_state = "waiting"
                self.remaining_ms = self.MATCH_DURATION_MS
                self.match_start_time = None
                self.match_end_time = None
                self.on_match_end() #call parent function to end the match and close the robots
                self.lights._wait_loop()
            time.sleep(0.1)

    def stop(self):
        """Clean up handler."""
        self._stop_event.set()
        self.lights.off()
        self.sock.close()
