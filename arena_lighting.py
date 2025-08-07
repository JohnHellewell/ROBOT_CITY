from ola.ClientWrapper import ClientWrapper
import time

UNIVERSE = 1

# Blue: full dimmer, full blue, no red/green
data = [0, 0, 255, 0] + [0] * 508  # total 512 channels

def dmx_sent(status):
    if status.Succeeded():
        print("DMX data sent successfully!")
    else:
        print("Failed to send DMX data")

wrapper = ClientWrapper()
client = wrapper.Client()
client.SendDmx(UNIVERSE, bytearray(data), dmx_sent)

wrapper.Run()

#8ch: [red, green, blue, white, amber, UV, strobe, master dimmer]
# Red, Green, Blue: main colors. They work as expected
# White: corrects it to true white when put at same level with R, G, B
# Amber
# strobe: percentage of time on. Put at 100% for no strobe
# master dimmer is master dimmer