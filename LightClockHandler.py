# LightClockHandler.py
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

        # parent function call
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

        # Lock to protect state
        self._state_lock = threading.Lock()

        # Start monitoring thread
        threading.Thread(target=self._monitor_timer, daemon=True).start()

        # Start lights in waiting mode in a separate thread (non-blocking)
        threading.Thread(target=self.lights.wait, daemon=True).start()

    # --------------------------
    # Helper methods
    # --------------------------
    def _send_command(self, command, time_ms):
        try:
            data = struct.pack("!HH", command, max(0, int(time_ms // 100)))  # time in deciseconds
            self.sock.sendto(data, (self.ip, self.port))
            print(f"[Lights UDP] Sent command {command} with time {time_ms} ms")
        except Exception as e:
            print(f"[Lights UDP] Error sending command: {e}")

    def _get_elapsed_time(self):
        with self._state_lock:
            start = self.match_start_time
        if start is None:
            return 0
        elapsed = int(time.time() * 1000) - start - self.ANIMATION_BUFFER_MS
        return max(0, elapsed)

    def get_remaining_time(self):
        with self._state_lock:
            state = self.current_state
            end = self.match_end_time
            remaining = self.remaining_ms
        if state == "counting" and end is not None:
            now = int(time.time() * 1000)
            return max(0, end - now)
        else:
            return remaining

    # --------------------------
    # Match controls
    # --------------------------
    def start_match(self):
        with self._state_lock:
            if self.current_state != "waiting":
                print("[LightClock] start_match prevented: not in 'waiting' state.")
                return
            # initialize times
            self.remaining_ms = self.MATCH_DURATION_MS
            self.match_start_time = int(time.time() * 1000)
            self.match_end_time = self.match_start_time + self.remaining_ms + self.ANIMATION_BUFFER_MS
            self.current_state = "counting"

        print("[LightClock] Match starting.")
        # non-blocking lights/commands
        threading.Thread(target=self.lights.battle_start, daemon=True).start()
        self._send_command(1, self.remaining_ms)

    def pause_match(self):
        with self._state_lock:
            if self.current_state != "counting":
                print("[LightClock] Can only pause while counting.")
                return
            self.remaining_ms = self.get_remaining_time()
            self.current_state = "paused"

        print("[LightClock] Match paused; remaining_ms =", self.remaining_ms)
        threading.Thread(target=self.lights.pause, daemon=True).start()
        self._send_command(2, self.remaining_ms + 5000)

    def resume_match(self):
        with self._state_lock:
            if self.current_state != "paused":
                print("[LightClock] Can only resume from paused state.")
                return
            self.match_start_time = int(time.time() * 1000)
            self.match_end_time = self.match_start_time + self.remaining_ms + self.ANIMATION_BUFFER_MS
            self.current_state = "counting"

        print("[LightClock] Resuming match.")
        threading.Thread(target=self.lights.battle_start, kwargs={"chase": False}, daemon=True).start()
        self._send_command(3, self.remaining_ms + 5000)

    def add_time(self, new_time_ms):
        with self._state_lock:
            self.remaining_ms = new_time_ms
            self.match_start_time = int(time.time() * 1000)
            self.match_end_time = self.match_start_time + self.remaining_ms + self.ANIMATION_BUFFER_MS

        print("[LightClock] Time added. New remaining_ms =", self.remaining_ms)
        self._send_command(4, self.remaining_ms)

    def ko_match(self):
        # End match and return to waiting. Do not block the caller with long light animations.
        with self._state_lock:
            # capture current remaining time
            self.remaining_ms = self.get_remaining_time()
            self.current_state = "waiting"
            self.match_start_time = None
            self.match_end_time = None

        print("[LightClock] KO match -> switching to waiting. remaining_ms =", self.remaining_ms)
        # send command (non-blocking)
        self._send_command(5, self.remaining_ms + 5000)
        # run the possibly-blocking light animation in its own thread
        threading.Thread(target=self._run_battle_end_and_wait, args=(5,), daemon=True).start()

    def _run_battle_end_and_wait(self, param):
        try:
            self.lights.battle_end(param)
        except Exception as e:
            print(f"[LightClock] lights.battle_end error: {e}")
        # After animation, ensure lights return to waiting (non-blocking)
        try:
            # if there's a dedicated wait loop method that blocks, call it here
            # but do it in this thread so monitor/main thread aren't blocked.
            if hasattr(self.lights, "_wait_loop"):
                try:
                    self.lights._wait_loop()
                except Exception:
                    # If _wait_loop blocks forever, prefer using lights.wait() if available
                    if hasattr(self.lights, "wait"):
                        self.lights.wait()
            elif hasattr(self.lights, "wait"):
                self.lights.wait()
        except Exception as e:
            print(f"[LightClock] Error returning lights to waiting: {e}")

    def winner(self, winner):
        with self._state_lock:
            self.current_state = "waiting"
            self.match_start_time = None
            self.match_end_time = None
        print(f"[LightClock] Winner: {winner}")
        threading.Thread(target=self.lights.celebrate, args=(winner,), daemon=True).start()
        self._send_command(5, self.remaining_ms)

    # --------------------------
    # Background monitor
    # --------------------------
    def _monitor_timer(self):
        while not self._stop_event.is_set():
            should_call_on_match_end = False
            with self._state_lock:
                state = self.current_state
                remaining = None
                if state == "counting":
                    now = int(time.time() * 1000)
                    remaining = self.match_end_time - now if self.match_end_time is not None else None
                    if remaining is not None and remaining <= 0:
                        # transition to waiting and reset
                        print("[LightClock monitor] Match timer reached zero.")
                        self.current_state = "waiting"
                        self.remaining_ms = self.MATCH_DURATION_MS
                        self.match_start_time = None
                        self.match_end_time = None
                        should_call_on_match_end = True

            if should_call_on_match_end:
                # Call callback in separate thread so monitor thread stays free
                if callable(self.on_match_end):
                    print("[LightClock monitor] Calling on_match_end callback.")
                    threading.Thread(target=self._safe_call_on_match_end, daemon=True).start()
                # return lights to waiting mode (run animation in its own thread)
                threading.Thread(target=self._run_battle_end_and_wait, args=(0,), daemon=True).start()

            time.sleep(0.1)

    def _safe_call_on_match_end(self):
        try:
            self.on_match_end()
        except Exception as e:
            print(f"[LightClock] on_match_end error: {e}")

    def stop(self):
        """Clean up handler."""
        print("[LightClock] Stopping handler.")
        self._stop_event.set()
        try:
            self.lights.off()
        except Exception as e:
            print(f"[LightClock] lights.off error: {e}")
        try:
            self.sock.close()
        except Exception:
            pass
