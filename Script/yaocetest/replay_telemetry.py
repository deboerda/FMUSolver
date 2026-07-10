import socket
import time
import re
import sys
import os
from datetime import datetime

def replay_log(file_path, target_ip="127.0.0.1", target_port=30019, speed=0.1, loop=True):
    """
    Replays a YaoCe raw record log file to a UDP target.
    speed: 0.5 means half speed (slower), 1.0 means original speed, 2.0 means double speed.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Pre-count lines for progress display
    total_lines = sum(1 for _ in open(file_path, 'r', encoding='utf-8'))
    
    print(f"[*] Replaying: {os.path.basename(file_path)}")
    print(f"[*] Target: {target_ip}:{target_port}")
    print(f"[*] Speed: {speed}x (Sending 1 second of data every {1/speed:.1f} seconds)")
    print("[*] Loop mode: ON. Press Ctrl+C to stop." if loop else "[*] Loop mode: OFF.")

    # Regex to match the timestamp line
    ts_pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\] RX")

    total_packet_count = 0
    start_time = time.time()
    loop_count = 0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        while True:
            loop_count += 1
            last_ts = None
            loop_packet_count = 0
            print(f"[*] Replay loop #{loop_count} started.")

            i = 0
            while i < len(lines):
                line = lines[i].strip()
                match = ts_pattern.match(line)
                if match:
                    # Parse timestamp from log
                    current_ts = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S.%f")

                    # Read the next line for hex data
                    i += 1
                    if i >= len(lines): break
                    hex_data = lines[i].strip()

                    if hex_data:
                        try:
                            # Strip spaces to ensure compatibility with all Python versions
                            clean_hex = hex_data.replace(" ", "").replace("\t", "")
                            data_bytes = bytes.fromhex(clean_hex)

                            # Real-time synchronization
                            if last_ts is not None:
                                delay = (current_ts - last_ts).total_seconds()
                                if delay > 0:
                                    # Wait based on speed factor
                                    time.sleep(delay / speed)

                            # Send
                            sock.sendto(data_bytes, (target_ip, target_port))
                            total_packet_count += 1
                            loop_packet_count += 1

                            if total_packet_count == 1:
                                print(f"[OK] First packet sent! Size: {len(data_bytes)} bytes")

                            if loop_packet_count % 100 == 0:
                                progress = (i / total_lines) * 100
                                print(f"[REPLAY] loop #{loop_count}: {loop_packet_count} packets ({progress:.1f}%), total={total_packet_count}")

                            last_ts = current_ts
                        except Exception:
                            # Skip malformed lines
                            pass

                i += 1

            print(f"[*] Replay loop #{loop_count} finished. loop_packets={loop_packet_count}, total={total_packet_count}")
            if not loop:
                break
            time.sleep(0.2)
                
    except KeyboardInterrupt:
        print("\n[*] Replay stopped by user.")
    except Exception as e:
        print(f"[!] Error during replay: {e}")
    finally:
        sock.close()
        duration = time.time() - start_time
        print(f"[*] Replay finished. Loops: {loop_count}. Total packets sent: {total_packet_count}. Duration: {duration:.1f}s")

if __name__ == "__main__":
    # Default file path
    log_file = r"c:\Spaceship\FMUSOLVER\FmuSolver_Package\yaocetest\xianchangtiaoshi\raw_record_20260422_161143.log"
    target = "127.0.0.1"
    
    # Set default speed to 0.5 (half speed)
    speed_val = 0.1
    
    # Allow overriding via command line
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    
    if len(sys.argv) > 2:
        target = sys.argv[2]
        
    if len(sys.argv) > 3:
        speed_val = float(sys.argv[3])
        
    replay_log(log_file, target_ip=target, speed=speed_val)
