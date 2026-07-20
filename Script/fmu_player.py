import os
import time
import socket
import base64
import threading
import platform
import zipfile
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import builtins
import json
import hashlib
import re
import queue
import traceback
import struct

class AsyncRotatingFileLogger:
    """Small bounded async logger for long-running worker diagnostics."""
    def __init__(self, path, max_bytes=10 * 1024 * 1024, backups=3, queue_size=1000, flush_interval=0.5, batch_size=100):
        self.path = path
        self.max_bytes = max(1024 * 1024, int(max_bytes))
        self.backups = max(1, int(backups))
        self.queue = queue.Queue(maxsize=max(10, int(queue_size)))
        self.flush_interval = max(0.1, float(flush_interval))
        self.batch_size = max(1, int(batch_size))
        self.stop_event = threading.Event()
        self.drop_count = 0
        self.thread = threading.Thread(target=self._loop, name="FmuWorkerAsyncLog", daemon=True)
        self.thread.start()

    def log(self, line, important=False):
        text = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n"
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
                        pending.insert(0, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [LOG] dropped {self.drop_count} perf log lines due to backpressure\n")
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
    if os.name == 'nt':
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
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

def start_parent_watchdog(stop_event=None):
    parent_pid = os.environ.get("FMUSOLVER_PARENT_PID", "")
    if not parent_pid:
        return
    def watch_parent():
        while True:
            time.sleep(1.0)
            if stop_event is not None and stop_event.is_set():
                return
            if not is_process_alive(parent_pid):
                print(f"[SYS] Parent process {parent_pid} is gone; FMU worker exiting.", flush=True)
                os._exit(0)
    threading.Thread(target=watch_parent, daemon=True).start()

# ── 优先使用环境变量传入的 C 盘安全目录，或退回默认 ──
_base_temp = os.environ.get('TEMP', tempfile.gettempdir() if 'tempfile' in sys.modules else "C:\\FmuSolver_Runtime")

def get_safe_windows_path(path):
    norm_path = os.path.normpath(path)
    if os.name != 'nt' or not os.path.exists(norm_path):
        return norm_path
    try:
        import ctypes
        buffer_size = 4096
        output = ctypes.create_unicode_buffer(buffer_size)
        result = ctypes.windll.kernel32.GetShortPathNameW(norm_path, output, buffer_size)
        if result and output.value != norm_path:
            return output.value
    except: pass
    return norm_path

def get_guaranteed_safe_workspace(app_dir, name="fmu_work_worker2"):
    base_dir = "C:\\FmuSolver_Runtime"
    try:
        os.makedirs(base_dir, exist_ok=True)
    except:
        base_dir = _base_temp
    
    candidate = os.path.join(base_dir, name)
    os.makedirs(candidate, exist_ok=True)
    return get_safe_windows_path(candidate)

def get_unique_safe_workspace(prefix="fmu_work_worker2"):
    base_dir = "C:\\FmuSolver_Runtime"
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        base_dir = _base_temp
    name = f"{prefix}_{os.getpid()}_{int(time.time() * 1000)}"
    candidate = os.path.join(base_dir, name)
    os.makedirs(candidate, exist_ok=True)
    return get_safe_windows_path(candidate)

def cleanup_old_workspaces(prefix="fmu_work_worker2", max_age_hours=12):
    base_dir = "C:\\FmuSolver_Runtime"
    if not os.path.isdir(base_dir):
        return
    cutoff = time.time() - max_age_hours * 3600.0
    for name in os.listdir(base_dir):
        if not name.startswith(prefix + "_"):
            continue
        path = os.path.join(base_dir, name)
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path)
        except Exception:
            pass

def _configure_unbuffered_output():
    try:
        stdout = getattr(sys, 'stdout', None)
        if stdout and hasattr(stdout, 'reconfigure'):
            stdout.reconfigure(line_buffering=True, write_through=True)
    except: pass
    old_print = builtins.print
    def flushed_print(*args, **kwargs):
        kwargs.setdefault('flush', True)
        return old_print(*args, **kwargs)
    builtins.print = flushed_print

_configure_unbuffered_output()

try:
    import fmpy
    from fmpy import instantiate_fmu, read_model_description
except ImportError:
    fmpy = None

try:
    import ddm_pb2
except ImportError:
    ddm_pb2 = None

def check_dll_arch(filepath):
    try:
        import struct
        with open(filepath, 'rb') as f:
            dos = f.read(64)
            if dos[:2] != b'MZ': return None
            ofs = struct.unpack('<I', dos[60:64])[0]
            f.seek(ofs + 4)
            m = struct.unpack('<H', f.read(2))[0]
            if m == 0x014c: return "win32"
            if m == 0x8664: return "win64"
    except: pass
    return None

def iter_resource_roots(root_dir):
    roots = []
    seen = set()

    def add(path):
        norm = os.path.normpath(path)
        if norm in seen or not os.path.isdir(norm):
            return
        seen.add(norm)
        roots.append(norm)

    add(root_dir)
    add(os.path.join(root_dir, ".."))
    add(os.path.join(root_dir, "..", "FmuSolver_Package"))
    add(os.path.join(root_dir, "..", "FmuSolver_Package05061502", "FmuSolver_Package"))
    add(os.path.join(root_dir, "fmu_work_worker2", "binaries", "win32"))
    add(os.path.join(root_dir, "fmu_work_worker2", "binaries", "win64"))
    return roots

def file_fingerprint(path):
    st = os.stat(path)
    seed = f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}"
    return hashlib.sha1(seed.encode('utf-8', errors='ignore')).hexdigest()

def normalize_guid(guid):
    return str(guid or '').strip().strip('{}').lower()

def binary_contains_guid(path, guid):
    """Return False when a cached FMU DLL clearly belongs to another modelDescription."""
    expected = normalize_guid(guid)
    if not expected or not os.path.exists(path):
        return True
    try:
        with open(path, 'rb') as f:
            data = f.read()
        found = {
            normalize_guid(m.decode('ascii', errors='ignore'))
            for m in re.findall(rb'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', data)
        }
        return not found or expected in found
    except Exception:
        return True

def normalize_var_key(name):
    return str(name or '').strip().replace('.', '_').replace(':', '_').replace('/', '_').replace(' ', '_')

def strip_source_prefix(name):
    text = str(name or '').strip()
    for prefix in ('PE.', 'YC.'):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text

RAW_TIME_TELEMETRY_NAMES = {
    'S0067', 'DCSM34', 'DCSH34', 'DCSW34',
    'A024', 'A025', 'A026', 'A027', 'A028',
    'A029', 'A02A', 'A02B', 'A02C', 'A02D', 'A02E',
    'DCSH34.d', 'DCSH34.h', 'DCSH34.m', 'DCSH34.s', 'DCSH34.ms',
    'DCSW34.d', 'DCSW34.h', 'DCSW34.m', 'DCSW34.s', 'DCSW34.ms',
}

def should_forward_telemetry_to_pe(name):
    if os.environ.get('FMUSOLVER_PE_FORWARD_RAW_TIME', '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return True
    return strip_source_prefix(name) not in RAW_TIME_TELEMETRY_NAMES

def parse_bool_value(value):
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)

def to_float32(value):
    return struct.unpack('<f', struct.pack('<f', float(value)))[0]

def normalize_external_real_value(name, value):
    clean_name = strip_source_prefix(name)
    val = to_float32(value)
    if 'ShelterRatio_CJinput' in clean_name:
        val = max(0.0, min(1.0, val))
        return round(val, 6)
    if 'SolarAngle_CJinput' in clean_name or 'solar_CJinput' in clean_name:
        return round(val, 6)
    return val

DEFAULT_INJECTION_BLACKLIST = set()

def load_injection_blacklist(root_dir):
    path = os.path.join(root_dir, "fmu_injection_blacklist.json")
    blacklist = set(DEFAULT_INJECTION_BLACKLIST)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            items = data.get("variables", data)
            if isinstance(items, dict):
                blacklist.update(str(k) for k in items.keys())
                return path, blacklist
            if isinstance(items, list):
                blacklist.update(str(k) for k in items)
                return path, blacklist
    except Exception:
        pass
    return path, blacklist

def append_injection_blacklist(path, variable, reason):
    variable = str(variable or '').strip()
    if not variable:
        return
    data = {"variables": {}}
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                old = json.load(f)
            if isinstance(old, dict):
                if isinstance(old.get("variables"), dict):
                    data = old
                else:
                    data["variables"] = {str(k): v for k, v in old.items()}
    except Exception:
        pass
    data.setdefault("variables", {})[variable] = {
        "reason": reason,
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

class FMUProcessor:
    def __init__(self, fmu_path):
        self.fmu_path = fmu_path
        # Use a per-run workspace so Windows DLL locks from an old worker never block a new FMU extraction.
        cleanup_old_workspaces("fmu_work_worker2")
        self.temp_dir = get_unique_safe_workspace("fmu_work_worker2")
        self.model_desc = None

    def check_and_prepare(self):
        if not self.model_desc and fmpy:
            self.model_desc = read_model_description(self.fmu_path, validate=False)
            print(f"[OK] FMU Metadata Loaded: {self.model_desc.modelName}")

        fmu_name = os.path.basename(self.fmu_path)
        marker_file = os.path.join(self.temp_dir, f"__extracted_{fmu_name}__")
        expected_marker = file_fingerprint(self.fmu_path)
        host_arch = "win64" if sys.maxsize > 2**32 else "win32"
        target_bin = os.path.join(self.temp_dir, "binaries", host_arch)

        core_lib_name = self.model_desc.modelIdentifier if self.model_desc else fmu_name.replace(".fmu", "")
        core_dll = os.path.join(target_bin, f"{core_lib_name}.dll")

        print(f"[*] Runtime workspace: {self.temp_dir}")
        print(f"[*] Extracting FMU into isolated workspace: {fmu_name}")
        with zipfile.ZipFile(self.fmu_path, 'r') as z:
            z.extractall(self.temp_dir)
        with open(marker_file, 'w', encoding='utf-8') as f: f.write(expected_marker)
        
        root_dir = os.path.abspath(os.path.dirname(sys.argv[0]) if sys.argv[1:] else os.getcwd())
        resource_roots = iter_resource_roots(root_dir)
        protected = ['kernel32.dll', 'user32.dll', 'ntdll.dll', 'advapi32.dll']
        os.makedirs(target_bin, exist_ok=True)

        copied = set()
        for search_root in resource_roots:
            for fname in os.listdir(search_root):
                ext = fname.lower().split('.')[-1] if '.' in fname else ''
                if ext not in ['dll', 'txt', 'dat', 'xml', 'ini', 'json']:
                    continue
                if fname.lower() in protected or fname.lower() in copied:
                    continue

                src_file = os.path.join(search_root, fname)
                target_file = os.path.join(target_bin, fname)
                if ext == 'dll':
                    if os.path.exists(target_file):
                        copied.add(fname.lower())
                        continue
                    arch = check_dll_arch(src_file)
                    if arch and arch != host_arch:
                        continue

                try:
                    shutil.copy2(src_file, target_file)
                    copied.add(fname.lower())
                except:
                    pass

        return self.model_desc

class DDMCommManager:
    def __init__(self, remote_ip="127.0.0.1", remote_port=8889, listen_port=8898, replace_dot=False):
        self.target_addr = (remote_ip, remote_port)
        self.viz_addr = ("127.0.0.1", 22345) # 专用图表端口，避免冲突
        raw_viz_ports = os.environ.get("FMUSOLVER_VIZ_PORTS", "22345,8888")
        self.viz_addrs = []
        for port_text in raw_viz_ports.split(','):
            try:
                addr = ("127.0.0.1", int(port_text.strip()))
                if addr not in self.viz_addrs:
                    self.viz_addrs.append(addr)
            except Exception:
                pass
        if self.viz_addr not in self.viz_addrs:
            self.viz_addrs.insert(0, self.viz_addr)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_received_data = None
        self.received_queue = queue.Queue(maxsize=1000)
        self.listen_port = listen_port
        self.replace_dot = replace_dot
        self.recv_count = 0
        self.recv_drop_count = 0
        self.ext_send_count = 0
        self.viz_send_count = 0
        self.viz_echo_send_count = 0
        self.send_error_count = 0
        self.last_ext_var_count = 0
        self.last_ext_payload_bytes = 0
        self.last_viz_var_count = 0
        self.last_viz_payload_bytes = 0
        self.viz_send_max_hz = max(0.1, float(os.environ.get("FMUSOLVER_VIZ_SEND_HZ", "10.0")))
        self.viz_send_interval = 1.0 / self.viz_send_max_hz
        self.last_viz_send_wall = 0.0
        self.viz_skip_count = 0

    def start_receiver(self):
        def listen_loop():
            recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            actual_port = self.listen_port
            for _ in range(10):
                try:
                    recv_sock.bind(("0.0.0.0", actual_port))
                    print(f"[*] Command Receiver bound to UDP port {actual_port}")
                    break
                except: actual_port += 1
            else: return
            while True:
                data, _ = recv_sock.recvfrom(65536)
                self.recv_count += 1
                self.last_received_data = data
                try:
                    self.received_queue.put_nowait(data)
                except queue.Full:
                    self.recv_drop_count += 1
                    try: self.received_queue.get_nowait()
                    except Exception: pass
                    try: self.received_queue.put_nowait(data)
                    except Exception: pass
        threading.Thread(target=listen_loop, daemon=True).start()

    def send_fmu_data(self, sim_time, variables, chunk_size=200, extra_external_variables=None):
        if ddm_pb2 is None or not variables: return
        external_variables = dict(variables)
        if extra_external_variables:
            external_variables.update(extra_external_variables)

        viz_variables = dict(variables)
        if extra_external_variables and os.environ.get("FMUSOLVER_VIZ_INCLUDE_YC", "1").strip().lower() not in ("0", "false", "no", "off"):
            for name, val in extra_external_variables.items():
                name_text = str(name)
                viz_name = name_text if name_text.startswith(("PE.", "YC.")) else f"YC.{name_text}"
                viz_variables[viz_name] = val

        var_names = list(viz_variables.keys())
        ext_var_names = list(external_variables.keys())
        for i in range(0, len(ext_var_names), chunk_size):
            ext_chunk_names = ext_var_names[i:i + chunk_size]
            
            # --- 1. 组装给外部的包 (应用重命名逻辑) ---
            packet_ext = ddm_pb2.DDMData()
            packet_ext.machine_time = time.time()
            packet_ext.sim_time = sim_time
            
            for name in ext_chunk_names:
                val = external_variables[name]

                # 配置外部包
                svar_ext = packet_ext.sim_vars.add()
                svar_ext.name = name.replace('.', '_') if self.replace_dot else name

                # 类型推断与赋值
                if isinstance(val, bool):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Bool")
                    svar_ext.type = vt
                    svar_ext.bool_value = 1.0 if val else 0.0
                elif isinstance(val, int):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Int")
                    svar_ext.type = vt
                    svar_ext.int_value = float(val)
                elif isinstance(val, float):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Double")
                    svar_ext.type = vt
                    svar_ext.double_value = val
                elif isinstance(val, str):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("String")
                    svar_ext.type = vt
                    svar_ext.string_value = str(val)

            try:
                raw_ext = packet_ext.SerializeToString()
                self.last_ext_var_count = len(ext_chunk_names)
                self.last_ext_payload_bytes = len(raw_ext)
                self.sock.sendto(base64.b64encode(raw_ext).decode('ascii').encode('ascii'), self.target_addr)
                self.ext_send_count += 1
            except Exception:
                self.send_error_count += 1

        now_wall = time.perf_counter()
        if now_wall - self.last_viz_send_wall < self.viz_send_interval:
            self.viz_skip_count += 1
            return
        self.last_viz_send_wall = now_wall

        for i in range(0, len(var_names), chunk_size):
            chunk_names = var_names[i:i + chunk_size]

            # --- 2. 组装给本地看板的包 (绝对不重命名) ---
            packet_viz = ddm_pb2.DDMData()
            packet_viz.machine_time = time.time()
            packet_viz.sim_time = sim_time

            for name in chunk_names:
                val = viz_variables[name]

                # 配置看板包
                svar_viz = packet_viz.sim_vars.add()
                svar_viz.name = name

                # 类型推断与赋值
                if isinstance(val, bool):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Bool")
                    svar_viz.type = vt
                    svar_viz.bool_value = 1.0 if val else 0.0
                elif isinstance(val, int):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Int")
                    svar_viz.type = vt
                    svar_viz.int_value = float(val)
                elif isinstance(val, float):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Double")
                    svar_viz.type = vt
                    svar_viz.double_value = val
                elif isinstance(val, str):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("String")
                    svar_viz.type = vt
                    svar_viz.string_value = str(val)
                    
            try:
                raw_viz = packet_viz.SerializeToString()
                self.last_viz_var_count = len(chunk_names)
                self.last_viz_payload_bytes = len(raw_viz)
                viz_payload = base64.b64encode(raw_viz).decode('ascii').encode('ascii')
                for viz_addr in self.viz_addrs:
                    self.sock.sendto(viz_payload, viz_addr)
                self.viz_send_count += 1
            except Exception:
                self.send_error_count += 1

    def send_injection_echo_to_viz(self, sim_time, variables, prefix="PE"):
        """Mirror external injected variables to the local dashboard for observability."""
        if ddm_pb2 is None or not variables:
            return
        packet = ddm_pb2.DDMData()
        packet.machine_time = time.time()
        packet.sim_time = sim_time
        for name, val in variables.items():
            svar = packet.sim_vars.add()
            name_text = str(name)
            svar.name = name_text if name_text.startswith(('PE.', 'YC.')) else f"{prefix}.{name_text}"
            if isinstance(val, bool):
                svar.type = ddm_pb2.DDMData.SimVar.Type.Value("Bool")
                svar.bool_value = 1.0 if val else 0.0
            elif isinstance(val, int) and not isinstance(val, bool):
                svar.type = ddm_pb2.DDMData.SimVar.Type.Value("Int")
                svar.int_value = float(val)
            elif isinstance(val, str):
                try:
                    num = float(val)
                    svar.type = ddm_pb2.DDMData.SimVar.Type.Value("Double")
                    svar.double_value = num
                except Exception:
                    svar.type = ddm_pb2.DDMData.SimVar.Type.Value("String")
                    svar.string_value = val
            else:
                svar.type = ddm_pb2.DDMData.SimVar.Type.Value("Double")
                svar.double_value = float(val)
        try:
            raw = packet.SerializeToString()
            payload = base64.b64encode(raw).decode('ascii').encode('ascii')
            for viz_addr in self.viz_addrs:
                self.sock.sendto(payload, viz_addr)
            self.viz_echo_send_count += 1
        except Exception:
            pass

    def normalize_injection_echo_vars(self, variables, prefix="PE"):
        normalized = {}
        if not variables:
            return normalized
        for name, val in variables.items():
            name_text = str(name)
            out_name = name_text if name_text.startswith(('PE.', 'YC.')) else f"{prefix}.{name_text}"
            normalized[out_name] = val
        return normalized

class FMUPlayer:
    def __init__(self, fmu_path, remote_ip="127.0.0.1", remote_port=8889, sim_id=None, sync_vars_file=None, control_port=8898, replace_dot=False, pause_file=None):
        self.fmu_path = fmu_path
        self.sim_id = sim_id
        self.processor = FMUProcessor(fmu_path)
        self.comm = DDMCommManager(remote_ip=remote_ip, remote_port=remote_port, listen_port=control_port, replace_dot=replace_dot)
        self.sync_vars_file = sync_vars_file
        self.pause_file = pause_file

    def run(self, step_size=0.01, sim_time=float('inf'), sim_rate=1.0, sample_freq=0.0, init_params=None):
        md = self.processor.check_and_prepare()
        if not md or not fmpy: return False
        self.comm.start_receiver()
        
        host_arch = "win64" if sys.maxsize > 2**32 else "win32"
        dll_path = os.path.abspath(os.path.join(self.processor.temp_dir, "binaries", host_arch))
        root_dir = os.path.abspath(os.path.dirname(sys.argv[0]) if sys.argv[1:] else os.getcwd())
        blacklist_path, injection_blacklist = load_injection_blacklist(root_dir)
        if injection_blacklist:
            print(f"[*] Injection blacklist loaded: {len(injection_blacklist)} vars from {blacklist_path}", flush=True)
        perf_log_path = os.path.join(root_dir, "fmu_worker_perf.log")
        perf_logger = AsyncRotatingFileLogger(
            perf_log_path,
            max_bytes=int(os.environ.get("FMUSOLVER_FMU_PERF_LOG_MB", "10")) * 1024 * 1024,
            backups=int(os.environ.get("FMUSOLVER_FMU_PERF_LOG_BACKUPS", "3")),
            queue_size=int(os.environ.get("FMUSOLVER_FMU_PERF_LOG_QUEUE", "1000")),
            flush_interval=float(os.environ.get("FMUSOLVER_FMU_PERF_LOG_FLUSH", "0.5")),
            batch_size=int(os.environ.get("FMUSOLVER_FMU_PERF_LOG_BATCH", "100")),
        )

        def append_perf_log(line):
            try:
                perf_logger.log(line, important=("[ERROR]" in str(line) or "[!]" in str(line)))
            except Exception:
                pass
        append_perf_log(f"[SESSION][FMU] start fmu={os.path.basename(self.fmu_path)} pid={os.getpid()} step={step_size} sample_freq={sample_freq} sim_rate={sim_rate}")
        
        for p in [dll_path, root_dir]:
            if os.path.exists(p):
                if hasattr(os, 'add_dll_directory'): os.add_dll_directory(p)
                os.environ['PATH'] = p + os.pathsep + os.environ.get('PATH', '')

        orig_cwd = os.getcwd()
        fmu_instance = None
        run_ok = False
        stop_requested = False
        try:
            if os.path.exists(dll_path):
                os.chdir(dll_path)
                import ctypes
                from ctypes import wintypes
                
                # Python 3.8+ compatibility: winmode=0 or direct API call
                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel32.LoadLibraryW.argtypes = [wintypes.LPCWSTR]
                kernel32.LoadLibraryW.restype = wintypes.HMODULE

                for f in sorted(os.listdir(dll_path)):
                    if f.lower().endswith('.dll'):
                        fpath = os.path.join(dll_path, f)
                        try: 
                            ctypes.CDLL(fpath, winmode=0)
                        except: 
                            try:
                                kernel32.LoadLibraryW(fpath)
                            except:
                                pass

            fmu_instance = fmpy.instantiate_fmu(unzipdir=self.processor.temp_dir, model_description=md, fmi_type='CoSimulation')
            fmu_instance.setupExperiment(startTime=0.0)

            # 自动修复路径参数
            vars_list = getattr(md, 'modelVariables', []) + getattr(md, 'scalarVariables', [])
            for v in vars_list:
                t = getattr(v, 'type', 'Real')
                if t == 'String' and getattr(v, 'start', ''):
                    if '.txt' in v.start.lower() and (':' in v.start):
                        fname = os.path.basename(v.start.replace('\\', '/'))
                        abs_p = os.path.abspath(fname).replace('\\', '/')
                        if os.path.exists(abs_p):
                            fsize = os.path.getsize(abs_p)
                            print(f"[*] Verified path exists: {abs_p} (Size: {fsize} bytes)")
                        else:
                            print(f"[!] CRITICAL: File NOT FOUND at {abs_p}")
                        fmu_instance.setString([v.valueReference], [abs_p])
                        print(f"[*] Overriding filepath: {v.name} -> {abs_p}")

            # 旧版FMU允许在 enterInitializationMode 之前 setReal；
            # 新版MWORKS(26.1.2+)导出的FMU会报 "invalid execution timing"，
            # 需要在 InitializationMode 内设置。两阶段尝试以兼容新旧FMU。
            deferred_sets = []

            def _try_set(v_obj, t, val, label, defer=True):
                try:
                    if t == 'Real': fmu_instance.setReal([v_obj.valueReference], [float(val)])
                    elif t == 'Integer': fmu_instance.setInteger([v_obj.valueReference], [int(val)])
                    elif t == 'Boolean': fmu_instance.setBoolean([v_obj.valueReference], [bool(val)])
                    return True
                except Exception as e:
                    if defer:
                        deferred_sets.append((v_obj, t, val, label))
                    else:
                        print(f"[!] Cannot set {label} = {val} in either phase: {e}")
                    return False

            if init_params:
                print("[*] Injecting initialization parameters...")
                for k, v in init_params.items():
                    if k.startswith("Table_"):
                        try:
                            rows = [r.split(',') for r in str(v).split(';') if r.strip()]
                            if rows:
                                for i, row in enumerate(rows):
                                    for j, val in enumerate(row):
                                        cands = [f"{k}[{i+1},{j+1}]", f"{k}[{i+1}, {j+1}]"]
                                        v_obj = next((mv for mv in vars_list if mv.name in cands), None)
                                        if v_obj:
                                            _try_set(v_obj, 'Real', val.strip(), f"{k}[{i+1},{j+1}]")
                                print(f"[OK] Parsed and injected table {k} ({len(rows)}x{len(rows[0])})")
                        except Exception as e:
                            print(f"[!] Error parsing table {k}: {e}")
                    else:
                        v_obj = next((mv for mv in vars_list if mv.name == k), None)
                        if v_obj:
                            t = getattr(v_obj, 'type', 'Real')
                            if _try_set(v_obj, t, v, k):
                                print(f"[OK] Set param {k} = {v}")

            fmu_instance.enterInitializationMode()
            if deferred_sets:
                print(f"[*] Retrying {len(deferred_sets)} params inside InitializationMode (new MWORKS FMU)...")
                retry_list, deferred_sets = deferred_sets, []
                for v_obj, t, val, label in retry_list:
                    if _try_set(v_obj, t, val, label, defer=False):
                        print(f"[OK] Set param {label} = {val} (init mode)")
            fmu_instance.exitInitializationMode()

            # 建立 FMU 变量名查找索引 (支持模糊匹配)
            fmu_vars_map = {v.name: v for v in vars_list}
            fmu_vars_fuzzy = {v.name.replace('.', '_').replace(':', '_'): v.name for v in vars_list}

            # 变量映射处理 (支持 Alias)
            target_vars = set()
            var_mapping = {} # FMU_VarName -> DisplayName
            found_count = 0
            missing_vars = []

            if self.sync_vars_file and os.path.exists(self.sync_vars_file):
                try:
                    with open(self.sync_vars_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    field_list = data.get("fields", []) if isinstance(data, dict) else data
                    for item in field_list:
                        if isinstance(item, dict):
                            name = item.get("name")
                            source = item.get("source") or name
                            if not item.get("sync", True): continue
                            
                            # 多级查找策略
                            actual_fmu_name = None
                            # 1. 精确匹配 Source
                            if source in fmu_vars_map: actual_fmu_name = source
                            # 2. 模糊匹配 Source
                            if not actual_fmu_name:
                                actual_fmu_name = fmu_vars_fuzzy.get(source.replace('.', '_').replace(':', '_'))
                            # 3. 如果 Source 找不到且与 Name 不同，尝试匹配 Name
                            if not actual_fmu_name and source != name:
                                if name in fmu_vars_map: actual_fmu_name = name
                                if not actual_fmu_name:
                                    actual_fmu_name = fmu_vars_fuzzy.get(name.replace('.', '_').replace(':', '_'))
                            
                            # 4. 终极兜底：后缀匹配 (处理 Modelica 层次结构路径，如 model.sub.var -> var)
                            if not actual_fmu_name:
                                search_suffix = "." + source if "." not in source else source
                                for fmu_n in fmu_vars_map.keys():
                                    if fmu_n.endswith(source) or (source.startswith("[") and fmu_n.endswith(source)):
                                        actual_fmu_name = fmu_n
                                        break

                            if actual_fmu_name:
                                target_vars.add(actual_fmu_name)
                                var_mapping[actual_fmu_name] = name
                                found_count += 1
                            else:
                                missing_vars.append(source)
                except Exception as e:
                    print(f"[!] Sync file read error: {e}")

            print(f"[*] Variable Filter Summary: {found_count} found, {len(missing_vars)} missing (Total FMU Vars: {len(vars_list)})")
            if missing_vars:
                print(f"[!] Missing variables (first 20): {', '.join(missing_vars[:20])}")

            def is_sync(n): return n in target_vars

            v_real = [v for v in vars_list if getattr(v, 'type', 'Real') == 'Real' and is_sync(v.name)]
            v_int  = [v for v in vars_list if getattr(v, 'type', 'Integer') == 'Integer' and is_sync(v.name)]
            v_bool = [v for v in vars_list if getattr(v, 'type', 'Boolean') == 'Boolean' and is_sync(v.name)]
            
            def get_out_name(fmu_name):
                return var_mapping.get(fmu_name, fmu_name)

            real_vr_map = {v.name: v.valueReference for v in v_real}
            int_vr_map = {v.name: v.valueReference for v in v_int}
            bool_vr_map = {v.name: v.valueReference for v in v_bool}

            def is_runtime_settable(v):
                causality = str(getattr(v, 'causality', '') or '').lower()
                variability = str(getattr(v, 'variability', '') or '').lower()
                return causality == 'input' or (causality == 'parameter' and variability == 'tunable')

            injectable_vars = [v for v in vars_list if is_runtime_settable(v)]
            input_real_vr_map = {v.name: v.valueReference for v in injectable_vars if getattr(v, 'type', 'Real') == 'Real'}
            input_int_vr_map = {v.name: v.valueReference for v in injectable_vars if getattr(v, 'type', 'Integer') == 'Integer'}
            input_bool_vr_map = {v.name: v.valueReference for v in injectable_vars if getattr(v, 'type', 'Boolean') == 'Boolean'}
            input_all_names = list(input_real_vr_map) + list(input_int_vr_map) + list(input_bool_vr_map)
            print(f"[*] Runtime injectable variables: {len(input_all_names)} (Real={len(input_real_vr_map)}, Int={len(input_int_vr_map)}, Bool={len(input_bool_vr_map)})")
            input_fuzzy = {}
            for n in input_all_names:
                for key in {normalize_var_key(n), normalize_var_key(n.split('.')[-1]), normalize_var_key(n.split(':')[-1])}:
                    input_fuzzy.setdefault(key, n)

            def resolve_input_name(name):
                key = strip_source_prefix(name)
                if key in input_real_vr_map or key in input_int_vr_map or key in input_bool_vr_map:
                    return key
                norm = normalize_var_key(key)
                if norm in input_fuzzy:
                    return input_fuzzy[norm]
                for candidate in input_all_names:
                    if candidate.endswith(key) or normalize_var_key(candidate).endswith(norm):
                        return candidate
                return None

            current_time = 0.0
            next_sample_time = 0.0
            sim_wall_anchor = time.perf_counter()
            sim_time_anchor = current_time
            last_log_wall = time.perf_counter()
            last_log_pct = -1
            paused = False
            last_injection_log_wall = 0.0
            latest_telemetry_for_pe = {}
            telemetry_ttl_sec = max(0.2, float(os.environ.get("FMUSOLVER_YC_MERGE_TTL_SEC", "3.0")))
            telemetry_max_vars = max(1, int(os.environ.get("FMUSOLVER_YC_MERGE_MAX_VARS", "500")))
            last_perf_log_wall = time.perf_counter()
            control_cmd_count = 0
            control_error_count = 0
            recent_injections = []
            last_perf_snapshot = ""
            missing_input_cache = set()
            last_applied_injection = None
            viz_echo_cache = {}
            viz_echo_last_send = 0.0
            viz_echo_interval = max(0.05, float(os.environ.get("FMUSOLVER_VIZ_INJECTION_ECHO_INTERVAL", "0.2")))
            last_injection_recv_log_wall = 0.0
            pending_limited_injection = {}
            limited_inject_freq = max(0.1, float(os.environ.get("FMUSOLVER_YC_INJECT_FREQ", str(min(5.0, sample_freq or 5.0)))))
            limited_inject_interval = 1.0 / limited_inject_freq
            last_limited_inject_wall = 0.0
            ext_inject_grace_sim_sec = max(0.0, float(os.environ.get("FMUSOLVER_EXT_INJECT_GRACE_SIM_SEC", "2.0")))
            ext_grace_logged = False
            external_inject_state = {}
            external_inject_min_interval = max(0.02, float(os.environ.get("FMUSOLVER_EXT_INJECT_MIN_INTERVAL", "0.2")))
            sensitive_inject_min_interval = max(external_inject_min_interval, float(os.environ.get("FMUSOLVER_SENSITIVE_INJECT_MIN_INTERVAL", "1.0")))
            external_inject_epsilon = max(0.0, float(os.environ.get("FMUSOLVER_EXT_INJECT_EPS", "1e-5")))
            sensitive_inject_names = tuple(
                item.strip() for item in os.environ.get(
                    "FMUSOLVER_SENSITIVE_INJECT_NAMES",
                    "ShelterRatio_CJinput,SolarAngle_CJinput,solar_CJinput"
                ).split(',') if item.strip()
            )
            injection_stdout_interval = max(1.0, float(os.environ.get("FMUSOLVER_INJECTION_STDOUT_INTERVAL", "10.0")))
            last_injection_stdout_wall = 0.0

            def remember_injection(source, actual, kind, value, status):
                recent_injections.append({
                    "wall": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "sim_time": current_time,
                    "source": str(source),
                    "actual": str(actual or ""),
                    "kind": kind,
                    "value": repr(value),
                    "status": status,
                })
                if len(recent_injections) > 20:
                    del recent_injections[:len(recent_injections) - 20]

            def should_apply_external_injection(source, actual, value):
                if not str(source).startswith(("PE.", "YC.")):
                    return True
                now_state = time.perf_counter()
                clean_source = strip_source_prefix(source)
                compare_value = normalize_external_real_value(source, value)
                is_sensitive = any(token in clean_source or token in str(actual or "") for token in sensitive_inject_names)
                min_interval = sensitive_inject_min_interval if is_sensitive else external_inject_min_interval
                key = str(actual or clean_source)
                old_value, old_wall = external_inject_state.get(key, (None, 0.0))
                try:
                    changed = old_value is None or abs(float(compare_value) - float(old_value)) > external_inject_epsilon
                except Exception:
                    changed = old_value != compare_value
                if not changed and now_state - old_wall < min_interval:
                    remember_injection(source, actual, "Skipped", value, "unchanged_throttled")
                    return False
                if now_state - old_wall < min_interval:
                    remember_injection(source, actual, "Skipped", value, "rate_limited")
                    return False
                external_inject_state[key] = (compare_value, now_state)
                return True
            
            print(f"[*] Simulation Loop Started. Step={step_size}s, Rate={sim_rate}x")

            while current_time <= sim_time:
                while True:
                    try:
                        raw_cmd = self.comm.received_queue.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        cmd = json.loads(raw_cmd.decode('utf-8'))
                        control_cmd_count += 1
                        # Telemetry bridge sends pure PE./YC. variable JSON directly to the worker
                        # and intentionally has no GUI session id. Keep session checks for GUI
                        # control commands, but do not drop external variable injections.
                        has_session_id = "sim_id" in cmd
                        has_external_vars = any(str(k).startswith(("PE.", "YC.")) for k in cmd.keys())
                        if self.sim_id and has_session_id and cmd.get("sim_id") != self.sim_id:
                            self.comm.last_received_data = None
                            continue
                        if self.sim_id and not has_session_id and not has_external_vars:
                            self.comm.last_received_data = None
                            continue
                        if cmd.get("exit"):
                            stop_requested = True
                            break
                        if "pause" in cmd:
                            paused = bool(cmd.get("pause"))
                            print(f"[*] Simulation {'Paused' if paused else 'Resumed'}", flush=True)
                        if "resume" in cmd and cmd.get("resume"):
                            paused = False
                            print("[*] Simulation Resumed", flush=True)
                        if "sim_rate" in cmd:
                            sim_rate = float(cmd["sim_rate"])
                            sim_wall_anchor = time.perf_counter()
                            sim_time_anchor = current_time
                        if "sample_freq" in cmd:
                            sample_freq = float(cmd["sample_freq"])
                        if "yc_inject_freq" in cmd:
                            limited_inject_freq = max(0.1, float(cmd["yc_inject_freq"]))
                            limited_inject_interval = 1.0 / limited_inject_freq
                        injected_count = 0
                        missing_injection = []
                        injected_echo = {}
                        for k, v in cmd.items():
                            if k in ("sim_id", "exit", "pause", "resume", "sim_rate", "step_size", "sim_time", "sample_freq", "yc_inject_freq", "__apply_yc_now"):
                                continue
                            is_rate_limited_external = str(k).startswith(("PE.", "YC."))
                            if str(k).startswith("YC."):
                                pe_name = strip_source_prefix(k)
                                if should_forward_telemetry_to_pe(pe_name):
                                    latest_telemetry_for_pe[pe_name] = (v, time.perf_counter())
                                if len(latest_telemetry_for_pe) > telemetry_max_vars:
                                    overflow = len(latest_telemetry_for_pe) - telemetry_max_vars
                                    for old_name, _ in sorted(latest_telemetry_for_pe.items(), key=lambda item: item[1][1])[:overflow]:
                                        latest_telemetry_for_pe.pop(old_name, None)
                            if is_rate_limited_external and not cmd.get("__apply_yc_now"):
                                pending_limited_injection[str(k)] = v
                                continue
                            if is_rate_limited_external and current_time < ext_inject_grace_sim_sec:
                                pending_limited_injection[str(k)] = v
                                continue
                            if is_rate_limited_external:
                                display_value = v
                                if isinstance(v, (int, float)) and not isinstance(v, bool):
                                    display_value = normalize_external_real_value(k, v)
                                injected_echo[str(k)] = display_value
                            if str(k) in missing_input_cache:
                                continue
                            actual = resolve_input_name(k)
                            if actual and actual in injection_blacklist:
                                remember_injection(k, actual, "Skipped", v, "blacklisted")
                                continue
                            if actual and not should_apply_external_injection(k, actual, v):
                                continue
                            if actual in input_real_vr_map:
                                try:
                                    normalized_v = normalize_external_real_value(k, v) if is_rate_limited_external else float(v)
                                    fmu_instance.setReal([input_real_vr_map[actual]], [normalized_v])
                                    injected_count += 1
                                    injected_echo[str(k)] = normalized_v
                                    remember_injection(k, actual, "Real", normalized_v, "applied")
                                    last_applied_injection = {"source": str(k), "actual": str(actual), "kind": "Real", "value": repr(normalized_v), "sim_time": current_time}
                                    if time.perf_counter() - last_injection_stdout_wall > injection_stdout_interval:
                                        print(f"[*] Injected Real {strip_source_prefix(k)} <- {k} = {normalized_v}", flush=True); last_injection_stdout_wall = time.perf_counter()
                                except Exception as set_e:
                                    remember_injection(k, actual, "Real", v, f"setReal failed: {set_e}")
                                    missing_injection.append(f"{k}->{actual} setReal failed: {set_e}")
                            elif actual in input_int_vr_map:
                                try:
                                    fmu_instance.setInteger([input_int_vr_map[actual]], [int(v)])
                                    injected_count += 1
                                    injected_echo[str(k)] = int(v)
                                    remember_injection(k, actual, "Integer", v, "applied")
                                    last_applied_injection = {"source": str(k), "actual": str(actual), "kind": "Integer", "value": repr(v), "sim_time": current_time}
                                    if time.perf_counter() - last_injection_stdout_wall > injection_stdout_interval:
                                        print(f"[*] Injected Integer {strip_source_prefix(k)} <- {k} = {v}", flush=True); last_injection_stdout_wall = time.perf_counter()
                                except Exception as set_e:
                                    remember_injection(k, actual, "Integer", v, f"setInteger failed: {set_e}")
                                    missing_injection.append(f"{k}->{actual} setInteger failed: {set_e}")
                            elif actual in input_bool_vr_map:
                                try:
                                    bool_v = parse_bool_value(v)
                                    fmu_instance.setBoolean([input_bool_vr_map[actual]], [bool_v])
                                    injected_count += 1
                                    injected_echo[str(k)] = bool_v
                                    remember_injection(k, actual, "Boolean", v, "applied")
                                    last_applied_injection = {"source": str(k), "actual": str(actual), "kind": "Boolean", "value": repr(v), "sim_time": current_time}
                                    if time.perf_counter() - last_injection_stdout_wall > injection_stdout_interval:
                                        print(f"[*] Injected Boolean {strip_source_prefix(k)} <- {k} = {v}", flush=True); last_injection_stdout_wall = time.perf_counter()
                                except Exception as set_e:
                                    remember_injection(k, actual, "Boolean", v, f"setBoolean failed: {set_e}")
                                    missing_injection.append(f"{k}->{actual} setBoolean failed: {set_e}")
                            else:
                                remember_injection(k, actual, "Unknown", v, "missing")
                                missing_input_cache.add(str(k))
                                missing_injection.append(str(k))
                        if time.perf_counter() - last_injection_log_wall > 5.0:
                            total_cmd = len([k for k in cmd if k not in ("sim_id", "exit", "pause", "resume", "sim_rate", "step_size", "sim_time", "sample_freq", "yc_inject_freq", "__apply_yc_now")])
                            if missing_injection:
                                print(f"[!] Injection summary: {injected_count}/{total_cmd} applied; missing: {', '.join(missing_injection[:8])}", flush=True)
                            elif injected_count:
                                print(f"[*] Injection summary: {injected_count}/{total_cmd} applied", flush=True)
                            last_injection_log_wall = time.perf_counter()
                        if injected_echo:
                            viz_echo_cache.update(self.comm.normalize_injection_echo_vars(injected_echo))
                            if time.perf_counter() - last_injection_recv_log_wall > 5.0:
                                pe_count = sum(1 for name in injected_echo if str(name).startswith("PE."))
                                yc_count = sum(1 for name in injected_echo if str(name).startswith("YC."))
                                print(f"[*] Applied external variables mirrored to dashboard: PE={pe_count} YC={yc_count} pending={len(pending_limited_injection)}", flush=True)
                                last_injection_recv_log_wall = time.perf_counter()
                    except Exception as e:
                        control_error_count += 1
                        print(f"[!] Control command error: {e}", flush=True)
                now_limited_inject = time.perf_counter()
                if pending_limited_injection and current_time < ext_inject_grace_sim_sec:
                    if not ext_grace_logged:
                        print(f"[*] External PE/YC injection delayed until sim_time >= {ext_inject_grace_sim_sec:.2f}s for FMU startup stability.", flush=True)
                        ext_grace_logged = True
                elif pending_limited_injection and now_limited_inject - last_limited_inject_wall >= limited_inject_interval:
                    apply_cmd = {"sim_id": self.sim_id or "", "__apply_yc_now": True}
                    apply_cmd.update(pending_limited_injection)
                    pending_limited_injection = {}
                    last_limited_inject_wall = now_limited_inject
                    try:
                        self.comm.received_queue.put_nowait(json.dumps(apply_cmd).encode('utf-8'))
                    except queue.Full:
                        try: self.comm.received_queue.get_nowait()
                        except Exception: pass
                        try: self.comm.received_queue.put_nowait(json.dumps(apply_cmd).encode('utf-8'))
                        except Exception: pass
                if stop_requested:
                    run_ok = True
                    print("[*] Simulation exit requested.", flush=True)
                    break
                self.comm.last_received_data = None

                if self.pause_file:
                    file_paused = os.path.exists(self.pause_file)
                    if file_paused != paused:
                        paused = file_paused
                        print(f"[*] Simulation {'Paused' if paused else 'Resumed'} by pause flag", flush=True)

                if paused:
                    time.sleep(0.05)
                    sim_wall_anchor = time.perf_counter()
                    sim_time_anchor = current_time
                    continue

                now_echo = time.perf_counter()
                if viz_echo_cache and now_echo - viz_echo_last_send >= viz_echo_interval:
                    self.comm.send_injection_echo_to_viz(current_time, viz_echo_cache)
                    viz_echo_cache.clear()
                    viz_echo_last_send = now_echo

                # doStep in FMPy may return None on success. Error handling is managed internally via exceptions.
                fmu_instance.doStep(currentCommunicationPoint=current_time, communicationStepSize=step_size)
                
                do_sample = True
                if sample_freq > 0:
                    if current_time >= next_sample_time - 1e-6:
                        next_sample_time += (1.0 / sample_freq)
                        do_sample = True
                    else: do_sample = False

                if do_sample:
                    out = {}
                    if v_real:
                        vals = fmu_instance.getReal([v.valueReference for v in v_real])
                        for v, val in zip(v_real, vals): out[get_out_name(v.name)] = float(val)
                    if v_int:
                        vals = fmu_instance.getInteger([v.valueReference for v in v_int])
                        for v, val in zip(v_int, vals): out[get_out_name(v.name)] = int(val)
                    if v_bool:
                        vals = fmu_instance.getBoolean([v.valueReference for v in v_bool])
                        for v, val in zip(v_bool, vals): out[get_out_name(v.name)] = bool(val)
                    now_for_yc = time.perf_counter()
                    stale_yc = [name for name, (_, ts) in latest_telemetry_for_pe.items() if now_for_yc - ts > telemetry_ttl_sec]
                    for name in stale_yc:
                        latest_telemetry_for_pe.pop(name, None)
                    fresh_yc_for_pe = {name: value for name, (value, _) in latest_telemetry_for_pe.items()}
                    self.comm.send_fmu_data(current_time, out, extra_external_variables=fresh_yc_for_pe)

                # Keep logs tied to wall-clock time so high-speed simulation does not flood the GUI.
                now_wall = time.perf_counter()
                pct = min(100, int((current_time / sim_time) * 100)) if sim_time > 0 and sim_time != float('inf') else 0
                if (now_wall - last_log_wall) >= 1.0 or pct != last_log_pct:
                    v_count = len(v_real) + len(v_int) + len(v_bool)
                    print(f"[Live] [{pct}%] Time: {current_time:6.2f}s | Sent {v_count} vars | Rate: {sim_rate:4.1f}x | Freq: {sample_freq:4.1f}Hz", flush=True)
                    last_log_wall = now_wall
                    last_log_pct = pct
                if now_wall - last_perf_log_wall >= 5.0:
                    last_perf_snapshot = (
                        f"[PERF][FMU] sim={current_time:.2f}s control_recv={self.comm.recv_count} "
                        f"control_cmd={control_cmd_count} control_err={control_error_count} "
                        f"queue={self.comm.received_queue.qsize()}/{self.comm.received_queue.maxsize} "
                        f"queue_drop={self.comm.recv_drop_count} yc_cache={len(latest_telemetry_for_pe)} ext_pending={len(pending_limited_injection)} ext_inj_freq={limited_inject_freq:.1f}Hz "
                        f"ext_grace={ext_inject_grace_sim_sec:.1f}s yc_ttl={telemetry_ttl_sec:.1f}s yc_max={telemetry_max_vars} "
                        f"pe_send={self.comm.ext_send_count} viz_send={self.comm.viz_send_count} "
                        f"viz_skip={self.comm.viz_skip_count} viz_hz={self.comm.viz_send_max_hz:.1f} viz_echo={self.comm.viz_echo_send_count} send_err={self.comm.send_error_count} last_pe_vars={self.comm.last_ext_var_count} "
                        f"last_pe_bytes={self.comm.last_ext_payload_bytes} "
                        f"last_viz_vars={self.comm.last_viz_var_count} last_viz_bytes={self.comm.last_viz_payload_bytes}"
                    )
                    print(last_perf_snapshot, flush=True)
                    append_perf_log(last_perf_snapshot)
                    last_perf_log_wall = now_wall

                current_time += step_size
                if sim_rate > 0:
                    target_wall = sim_wall_anchor + (current_time - sim_time_anchor) / sim_rate
                    diff = target_wall - time.perf_counter()
                    if diff > 0.002: time.sleep(diff)
            else:
                run_ok = True

        except Exception as e:
            print(f"[!] Simulation Error: {e}")
            print(traceback.format_exc(), flush=True)
            try:
                fatal_path = os.path.join(root_dir, "fmu_worker_runtime_fatal.log")
                with open(fatal_path, "a", encoding="utf-8") as f:
                    f.write(f"\n--- FMU Worker Fatal {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    f.write(f"error={e}\n")
                    f.write(f"sim_time={locals().get('current_time', 'unknown')} step_size={step_size} sample_freq={sample_freq} sim_rate={sim_rate}\n")
                    if last_perf_snapshot:
                        f.write(last_perf_snapshot + "\n")
                    f.write("Recent injections (oldest -> newest):\n")
                    for item in recent_injections:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    if last_applied_injection:
                        f.write("Last applied injection before crash:\n")
                        f.write(json.dumps(last_applied_injection, ensure_ascii=False) + "\n")
                    f.write("Telemetry cache sample:\n")
                    try:
                        sample = {k: v for k, (v, _) in list(latest_telemetry_for_pe.items())[-30:]}
                        f.write(json.dumps(sample, ensure_ascii=False, default=str) + "\n")
                    except Exception:
                        pass
                    f.write(traceback.format_exc())
            except Exception:
                pass
            error_text = str(e)
            if last_applied_injection and ("0xe06d7363" in error_text or "fmi2DoStep failed with status 3" in error_text):
                actual = last_applied_injection.get("actual")
                append_injection_blacklist(blacklist_path, actual, f"Auto-added after FMU step/native failure at sim_time={last_applied_injection.get('sim_time')}: {e}")
                print(f"[!] Auto-blacklisted injection variable after FMU failure: {actual}", flush=True)
            # --- 深度诊断：如果是读取失败，尝试定位具体变量 ---
            if "fmi2GetReal" in str(e):
                print("[*] Diagnostic: Checking which variable caused fmi2GetReal error...")
                for v in v_real:
                    try:
                        fmu_instance.getReal([v.valueReference])
                    except:
                        print(f"[!] FAILED VARIABLE: {v.name} (VR={v.valueReference})")
        finally:
            os.chdir(orig_cwd)
            try:
                perf_logger.close()
            except Exception:
                pass
            try:
                if fmu_instance is not None:
                    fmu_instance.terminate(); fmu_instance.freeInstance()
            except: pass
        return run_ok

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("fmu_path")
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8889)
    parser.add_argument("--sync_vars", default=None)
    parser.add_argument("--step", type=float, default=0.01)
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--freq", type=float, default=0.0)
    parser.add_argument("--time", type=float, default=100.0)
    parser.add_argument("--params", default=None)
    parser.add_argument("--control_port", type=int, default=8898)
    parser.add_argument("--sim_id", default=None)
    parser.add_argument("--replace_dot", action="store_true", help="Replace '.' with '_' in variable names")
    parser.add_argument("--pause_file", default=None, help="Pause while this file exists")
    args = parser.parse_args()
    
    init_params = None
    if args.params:
        try: init_params = json.loads(args.params)
        except: pass
    start_parent_watchdog()

    ok = FMUPlayer(args.fmu_path, args.ip, args.port, sim_id=args.sim_id, sync_vars_file=args.sync_vars, control_port=args.control_port, replace_dot=args.replace_dot, pause_file=args.pause_file).run(
        step_size=args.step, sim_time=args.time, sim_rate=args.rate, sample_freq=args.freq, init_params=init_params
    )
    sys.exit(0 if ok else 2)
