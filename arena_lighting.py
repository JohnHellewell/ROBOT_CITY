import serial
import time

DMX_PORT = 'COM14'  # Your USB-DMX adapter port
DMX_CHANNELS = 512

# Build DMX frame: 512 channels, CH1 = dimmer, CH2 = red
dmx_data = bytearray([0] * DMX_CHANNELS)
dmx_data[0] = 255  # CH1: Master dimmer full
dmx_data[1] = 255  # CH2: Red full
# CH3–CH6 (Green, Blue, Amber, White) default to 0

# Open DMX serial port
ser = serial.Serial(DMX_PORT, baudrate=250000, bytesize=8, parity='N', stopbits=2)

while True:
    ser.break_condition = True
    time.sleep(0.001)  # Break for 88µs or more
    ser.break_condition = False
    time.sleep(0.001)  # Mark After Break

    ser.write(bytes([0]))        # DMX Start Code = 0
    ser.write(dmx_data)          # 512 bytes of DMX data
    time.sleep(0.03)             # Send ~30 times per second
