import socket
import sys

def sniff(port=30019):
    print(f"[*] Sniffing on UDP {port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 显式绑定 0.0.0.0
        sock.bind(('0.0.0.0', port))
        sock.settimeout(15)
        while True:
            try:
                data, addr = sock.recvfrom(65535)
                print(f"[OK] RECEIVED {len(data)} bytes from {addr}")
                # 打印前 16 字节确认内容
                print(f"     Hex: {data[:16].hex(' ').upper()}")
            except socket.timeout:
                print("[-] Timeout: No data received on 30019 in 15s.")
                break
    except Exception as e:
        print(f"[!] Sniff Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    p = 30019
    if len(sys.argv) > 1:
        p = int(sys.argv[1])
    sniff(p)
