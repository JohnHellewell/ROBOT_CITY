import socket
import struct

def send_command(sock, ip, port, command, time_ms):
    # Convert ms to deciseconds
    time_ds = time_ms // 100
    # Pack command and time_ds as unsigned shorts (big endian)
    data = struct.pack('!HH', command, time_ds)
    sock.sendto(data, (ip, port))

# Example usage
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip = '192.168.8.7'  # your ESP32 IP
port = 50001

command = 1         # example command: start countdown
time_ms = 180000    # 3 minutes in ms

send_command(sock, ip, port, command, time_ms)

print("sent")
