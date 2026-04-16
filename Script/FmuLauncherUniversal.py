import sys
import os
import subprocess
import threading
import json
import socket
import struct
import zipfile
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext

# ─── 运行时路径逻辑 ───
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

def get_fmu_arch(fmu_path):
    """快速检测 FMU 架构"""
    try:
        with zipfile.ZipFile(fmu_path, 'r') as z:
            names = z.namelist()
            if any(n.startswith('binaries/win64/') for n in names): return 64
            if any(n.startswith('binaries/win32/') for n in names): return 32
    except: pass
    return None

class FmuSolverGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FmuSolver - 卫星载荷仿真与轨道预示平台")
        self.root.geometry("950x850")
        try:
            icon_path = os.path.join(APP_DIR, "satellite_icon_149794.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass
        
        self.worker_process = None
        self.log_thread = None
        self.current_arch = struct.calcsize('P') * 8
        self.orbit_data = [] 
        
        self.create_widgets()

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tab_sim = ttk.Frame(self.notebook)
        self.tab_orbit = ttk.Frame(self.notebook)
        self.tab_data = ttk.Frame(self.notebook)
        self.tab_fields = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_fields, text=" 字段配置 ")
        self.notebook.add(self.tab_sim, text=" 实时仿真控制 ")
        self.notebook.add(self.tab_orbit, text=" 轨道预示计算 ")
        self.notebook.add(self.tab_data, text=" 数据结果展示 ")
        
        self._setup_fields_tab()
        self._setup_sim_tab()
        self._setup_orbit_tab()
        self._setup_data_tab()

    def _setup_fields_tab(self):
        # 顶部操作栏
        frame_top = tk.Frame(self.tab_fields)
        frame_top.pack(fill=tk.X, padx=10, pady=5)
        
        btn_add = tk.Button(frame_top, text="+ 手动添加", command=self._add_field_manual, bg="#e0f7fa")
        btn_add.pack(side=tk.LEFT, padx=5)
        
        btn_parse = tk.Button(frame_top, text="⚡ 智能解析粘贴文本", command=self._parse_pasted_text, bg="#fff9c4")
        btn_parse.pack(side=tk.LEFT, padx=5)
        
        btn_clear = tk.Button(frame_top, text="🗑 清除所有字段", command=self._clear_fields, bg="#ffebee")
        btn_clear.pack(side=tk.LEFT, padx=5)
        
        btn_save = tk.Button(frame_top, text="💾 应用并保存配置", command=self._save_fields_cfg, bg="#e8f5e9", font=("", 9, "bold"))
        btn_save.pack(side=tk.RIGHT, padx=5)
        
        # 提示文本
        tk.Label(frame_top, text="双击某行的【同步】列可快速切换 ☑/☐", fg="gray").pack(side=tk.RIGHT, padx=10)
        
        # 表格
        cols = ("name", "type", "desc", "sync")
        self.tree = ttk.Treeview(self.tab_fields, columns=cols, show="headings", height=20)
        self.tree.heading("name", text="字段名 (唯一键)")
        self.tree.heading("type", text="类型")
        self.tree.heading("desc", text="描述")
        self.tree.heading("sync", text="同步")
        
        self.tree.column("name", width=300, anchor=tk.W)
        self.tree.column("type", width=80, anchor=tk.CENTER)
        self.tree.column("desc", width=400, anchor=tk.W)
        self.tree.column("sync", width=80, anchor=tk.CENTER)
        
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 双击切换同步状态
        self.tree.bind("<Double-1>", self._on_tree_dblclick)
        
        self.sync_cfg_path = os.path.join(APP_DIR, "sync_fields.json")
        self._load_fields_cfg()

    def _on_tree_dblclick(self, event):
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if item and col == '#4':  # "sync" column
            vals = list(self.tree.item(item, 'values'))
            vals[3] = "☐" if vals[3] == "☑" else "☑"
            self.tree.item(item, values=tuple(vals))
            self._save_fields_cfg(silent=True)
            
    def _add_field_manual(self):
        import tkinter.simpledialog as sd
        name = sd.askstring("添加字段", "请输入要同步的 FMU 变量名称:")
        if not name: return
        self.tree.insert("", tk.END, values=(name, "Real", "手动添加", "☑"))
        self._save_fields_cfg(silent=True)

    def _clear_fields(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._save_fields_cfg(silent=True)

    def _parse_pasted_text(self):
        top = tk.Toplevel(self.root)
        top.title("智能解析粘贴文本 (Modelica 语法)")
        top.geometry("600x400")
        
        tk.Label(top, text="直接粘贴包含变量声明的代码 (如: output Real MTSatPos[3] ...):").pack(pady=5, anchor=tk.W, padx=10)
        txt = tk.Text(top, wrap=tk.WORD, height=15)
        txt.pack(fill=tk.BOTH, expand=True, padx=10)
        
        def do_parse():
            content = txt.get("1.0", tk.END).strip()
            lines = content.split('\n')
            import re
            added = 0
            for line in lines:
                line = line.strip()
                if not line: continue
                # 兼容 Modelica 和 普通名字
                m = re.search(r'(?:output\s+)?(?:(Real|Integer|Boolean|String)\s+)?([a-zA-Z0-9_\.]+)(?:\[(\d+)\])?(.*)', line)
                if m:
                    var_type = m.group(1) or 'Real'
                    base_name = m.group(2)
                    size = int(m.group(3)) if m.group(3) else 1
                    desc_match = re.search(r'\"([^\"]+)\"', m.group(4))
                    desc = desc_match.group(1) if desc_match else ''
                    
                    for i in range(1, size + 1):
                        name = f"{base_name}[{i}]" if size > 1 else base_name
                        # 检查去重
                        exists = False
                        for child in self.tree.get_children():
                            if self.tree.item(child, 'values')[0] == name:
                                exists = True; break
                        if not exists:
                            self.tree.insert("", tk.END, values=(name, var_type, desc, "☑"))
                            added += 1
            self._save_fields_cfg(silent=False)
            import tkinter.messagebox as mb
            mb.showinfo("完成", f"成功解析并添加了 {added} 个变量！")
            top.destroy()
            
        tk.Button(top, text="确认解析", command=do_parse, bg="#e8f5e9", height=2).pack(fill=tk.X, padx=10, pady=10)

    def _save_fields_cfg(self, silent=False):
        import json
        data = []
        for child in self.tree.get_children():
            v = self.tree.item(child, 'values')
            data.append({"name": str(v[0]), "type": str(v[1]), "desc": str(v[2]), "sync": (v[3] == "☑")})
        try:
            with open(self.sync_cfg_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if not silent:
                import tkinter.messagebox as mb
                mb.showinfo("成功", "配置已保存，下次打开将自动加载。")
        except: pass

    def _load_fields_cfg(self):
        import json
        if os.path.exists(self.sync_cfg_path):
            try:
                with open(self.sync_cfg_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in self.tree.get_children(): self.tree.delete(item)
                for d in data:
                    self.tree.insert("", tk.END, values=(d["name"], d.get("type", "Real"), d.get("desc", ""), "☑" if d.get("sync", True) else "☐"))
            except: pass

    def _setup_sim_tab(self):
        # --- 模型选择 ---
        frame_file = ttk.LabelFrame(self.tab_sim, text="1. 模型与路径配置")
        frame_file.pack(fill=tk.X, padx=10, pady=5)
        
        self.fmu_path_var = tk.StringVar(value=r"C:\Spaceship\FmuSolver_Package\FMU\MTLibrary_System_EPS_PD_EPS_CJ.fmu")
        tk.Entry(frame_file, textvariable=self.fmu_path_var, width=80).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(frame_file, text="浏览...", command=self.browse_file).pack(side=tk.LEFT, padx=5, pady=5)
        
        # --- 通信配置 ---
        frame_comm = ttk.LabelFrame(self.tab_sim, text="2. 通信网络设置")
        frame_comm.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(frame_comm, text="远程地址 (IP):").grid(row=0, column=0, padx=5, pady=5)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(frame_comm, textvariable=self.ip_var, width=15).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(frame_comm, text="端口:").grid(row=0, column=2, padx=5, pady=5)
        self.port_var = tk.IntVar(value=8889)
        tk.Entry(frame_comm, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=5, pady=5)
        
        # --- 初值设置 ---
        frame_init = ttk.LabelFrame(self.tab_sim, text="3. 初值与参数定义 (EPS_CJ)")
        frame_init.pack(fill=tk.X, padx=10, pady=5)
        
        self.cj_year = tk.IntVar(value=2026); self.cj_mon = tk.IntVar(value=3); self.cj_day = tk.IntVar(value=31)
        self.cj_hour = tk.IntVar(value=12); self.cj_min = tk.IntVar(value=19); self.cj_sec = tk.DoubleVar(value=0.0)
        
        time_inputs = [
            ("Year:", self.cj_year, 0, 0), ("Mon:", self.cj_mon, 0, 2), ("Day:", self.cj_day, 0, 4),
            ("Hour:", self.cj_hour, 1, 0), ("Min:", self.cj_min, 1, 2), ("Sec:", self.cj_sec, 1, 4),
        ]
        for label, var, r, c in time_inputs:
            tk.Label(frame_init, text=label).grid(row=r, column=c, padx=5, pady=2, sticky=tk.E)
            tk.Entry(frame_init, textvariable=var, width=8).grid(row=r, column=c+1, padx=2, sticky=tk.W)

        self.cj_table_a = tk.StringVar(value="1000, 3640; 2000, 3640")
        self.cj_table_b = tk.StringVar(value="1000, 3640; 2000, 3640")
        self.cj_table_fb = tk.StringVar(value="1000, 360, 184; 2000, 360, 184")
        self.cj_table_att = tk.StringVar(value="1000, 0, 3, 90; 2000, 0, 3, 90")
        
        tk.Label(frame_init, text="Table_A:").grid(row=2, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_a, width=50).grid(row=2, column=1, columnspan=5, sticky=tk.W)
        tk.Label(frame_init, text="Table_B:").grid(row=3, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_b, width=50).grid(row=3, column=1, columnspan=5, sticky=tk.W)
        tk.Label(frame_init, text="Table_FB:").grid(row=4, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_fb, width=50).grid(row=4, column=1, columnspan=5, sticky=tk.W)
        tk.Label(frame_init, text="Table_Att:").grid(row=5, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_att, width=50).grid(row=5, column=1, columnspan=5, sticky=tk.W)

        # --- 策略参数 ---
        frame_params = ttk.LabelFrame(self.tab_sim, text="4. 仿真策略配置")
        frame_params.pack(fill=tk.X, padx=10, pady=5)
        
        self.step_var = tk.DoubleVar(value=0.02)
        self.rate_var = tk.DoubleVar(value=1.0)
        self.freq_var = tk.DoubleVar(value=50.0)
        self.time_var = tk.DoubleVar(value=99999.0)
        
        grid_params = [
            ("步长 (s):", self.step_var, 0, 0), ("仿真速率:", self.rate_var, 0, 2),
            ("采样频率(Hz):", self.freq_var, 1, 0), ("自动停止(s):", self.time_var, 1, 2)
        ]
        for label, var, r, c in grid_params:
            tk.Label(frame_params, text=label).grid(row=r, column=c, padx=5, pady=5, sticky=tk.E)
            tk.Entry(frame_params, textvariable=var, width=12).grid(row=r, column=c+1, padx=5, pady=5, sticky=tk.W)

        # --- 控制按钮 ---
        frame_btn = tk.Frame(self.tab_sim)
        frame_btn.pack(fill=tk.X, padx=10, pady=10)
        self.btn_start = tk.Button(frame_btn, text="▶ 启动实时仿真", command=self.start_sim, bg="#e1f5fe", font=("微软雅黑", 10, "bold"), padx=15)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_update = tk.Button(frame_btn, text="♻ 应用参数", command=self.update_params, bg="#f1f8e9", padx=10)
        self.btn_update.pack(side=tk.LEFT, padx=5)
        
        self.is_initial_val = 0.0
        self.btn_initial = tk.Button(frame_btn, text="⚡ 同步信号 (0)", bg="#fff9c4", command=self.toggle_is_initial, padx=10)
        self.btn_initial.pack(side=tk.LEFT, padx=5)

        self.btn_stop = tk.Button(frame_btn, text="⏹ 停止仿真", command=self.stop_sim, bg="#ffebee", state=tk.DISABLED, padx=10)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="OS Ready")
        tk.Label(frame_btn, textvariable=self.status_var, fg="#666").pack(side=tk.RIGHT, padx=10)

        # --- 日志面板 ---
        frame_log = ttk.LabelFrame(self.tab_sim, text="实时日志")
        frame_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.txt_log = scrolledtext.ScrolledText(frame_log, wrap=tk.WORD, height=12, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.txt_log.tag_config("info", foreground="#1b5e20"); self.txt_log.tag_config("error", foreground="#b71c1c"); self.txt_log.tag_config("sys", foreground="#455a64")

    def _setup_orbit_tab(self):
        # 独立FMU路径选择
        frame_orbit_fmu = ttk.LabelFrame(self.tab_orbit, text="0. 轨道预示 FMU 模型")
        frame_orbit_fmu.pack(fill=tk.X, padx=10, pady=5)
        self.orbit_fmu_path_var = tk.StringVar(value=r"C:\Spaceship\FmuSolver_Package\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu")
        tk.Entry(frame_orbit_fmu, textvariable=self.orbit_fmu_path_var, width=72).pack(side=tk.LEFT, padx=5, pady=4)
        ttk.Button(frame_orbit_fmu, text="浏览...", command=lambda: self.orbit_fmu_path_var.set(
            filedialog.askopenfilename(filetypes=[("FMU", "*.fmu")]) or self.orbit_fmu_path_var.get()
        )).pack(side=tk.LEFT, padx=3)

        # 轨道参数输入
        frame_input = ttk.LabelFrame(self.tab_orbit, text="1. 轨道初始根数设置")
        frame_input.pack(fill=tk.X, padx=10, pady=5)
        
        # NOTE: Year is auto-managed by the engine (FMU EOP covers 2026+)
        self.year_var = tk.IntVar(value=2026); self.mon_var = tk.IntVar(value=4); self.day_var = tk.IntVar(value=10)
        self.hour_var = tk.IntVar(value=8); self.min_var = tk.IntVar(value=0); self.sec_var = tk.DoubleVar(value=0.0)
        self.a_mt_var = tk.DoubleVar(value=6766.71777); self.e_mt_var = tk.DoubleVar(value=0.00110); self.i_mt_var = tk.DoubleVar(value=0.72653)
        self.OMEGA_mt_var = tk.DoubleVar(value=2.39969); self.omega_mt_var = tk.DoubleVar(value=1.34409); self.f_mt_var = tk.DoubleVar(value=1.00447)
        # EOP notice
        tk.Label(frame_input, text="⚠ 计算年份受 FMU EOP 数据范围限制 (2026)，年份将自动修正",
                 fg="#b26a00", font=("微软雅黑", 8)).grid(row=4, column=0, columnspan=6, sticky=tk.W, padx=5)
        
        inputs = [
            ("Year:", self.year_var, 0, 0), ("Mon:", self.mon_var, 0, 2), ("Day:", self.day_var, 0, 4),
            ("Hour:", self.hour_var, 1, 0), ("Min:", self.min_var, 1, 2), ("Sec:", self.sec_var, 1, 4),
            ("a_MT (km):", self.a_mt_var, 2, 0), ("e_MT:", self.e_mt_var, 2, 2), ("i_MT (rad):", self.i_mt_var, 2, 4),
            ("OMEGA(rad):", self.OMEGA_mt_var, 3, 0), ("omega(rad):", self.omega_mt_var, 3, 2), ("f_MT(rad):", self.f_mt_var, 3, 4)
        ]
        for label, var, r, c in inputs:
            tk.Label(frame_input, text=label).grid(row=r, column=c, padx=5, pady=5, sticky=tk.E)
            tk.Entry(frame_input, textvariable=var, width=12).grid(row=r, column=c+1, padx=5, sticky=tk.W)

        # 策略参数
        frame_strat = ttk.LabelFrame(self.tab_orbit, text="2. 离线计算策略配置")
        frame_strat.pack(fill=tk.X, padx=10, pady=5)
        
        self.orbit_step = tk.DoubleVar(value=10.0)   # FMU requires multiples of 10s
        self.orbit_rate = tk.DoubleVar(value=0.0)
        self.orbit_freq = tk.DoubleVar(value=0.1) # 默认 10s 一行，即 0.1Hz
        self.orbit_duration = tk.DoubleVar(value=86400.0)
        
        strats = [
            ("计算步长 (s):", self.orbit_step, 0, 0), ("仿真速率 (0=最大):", self.orbit_rate, 0, 2),
            ("采样频率 (Hz):", self.orbit_freq, 1, 0), ("计算时长 (s):", self.orbit_duration, 1, 2)
        ]
        for label, var, r, c in strats:
            tk.Label(frame_strat, text=label).grid(row=r, column=c, padx=5, pady=5, sticky=tk.E)
            tk.Entry(frame_strat, textvariable=var, width=15).grid(row=r, column=c+1, padx=5, sticky=tk.W)

        # 运行控制
        frame_ctrl = ttk.Frame(self.tab_orbit)
        frame_ctrl.pack(fill=tk.X, padx=10, pady=10)
        self.btn_run_orbit = tk.Button(frame_ctrl, text="🚀 开始预示解析", command=self.run_orbit_precalc, bg="#e8f5e9", font=("微软雅黑", 10, "bold"), padx=25)
        self.btn_run_orbit.pack(side=tk.LEFT, padx=5)
        self.btn_stop_orbit = tk.Button(frame_ctrl, text="⏹ 停止", command=self.stop_orbit, bg="#ffebee", padx=15, state=tk.DISABLED)
        self.btn_stop_orbit.pack(side=tk.LEFT, padx=5)
        self.btn_export_txt = tk.Button(frame_ctrl, text="💾 导出结果", command=self.export_orbit_txt, bg="#f3e5f5", padx=20, state=tk.DISABLED)
        self.btn_export_txt.pack(side=tk.LEFT, padx=5)

        # 独立日志框
        frame_olog = ttk.LabelFrame(self.tab_orbit, text="轨道预示日志")
        frame_olog.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.txt_orbit_log = scrolledtext.ScrolledText(frame_olog, wrap=tk.WORD, height=12, font=("Consolas", 9))
        self.txt_orbit_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.txt_orbit_log.tag_config("info", foreground="#1b5e20")
        self.txt_orbit_log.tag_config("error", foreground="#b71c1c")
        self.txt_orbit_log.tag_config("sys", foreground="#455a64")
        self.olog("[SYS] 轨道预示模块就绪。", "sys")

    def _setup_data_tab(self):
        self.txt_data = scrolledtext.ScrolledText(self.tab_data, wrap=tk.NONE, font=("Consolas", 10), bg="#fafafa")
        self.txt_data.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("FMU Files", "*.fmu")]); 
        if f: self.fmu_path_var.set(f)
        
    def log(self, msg, tag="sys"):
        self.txt_log.insert(tk.END, msg + "\n", tag); self.txt_log.see(tk.END)

    def olog(self, msg, tag="sys"):
        """Orbit-specific log panel"""
        self.txt_orbit_log.insert(tk.END, msg + "\n", tag); self.txt_orbit_log.see(tk.END)

    def get_cj_params(self):
        return {
            "Year": self.cj_year.get(), "Mon": self.cj_mon.get(), "Day": self.cj_day.get(),
            "Hour": self.cj_hour.get(), "Min": self.cj_min.get(), "Sec": self.cj_sec.get(),
            "Table_A": self.cj_table_a.get(), "Table_B": self.cj_table_b.get(),
            "Table_FB": self.cj_table_fb.get(), "Table_Att": self.cj_table_att.get()
        }

    def start_sim(self):
        fmu_path = self.fmu_path_var.get().strip()
        if not os.path.exists(fmu_path): self.log(f"[!] 找不到文件 {fmu_path}", "error"); return
        fmu_bit = get_fmu_arch(fmu_path)
        cmd = [sys.executable]
        if not getattr(sys, 'frozen', False): cmd.append(os.path.abspath(__file__))
        sim_args = ["--step", str(self.step_var.get()), "--rate", str(self.rate_var.get()), 
                    "--freq", str(self.freq_var.get()), "--time", str(self.time_var.get()),
                    "--params", json.dumps(self.get_cj_params())]
        cmd.extend(["--worker", fmu_path, "--ip", self.ip_var.get(), "--port", str(self.port_var.get()), "--sync_vars", getattr(self, "sync_cfg_path", "sync_fields.json")] + sim_args)
        if fmu_bit != self.current_arch:
            worker_p = os.path.join(APP_DIR, f"FmuWorker{fmu_bit}.exe")
            if not os.path.exists(worker_p): self.log(f"[!] 缺少网桥 {worker_p}", "error"); return
            cmd = [worker_p, fmu_path, "--ip", self.ip_var.get(), "--port", str(self.port_var.get()), "--sync_vars", getattr(self, "sync_cfg_path", "sync_fields.json")] + sim_args
        self.btn_start.config(state=tk.DISABLED); self.btn_stop.config(state=tk.NORMAL)
        try:
            self.worker_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=APP_DIR)
            self.root.after(1500, self.update_params)
            threading.Thread(target=self._read_worker_logs, daemon=True).start()
        except: self.stop_sim()

    def _read_worker_logs(self):
        if not self.worker_process: return
        for line in iter(self.worker_process.stdout.readline, ''):
            if not line: continue
            tag = "info" if "[OK]" in line else ("error" if "[!]" in line else "sys")
            self.root.after(0, self.log, line.strip(), tag)
        self.worker_process.stdout.close(); self.worker_process.wait(); self.root.after(0, self._reset_ui)

    def _reset_ui(self):
        self.btn_start.config(state=tk.NORMAL); self.btn_stop.config(state=tk.DISABLED); self.worker_process = None

    def stop_sim(self):
        if self.worker_process:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try: sock.sendto(json.dumps({"exit": True}).encode('utf-8'), ("127.0.0.1", 8888))
            except: pass
            finally: sock.close()
            self.root.after(300, lambda: subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.worker_process.pid)], creationflags=subprocess.CREATE_NO_WINDOW) if self.worker_process else None)
        self._reset_ui()

    def update_params(self):
        cmd = {"step_size": self.step_var.get(), "sim_time": self.time_var.get(), "sim_rate": self.rate_var.get(), "sample_freq": self.freq_var.get()}
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: s.sendto(json.dumps(cmd).encode('utf-8'), ("127.0.0.1", 8888))
        except: pass
        finally: s.close()

    def toggle_is_initial(self):
        if self.is_initial_val == 0.0:
            self.is_initial_val = 1.0
            self.btn_initial.config(text="⚡ 同步信号 (1) 🟢", bg="#ffb74d")
        else:
            self.is_initial_val = 0.0
            self.btn_initial.config(text="⚡ 同步信号 (0) ⚪", bg="#fff9c4")
        self.send_ctrl_signal("Is_initial", self.is_initial_val)

    def send_ctrl_signal(self, name, val):
        if self.worker_process:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try: s.sendto(json.dumps({name: val}).encode('utf-8'), ("127.0.0.1", 8888))
            except: pass
            finally: s.close()

    def run_orbit_precalc(self):
        fmu_path = self.orbit_fmu_path_var.get().strip()   # Use orbit-specific FMU path
        worker_path = os.path.join(APP_DIR, "OrbitPreCalc32.exe")
        if not os.path.exists(worker_path):
            self.olog("[!] 找不到计算引擎 OrbitPreCalc32.exe", "error"); return
        if not os.path.exists(fmu_path):
            self.olog(f"[!] 找不到FMU文件: {fmu_path}", "error"); return

        params = {"Year": self.year_var.get(), "Mon": self.mon_var.get(), "Day": self.day_var.get(), "Hour": self.hour_var.get(), "Min": self.min_var.get(), "Sec": self.sec_var.get(),
            "a_MT": self.a_mt_var.get(), "e_MT": self.e_mt_var.get(), "i_MT": self.i_mt_var.get(), "OMEGA_MT": self.OMEGA_mt_var.get(), "omega_MT": self.omega_mt_var.get(), "f_MT": self.f_mt_var.get()}
        cmd = [worker_path, fmu_path,
               "--params",      json.dumps(params),
               "--stop_time",   str(self.orbit_duration.get()),
               "--step_size",   str(self.orbit_step.get()),
               "--sample_freq", str(self.orbit_freq.get()),
               "--sim_rate",    str(self.orbit_rate.get())]

        self.olog(f"[*] 启动轨道计算引擎...", "sys")
        self.olog(f"[*] 步长={self.orbit_step.get()}s | 频率={self.orbit_freq.get()}Hz | 时长={self.orbit_duration.get()}s | 速率={self.orbit_rate.get()}x", "sys")
        self.btn_run_orbit.config(state=tk.DISABLED, text="计算中...")
        self.btn_stop_orbit.config(state=tk.NORMAL)
        self.orbit_proc = None

        def run_thread():
            try:
                self.orbit_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=APP_DIR)
                ready_file = None
                for line in iter(self.orbit_proc.stdout.readline, ''):
                    line = line.strip()
                    if not line: continue
                    if "[EXPORT_READY]" in line:
                        ready_file = line.replace("[EXPORT_READY]", "").strip()
                    tag = "info" if "[OK]" in line or "SUCCESS" in line else ("error" if "[!]" in line or "Error" in line or "Fatal" in line else "sys")
                    self.root.after(0, self.olog, line, tag)
                self.orbit_proc.stdout.close()
                rc = self.orbit_proc.wait()

                if ready_file and os.path.exists(ready_file):
                    with open(ready_file, 'r') as f:
                        self.orbit_data = json.load(f)
                    self.root.after(0, self._display_orbit_results)
                    self.root.after(0, lambda: self.btn_export_txt.config(state=tk.NORMAL))
                    self.root.after(0, self.olog, f"[OK] 解析完成，共 {len(self.orbit_data)} 行数据。", "info")
                else:
                    self.root.after(0, self.olog, f"[!] 计算结束但未找到结果文件 (rc={rc})。", "error")
            except Exception as e:
                self.root.after(0, self.olog, f"[!] 线程异常: {e}", "error")
            finally:
                self.orbit_proc = None
                self.root.after(0, lambda: self.btn_run_orbit.config(state=tk.NORMAL, text="🚀 开始预示解析"))
                self.root.after(0, lambda: self.btn_stop_orbit.config(state=tk.DISABLED))

        threading.Thread(target=run_thread, daemon=True).start()

    def stop_orbit(self):
        if hasattr(self, 'orbit_proc') and self.orbit_proc:
            try:
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.orbit_proc.pid)],
                                creationflags=subprocess.CREATE_NO_WINDOW)
                self.olog("[!] 用户手动停止计算进程。", "error")
            except: pass

    def _display_orbit_results(self):
        self.notebook.select(self.tab_data); self.txt_data.delete(1.0, tk.END)
        self.txt_data.insert(tk.END, f"{'Time':<10} | {'JD':<13} | {'a':<10} | {'e':<9} | {'i':<9} | {'OMEGA':<9} | {'omega':<9} | {'f':<9}\n" + "-"*90 + "\n")
        for row in self.orbit_data[:200]:
            self.txt_data.insert(tk.END, "{:<10.1f} | {:<13.5f} | {:<10.2f} | {:<9.5f} | {:<9.5f} | {:<9.5f} | {:<9.5f} | {:<9.5f}\n".format(*row))
        if len(self.orbit_data) > 200: self.txt_data.insert(tk.END, "... 余下数据点击导出查看 ...\n")

    def export_orbit_txt(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="Orbit_Pre.txt")
        if not f: return
        try:
            with open(f, 'w') as out:
                out.write("#1\ndouble table({},7)\n".format(len(self.orbit_data)))
                for row in self.orbit_data: out.write("\t".join([f"{x:.5f}" for x in row[1:]]) + "\n")
            self.log(f"[OK] 导出成功: {f}", "info")
        except Exception as e: self.log(f"[!] 导出失败: {e}", "error")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        import argparse; parser = argparse.ArgumentParser()
        parser.add_argument("--worker", action="store_true"); parser.add_argument("fmu_path"); parser.add_argument("--ip", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8889); parser.add_argument("--sync_vars", default=None)
        args = parser.parse_args(); os.chdir(APP_DIR)
        try: from fmu_player import FMUPlayer; FMUPlayer(args.fmu_path, remote_ip=args.ip, remote_port=args.port, sync_vars_file=args.sync_vars).run()
        except: pass
        sys.exit(0)
    else: root = tk.Tk(); FmuSolverGUI(root); root.mainloop()
