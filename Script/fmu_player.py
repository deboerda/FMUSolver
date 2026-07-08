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

def parse_bool_value(value):
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)

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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_received_data = None
        self.received_queue = queue.Queue(maxsize=1000)
        self.listen_port = listen_port
        self.replace_dot = replace_dot

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
                self.last_received_data = data
                try:
                    self.received_queue.put_nowait(data)
                except queue.Full:
                    try: self.received_queue.get_nowait()
                    except Exception: pass
                    try: self.received_queue.put_nowait(data)
                    except Exception: pass
        threading.Thread(target=listen_loop, daemon=True).start()

    def send_fmu_data(self, sim_time, variables, chunk_size=200):
        if ddm_pb2 is None or not variables: return
        var_names = list(variables.keys())
        for i in range(0, len(var_names), chunk_size):
            chunk_names = var_names[i:i + chunk_size]
            
            # --- 1. 组装给外部的包 (应用重命名逻辑) ---
            packet_ext = ddm_pb2.DDMData()
            packet_ext.machine_time = time.time()
            packet_ext.sim_time = sim_time
            
            # --- 2. 组装给本地看板的包 (绝对不重命名) ---
            packet_viz = ddm_pb2.DDMData()
            packet_viz.machine_time = time.time()
            packet_viz.sim_time = sim_time
            
            for name in chunk_names:
                val = variables[name]
                
                # 配置外部包
                svar_ext = packet_ext.sim_vars.add()
                svar_ext.name = name.replace('.', '_') if self.replace_dot else name
                
                # 配置看板包
                svar_viz = packet_viz.sim_vars.add()
                svar_viz.name = name
                
                # 类型推断与赋值
                if isinstance(val, bool):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Bool")
                    svar_ext.type = vt; svar_viz.type = vt
                    svar_ext.bool_value = 1.0 if val else 0.0
                    svar_viz.bool_value = 1.0 if val else 0.0
                elif isinstance(val, int):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Int")
                    svar_ext.type = vt; svar_viz.type = vt
                    svar_ext.int_value = float(val)
                    svar_viz.int_value = float(val)
                elif isinstance(val, float):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("Double")
                    svar_ext.type = vt; svar_viz.type = vt
                    svar_ext.double_value = val
                    svar_viz.double_value = val
                elif isinstance(val, str):
                    vt = ddm_pb2.DDMData.SimVar.Type.Value("String")
                    svar_ext.type = vt; svar_viz.type = vt
                    svar_ext.string_value = str(val)
                    svar_viz.string_value = str(val)
                    
            # 广播发送
            try:
                # 给外部系统
                raw_ext = packet_ext.SerializeToString()
                self.sock.sendto(base64.b64encode(raw_ext).decode('ascii').encode('ascii'), self.target_addr)
                
                # 给本地看板
                raw_viz = packet_viz.SerializeToString()
                self.sock.sendto(base64.b64encode(raw_viz).decode('ascii').encode('ascii'), self.viz_addr)
            except: pass

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
            self.sock.sendto(base64.b64encode(raw).decode('ascii').encode('ascii'), self.viz_addr)
        except Exception:
            pass

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
        if not md or not fmpy: return
        self.comm.start_receiver()
        
        host_arch = "win64" if sys.maxsize > 2**32 else "win32"
        dll_path = os.path.abspath(os.path.join(self.processor.temp_dir, "binaries", host_arch))
        root_dir = os.path.abspath(os.path.dirname(sys.argv[0]) if sys.argv[1:] else os.getcwd())
        
        for p in [dll_path, root_dir]:
            if os.path.exists(p):
                if hasattr(os, 'add_dll_directory'): os.add_dll_directory(p)
                os.environ['PATH'] = p + os.pathsep + os.environ.get('PATH', '')

        orig_cwd = os.getcwd()
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
                                            fmu_instance.setReal([v_obj.valueReference], [float(val.strip())])
                                print(f"[OK] Parsed and injected table {k} ({len(rows)}x{len(rows[0])})")
                        except Exception as e:
                            print(f"[!] Error parsing table {k}: {e}")
                    else:
                        v_obj = next((mv for mv in vars_list if mv.name == k), None)
                        if v_obj:
                            t = getattr(v_obj, 'type', 'Real')
                            if t == 'Real': fmu_instance.setReal([v_obj.valueReference], [float(v)])
                            elif t == 'Integer': fmu_instance.setInteger([v_obj.valueReference], [int(v)])
                            elif t == 'Boolean': fmu_instance.setBoolean([v_obj.valueReference], [bool(v)])
                            print(f"[OK] Set param {k} = {v}")

            fmu_instance.enterInitializationMode()
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
            input_real_vr_map = {v.name: v.valueReference for v in vars_list if getattr(v, 'type', 'Real') == 'Real'}
            input_int_vr_map = {v.name: v.valueReference for v in vars_list if getattr(v, 'type', 'Integer') == 'Integer'}
            input_bool_vr_map = {v.name: v.valueReference for v in vars_list if getattr(v, 'type', 'Boolean') == 'Boolean'}
            input_all_names = list(input_real_vr_map) + list(input_int_vr_map) + list(input_bool_vr_map)
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
            
            print(f"[*] Simulation Loop Started. Step={step_size}s, Rate={sim_rate}x")

            while current_time <= sim_time:
                while True:
                    try:
                        raw_cmd = self.comm.received_queue.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        cmd = json.loads(raw_cmd.decode('utf-8'))
                        if self.sim_id and cmd.get("sim_id") != self.sim_id:
                            self.comm.last_received_data = None
                            continue
                        if cmd.get("exit"): break
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
                        injected_count = 0
                        missing_injection = []
                        injected_echo = {}
                        for k, v in cmd.items():
                            if k in ("sim_id", "exit", "pause", "resume", "sim_rate", "step_size", "sim_time", "sample_freq"):
                                continue
                            injected_echo[str(k)] = v
                            actual = resolve_input_name(k)
                            if actual in input_real_vr_map:
                                fmu_instance.setReal([input_real_vr_map[actual]], [float(v)])
                                injected_count += 1
                                if time.perf_counter() - last_injection_log_wall > 1.0:
                                    print(f"[*] Injected Real {actual}={v}", flush=True); last_injection_log_wall = time.perf_counter()
                            elif actual in input_int_vr_map:
                                fmu_instance.setInteger([input_int_vr_map[actual]], [int(v)])
                                injected_count += 1
                                if time.perf_counter() - last_injection_log_wall > 1.0:
                                    print(f"[*] Injected Integer {actual}={v}", flush=True); last_injection_log_wall = time.perf_counter()
                            elif actual in input_bool_vr_map:
                                fmu_instance.setBoolean([input_bool_vr_map[actual]], [parse_bool_value(v)])
                                injected_count += 1
                                if time.perf_counter() - last_injection_log_wall > 1.0:
                                    print(f"[*] Injected Boolean {actual}={v}", flush=True); last_injection_log_wall = time.perf_counter()
                            else:
                                missing_injection.append(str(k))
                        if time.perf_counter() - last_injection_log_wall > 1.0:
                            total_cmd = len([k for k in cmd if k not in ("sim_id", "exit", "pause", "resume", "sim_rate", "step_size", "sim_time", "sample_freq")])
                            if missing_injection:
                                print(f"[!] Injection summary: {injected_count}/{total_cmd} applied; missing: {', '.join(missing_injection[:8])}", flush=True)
                            elif injected_count:
                                print(f"[*] Injection summary: {injected_count}/{total_cmd} applied", flush=True)
                            last_injection_log_wall = time.perf_counter()
                        self.comm.send_injection_echo_to_viz(current_time, injected_echo)
                    except Exception as e:
                        print(f"[!] Control command error: {e}", flush=True)
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
                    self.comm.send_fmu_data(current_time, out)

                # Keep logs tied to wall-clock time so high-speed simulation does not flood the GUI.
                now_wall = time.perf_counter()
                pct = min(100, int((current_time / sim_time) * 100)) if sim_time > 0 and sim_time != float('inf') else 0
                if (now_wall - last_log_wall) >= 1.0 or pct != last_log_pct:
                    v_count = len(v_real) + len(v_int) + len(v_bool)
                    print(f"[Live] [{pct}%] Time: {current_time:6.2f}s | Sent {v_count} vars | Rate: {sim_rate:4.1f}x | Freq: {sample_freq:4.1f}Hz", flush=True)
                    last_log_wall = now_wall
                    last_log_pct = pct

                current_time += step_size
                if sim_rate > 0:
                    target_wall = sim_wall_anchor + (current_time - sim_time_anchor) / sim_rate
                    diff = target_wall - time.perf_counter()
                    if diff > 0.002: time.sleep(diff)

        except Exception as e:
            print(f"[!] Simulation Error: {e}")
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
            try: fmu_instance.terminate(); fmu_instance.freeInstance()
            except: pass

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
        
    FMUPlayer(args.fmu_path, args.ip, args.port, sim_id=args.sim_id, sync_vars_file=args.sync_vars, control_port=args.control_port, replace_dot=args.replace_dot, pause_file=args.pause_file).run(
        step_size=args.step, sim_time=args.time, sim_rate=args.rate, sample_freq=args.freq, init_params=init_params
    )
