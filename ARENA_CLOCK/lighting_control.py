# lighting_controller.py

from ola.ClientWrapper import ClientWrapper
import threading
import time

UNIVERSE = 1

class LightingController:
    def __init__(self):
        self.wrapper = ClientWrapper()
        self.client = self.wrapper.Client()
        self.data = [0] * 512

        # Start the OLA event loop in the background
        self.thread = threading.Thread(target=self.wrapper.Run)
        self.thread.daemon = True
        self.thread.start()
        self.send_dmx(self.data)

    def send_dmx(self, data=None):
        if data is None:
            data = self.data

        def dmx_sent(status):
            pass  # No printout, silent success/failure

        self.client.SendDmx(UNIVERSE, bytearray(data), dmx_sent)

    def rgb(self, r, g, b, white = 0):
        self.data[0] = r
        self.data[1] = g
        self.data[2] = b
        self.data[3] = white
        self.send_dmx()

    def _battle_start_sequence(self):
        self.data = [0] * 512
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

    def battle_start(self):
        threading.Thread(target=self._battle_start_sequence, daemon=True).start()
    
    def off(self):
        self.data = [0] * 512
        self.send_dmx(self.data)

    def pause(self):
        self.data = [0] * 512
        self.data[2] = 255  # Blue
        self.data[6] = 255
        self.data[7] = 255
        self.send_dmx()
