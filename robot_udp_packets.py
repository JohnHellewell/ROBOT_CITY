import socket
import struct
from time import sleep
import time

ESP32_IP = "192.168.1.4"  # Replace with variable robot IP
PORT = 4210 # Replace with robot port

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.05)

last_response_time = time.time()

def send_and_receive(values):
    assert len(values) == 4
    #assert all(1000 <= v <= 2000 for v in values), "Values must be 1000"
    
    
    # Pack 4 unsigned bytes
    packet = struct.pack('HHHH', *values)
    
    # Send
    sock.sendto(packet, (ESP32_IP, PORT))
    
    try:
        data, _ = sock.recvfrom(1024)
        result = struct.unpack('?', data[:1])[0]  # Use only the first byte
        print("Received bool:", result)
        return result
    except socket.timeout:
        print("No response (timeout)")

def stress_test(duration_sec=10):
    count_sent = 0
    count_received = 0
    total_rtt = 0  # Total round-trip time

    start = time.time()
    while time.time() - start < duration_sec:
        count_sent += 1
        t0 = time.time()
        result = send_and_receive([1500, 1500, 1500, 0])
        t1 = time.time()
        if result is not None:
            count_received += 1
            total_rtt += (t1 - t0)

    elapsed = time.time() - start
    avg_ping_ms = (total_rtt / count_received * 1000) if count_received > 0 else 0

    print(f"Sent: {count_sent} packets")
    print(f"Received: {count_received} packets")
    print(f"Avg send rate: {count_sent / elapsed:.2f} packets/sec")
    print(f"Avg response rate: {count_received / elapsed:.2f} packets/sec")
    print(f"Average ping: {avg_ping_ms:.2f} ms")

while(True):
    stress_test()
    break
    #send_and_receive([1500, 1500, 1500, 0])
    #sleep(2)
