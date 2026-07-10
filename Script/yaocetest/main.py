import socket
import threading
import queue
import time
import struct
import os
import sys
import base64
import traceback
import json
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

class AsyncRotatingFileLogger:
    """Bounded async logger for production telemetry diagnostics."""
    def __init__(self, path, max_bytes=5 * 1024 * 1024, backups=3, queue_size=1000, flush_interval=0.5, batch_size=100):
        self.path = path
        self.max_bytes = max(1024 * 1024, int(max_bytes))
        self.backups = max(1, int(backups))
        self.queue = queue.Queue(maxsize=max(10, int(queue_size)))
        self.flush_interval = max(0.1, float(flush_interval))
        self.batch_size = max(1, int(batch_size))
        self.stop_event = threading.Event()
        self.drop_count = 0
        self.thread = threading.Thread(target=self._loop, name="YaoCePerfAsyncLog", daemon=True)
        self.thread.start()

    def log(self, line, important=False):
        text = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {line}\n"
        try:
            self.queue.put_nowait((text, important))
        except queue.Full:
            self.drop_count += 1
            if not important:
                return
            try:
                self.queue.get_nowait()
                try: self.queue.task_done()
                except Exception: pass
            except Exception:
                pass
            try: self.queue.put_nowait((text, important))
            except Exception: pass

    def close(self, timeout=2.0):
        self.stop_event.set()
        try: self.thread.join(timeout=timeout)
        except Exception: pass

    def _rotate_if_needed(self):
        try:
            if not os.path.exists(self.path) or os.path.getsize(self.path) <= self.max_bytes:
                return
            for idx in range(self.backups, 0, -1):
                src = f"{self.path}.{idx}"
                dst = f"{self.path}.{idx + 1}"
                if os.path.exists(dst):
                    try: os.remove(dst)
                    except Exception: pass
                if os.path.exists(src):
                    try: os.replace(src, dst)
                    except Exception: pass
            try: os.replace(self.path, f"{self.path}.1")
            except Exception: pass
        except Exception:
            pass

    def _loop(self):
        pending = []
        last_flush = time.time()
        while not self.stop_event.is_set() or not self.queue.empty() or pending:
            timeout = max(0.05, self.flush_interval - (time.time() - last_flush))
            try:
                item, _important = self.queue.get(timeout=timeout)
                pending.append(item)
                try: self.queue.task_done()
                except Exception: pass
                while len(pending) < self.batch_size:
                    try:
                        item, _important = self.queue.get_nowait()
                        pending.append(item)
                        try: self.queue.task_done()
                        except Exception: pass
                    except queue.Empty:
                        break
            except queue.Empty:
                pass
            if pending and (len(pending) >= self.batch_size or time.time() - last_flush >= self.flush_interval or self.stop_event.is_set()):
                try:
                    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                    self._rotate_if_needed()
                    if self.drop_count:
                        pending.insert(0, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [LOG] dropped {self.drop_count} telemetry perf log lines due to backpressure\n")
                        self.drop_count = 0
                    with open(self.path, "a", encoding="utf-8", buffering=1024 * 1024) as f:
                        f.writelines(pending)
                except Exception:
                    pass
                pending.clear()
                last_flush = time.time()

def is_process_alive(pid):
    try:
        pid = int(pid)
    except Exception:
        return True
    if pid <= 0 or pid == os.getpid():
        return True
    if sys.platform == 'win32':
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

class YaoCeLinkLayerApp:
    def __init__(self, root_dir):
        self.config_mgr = ConfigManager(root_dir)
        self.data_queue = queue.Queue(maxsize=int(os.environ.get("FMUSOLVER_YC_DATA_QUEUE_MAX", "3000")))
        self.log_queue = queue.Queue(maxsize=int(os.environ.get("FMUSOLVER_YC_LOG_QUEUE_MAX", "2000")))
        self.running = False
        self.reported_matches = set() # 记录已匹配过的参数名
        self.packet_count = 0
        self.reported_warnings = set()
        self.log_dir = os.path.join(self.config_mgr.root_dir, "logs")
        self.max_log_bytes = max(1, int(os.environ.get("FMUSOLVER_YC_MAX_LOG_MB", "5"))) * 1024 * 1024
        self.raw_log_sample = max(1, int(os.environ.get("FMUSOLVER_YC_RAW_LOG_SAMPLE", "200")))
        self.send_log_sample = max(1, int(os.environ.get("FMUSOLVER_YC_SEND_LOG_SAMPLE", "200")))
        self.live_log_interval = max(1.0, float(os.environ.get("FMUSOLVER_YC_LIVE_LOG_INTERVAL", "5.0")))
        self.rx_count = 0
        self.rx_drop_count = 0
        self.log_drop_count = 0
        self.send_count = 0
        self.send_error_count = 0
        self.last_perf_log = time.time()
        self.perf_log_path = os.path.join(self.log_dir, "yaoce_perf.log")
        self.perf_log_max_bytes = max(1, int(os.environ.get("FMUSOLVER_YC_PERF_LOG_MB", "5"))) * 1024 * 1024
        self.perf_logger = AsyncRotatingFileLogger(
            self.perf_log_path,
            max_bytes=self.perf_log_max_bytes,
            backups=int(os.environ.get("FMUSOLVER_YC_PERF_LOG_BACKUPS", "3")),
            queue_size=int(os.environ.get("FMUSOLVER_YC_PERF_LOG_QUEUE", "1000")),
            flush_interval=float(os.environ.get("FMUSOLVER_YC_PERF_LOG_FLUSH", "0.5")),
            batch_size=int(os.environ.get("FMUSOLVER_YC_PERF_LOG_BATCH", "100")),
        )
        self.last_perf_rx = 0
        self.last_perf_parsed = 0
        self.last_perf_sent = 0
        self.last_perf_time = self.last_perf_log
        self.parent_pid = os.environ.get("FMUSOLVER_PARENT_PID", "")
        self.worker_json_send_count = 0

    def enqueue_latest(self, q, item, drop_attr):
        try:
            q.put_nowait(item)
            return True
        except queue.Full:
            try:
                q.get_nowait()
                try: q.task_done()
                except Exception: pass
            except Exception:
                pass
            try:
                q.put_nowait(item)
            except Exception:
                pass
            setattr(self, drop_attr, getattr(self, drop_attr) + 1)
            return False

    def print_perf_stats(self, force=False):
        now = time.time()
        if not force and now - self.last_perf_log < 10.0:
            return
        elapsed = max(0.001, now - self.start_time) if hasattr(self, 'start_time') else 0.001
        interval = max(0.001, now - self.last_perf_time)
        rx_rate = (self.rx_count - self.last_perf_rx) / interval
        parse_rate = (self.packet_count - self.last_perf_parsed) / interval
        send_rate = (self.send_count - self.last_perf_sent) / interval
        line = (
            f"[PERF][YC] uptime={elapsed:.1f}s rx={self.rx_count} parsed={self.packet_count} "
            f"sent={self.send_count} worker_json={self.worker_json_send_count} send_err={self.send_error_count} "
            f"rx_rate={rx_rate:.1f}/s parse_rate={parse_rate:.1f}/s send_rate={send_rate:.1f}/s "
            f"data_q={self.data_queue.qsize()}/{self.data_queue.maxsize} "
            f"log_q={self.log_queue.qsize()}/{self.log_queue.maxsize} "
            f"rx_drop={self.rx_drop_count} log_drop={self.log_drop_count}"
        )
        print(line, flush=True)
        self.write_perf_log(line)
        self.last_perf_rx = self.rx_count
        self.last_perf_parsed = self.packet_count
        self.last_perf_sent = self.send_count
        self.last_perf_time = now
        self.last_perf_log = now

    def write_perf_log(self, line):
        try:
            self.perf_logger.log(line, important=("[!]" in str(line) or "Error" in str(line) or "Exception" in str(line)))
        except Exception:
            pass
        
    def start(self):
        self.config_mgr.load_config()
        self.config_mgr.load_filter_params()
        os.makedirs(self.log_dir, exist_ok=True)
        self.running = True
        
        print(f"[*] YaoCe -> DDM Bridge (SimVar Mode) Started.")
        print(f"[*] Filtered Parameters: {len(self.config_mgr.filter_params)}")
        print(f"[*] Targets: {self.config_mgr.targets}")
        self.start_parent_watchdog()
        
        self.logger_thread = threading.Thread(target=self.logging_loop, daemon=True)
        self.logger_thread.start()
        self.process_thread = threading.Thread(target=self.processing_loop, daemon=True)
        self.process_thread.start()
        try:
            self.receive_loop()
        finally:
            self.running = False
            try: self.process_thread.join(timeout=2.0)
            except Exception: pass
            try: self.logger_thread.join(timeout=2.0)
            except Exception: pass
            try: self.perf_logger.close()
            except Exception: pass

    def start_parent_watchdog(self):
        if not self.parent_pid:
            return
        def watch_parent():
            while self.running:
                time.sleep(1.0)
                if not is_process_alive(self.parent_pid):
                    print(f"[SYS] Parent process {self.parent_pid} is gone; YaoCe worker exiting.", flush=True)
                    self.running = False
                    break
        threading.Thread(target=watch_parent, daemon=True).start()

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
            sock.settimeout(1.0)
            
            print(f"[*] Listening on UDP {recv_port}...")
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                self.last_recv_time = time.time()
                self.rx_count += 1
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                self.enqueue_latest(self.data_queue, data, 'rx_drop_count')
                if self.rx_count <= 5 or self.rx_count % self.raw_log_sample == 0:
                    self.enqueue_latest(self.log_queue, ("original", data, addr, ts), 'log_drop_count')
                self.print_perf_stats()
        except Exception as e:
            print(f"[!] Receiver error: {e}")
        finally:
            self.running = False
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
                            if self.config_mgr.is_local_injection_target(target_ip, target_port):
                                cmd = {}
                                for var in ddm_msg.sim_vars:
                                    name = var.name if str(var.name).startswith(("PE.", "YC.")) else "YC." + var.name
                                    if var.type == ddm_pb2.DDMData.SimVar.Type.Value("Bool"):
                                        cmd[name] = bool(var.bool_value)
                                    elif var.type == ddm_pb2.DDMData.SimVar.Type.Value("Int"):
                                        cmd[name] = int(var.int_value)
                                    elif var.type == ddm_pb2.DDMData.SimVar.Type.Value("String"):
                                        cmd[name] = var.string_value
                                    else:
                                        cmd[name] = float(var.double_value)
                                payload = json.dumps(cmd, ensure_ascii=False).encode('utf-8')
                                self.worker_json_send_count += 1
                            else:
                                raw_bytes = ddm_msg.SerializeToString()
                                payload = base64.b64encode(raw_bytes)
                            send_sock.sendto(payload, (target_ip, target_port))
                            self.send_count += 1
                        
                        # Log converted visible data to queue
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        if self.packet_count <= 5 or self.packet_count % self.send_log_sample == 0:
                            vars_str = ", ".join([f"{var.name}={var.double_value}" for var in ddm_msg.sim_vars])
                            self.enqueue_latest(self.log_queue, ("send", ddm_msg.sim_time, vars_str, ts), 'log_drop_count')

                        # 严格按照用户要求的格式：[Live]Time: 38.00s | Sent40vars | Rate: 1.0x | Freq:50.0Hz
                        now = time.time()
                        if now - self.last_log_time >= self.live_log_interval:
                            elapsed = now - self.start_time
                            freq = (self.packet_count - self.last_packet_count) / (now - self.last_log_time)
                            print(f"[Live]Time: {elapsed:.2f}s | Sent{len(ddm_msg.sim_vars)}vars | Rate: 1.0x | Freq:{freq:.1f}Hz")
                            self.last_log_time = now
                            self.last_packet_count = self.packet_count
                    except Exception as e:
                        self.send_error_count += 1
                        print(f"[!] Send error: {e}")
                else:
                    if time.time() - self.last_log_time >= self.live_log_interval:
                        elapsed = time.time() - self.start_time
                        print(f"[Live]Time: {elapsed:.2f}s | Sent0vars | Rate: 1.0x | Freq:0.0Hz")
                        self.last_log_time = time.time()
                        self.last_packet_count = self.packet_count
            except queue.Empty: continue
            except Exception as e:
                print(f"[!] Processor error: {e}")
            finally:
                self.print_perf_stats()

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
            if now - last_flush_time >= 2.0:
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
        clock_codes = {"S0067", "DCSM34", "DCSH34", "DCSW34"}
        time_component_codes = {"A024", "A025", "A026", "A027", "A028", "DCSH34.d", "DCSH34.h", "DCSH34.m", "DCSH34.s", "DCSH34.ms", "DCSW34.d", "DCSW34.h", "DCSW34.m", "DCSW34.s", "DCSW34.ms"}
        beijing_time_codes = {"A029", "A02A", "A02B", "A02C", "A02D", "A02E"}
        time_values = {}

        def normalize_time_component_code(code):
            mapping = {
                "DCSH34.d": "A024", "DCSH34.h": "A025", "DCSH34.m": "A026", "DCSH34.s": "A027", "DCSH34.ms": "A028",
                "DCSW34.d": "A024", "DCSW34.h": "A025", "DCSW34.m": "A026", "DCSW34.s": "A027", "DCSW34.ms": "A028",
            }
            return mapping.get(code, code)

        def parse_numeric_value(val):
            if isinstance(val, (int, float)):
                return float(val)
            clean = str(val).strip()
            if not clean:
                return None
            try:
                return float(clean)
            except Exception:
                return None

        def is_valid_time_component(code, value):
            if value is None:
                return False
            code = normalize_time_component_code(code)
            if code == "A024": return 0 <= value <= 100000
            if code == "A025": return 0 <= value <= 23
            if code in ("A026", "A027"): return 0 <= value <= 59
            if code == "A028": return 0 <= value <= 999
            if code == "A029": return 1900 <= value <= 2200
            if code == "A02A": return 1 <= value <= 12
            if code == "A02B": return 1 <= value <= 31
            if code == "A02C": return 0 <= value <= 23
            if code in ("A02D", "A02E"): return 0 <= value <= 59
            return True

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

        def remember_time_value(code, value):
            normalized = normalize_time_component_code(code)
            numeric = parse_numeric_value(value)
            if is_valid_time_component(normalized, numeric):
                time_values[normalized] = numeric
                return True, numeric
            warn_key = (normalized, "invalid_time", str(value))
            if warn_key not in self.reported_warnings:
                print(f"[WARN] Invalid time component ignored: {normalized}={value}")
                self.reported_warnings.add(warn_key)
            return False, numeric

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
                        for code in ("A024", "A025", "A026", "A027", "A028"):
                            remember_time_value(code, parsed_clock[code])
                            add_to_sim_vars(self.config_mgr.map_to_sim_var(code), parsed_clock[code])
                    elif item.sys_ident == mapped_name:
                        warn_key = (mapped_name, "clock_fallback")
                        if warn_key not in self.reported_warnings:
                            print(f"[WARN] Clock field '{mapped_name}' has non-clock payload '{item.value}', ignored for PE/FMU safety.")
                            self.reported_warnings.add(warn_key)
                    else:
                        warn_key = (item.sys_ident, mapped_name, "clock_collision")
                        if warn_key not in self.reported_warnings:
                            print(f"[WARN] Ignored suffix-based remap '{item.sys_ident}' -> '{mapped_name}' because payload '{item.value}' is not a clock string.")
                            self.reported_warnings.add(warn_key)
                elif mapped_name in time_component_codes or mapped_name in beijing_time_codes:
                    ok, numeric = remember_time_value(mapped_name, item.value)
                    if ok:
                        add_to_sim_vars(sim_var_name, numeric)
                else:
                    add_to_sim_vars(sim_var_name, item.value)
            except Exception as e:
                print(f"[!] Unexpected error mapping field '{mapped_name}': {e}")

        expr_values = self.config_mgr.evaluate_expression_mappings(time_values)
        for sim_var, value in expr_values.items():
            add_to_sim_vars(sim_var, value)
            is_any_field_added = True
                    
        return msg if is_any_field_added else None

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    try:
        arch_bits = struct.calcsize('P') * 8
        mem_note = ""
        try:
            if sys.platform == 'win32':
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    mem_note = f" mem_free={stat.ullAvailPhys // (1024*1024)}MB virt_addr_free={stat.ullAvailVirtual // (1024*1024)}MB mem_load={stat.dwMemoryLoad}%"
        except Exception:
            pass
        print(f"[SYS] YaoCe standalone entry. root={root} pid={os.getpid()} arch={arch_bits}bit python={sys.executable} cwd={os.getcwd()}{mem_note}", flush=True)
        app = YaoCeLinkLayerApp(root)
        app.start()
    except Exception:
        text = traceback.format_exc()
        print(f"[!] YaoCe Fatal Error:\n{text}", flush=True)
        try:
            log_dir = os.path.join(root, "logs")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "yaoce_fatal.log"), "a", encoding="utf-8") as f:
                f.write(f"\n--- YaoCe Fatal {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(text)
        except Exception:
            pass
        raise
