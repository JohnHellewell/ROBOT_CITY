import socket
import struct
from time import sleep

ESP32_IP = "192.168.1.11"  # Replace with actual IP
PORT = 4210

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(2)

def send_and_receive(values):
    assert len(values) == 4
    assert all(0 <= v <= 1000 for v in values), "Values must be 1000"
    
    
    # Pack 4 unsigned bytes
    packet = struct.pack('BBBB', *values)
    
    # Send
    sock.sendto(packet, (ESP32_IP, PORT))
    
    # Receive 4-byte float
    try:
        data, _ = sock.recvfrom(1024)
        result = round(struct.unpack('f', data)[0], 2)
        print("Received float:", result)
        return result
    except socket.timeout:
        print("No response (timeout)")

while(True):
    send_and_receive([100, 120, 255, 0])
    sleep(2)
