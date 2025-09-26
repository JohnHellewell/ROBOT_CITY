# lighting_control.py — improved LightingController
import threading
import time
from ola.ClientWrapper import ClientWrapper
import math

UNIVERSE = 1

class LightingController:
    def __init__(self):
        self.wrapper = ClientWrapper()
        self.client = self.wrapper.Client()
        self.data = [0] * 512

        # Event to control wait loop / sequence stop
        self.waiting = threading.Event()
        self.wait_thread = None

        # Lock + throttle to serialize DMX sends
        self._send_lock = threading.Lock()
        self._last_send_time = 0.0
        self.min_send_interval = 0.02  # seconds (50 Hz); raise to 0.03-0.05 if needed

        # push a clean frame immediately
        self.send_dmx(replicate=False)

    # ---------- DMX send with serialization + throttle ----------
    def send_dmx(self, data=None, replicate=True):
        if data is None:
            data = self.data

        if replicate:
            ch1 = data[:8]
            new_data = ch1 * 4
            new_data.extend([0] * (512 - len(new_data)))
            data = new_data
            self.data = new_data

        def dmx_sent(status):
            pass

        with self._send_lock:
            now = time.time()
            since = now - self._last_send_time
            if since < self.min_send_interval:
                time.sleep(self.min_send_interval - since)
            try:
                self.client.SendDmx(UNIVERSE, bytearray(data), dmx_sent)
            except Exception as e:
                print("[LightingController] SendDmx exception:", e)
            self._last_send_time = time.time()

    # ---------- Safe stop / join ----------
    def stop_wait(self):
        """Signal current sequence/thread to stop and join it cleanly (short timeout)."""
        self.waiting.clear()
        if self.wait_thread and self.wait_thread.is_alive():
            self.wait_thread.join(timeout=1.0)
        self.wait_thread = None

    # ---------- Wait loop (background thread target) ----------
    def _wait_loop(self, wait=5):
        delay = 0.02
        self.waiting.set()

        # small pre-wait
        time.sleep(wait)

        # simple color sweep and loop until signaled
        for r in range(256):
            if not self.waiting.is_set():
                return
            self.rgb(r, 0, 0)
            time.sleep(delay)

        while self.waiting.is_set():
            for g in range(256):
                if not self.waiting.is_set(): return
                self.rgb(255 - g, g, 0)
                time.sleep(delay)
            for b in range(256):
                if not self.waiting.is_set(): return
                self.rgb(0, 255 - b, b)
                time.sleep(delay)
            for u in range(256):
                if not self.waiting.is_set(): return
                self.rgb(0, 0, 255 - u, uv=u // 2)
                time.sleep(delay)
            for r in range(256):
                if not self.waiting.is_set(): return
                self.rgb(r, 0, 0, uv=(255 - r) // 2)
                time.sleep(delay)

    def wait(self, wait_seconds=5):
        """Start the wait loop in a new background thread (replaces any existing)."""
        self.stop_wait()
        t = threading.Thread(target=self._wait_loop, args=(wait_seconds,), daemon=True)
        t.start()
        self.wait_thread = t

    # ---------- Chase sequence (background) ----------
    def _chase_sequence_blocking(self, r, g, b, white, amber, delay, period, duration):
        self.waiting.set()
        start_time = time.time()
        end_time = start_time + max(0, duration - 0.05)

        # small initial frame
        self.data = [0] * 512
        self.send_dmx(replicate=False)
        time.sleep(0.05)

        while self.waiting.is_set():
            now = time.time()
            t = now - start_time
            remaining = end_time - now
            if remaining <= 0:
                break

            scale = 1.0
            if t < 0.5:
                scale = t / 0.5
            elif remaining < 0.5:
                scale = remaining / 0.5

            self.data = [0] * 512
            for light in range(4):
                phase = (2 * math.pi * t / period) + (light * math.pi / 2)
                sine_val = (math.sin(phase) + 1) / 2
                brightness = 0 if sine_val < 0.5 else (sine_val - 0.5) * 2
                offset = light * 8
                self.data[offset + 0] = r
                self.data[offset + 1] = g
                self.data[offset + 2] = b
                self.data[offset + 3] = white
                self.data[offset + 4] = amber
                self.data[offset + 6] = 255
                self.data[offset + 7] = int(255 * scale * brightness)

            self.send_dmx(replicate=False)
            time.sleep(delay)

        # clear when done
        self.data = [0] * 512
        self.send_dmx(replicate=False)

    def chase_sequence(self, r=255, g=255, b=255, white=255, amber=0, delay=0.02, period=0.45, duration=5.0):
        self.stop_wait()
        t = threading.Thread(target=self._chase_sequence_blocking,
                             args=(r, g, b, white, amber, delay, period, duration),
                             daemon=True)
        t.start()
        self.wait_thread = t

    # ---------- Basic immediate controls ----------
    def rgb(self, r, g, b, white=0, amber=0, uv=0):
        # safe to call from any thread
        self.data[0] = r
        self.data[1] = g
        self.data[2] = b
        self.data[3] = white
        self.data[4] = amber
        self.data[5] = uv
        self.send_dmx()

    def pause(self):
        self.stop_wait()
        self.data = [0] * 512
        self.data[2] = 255  # Blue
        self.data[6] = 255
        self.data[7] = 255
        self.send_dmx()

    def off(self):
        self.stop_wait()
        self.data = [0] * 512
        self.send_dmx()

    # ---------- Fade out (non-blocking) ----------
    def _fade_out_blocking(self, duration=1.0, kill=True):
        if kill:
            self.stop_wait()
        delay = 0.01
        wait = 0.0

        while wait < duration:
            for i in range(4):
                if wait == 0.0:
                    self.data[i * 8 + 7] = 255
                else:
                    self.data[i * 8 + 7] = int(255 - (255 * (wait / duration)))
            self.send_dmx(replicate=False)
            time.sleep(delay)
            wait += delay

        # reset channels 6 & 7
        self.data = [0] * 512
        for i in range(4):
            self.data[i * 8 + 6] = 255
            self.data[i * 8 + 7] = 255
        self.send_dmx(replicate=False)

    def fade_out(self, duration=1.0, kill=True):
        self.stop_wait()
        t = threading.Thread(target=self._fade_out_blocking, args=(duration, kill), daemon=True)
        t.start()
        self.wait_thread = t

    # ---------- Celebrate (non-blocking) ----------
    def celebrate(self, color):
        def _seq():
            rgb = [0, 0, 0]
            amb = 0
            if color == "BLUE":
                rgb = [0, 0, 255]
            elif color == "ORANGE":
                rgb = [255, 30, 0]; amb = 255
            elif color == "YELLOW":
                rgb = [255, 255, 0]; amb = 255
            elif color == "GREEN":
                rgb = [0, 255, 0]

            self.stop_wait()
            self._fade_out_blocking()
            time.sleep(1)

            for _ in range(6):
                self.rgb(r=rgb[0], g=rgb[1], b=rgb[2], amber=amb)
                time.sleep(0.15)
                self.rgb(0, 0, 0, amber=0)
                time.sleep(0.15)
            self.rgb(255, 255, 255, amber=amb)

            # start chase in background
            self.chase_sequence(r=rgb[0], g=rgb[1], b=rgb[2], white=0, amber=amb)

        t = threading.Thread(target=_seq, daemon=True)
        t.start()
        self.wait_thread = t
    
    def battle_start(self, chase=True):
        self.stop_wait()

        if chase:
            self.fade_out(duration=1.0)
            self.chase_sequence(r=255, g=255, b=255, white=255, duration=3)
            time.sleep(4)  # 3s chase + 1s pause

        def _run():
            self.stop_all()  # ensure nothing else runs during countdown
            self.data = [0] * 512
            self.data[6] = 255  # strobe channels "armed"
            self.data[7] = 255
            for _ in range(3):  # red flash 3-2-1
                self.data[0] = 255
                self.send_dmx()
                time.sleep(0.5)
                self.data[0] = 0
                self.send_dmx()
                time.sleep(0.5)
            self.rgb(255, 255, 255, 255)  # full white at "start"

        self.wait_thread = threading.Thread(target=_run, daemon=True)
        self.wait_thread.start()

