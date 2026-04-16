import os
import time
import socket
import base64
import threading
import platform
import zipfile
import shutil
import sys
import xml.etree.ElementTree as ET

# 依赖库检测与提示
try:
    import fmpy
    from fmpy import instantiate_fmu, read_model_description
except ImportError:
    print("[!] FMPy is missing. Please run: pip install fmpy")
    fmpy = None

try:
    import ddm_pb2
except ImportError:
    print("[!] ddm_pb2.py is missing. Please run: protoc --python_out=. ddm.proto")
    ddm_pb2 = None

# --------------------------------------------------------------------------------
# 1. 架构识别与 FMU 文件处理
# --------------------------------------------------------------------------------
def check_dll_arch(filepath):
    """检测 DLL 的 PE 架构 (win32 或 win64)"""
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

class FMUProcessor:
    def __init__(self, fmu_path):
        self.fmu_path = fmu_path
        self.temp_dir = os.path.abspath("./fmu_work_worker2")
        self.model_desc = None
        self.arch_matched = False

    def check_and_prepare(self):
        # 0. 先加载 XML 元数据（不需要解压也能从 zip 读），我们需要知道 modelIdentifier
        if not self.model_desc and fmpy:
            self.model_desc = read_model_description(self.fmu_path, validate=False)
            print(f"[OK] FMU Metadata Loaded: {self.model_desc.modelName}")

        fmu_name = os.path.basename(self.fmu_path)
        marker_file = os.path.join(self.temp_dir, f"__extracted_{fmu_name}__")
        
        # 1. 确定二进制路径
        host_arch = "win64" if sys.maxsize > 2**32 else "win32"
        target_bin = os.path.join(self.temp_dir, "binaries", host_arch)

        # 2. 验证环境完整性 (如果 .dll 没了，即便 marker 在也要重解压)
        core_lib_name = self.model_desc.modelIdentifier if self.model_desc else fmu_name.replace(".fmu", "")
        core_dll = os.path.join(target_bin, f"{core_lib_name}.dll")

        if not os.path.exists(marker_file) or not os.path.exists(core_dll):
            print(f"[*] Environment incomplete or new FMU: {fmu_name}. Patching...")
            with zipfile.ZipFile(self.fmu_path, 'r') as z:
                z.extractall(self.temp_dir)
            with open(marker_file, 'w') as f: f.write(str(time.time()))
        else:
            print(f"[*] Environment ready for {fmu_name}. Registry confirmed.")

        # --- 💡 自动环境修复逻辑 (始终确保补丁 DLL 同步) ---
        root_dir = os.path.abspath(os.path.dirname(sys.argv[0]) if sys.argv[1:] else os.getcwd())
        protected = ['kernel32.dll', 'user32.dll', 'ntdll.dll', 'advapi32.dll']
        os.makedirs(target_bin, exist_ok=True)
        
        for file in os.listdir(root_dir):
            src_file = os.path.join(root_dir, file)
            if file.lower().endswith('.dll') and file.lower() not in protected:
                arch = check_dll_arch(src_file)
                if arch and arch != host_arch:
                    continue  # 跳过不匹配当前架构的 DLL（例如避免把64位的MWSolver.dll拷入win32）
                    
            if (file.lower().endswith('.dll') or file.lower().endswith('.txt')) and file.lower() not in protected:
                target_file = os.path.join(target_bin, file)
                if not os.path.exists(target_file):
                    print(f"[*] Auto-patching: Syncing {file} to model environment...")
                    shutil.copy2(src_file, target_file)

        # ── Also scan txt/ subfolder (e.g. FmuSolver_Package/txt/Orbit_Pre.txt) ──
        txt_subdir = os.path.join(root_dir, 'txt')
        if os.path.exists(txt_subdir):
            for file in os.listdir(txt_subdir):
                if file.lower().endswith('.txt') and file.lower() not in protected:
                    target_file = os.path.join(target_bin, file)
                    # Always refresh txt data files (they may have been updated by orbit pre-calc)
                    print(f"[*] Auto-patching: Syncing txt/{file} to model environment...")
                    shutil.copy2(os.path.join(txt_subdir, file), target_file)

        if os.path.exists(target_bin):
            self.arch_matched = True
        
        return self.model_desc

# --------------------------------------------------------------------------------
# 2. UDP + ddm.proto 通信模块 (重点: 发送)
# --------------------------------------------------------------------------------
class DDMCommManager:
    def __init__(self, remote_ip="127.0.0.1", remote_port=8889, listen_port=8888):
        self.target_addr = (remote_ip, remote_port)
        self.listen_addr = ("0.0.0.0", listen_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 预留接收缓存
        self.last_received_data = None

    def start_receiver(self):
        """预留接收接口线程"""
        def listen_loop():
            recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 允许地址重用
            if platform.system() != 'Windows':
                recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 尝试绑定端口，如果占用则尝试下一个
            actual_port = self.listen_addr[1]
            max_retries = 10
            while max_retries > 0:
                try:
                    recv_sock.bind((self.listen_addr[0], actual_port))
                    print(f"[*] Command Receiver bound to UDP port {actual_port}")
                    break
                except OSError:
                    actual_port += 1
                    max_retries -= 1
            else:
                print("[!] Failed to bind any command port. Command receiver disabled.")
                return

            while True:
                data, addr = recv_sock.recvfrom(65536)
                self.last_received_data = data
        
        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()

    def send_fmu_data(self, sim_time, variables, chunk_size=200):
        """
        核心任务：分包将 FMU 变量打包为 ddm.proto 并发送
        variables: dict { "name": value }
        chunk_size: 每个包包含的最大变量数，防止超过 UDP 64KB 限制
        """
        if ddm_pb2 is None or not variables: return

        # 将所有变量的 key 转为列表，按 chunk_size 拆分
        var_names = list(variables.keys())
        for i in range(0, len(var_names), chunk_size):
            chunk_names = var_names[i:i + chunk_size]
            
            # 构建一个 DDMData 分包
            packet = ddm_pb2.DDMData()
            packet.machine_time = time.time()
            packet.sim_time = sim_time
            # 标记是否为分包中最后一个包 (可选，如果 ddm.proto 有标志)
            
            for name in chunk_names:
                val = variables[name]
                svar = packet.sim_vars.add()
                svar.name = name
                
                # 类型映射逻辑: Python 的 bool 同时也是 int，所以必须先判断 bool
                if isinstance(val, bool):
                    svar.type = ddm_pb2.DDMData.SimVar.Type.Value("Bool")
                    svar.bool_value = 1.0 if val else 0.0
                elif isinstance(val, int):
                    svar.type = ddm_pb2.DDMData.SimVar.Type.Value("Int")
                    svar.int_value = float(val)
                elif isinstance(val, float):
                    svar.type = ddm_pb2.DDMData.SimVar.Type.Value("Double")
                    svar.double_value = val
                elif isinstance(val, str):
                    svar.type = ddm_pb2.DDMData.SimVar.Type.Value("String")
                    svar.string_value = str(val)

            # 序列化并发送分包
            try:
                raw_bytes = packet.SerializeToString()
                # 再次封装 Base64 (如果对面是用 Base64 接收的)
                b64_str = base64.b64encode(raw_bytes).decode('ascii')
                self.sock.sendto(b64_str.encode('ascii'), self.target_addr)
            except Exception as e:
                print(f"[!] Send error: {e}")

# --------------------------------------------------------------------------------
# 3. 仿真主循环 (Driver)
# --------------------------------------------------------------------------------
class FMUPlayer:
    def __init__(self, fmu_path, remote_ip="127.0.0.1", remote_port=8889, sync_vars_file=None):
        self.processor = FMUProcessor(fmu_path)
        self.comm = DDMCommManager(remote_ip=remote_ip, remote_port=remote_port)
        self.model = None
        self.sync_vars_file = sync_vars_file

    def run(self, step_size=0.01, sim_time=float('inf'), sim_rate=1.0, sample_freq=0.0, init_params=None):
        # 1. 初始化
        self.model = self.processor.check_and_prepare()
        if not self.model: return

        self.comm.start_receiver() # 开启预留接口

        # 2. FMI 实例化
        if not fmpy: return
        unzip_dir = self.processor.temp_dir
        
        # DLL search path setup
        dll_path = None
        if platform.system() == 'Windows':
            import ctypes
            host_arch = "win64" if sys.maxsize > 2**32 else "win32"
            dll_path = os.path.abspath(os.path.join(unzip_dir, "binaries", host_arch))

            # Also add the root app dir (for msvcr100.dll, MWSolver.dll, etc.)
            root_dir = os.path.abspath(os.path.dirname(sys.argv[0]) if sys.argv[1:] else os.getcwd())

            for search_dir in [dll_path, root_dir]:
                if os.path.exists(search_dir):
                    if hasattr(os, 'add_dll_directory'):
                        os.add_dll_directory(search_dir)
                    os.environ['PATH'] = search_dir + os.pathsep + os.environ.get('PATH', '')

            print(f"[*] DLL search dirs: {dll_path}")

        original_cwd = os.getcwd()
        try:
            if dll_path and os.path.exists(dll_path):
                os.chdir(dll_path)
                print(f"[*] CWD → {os.getcwd()}")

                # ── Pre-load all companion DLLs from bin_dir into process space ──
                # This is required in PyInstaller frozen apps where DLL dependency
                # resolution during ctypes.CDLL() load differs from the normal runtime.
                import ctypes
                protected_names = {'kernel32.dll', 'user32.dll', 'ntdll.dll', 'advapi32.dll'}
                loaded_ok = []
                load_fail = []
                for fname in sorted(os.listdir(dll_path)):
                    if fname.lower().endswith('.dll') and fname.lower() not in protected_names:
                        fpath = os.path.join(dll_path, fname)
                        try:
                            ctypes.CDLL(fpath)
                            loaded_ok.append(fname)
                        except Exception as e:
                            load_fail.append(f"{fname}: {e}")
                print(f"[*] Pre-loaded {len(loaded_ok)} DLLs. Failures: {len(load_fail)}")
                for f in load_fail:
                    print(f"[!] Pre-load FAIL: {f}")
                # ────────────────────────────────────────────────────────────────
                
            def fmu_logger(componentEnvironment, instanceName, status, category, message):
                msg = message.decode('utf-8') if isinstance(message, bytes) else message
                print(f"[FMU LOG] {status} - {category}: {msg}")

            fmu_instance = fmpy.instantiate_fmu(
                unzipdir=unzip_dir, 
                model_description=self.model,
                fmi_type='CoSimulation'
            )
            
            fmu_instance.setupExperiment(startTime=0.0)

            # ── Override hardcoded absolute file paths in String parameters ──
            # Handles any absolute path (D:/ or C:\) pointing to a .txt data file (e.g. Orbit_Pre.txt)
            for v in getattr(self.model, 'modelVariables', []) + getattr(self.model, 'scalarVariables', []):
                if getattr(v, 'type', None) == 'String' or getattr(v, 'typeName', None) == 'String':
                    start_val = getattr(v, 'start', '') or ''
                    has_abs_path = start_val and (':/' in start_val or ':\\' in start_val or ':/' in start_val)
                    has_txt_file = start_val.lower().endswith('.txt')
                    if has_abs_path and has_txt_file:
                        # Get just the filename and resolve it relative to CWD (= bin_dir)
                        txt_filename = os.path.basename(start_val.replace('\\', '/'))
                        local_path = os.path.abspath(txt_filename).replace('\\', '/')
                        print(f"[*] Overriding filepath: {v.name}: .../{txt_filename} → {local_path}")
                        fmu_instance.setString([v.valueReference], [local_path])
            
            # ── Inject custom Initialization Parameters ──
            if init_params:
                print("[*] Injecting initialization parameters...")
                md_vars = getattr(self.model, 'modelVariables', []) + getattr(self.model, 'scalarVariables', [])
                for k, v_val in init_params.items():
                    if isinstance(v_val, str) and ';' in str(v_val):
                        # Table array parsing: "1000, 3640; 2000, 3640" -> Table_A[1,1], Table_A[1,2]...
                        try:
                            rows = [[float(x) for x in row.split(',') if x.strip()] for row in v_val.split(';') if row.strip()]
                            for i, row in enumerate(rows):
                                for j, val in enumerate(row):
                                    var_n = f"{k}[{i+1},{j+1}]"
                                    v_obj = next((mv for mv in md_vars if mv.name == var_n), None)
                                    if v_obj: fmu_instance.setReal([v_obj.valueReference], [val])
                            print(f"[OK] Parsed and injected table {k} ({len(rows)}x{len(rows[0]) if rows else 0})")
                        except Exception as e:
                            print(f"[!] Error parsing table {k}: {e}")
                    else:
                        v_obj = next((mv for mv in md_vars if mv.name == k), None)
                        if v_obj:
                            t = getattr(v_obj, 'type', None) or getattr(v_obj, 'typeName', 'Real')
                            if t == 'Real': fmu_instance.setReal([v_obj.valueReference], [float(v_val)])
                            elif t == 'Integer': fmu_instance.setInteger([v_obj.valueReference], [int(v_val)])
                            elif t == 'Boolean': fmu_instance.setBoolean([v_obj.valueReference], [bool(v_val)])
                            print(f"[OK] Set param {k} = {v_val}")

            # ────────────────────────────────────────────────────────

            fmu_instance.enterInitializationMode()
            fmu_instance.exitInitializationMode()

            # 3. 准备变量列表 (不限于 Output，包含输入、本地和参数)
            all_vars = getattr(self.model, 'modelVariables', None) or getattr(self.model, 'scalarVariables', [])
            relevant_causalities = {'output', 'input', 'parameter', 'local'}
            
            def get_v_type(v):
                return getattr(v, 'type', None) or getattr(v, 'typeName', 'Real')

            v_real = [v for v in all_vars if get_v_type(v) == 'Real' and (v.causality in relevant_causalities or not v.causality)]
            v_int = [v for v in all_vars if get_v_type(v) == 'Integer' and (v.causality in relevant_causalities or not v.causality)]
            v_bool = [v for v in all_vars if get_v_type(v) == 'Boolean' and (v.causality in relevant_causalities or not v.causality)]
            v_str = [v for v in all_vars if get_v_type(v) == 'String' and (v.causality in relevant_causalities or not v.causality)]

            if self.sync_vars_file and os.path.exists(self.sync_vars_file):
                import json
                try:
                    with open(self.sync_vars_file, 'r', encoding='utf-8') as f:
                        sync_data = json.load(f)
                    
                    target_vars = set()
                    for item in sync_data:
                        if isinstance(item, dict) and item.get("sync", False):
                            target_vars.add(item["name"])
                        elif isinstance(item, str):
                            target_vars.add(item)
                    
                    v_real = [v for v in v_real if v.name in target_vars]
                    v_int = [v for v in v_int if v.name in target_vars]
                    v_bool = [v for v in v_bool if v.name in target_vars]
                    v_str = [v for v in v_str if v.name in target_vars]
                    print(f"[*] Applied UDP Sync filter: {len(target_vars)} vars enabled.")
                except Exception as e:
                    print(f"[!] Failed to apply sync vars filter: {e}")

            print(f"[*] Monitoring {len(v_real)} Real, {len(v_int)} Int, {len(v_bool)} Bool, {len(v_str)} String vars.")

            # Map name to Reference for fast UDP write injections
            real_vr_map = {v.name: v.valueReference for v in v_real}
            int_vr_map = {v.name: v.valueReference for v in v_int}

            current_time = 0.0
            next_sample_time = 0.0
            target_sim_time = sim_time
            print(f"[*] Simulation Loop Started. Step={step_size}s, Rate={sim_rate}x, Freq={sample_freq}Hz")
            
            # --- 绝对时间同步锚点 ---
            sim_wall_anchor = time.perf_counter()
            sim_time_anchor = current_time

            # 发送一次仿真开始标识
            self.comm.send_fmu_data(current_time, {"SIM_STATUS": True}, chunk_size=10)

            while current_time <= target_sim_time:
                perf_start = time.perf_counter()

                # --- 动态指令解析 ---
                if self.comm.last_received_data:
                    import json
                    try:
                        cmd = json.loads(self.comm.last_received_data.decode('utf-8'))
                        if cmd.get("exit"):
                            print("[!] Received remote exit command. Shutting down worker...")
                            break
                        
                        cfg_keys = {"step_size", "sim_time", "sim_rate", "sample_freq", "exit"}
                        has_cfg_chg = False
                        if "step_size" in cmd: step_size = float(cmd["step_size"]); has_cfg_chg = True
                        if "sim_time" in cmd: target_sim_time = float(cmd["sim_time"]); has_cfg_chg = True
                        if "sim_rate" in cmd: 
                            sim_rate = float(cmd["sim_rate"]); has_cfg_chg = True
                            sim_wall_anchor = time.perf_counter()
                            sim_time_anchor = current_time
                        if "sample_freq" in cmd: 
                            sample_freq = float(cmd["sample_freq"]); has_cfg_chg = True
                            next_sample_time = current_time
                        
                        if has_cfg_chg:
                            print(f"[*] Sim config updated via UDP: step={step_size}, time={target_sim_time}, rate={sim_rate}, freq={sample_freq}Hz")

                        # Handle raw direct variable injection from external UI interaction (e.g. Is_initial, Control signals)
                        for k, v_raw in cmd.items():
                            if k not in cfg_keys:
                                if k in real_vr_map: fmu_instance.setReal([real_vr_map[k]], [float(v_raw)])
                                elif k in int_vr_map: fmu_instance.setInteger([int_vr_map[k]], [int(v_raw)])
                                # If it successfully injects, inform logs briefly (could be spammy if continuous, but fine for events)
                                print(f"[UDP-Ctrl] Injected {k} = {v_raw}")

                    except Exception as e:
                        print(f"[!] Invalid UDP command: {e}")
                    self.comm.last_received_data = None

                # Step 1: 执行 FMU 步进
                fmu_instance.doStep(currentCommunicationPoint=current_time, communicationStepSize=step_size)
                
                # Step 2 & 3: 采样逻辑 (控制发送频率)
                do_sample = True
                if sample_freq > 0:
                    if current_time >= next_sample_time - 1e-6:
                        next_sample_time += (1.0 / sample_freq)
                        do_sample = True
                    else:
                        do_sample = False

                output_data = {}
                if do_sample:
                    if v_real:
                        vals = fmu_instance.getReal([v.valueReference for v in v_real])
                        for v, val in zip(v_real, vals): output_data[v.name] = float(val)
                    if v_int:
                        vals = fmu_instance.getInteger([v.valueReference for v in v_int])
                        for v, val in zip(v_int, vals): output_data[v.name] = int(val)
                    if v_bool:
                        vals = fmu_instance.getBoolean([v.valueReference for v in v_bool])
                        for v, val in zip(v_bool, vals): output_data[v.name] = bool(val)
                    if v_str:
                        vals = fmu_instance.getString([v.valueReference for v in v_str])
                        for v, val in zip(v_str, vals): output_data[v.name] = str(val)

                    # 发送数据
                    self.comm.send_fmu_data(current_time, output_data)

                # Step 4: 高精度时间管理与仿真速率控制
                current_time += step_size
                
                if sim_rate > 0:
                    # 使用绝对时间增量计算目标时间点，避免误差累计累加
                    target_wall_time = sim_wall_anchor + (current_time - sim_time_anchor) / sim_rate
                    while True:
                        diff = target_wall_time - time.perf_counter()
                        if diff <= 0:
                            break
                        # Windows time.sleep 精度在 15ms 左右，仅在差距大于 15ms 时休眠大额时间交出 CPU 阻塞
                        if diff > 0.015:
                            time.sleep(diff - 0.015)
                        # 小于 15ms 的碎步长使用 spin-wait 空跑 (Busy Wait CPU) 获取微秒级控制！

                if int(current_time / step_size) % 100 == 0 and do_sample:
                    print(f"[Live] Time: {current_time:.2f}s | Sent {len(output_data)} vars | Rate: {sim_rate}x | Freq: {sample_freq}Hz")

        except KeyboardInterrupt:
            print("[*] Simulation Stopped by User.")
        except Exception as e:
            print(f"[!] Simulation Error: {e}")
        finally:
            os.chdir(original_cwd)
            try:
                fmu_instance.terminate()
                fmu_instance.freeInstance()
            except:
                pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("fmu_path", help="Path to FMU file")
    parser.add_argument("--ip", default="127.0.0.1", help="Remote UDP IP")
    parser.add_argument("--port", type=int, default=8889, help="Remote UDP Port")
    parser.add_argument("--sync_vars", default=None, help="Path to JSON file containing list of variables to send")
    args = parser.parse_args()
    
    player = FMUPlayer(args.fmu_path, remote_ip=args.ip, remote_port=args.port, sync_vars_file=args.sync_vars)
    player.run()
