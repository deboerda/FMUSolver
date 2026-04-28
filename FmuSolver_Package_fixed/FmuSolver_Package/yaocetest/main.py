import socket
import threading
import queue
import time
import struct
import os
import sys
import base64
from datetime import datetime
try:
    from packet_parser import PacketParser, InfoTransPkg
    from config_manager import ConfigManager
except ImportError:
    from yaocetest.packet_parser import PacketParser, InfoTransPkg
    from yaocetest.config_manager import ConfigManager

# 动态寻找 ddm 协议库
ddm_path = ""
app_dir = os.path.dirname(os.path.abspath(__file__))
while app_dir and app_dir.strip("\\") != "" and not app_dir.endswith(":\\"):
    test_path = os.path.join(app_dir, "Udp.Ddm.protobuf")
    if os.path.isdir(test_path):
        ddm_path = test_path
        break
    parent_dir = os.path.dirname(app_dir)
    if parent_dir == app_dir: break
    app_dir = parent_dir
    
if ddm_path not in sys.path and ddm_path:
    sys.path.append(ddm_path)

try:
    import ddm_pb2
except ImportError:
    print(f"[!] Warning: ddm_pb2 not found at {ddm_path}")
    ddm_pb2 = None

class YaoCeLinkLayerApp:
    def __init__(self, root_dir):
        self.config_mgr = ConfigManager(root_dir)
        self.data_queue = queue.Queue()
        self.running = False
        self.reported_matches = set() # 记录已匹配过的参数名
        self.packet_count = 0
        
    def start(self):
        self.config_mgr.load_config()
        self.config_mgr.load_filter_params()
        self.running = True
        
        print(f"[*] YaoCe -> DDM Bridge (SimVar Mode) Started.")
        print(f"[*] Filtered Parameters: {len(self.config_mgr.filter_params)}")
        print(f"[*] Targets: {self.config_mgr.targets}")
        
        self.process_thread = threading.Thread(target=self.processing_loop, daemon=True)
        self.process_thread.start()
        self.receive_loop()

    def receive_loop(self):
        recv_port = self.config_mgr.config['RecvPort']
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if sys.platform == 'win32':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        self.last_recv_time = time.time()
        record_file = os.path.join(self.config_mgr.root_dir, f"raw_record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        print(f"[*] Raw hex records will be saved to: {record_file}")
        
        def monitor_heartbeat():
            while self.running:
                time.sleep(5)
                if time.time() - self.last_recv_time > 10.0:
                    print(f"[-] Still listening on UDP {recv_port}, but no data received for over 10s.")
        
        threading.Thread(target=monitor_heartbeat, daemon=True).start()
        
        try:
            # Bind to 0.0.0.0 for maximum compatibility in multi-NIC environments
            sock.bind(('0.0.0.0', recv_port))
            # Increase receive buffer to 1MB to prevent packet drops for large UDP bursts
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
            except: pass
            
            print(f"[*] Listening on UDP {recv_port}...")
            
            with open(record_file, "a", encoding="utf-8") as f_rec:
                f_rec.write(f"--- YaoCe UDP Raw Record Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
                while self.running:
                    data, addr = sock.recvfrom(65535)
                    self.last_recv_time = time.time()
                    try:
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        hex_str = data.hex(' ').upper()
                        f_rec.write(f"[{ts}] RX {len(data)} bytes from {addr[0]}:{addr[1]}\n{hex_str}\n\n")
                        f_rec.flush()
                    except: pass
                    self.data_queue.put(data)
        except Exception as e:
            print(f"[!] Receiver error: {e}")
        finally:
            sock.close()

    def processing_loop(self):
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while self.running:
            try:
                raw_data = self.data_queue.get(timeout=1.0)
                self.packet_count += 1
                try:
                    mark = self.config_mgr.config.get('EndianMark', '<')
                    pkg = PacketParser.parse_datagram(raw_data, endian_mark=mark)
                except: continue
                    
                if not pkg: continue
                
                ddm_msg = self.generate_ddm_protobuf(pkg)
                if ddm_msg:
                    try:
                        raw_bytes = ddm_msg.SerializeToString()
                        payload = base64.b64encode(raw_bytes)
                        for target_ip, target_port in self.config_mgr.targets:
                            send_sock.sendto(payload, (target_ip, target_port))
                        if self.packet_count % 10 == 0: 
                            print(f"[SEND] Packet #{self.packet_count}: Forwarded {len(ddm_msg.sim_vars)} vars.")
                    except Exception as e:
                        print(f"[!] Send error: {e}")
                else:
                    if self.packet_count % 100 == 0:
                        print(f"[-] Packet #{self.packet_count}: 0 variables matched whitelist.")
            except queue.Empty: continue
            except Exception as e:
                print(f"[!] Processor error: {e}")

    def generate_ddm_protobuf(self, pkg: InfoTransPkg):
        if ddm_pb2 is None: return None
        msg = ddm_pb2.DDMData()
        msg.machine_time = time.time()
        try:
            dt = datetime.strptime(pkg.recv_time, "%Y-%m-%d %H:%M:%S")
            msg.sim_time = dt.timestamp()
        except: msg.sim_time = 0.0

        is_any_field_added = False

        def add_to_sim_vars(name, val_str):
            svar = msg.sim_vars.add()
            svar.name = name
            svar.type = ddm_pb2.DDMData.SimVar.Double
            clean_val = val_str.strip()
            if not clean_val:
                svar.double_value = 0.0
                return
            try:
                svar.double_value = float(clean_val)
            except ValueError:
                try:
                    svar.double_value = float(int(clean_val, 16))
                except Exception:
                    svar.double_value = 0.0
            except Exception:
                svar.double_value = 0.0

        for item in pkg.info_body_vct:
            allowed, mapped_name = self.config_mgr.is_param_allowed(item.sys_ident)
            if not allowed: continue
            
            if mapped_name not in self.reported_matches:
                print(f"[DEBUG] First match for parameter: Original='{item.sys_ident}', Mapped='{mapped_name}', Value='{item.value}'")
                self.reported_matches.add(mapped_name)
                
            is_any_field_added = True

            # 改进的时钟逻辑：仅当 ID 匹配且内容包含冒号时才按时钟拆分
            is_clock_id = item.sys_ident.endswith("0067") or mapped_name.endswith("0067")
            has_colon = ":" in item.value
            
            try:
                if is_clock_id and has_colon:
                    parts = item.value.split(":")
                    if len(parts) >= 5:
                        mapping = [("A024", 0), ("A025", 1), ("A026", 2), ("A027", 3), ("A028", 4)]
                        for code, idx in mapping:
                            add_to_sim_vars(code, parts[idx])
                    else:
                        add_to_sim_vars(mapped_name, item.value)
                else:
                    add_to_sim_vars(mapped_name, item.value)
            except Exception as e:
                print(f"[!] Unexpected error mapping field '{mapped_name}': {e}")
                    
        return msg if is_any_field_added else None

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    app = YaoCeLinkLayerApp(root)
    app.start()
