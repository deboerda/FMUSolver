import sys

with open('c:\\Spaceship\\fmu_player.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update method signature
content = content.replace("def run(self, step_size=0.01):", "def run(self, step_size=0.01, sim_time=float('inf'), sim_rate=1.0, sample_freq=0.0):")

# 2. Add extra variables before while loop
old_start = """            current_time = 0.0
            print(f"[*] Simulation Loop Started. Step={step_size}s")
            
            # 发送一次仿真开始标识
            self.comm.send_fmu_data(current_time, {"SIM_STATUS": True}, chunk_size=10)

            while True:"""

new_start = """            current_time = 0.0
            next_sample_time = 0.0
            target_sim_time = sim_time
            print(f"[*] Simulation Loop Started. Step={step_size}s, Rate={sim_rate}x, Freq={sample_freq}Hz")
            
            # 发送一次仿真开始标识
            self.comm.send_fmu_data(current_time, {"SIM_STATUS": True}, chunk_size=10)

            while current_time <= target_sim_time:"""
            
if old_start in content:
    content = content.replace(old_start, new_start)
else:
    print("WARNING: Could not find old_start")

# 3. Update the inside of while loop
old_loop = """                perf_start = time.perf_counter()

                # Step 1: 执行 FMU 步进
                fmu_instance.doStep(currentCommunicationPoint=current_time, communicationStepSize=step_size)
                
                # Step 2: 批量提取数据
                output_data = {}
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

                # Step 3: 发送数据 (Protobuf + UDP)
                self.comm.send_fmu_data(current_time, output_data)

                # Step 4: 时间管理
                current_time += step_size
                elapsed = time.perf_counter() - perf_start
                sleep_time = step_size - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

                if int(current_time / step_size) % 100 == 0:
                    print(f"[Live] Time: {current_time:.2f}s | Sent {len(output_data)} vars")"""

new_loop = """                perf_start = time.perf_counter()

                # --- 动态指令解析 ---
                if self.comm.last_received_data:
                    import json
                    try:
                        cmd = json.loads(self.comm.last_received_data.decode('utf-8'))
                        if "step_size" in cmd: step_size = float(cmd["step_size"])
                        if "sim_time" in cmd: target_sim_time = float(cmd["sim_time"])
                        if "sim_rate" in cmd: sim_rate = float(cmd["sim_rate"])
                        if "sample_freq" in cmd: 
                            sample_freq = float(cmd["sample_freq"])
                            next_sample_time = current_time
                        print(f"[*] Sim config updated via UDP: step_size={step_size}, time={target_sim_time}, rate={sim_rate}, freq={sample_freq}Hz")
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

                # Step 4: 时间管理与仿真速率控制
                current_time += step_size
                elapsed = time.perf_counter() - perf_start
                
                if sim_rate > 0:
                    sleep_time = (step_size / sim_rate) - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                if int(current_time / step_size) % 100 == 0 and do_sample:
                    print(f"[Live] Time: {current_time:.2f}s | Sent {len(output_data)} vars | Rate: {sim_rate}x | Freq: {sample_freq}Hz")"""

if old_loop in content:
    content = content.replace(old_loop, new_loop)
else:
    print("WARNING: Could not find old_loop")

with open('c:\\Spaceship\\fmu_player.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch applied.")
