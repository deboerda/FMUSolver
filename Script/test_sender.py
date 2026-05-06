import socket
import struct
import time

def send_mixed_test_data():
    # 改为受限广播地址，确保 0.0.0.0 监听器能捕获到
    target_addr = ("255.255.255.255", 30019)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print(f"[*] Starting Broadcast Test Sender to {target_addr}...")

    params = [
        "B017101.23/1.23",    # 存在
        "K0693055.5/55.5",    # 存在
        "N0387010.0/10.0",    # 存在
        "S99990ERROR/ERROR",  # 不存在
        "FAKE00NONE/NONE",    # 不存在
        "S00670560:12:00:00:001" # 时钟
    ]
    body_str = " ".join(params)
    body_bytes = body_str.encode('ascii')

    pkg_len = 29 + len(body_bytes)
    craft_num = b"TGMTC101"
    nDay = 8201
    nMS = int(time.time() % 86400 * 10000)
    
    header = struct.pack("<h", pkg_len)      # offset 0
    header += struct.pack("8s", craft_num)    # offset 2
    header += struct.pack("<hI", nDay, nMS)   # offset 10
    header += b"\x00"                         # offset 16
    header += b"\x01"                         # offset 17
    header += struct.pack("4s", b"YC01")      # offset 18
    header += b"\x00"                         # offset 22
    header += struct.pack("3s", b"SRC")       # offset 23
    header += struct.pack("3s", b"DST")       # offset 26

    packet = header + body_bytes
    
    try:
        sock.sendto(packet, target_addr)
        print(f"[+] Broadcasted {len(packet)} bytes.")
    except Exception as e:
        print(f"[!] Send failed: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    while True:
        send_mixed_test_data()
        time.sleep(2.0)
