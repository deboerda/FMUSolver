import socket
import threading
import queue
import time
import struct
import os
import sys
import base64
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

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
        self.log_queue = queue.Queue()
        self.running = False
        self.reported_matches = set() # 记录已匹配过的参数名
        self.packet_count = 0
        self.reported_warnings = set()
        self.log_dir = os.path.join(self.config_mgr.root_dir, "logs")
        self.max_log_bytes = 20 * 1024 * 1024
        
    def start(self):
        self.config_mgr.load_config()
        self.config_mgr.load_filter_params()
        os.makedirs(self.log_dir, exist_ok=True)
        self.running = True
        
        print(f"[*] YaoCe -> DDM Bridge (SimVar Mode) Started.")
        print(f"[*] Filtered Parameters: {len(self.config_mgr.filter_params)}")
        print(f"[*] Targets: {self.config_mgr.targets}")
        
        self.logger_thread = threading.Thread(target=self.logging_loop, daemon=True)
        self.logger_thread.start()
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
        record_file = os.path.join(self.log_dir, "originaldata.log")
        print(f"[*] Raw hex records will be saved asynchronously to: {record_file}")
        
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
            
            while self.running:
                data, addr = sock.recvfrom(65535)
                self.last_recv_time = time.time()
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                self.data_queue.put(data)
                self.log_queue.put(("original", data, addr, ts))
        except Exception as e:
            print(f"[!] Receiver error: {e}")
        finally:
            sock.close()

    def processing_loop(self):
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.start_time = time.time()
        self.last_log_time = time.time()
        self.last_packet_count = 0
        
        while self.running:
            try:
                raw_data = self.data_queue.get(timeout=1.0)
                self.packet_count += 1
                try:
                    mark = self.config_mgr.config.get('EndianMark', '<')
                    pkg = PacketParser.parse_datagram(raw_data, endian_mark=mark, filter_set=self.config_mgr.filter_params)
                except: continue
                    
                if not pkg: continue
                
                ddm_msg = self.generate_ddm_protobuf(pkg)
                if ddm_msg:
                    try:
                        for target_ip, target_port in self.config_mgr.targets:
                            msg_to_send = ddm_msg
                            if self.config_mgr.is_local_injection_target(target_ip, target_port):
                                msg_to_send = self.clone_ddm_with_prefix(ddm_msg, "YC")
                            raw_bytes = msg_to_send.SerializeToString()
                            payload = base64.b64encode(raw_bytes)
                            send_sock.sendto(payload, (target_ip, target_port))
                        
                        # Log converted visible data to queue
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        vars_str = ", ".join([f"{var.name}={var.double_value}" for var in ddm_msg.sim_vars])
                        self.log_queue.put(("send", ddm_msg.sim_time, vars_str, ts))

                        # 严格按照用户要求的格式：[Live]Time: 38.00s | Sent40vars | Rate: 1.0x | Freq:50.0Hz
                        now = time.time()
                        if now - self.last_log_time >= 1.0: # 每秒输出一次日志
                            elapsed = now - self.start_time
                            freq = (self.packet_count - self.last_packet_count) / (now - self.last_log_time)
                            print(f"[Live]Time: {elapsed:.2f}s | Sent{len(ddm_msg.sim_vars)}vars | Rate: 1.0x | Freq:{freq:.1f}Hz")
                            self.last_log_time = now
                            self.last_packet_count = self.packet_count
                    except Exception as e:
                        print(f"[!] Send error: {e}")
                else:
                    if self.packet_count % 100 == 0:
                        elapsed = time.time() - self.start_time
                        print(f"[Live]Time: {elapsed:.2f}s | Sent0vars | Rate: 1.0x | Freq:0.0Hz")
            except queue.Empty: continue
            except Exception as e:
                print(f"[!] Processor error: {e}")

    def clone_ddm_with_prefix(self, msg, prefix):
        cloned = ddm_pb2.DDMData()
        cloned.machine_time = msg.machine_time
        cloned.sim_time = msg.sim_time
        prefix_text = f"{prefix}."
        for src in msg.sim_vars:
            dst = cloned.sim_vars.add()
            dst.CopyFrom(src)
            if not dst.name.startswith(prefix_text):
                dst.name = prefix_text + dst.name
        return cloned

    def logging_loop(self):
        originaldata_file = os.path.join(self.log_dir, "originaldata.log")
        senddata_file = os.path.join(self.log_dir, "senddata.log")
        
        f_orig = None
        f_send = None
        try:
            f_orig = open(originaldata_file, "w", encoding="utf-8", buffering=1024*1024)
            f_orig.write(f"--- YaoCe UDP Raw Record Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
            f_orig.flush()
        except Exception as e:
            print(f"[!] Failed to open originaldata.log: {e}")
            
        try:
            f_send = open(senddata_file, "a", encoding="utf-8", buffering=1024*1024)
        except Exception as e:
            print(f"[!] Failed to open senddata.log: {e}")

        last_flush_time = time.time()
        
        while self.running or not self.log_queue.empty():
            try:
                log_item = self.log_queue.get(timeout=0.5)
                log_type = log_item[0]
                
                if log_type == "original":
                    _, data, addr, ts = log_item
                    if f_orig:
                        hex_bytes = data[:512]
                        hex_str = hex_bytes.hex(' ').upper()
                        suffix = " ..." if len(data) > len(hex_bytes) else ""
                        f_orig.write(f"[{ts}] RX {len(data)} bytes from {addr[0]}:{addr[1]}\n{hex_str}{suffix}\n\n")
                elif log_type == "send":
                    _, sim_time, vars_str, ts = log_item
                    if f_send:
                        f_send.write(f"[{ts}] SimTime: {sim_time:.3f} | {vars_str}\n")
                        
                self.log_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                print(f"[!] Logger loop error: {e}")
                
            now = time.time()
            if now - last_flush_time >= 1.0:
                try:
                    if f_orig: f_orig.flush()
                    if f_send: f_send.flush()
                    if f_orig and f_orig.tell() > self.max_log_bytes:
                        f_orig.seek(0)
                        f_orig.truncate()
                        f_orig.write(f"--- YaoCe UDP Raw Record Rotated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
                    if f_send and f_send.tell() > self.max_log_bytes:
                        f_send.seek(0)
                        f_send.truncate()
                        f_send.write(f"--- YaoCe DDM Send Record Rotated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
                except: pass
                last_flush_time = now
                
        try:
            if f_orig: f_orig.close()
            if f_send: f_send.close()
        except: pass

    def generate_ddm_protobuf(self, pkg: InfoTransPkg):
        if ddm_pb2 is None: return None
        msg = ddm_pb2.DDMData()
        msg.machine_time = time.time()
        try:
            dt = datetime.strptime(pkg.recv_time, "%Y-%m-%d %H:%M:%S")
            msg.sim_time = dt.timestamp()
        except: msg.sim_time = 0.0

        is_any_field_added = False
        clock_codes = {"S0067", "DCSM34"}

        def add_to_sim_vars(name, val_str):
            svar = msg.sim_vars.add()
            svar.name = name
            svar.type = ddm_pb2.DDMData.SimVar.Double

            if isinstance(val_str, (int, float)):
                svar.double_value = float(val_str)
                return

            clean_val = str(val_str).strip()
            if not clean_val:
                svar.double_value = 0.0
                return
            try:
                svar.double_value = float(clean_val)
            except ValueError:
                # --- 修复：不再盲目进行十六进制转换 ---
                # 卫星遥测中的 AA55/AAAA 是占位符，不应转为天文数字注入 FMU
                svar.double_value = 0.0
            except Exception:
                svar.double_value = 0.0

        def parse_clock_value(clock_str):
            parts = [p.strip() for p in clock_str.split(":")]
            if len(parts) < 5:
                return None
            try:
                day = int(parts[0])
                hour = int(parts[1])
                minute = int(parts[2])
                second = int(parts[3])
                millisecond = int(parts[4])
            except ValueError:
                return None

            total_seconds = (
                day * 86400.0 +
                hour * 3600.0 +
                minute * 60.0 +
                second +
                millisecond / 1000.0
            )
            return {
                "A024": day,
                "A025": hour,
                "A026": minute,
                "A027": second,
                "A028": millisecond,
                "total": total_seconds,
            }

        for item in pkg.info_body_vct:
            allowed, mapped_name = self.config_mgr.is_param_allowed(item.sys_ident)
            if not allowed: continue
            sim_var_name = self.config_mgr.map_to_sim_var(mapped_name)
            
            if mapped_name not in self.reported_matches:
                print(f"[DEBUG] First match for parameter: Original='{item.sys_ident}', Code='{mapped_name}', SimVar='{sim_var_name}', Value='{item.value}'")
                self.reported_matches.add(mapped_name)
                
            is_any_field_added = True

            try:
                # 现场日志中真正的绝对时间码是冒号分隔格式，例如 1138:22:45:54:278。
                # 对 S0067/DCSM34 仅在收到该格式时才做时间码拆分，避免 T0067 等普通测点因后缀相同被误映射。
                if mapped_name in clock_codes:
                    parsed_clock = parse_clock_value(item.value)
                    if parsed_clock is not None:
                        add_to_sim_vars(sim_var_name, parsed_clock["total"])
                        add_to_sim_vars(self.config_mgr.map_to_sim_var("A024"), parsed_clock["A024"])
                        add_to_sim_vars(self.config_mgr.map_to_sim_var("A025"), parsed_clock["A025"])
                        add_to_sim_vars(self.config_mgr.map_to_sim_var("A026"), parsed_clock["A026"])
                        add_to_sim_vars(self.config_mgr.map_to_sim_var("A027"), parsed_clock["A027"])
                        add_to_sim_vars(self.config_mgr.map_to_sim_var("A028"), parsed_clock["A028"])
                    elif item.sys_ident == mapped_name:
                        warn_key = (mapped_name, "clock_fallback")
                        if warn_key not in self.reported_warnings:
                            print(f"[WARN] Clock field '{mapped_name}' has non-clock payload '{item.value}', forwarded as raw numeric fallback.")
                            self.reported_warnings.add(warn_key)
                        add_to_sim_vars(sim_var_name, item.value)
                    else:
                        warn_key = (item.sys_ident, mapped_name, "clock_collision")
                        if warn_key not in self.reported_warnings:
                            print(f"[WARN] Ignored suffix-based remap '{item.sys_ident}' -> '{mapped_name}' because payload '{item.value}' is not a clock string.")
                            self.reported_warnings.add(warn_key)
                else:
                    add_to_sim_vars(sim_var_name, item.value)
            except Exception as e:
                print(f"[!] Unexpected error mapping field '{mapped_name}': {e}")
                    
        return msg if is_any_field_added else None

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    app = YaoCeLinkLayerApp(root)
    app.start()
