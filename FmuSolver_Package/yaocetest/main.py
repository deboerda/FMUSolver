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

# 动态寻找 ddm 协议库（向下或同级搜索，适配独立 exe 和原始工作区）
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
        self.reported_matches = set() # 记录已匹配过的参数名，减少日志重复
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
        
        # 创建原始数据记录文件
        record_file = os.path.join(self.config_mgr.root_dir, f"raw_record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        print(f"[*] Raw hex records will be saved to: {record_file}")
        
        # 增加一个心跳监视线程，如果长时间未收到数据，打印提醒
        def monitor_heartbeat():
            while self.running:
                time.sleep(5)
                if time.time() - self.last_recv_time > 10.0:
                    print(f"[-] Still listening on UDP {recv_port}, but no data received for over 10s. Please check sender IP/Port.")
        
        threading.Thread(target=monitor_heartbeat, daemon=True).start()
        
        try:
            sock.bind(('', recv_port))
            print(f"[*] Listening on UDP {recv_port}...")
            
            with open(record_file, "a", encoding="utf-8") as f_rec:
                f_rec.write(f"--- YaoCe UDP Raw Record Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
                
                while self.running:
                    data, addr = sock.recvfrom(65535)
                    self.last_recv_time = time.time()
                    # 减少控制台 RECV 日志，每100个包打印一次，或只在调试时打印
                    # print(f"[RECV] RX {len(data)} bytes from {addr}")
                    
                    # 写入记录文件
                    try:
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        hex_str = data.hex(' ').upper()
                        f_rec.write(f"[{ts}] RX {len(data)} bytes from {addr[0]}:{addr[1]}\n{hex_str}\n\n")
                        f_rec.flush() # 强制刷入磁盘，防崩溃丢失
                    except Exception as e:
                        print(f"[!] Write record error: {e}")
                        
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
                except ValueError as ve:
                    print(f"[WARN] Packet parse rejected: {ve}")
                    continue
                except Exception as ex:
                    print(f"[!] Packet parse fatal error: {ex}")
                    continue
                    
                if not pkg: 
                    continue
                
                try:
                    ddm_msg = self.generate_ddm_protobuf(pkg)
                except Exception as ex:
                    print(f"[!] Protobuf generation failed: {ex}")
                    continue
                    
                if ddm_msg:
                    try:
                        raw_bytes = ddm_msg.SerializeToString()
                        b64_str = base64.b64encode(raw_bytes).decode('ascii')
                    except Exception as ex:
                        print(f"[!] Serialization to base64 failed: {ex}")
                        continue
                        
                    for target_ip, target_port in self.config_mgr.targets:
                        try:
                            send_sock.sendto(b64_str.encode('ascii'), (target_ip, target_port))
                            # 只打印有匹配的包
                            if self.packet_count % 10 == 0: # 采样打印发送日志
                                print(f"[SEND] Packet #{self.packet_count}: Forwarded {len(ddm_msg.sim_vars)} vars -> {target_ip}:{target_port}")
                        except Exception as e:
                            print(f"[!] Send to {target_ip}:{target_port} error: {e}")
                else:
                    # 如果一个匹配都没有，每100个包打印一次提醒，防止用户以为程序死掉
                    if self.packet_count % 100 == 0:
                        print(f"[-] Packet #{self.packet_count}: 0 variables matched whitelist in this batch (normal behavior for cycled telemetry).")
                    
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
        except Exception as e:
            print(f"[WARN] Failed to parse simulation time '{pkg.recv_time}': {e}")
            msg.sim_time = 0.0

        is_any_field_added = False

        # 定义映射助手，将数据添加进 sim_vars
        def add_to_sim_vars(name, val_str):
            svar = msg.sim_vars.add()
            svar.name = name
            svar.type = ddm_pb2.DDMData.SimVar.Double # 使用 Double 类型
            clean_val = val_str.strip()
            if not clean_val:
                svar.double_value = 0.0
                return
            try:
                svar.double_value = float(clean_val)
            except ValueError:
                try:
                    # 尝试将不能转为普通浮点数的字符串当作16进制解析
                    svar.double_value = float(int(clean_val, 16))
                except Exception:
                    # 如果转换彻底失败，记录一次详细日志
                    if name not in self.reported_matches:
                        print(f"[DEBUG] Field '{name}' value '{clean_val}' is not numeric/hex, setting to 0.0")
                    svar.double_value = 0.0
            except Exception as e:
                print(f"[WARN] Field '{name}' value '{clean_val}' error: {e}")
                svar.double_value = 0.0

        for item in pkg.info_body_vct:
            # 使用 ConfigManager 新的多轨匹配逻辑
            allowed, mapped_name = self.config_mgr.is_param_allowed(item.sys_ident)
            if not allowed:
                continue
            
            if mapped_name not in self.reported_matches:
                print(f"[DEBUG] First match for parameter: Original='{item.sys_ident}', Mapped='{mapped_name}', Value='{item.value}'")
                self.reported_matches.add(mapped_name)
                
            is_any_field_added = True

            # 处理 S0067 时钟拆分
            try:
                if mapped_name == "S0067":
                    parts = item.value.split(":")
                    if len(parts) >= 5:
                        mapping = [("A024", 0), ("A025", 1), ("A026", 2), ("A027", 3), ("A028", 4)]
                        for code, idx in mapping:
                            add_to_sim_vars(code, parts[idx])
                    else:
                        print(f"[WARN] S0067 clock format error: {item.value}")
                else:
                    # 使用映射后的名称发送（确保与 XML 一致）
                    add_to_sim_vars(mapped_name, item.value)
            except Exception as e:
                print(f"[!] Unexpected error mapping field '{mapped_name}': {e}")
                    
        return msg if is_any_field_added else None

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    app = YaoCeLinkLayerApp(root)
    app.start()
