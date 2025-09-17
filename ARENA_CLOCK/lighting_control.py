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


        # Event loop thread
        self.thread = threading.Thread(target=self.wrapper.Run)
        self.thread.daemon = True
        self.thread.start()

        # Event to control wait loop
        self.waiting = threading.Event()
        self.wait_thread = None

    def send_dmx(self, data=None, replicate = True):
        if data is None:
            data = self.data
        
        if(replicate):
            # take first 8
            ch1 = data[:8]

            # repeat 4 times
            new_data = ch1 * 4   # length = 32

            # pad with zeros to length 512
            new_data.extend([0] * (512 - len(new_data)))

            # replace original
            data = new_data


        def dmx_sent(status):
            pass  # Silent

        self.client.SendDmx(UNIVERSE, bytearray(data), dmx_sent)
    
    def chase_sequence(self, r=255, g=255, b=255, white=255, delay=0.02, period=0.45, duration=5.0):
    
        self.stop_wait()

        def _run():
            self.waiting.set()
            start_time = time.time()
            end_time = start_time + duration

            while self.waiting.is_set():
                now = time.time()
                t = now - start_time
                remaining = end_time - now

                if remaining <= 0:
                    break  # stop after duration

                # Default intensity scale (0→1)
                scale = 1.0
                if t < 0.5:  # fade-in
                    scale = t / 0.5
                elif remaining < 0.5:  # fade-out
                    scale = remaining / 0.5

                self.data = [0] * 512

                for light in range(4):
                    # Phase offset (0, 90, 180, 270 degrees)
                    phase = (2 * math.pi * t / period) + (light * math.pi / 2)

                    # Raw sine in [-1, 1] -> normalize to [0, 1]
                    sine_val = (math.sin(phase) + 1) / 2  

                    if sine_val < 0.5:
                        brightness = 0
                    else:
                        brightness = (sine_val - 0.5) * 2  

                    # Scale colors
                    offset = light * 8
                    self.data[offset + 0] = r
                    self.data[offset + 1] = g
                    self.data[offset + 2] = b
                    self.data[offset + 3] = white

                    # Strobes full on
                    self.data[offset + 6] = 255
                    self.data[offset + 7] = int(255 * scale * brightness)

                self.send_dmx(replicate=False)
                time.sleep(delay)

            # Turn off lights when done
            self.data = [0] * 512
            self.send_dmx(replicate=False)

        self.wait_thread = threading.Thread(target=_run, daemon=True)
        self.wait_thread.start()


    def rgb(self, r, g, b, white = 0, amber = 0, uv = 0):
        self.data[0] = r
        self.data[1] = g
        self.data[2] = b
        self.data[3] = white
        self.data[4] = amber
        self.data[5] = uv
        self.send_dmx()
    
    def fade_out(self, time = 1.0):
        self.stop_wait() #kill anything running
        delay = 0.01
        wait = 0.0
        
        data = self.data[:8*4]

        while wait < time:
            for i in range(4):
                if wait == 0.0:
                    self.data[i*8+7] = 255
                else:
                    self.data[i*8+7] = int(255 / (wait/time))
            self.send_dmx(replicate = False)
            time.sleep(delay)
            wait += delay
        
        self.data = [0] * 512 #reset to all 0s except channels 6 & 7
        for i in range(4):
            self.data[i*8+6] = 255
            self.data[i*8+7] = 255
            

    def _wait_loop(self):
        delay = 0.02 #time waiting between updates

        self.waiting.set()

        
        time.sleep(5) #just a bit of a wait before starting the effects
        for r in range(256):
            if not self.waiting.is_set(): return
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
                self.rgb(0, 0, 255-u, uv = u//2) #uv intensity cut n half
                time.sleep(delay)
            for r in range(256):
                if not self.waiting.is_set(): return
                self.rgb(r, 0, 0, uv = (255-r)//2)
                time.sleep(delay)
            

    def wait(self):
        # Stop any existing loop
        self.stop_wait()
        self.wait_thread = threading.Thread(target=self._wait_loop, daemon=True)
        self.wait_thread.start()

    def stop_wait(self):
        self.waiting.clear()
        if self.wait_thread and self.wait_thread.is_alive():
            self.wait_thread.join(timeout=1)
            self.wait_thread = None

    def battle_start(self, chase = True):
        if(chase):
            self.fade_out()
            self.chase_sequence(255, 255, 255, 255, duration = 3)
            time.sleep(5) #4s of chase sequence, then 1 second of pause (anticipation)

        self.stop_wait()
        def _run(): #red flash 3 2 1 countdown
            self.data = [0]*512
            self.data[6] = 255
            self.data[7] = 255
            for _ in range(3):
                self.data[0] = 255
                self.send_dmx()
                time.sleep(0.5)
                self.data[0] = 0
                self.send_dmx()
                time.sleep(0.5)
            self.rgb(255, 255, 255, 255)
        threading.Thread(target=_run, daemon=True).start()

    def pause(self):
        self.stop_wait()
        self.data = [0]*512
        self.data[2] = 255  # Blue
        self.data[6] = 255
        self.data[7] = 255
        self.send_dmx()

    def off(self):
        self.stop_wait()
        self.data = [0]*512
        self.send_dmx()
