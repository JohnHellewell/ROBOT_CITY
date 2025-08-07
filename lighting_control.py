from ola.ClientWrapper import ClientWrapper
import time

UNIVERSE = 1

wrapper = ClientWrapper()
client = wrapper.Client()

base = [0, 0, 0, 0, 0, 0, 0, 0] + [0]*504

def send_dmx(data):
    def dmx_sent(status):
        if status.Succeeded():
            print("DMX data sent successfully!")
        else:
            print("Failed to send DMX data")
    client.SendDmx(UNIVERSE, bytearray(data))

def main():
    # Base data with blue full, master dimmer full, strobe off, rest zero
    

    # We'll adjust blue channel (index 2) from 255 -> 0 and back
    try:
        battle_start()
        while True:
            # Dim blue down over 10 seconds, step 5 every 0.2 seconds -> 51 steps
            for blue_value in range(255, -1, -1):
                data = base.copy()
                data[2] = blue_value
                send_dmx(data)
                time.sleep(0.02)

            # Brighten blue up over 10 seconds
            for blue_value in range(0, 256, 1):
                data = base.copy()
                data[2] = blue_value
                send_dmx(data)
                time.sleep(0.02)
    except KeyboardInterrupt:
        # Turn off lights on exit
        base = [0, 0, 0, 0, 0, 0, 0, 0] + [0]*504
        send_dmx(base)
        print("Exiting, lights off.")

def battle_start():
    data = [0, 0, 0, 0, 0, 0, 255, 255] + [0]*504
    for i in range(3):
        data[0] = 255
        send_dmx(data)
        time.sleep(0.5)
        data[0] = 0
        send_dmx(data)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
    wrapper.Run()
