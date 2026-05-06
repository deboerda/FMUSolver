import socket
import json
import time
import threading
import base64
import os
import sys

# 动态寻找 ddm 协议库
app_dir = os.path.dirname(os.path.abspath(__file__))
# 尝试寻找 Udp.Ddm.protobuf 目录
ddm_path = ""
search_root = os.path.dirname(app_dir)
while search_root and search_root.strip("\\") != "" and not search_root.endswith(":\\"):
    test_path = os.path.join(search_root, "Udp.Ddm.protobuf")
    if os.path.isdir(test_path):
        ddm_path = test_path
        break
    parent = os.path.dirname(search_root)
    if parent == search_root: break
    search_root = parent

if ddm_path:
    sys.path.append(ddm_path)
    print(f"[*] Found DDM Protobuf at: {ddm_path}")

try:
    import ddm_pb2
except ImportError:
    print("[!] ddm_pb2 not found. Listening for raw data instead (limited functionality).")
    ddm_pb2 = None

# --- 核心映射表: Telemetry ID -> FMU Variable Name ---
TM_TO_FMU_MAP = {
    "K0693": "a_MT_Online", "K0694": "e_MT_Online", "K0695": "i_MT_Online",
    "K0696": "OMEGA_MT_Online", "K0697": "omega_MT_Online", "K0699": "f_WT_Online",
    "K0024": "Att_MT_Online[1]", "K0025": "Att_MT_Online[2]", "K0026": "Att_MT_Online[3]",
    "K0182": "Alpha_Online[1]", "K0191": "Alpha_Online[2]",
    "K0180": "Beta_Online[1]", "K0189": "Beta_Online[2]",
    "N0830": "DisChargeAh_MT_Online[1]", "N1111": "DisChargeAh_MT_Online[2]",
    "N1383": "DisChargeAh_MT_Online[3]", "N1655": "DisChargeAh_MT_Online[4]",
    "N2682": "DisChargeAh_MT_Online[5]", "N2963": "DisChargeAh_MT_Online[6]",
    "N3235": "DisChargeAh_MT_Online[7]", "N3507": "DisChargeAh_MT_Online[8]",
    "N0100": "BusFilter_MT_V_Online[1]", "N1973": "BusFilter_MT_V_Online[2]",
    "N0103": "BusFilter_MT_A_Online[1]", "N1976": "BusFilter_MT_A_Online[2]",
    "S0067": "relativetime_MT_Online", "DCSM34": "relativetime_MT_Online"
}
# 批量映射方阵电流
for i in range(1, 7):
    TM_TO_FMU_MAP[f"N{386+i:04d}"] = f"SolarArrayMTA_I_Online[{i}]"
    TM_TO_FMU_MAP[f"N{2259+i:04d}"] = f"SolarArrayMTB_I_Online[{i}]"

# --- 安全阈值保护配置 (进一步收紧范围以防止模型发散) ---
VAR_RANGE_LIMITS = {
    "BusFilter_MT_V_Online": (20, 100),      # 电压限制 20-100V (更符合实际卫星母线)
    "BusFilter_MT_A_Online": (-100, 100),    # 电流限制
    "SolarArrayMT": (-100, 100),             # 方阵电流
    "a_MT_Online": (6500, 7500),             # 轨道半长轴 (严限在近地轨道范围)
    "Att_MT_Online": (-360, 360),            # 姿态角
    "Alpha_Online": (-360, 360),
    "Beta_Online": (-360, 360),
    "DisChargeAh": (0, 1000),                # 电池容量
}

def is_value_safe(name, val):
    for key, (vmin, vmax) in VAR_RANGE_LIMITS.items():
        if key in name:
            if not (vmin <= val <= vmax):
                return False, vmin, vmax
    return True, 0, 0

class SyncController:
    def __init__(self, listen_port=8888, target_ip="127.0.0.1", target_port=8898):
        self.listen_port = listen_port
        self.target_addr = (target_ip, target_port)
        self.latest_data = {}
        self.running = True
        self.inject_log_path = os.path.join(app_dir, "injection_history.log")
        # 清空旧日志
        with open(self.inject_log_path, "w") as f: f.write("Time,Variable,Value\n")

    def log_injection(self, payload):
        """记录注入历史以便排查崩溃"""
        with open(self.inject_log_path, "a") as f:
            t_str = time.strftime("%H:%M:%S")
            for k, v in payload.items():
                f.write(f"{t_str},{k},{v}\n")

    def listen_bridge(self):
        """监听 main.py 转发出的 DDM 数据"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('0.0.0.0', self.listen_port))
            print(f"[*] SyncController: Listening on {self.listen_port}, logging to {self.inject_log_path}")
        except Exception as e:
            print(f"[!] Bind error: {e}")
            return
        
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while self.running:
            try:
                data, _ = sock.recvfrom(65535)
                if ddm_pb2:
                    try:
                        raw_pb = base64.b64decode(data)
                        msg = ddm_pb2.DDMData()
                        msg.ParseFromString(raw_pb)
                        
                        fmu_payload = {}
                        for var in msg.sim_vars:
                            if var.name in TM_TO_FMU_MAP:
                                fmu_name = TM_TO_FMU_MAP[var.name]
                                val = var.double_value
                                
                                safe, vmin, vmax = is_value_safe(fmu_name, val)
                                if safe:
                                    self.latest_data[fmu_name] = val
                                    fmu_payload[fmu_name] = val
                                else:
                                    print(f"[WARN] Range Block: {fmu_name}={val}")
                        
                        if fmu_payload:
                            send_sock.sendto(json.dumps(fmu_payload).encode('utf-8'), self.target_addr)
                            self.log_injection(fmu_payload) # 记录日志
                    except Exception:
                        pass
            except Exception:
                pass

    def trigger_pulse(self):
        """脉冲式触发同步信号 (仅控制 Is_initial 变量)"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 1. 发送高电平脉冲 (Is_initial = 1.0)
            sock.sendto(json.dumps({"Is_initial": 1.0}).encode('utf-8'), self.target_addr)
            print(f"\n[PULSE] STEP 1: Sending HIGH (1.0) for 'Is_initial'...")
            
            # 2. 脉冲宽度延迟 (100ms)
            time.sleep(0.1)
            
            # 3. 发送低电平复位 (Is_initial = 0.0)
            sock.sendto(json.dumps({"Is_initial": 0.0}).encode('utf-8'), self.target_addr)
            print("[PULSE] STEP 2: Sending LOW (0.0). Pulse complete.")
        except Exception as e:
            print(f"[!] Pulse trigger failed: {e}")
        finally:
            sock.close()

    def run_cli(self):
        threading.Thread(target=self.listen_bridge, daemon=True).start()
        print("\n==========================================")
        print("   FMU Telemetry Sync Controller (Pulse)")
        print("==========================================")
        print(f"[*] Target FMU Engine: {self.target_addr[0]}:{self.target_addr[1]}")
        print("[*] Controls: Press 'ENTER' to Sync, type 'exit' to quit.")
        print("------------------------------------------\n")
        
        while True:
            try:
                cmd = input(">> ").strip().lower()
                if cmd == 'exit':
                    self.running = False
                    break
                self.trigger_pulse()
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    # 默认监听 8888 (main.py 的转发端口), 目标 8898 (fmu_player 的控制端口)
    ctrl = SyncController(listen_port=8888, target_port=8898)
    ctrl.run_cli()
