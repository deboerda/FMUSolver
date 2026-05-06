import sys
import os

# ── 统一重定向临时目录到 C 盘，解决非系统盘运行不稳定的问题 ──
def setup_runtime_temp():
    import shutil
    import tempfile
    
    # 核心根目录
    base_temp = "C:\\FmuSolver_Runtime"
    try:
        if not os.path.exists(base_temp):
            os.makedirs(base_temp, exist_ok=True)
            
        # 启动时清理：尝试删除所有旧的残留目录 (session_* 和 job_*)
        for item in os.listdir(base_temp):
            if item.startswith("session_") or item.startswith("job_"):
                item_path = os.path.join(base_temp, item)
                if os.path.isdir(item_path):
                    try:
                        # 尝试删除，如果文件夹正被其它 FmuSolver 实例占用，会失败跳过
                        shutil.rmtree(item_path)
                    except:
                        pass
    except:
        # 如果 C 盘根目录完全无法写入（极罕见），则回退到系统默认
        base_temp = tempfile.gettempdir()

    # 为本次运行创建唯一的子目录，避免多开冲突
    import uuid
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    current_run_dir = os.path.join(base_temp, session_id)
    os.makedirs(current_run_dir, exist_ok=True)
    
    # 设置环境变量，确保 FMPy 和其它模块使用此路径
    os.environ['TEMP'] = current_run_dir
    os.environ['TMP'] = current_run_dir
    return current_run_dir

RUNTIME_TEMP = setup_runtime_temp()
# ──────────────────────────────────────────────────────────

import subprocess
import threading
import json
import socket
import struct
import zipfile
import time
import re
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext

# ─── 运行时路径逻辑 ───
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

CONTROL_PORT = 8898
GUI_CONFIG_PATH = os.path.join(APP_DIR, "gui_config.json")

def get_fmu_arch(fmu_path):
    """快速检测 FMU 架构"""
    try:
        with zipfile.ZipFile(fmu_path, 'r') as z:
            names = z.namelist()
            if any(n.startswith('binaries/win64/') for n in names): return 64
            if any(n.startswith('binaries/win32/') for n in names): return 32
    except: pass
    return None


def _norm_existing(path):
    if path and os.path.exists(path):
        return os.path.normpath(path)
    return None


def _find_file_by_names(search_roots, names):
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for name in names:
            direct = os.path.join(root, name)
            if os.path.exists(direct):
                return os.path.normpath(direct)
        for current_root, _, files in os.walk(root):
            file_map = {f.lower(): f for f in files}
            for name in names:
                hit = file_map.get(name.lower())
                if hit:
                    return os.path.normpath(os.path.join(current_root, hit))
    return None


def _find_file_by_keywords(search_roots, keywords, suffix=""):
    lower_keywords = [k.lower() for k in keywords]
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for current_root, _, files in os.walk(root):
            for file_name in files:
                lower_name = file_name.lower()
                if suffix and not lower_name.endswith(suffix.lower()):
                    continue
                if all(k in lower_name for k in lower_keywords):
                    return os.path.normpath(os.path.join(current_root, file_name))
    return None


def auto_find_fmu(preferred_names, keywords):
    search_roots = [os.path.join(APP_DIR, "FMU"), APP_DIR]
    return (
        _find_file_by_names(search_roots, preferred_names)
        or _find_file_by_keywords(search_roots, keywords, suffix=".fmu")
    )


def auto_find_yaoce_dir():
    candidates = [
        os.path.join(APP_DIR, "yaocetest"),
        os.path.join(APP_DIR, "dist", "yaocetest"),
    ]
    for candidate in candidates:
        if os.path.exists(os.path.join(candidate, "config.ini")):
            return os.path.normpath(candidate)

    for current_root, dirs, _ in os.walk(APP_DIR):
        for dir_name in dirs:
            if dir_name.lower() != "yaocetest":
                continue
            candidate = os.path.join(current_root, dir_name)
            if os.path.exists(os.path.join(candidate, "config.ini")):
                return os.path.normpath(candidate)

    return os.path.normpath(os.path.join(APP_DIR, "yaocetest"))

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
        self.gui_config_path = GUI_CONFIG_PATH
        self.gui_config = self._load_gui_config()
        self.default_sim_fmu = self._resolve_sim_fmu_path()
        self.default_orbit_fmu = self._resolve_orbit_fmu_path()
        self.yaoce_dir = self._resolve_yaoce_dir()
        self.default_ip = str(self.gui_config.get("ip", "127.0.0.1"))
        try:
            self.default_port = int(self.gui_config.get("port", 8889))
        except Exception:
            self.default_port = 8889
        
        self.create_widgets()

    def _load_gui_config(self):
        if os.path.exists(self.gui_config_path):
            try:
                with open(self.gui_config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _resolve_sim_fmu_path(self):
        auto_path = auto_find_fmu(
            ["MTLibrary_System_EPS_PD_EPS_CJ.fmu", "FMU_Model1.fmu", "TestFmu.fmu"],
            ["eps", "cj"],
        )
        return auto_path or _norm_existing(self.gui_config.get("sim_fmu")) or ""

    def _resolve_orbit_fmu_path(self):
        auto_path = auto_find_fmu(
            ["MTLibrary_System_EPS_PD_Orbit_Pre.fmu"],
            ["orbit", "pre"],
        )
        return auto_path or _norm_existing(self.gui_config.get("orbit_fmu")) or ""

    def _resolve_yaoce_dir(self):
        auto_path = auto_find_yaoce_dir()
        return auto_path or _norm_existing(self.gui_config.get("yaoce_dir")) or os.path.normpath(os.path.join(APP_DIR, "yaocetest"))

    def _child_env(self):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _save_gui_config(self):
        data = {
            "sim_fmu": self.fmu_path_var.get().strip() if hasattr(self, "fmu_path_var") else self.default_sim_fmu,
            "orbit_fmu": self.orbit_fmu_path_var.get().strip() if hasattr(self, "orbit_fmu_path_var") else self.default_orbit_fmu,
            "yaoce_dir": os.path.normpath(self.yaoce_dir) if getattr(self, "yaoce_dir", "") else "",
            "ip": self.ip_var.get().strip() if hasattr(self, "ip_var") else self.default_ip,
            "port": int(self.port_var.get()) if hasattr(self, "port_var") else self.default_port,
        }
        try:
            with open(self.gui_config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _browse_orbit_file(self):
        initial_dir = os.path.dirname(self.orbit_fmu_path_var.get().strip()) or os.path.join(APP_DIR, "FMU")
        f = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("FMU", "*.fmu")])
        if f:
            self.orbit_fmu_path_var.set(os.path.normpath(f))
            self._save_gui_config()

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tab_orbit = ttk.Frame(self.notebook)
        self.tab_sim = ttk.Frame(self.notebook)
        self.tab_yaoce = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_orbit, text=" 轨道预示计算 ")
        self.notebook.add(self.tab_sim, text=" 实时仿真控制 ")
        self.notebook.add(self.tab_yaoce, text=" 遥测接收转发 ")
        
        self._setup_orbit_tab()
        self._setup_sim_tab()
        self._setup_yaoce_tab()

    def _setup_yaoce_tab(self):
        # 1. 配置文件检查区域
        frame_cfg = ttk.LabelFrame(self.tab_yaoce, text="1. 配置文件与过滤白名单检查 (支持进厂断网环境查验)")
        frame_cfg.pack(fill=tk.X, padx=10, pady=5)
        
        dir_frame = tk.Frame(frame_cfg)
        dir_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.lbl_yaoce_dir = tk.Label(dir_frame, text=f"当前配置读取目录: {self.yaoce_dir}", fg="#455a64")
        self.lbl_yaoce_dir.pack(side=tk.LEFT)
        
        def choose_dir():
            d = filedialog.askdirectory(title="选择遥测配置文件目录 (需包含 config.ini)", initialdir=APP_DIR)
            if d:
                self.yaoce_dir = os.path.normpath(d)
                self.lbl_yaoce_dir.config(text=f"当前配置读取目录: {self.yaoce_dir}")
                self._save_gui_config()
                
        tk.Button(dir_frame, text="更改目录...", command=choose_dir, bg="#e0e0e0").pack(side=tk.RIGHT, padx=5)
        
        btn_frame = tk.Frame(frame_cfg)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        def open_config():
            cfg_path = os.path.join(self.yaoce_dir, "config.ini")
            if os.path.exists(cfg_path): os.startfile(cfg_path)
            else: self.ylog(f"[!] {cfg_path} 不存在! (请检查当前配置目录)", "error")
            
        def open_xml():
            xml_path = os.path.join(self.yaoce_dir, "ParamFilter.xml")
            if os.path.exists(xml_path): os.startfile(xml_path)
            else: self.ylog(f"[!] {xml_path} 不存在!", "error")
        
        tk.Button(btn_frame, text="📄 打开 config.ini (修改目标IP)", command=open_config, bg="#e3f2fd").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📄 打开 ParamFilter.xml (修改过滤参数)", command=open_xml, bg="#f3e5f5").pack(side=tk.LEFT, padx=5)
        
        # 2. 控制服务启动停止
        frame_ctrl = ttk.Frame(self.tab_yaoce)
        frame_ctrl.pack(fill=tk.X, padx=10, pady=10)
        
        self.btn_yaoce_start = tk.Button(frame_ctrl, text="▶ 启动遥测转发引擎", command=self.start_yaoce, bg="#e1f5fe", font=("微软雅黑", 10, "bold"), padx=15)
        self.btn_yaoce_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_yaoce_stop = tk.Button(frame_ctrl, text="⏹ 停止服务", command=self.stop_yaoce, bg="#ffebee", state=tk.DISABLED, padx=15)
        self.btn_yaoce_stop.pack(side=tk.LEFT, padx=5)
        
        # 3. 独立且完善的日志记录框
        frame_ylog = ttk.LabelFrame(self.tab_yaoce, text="2. 转发服务实时调试日志 (详细捕获)")
        frame_ylog.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.txt_yaoce_log = scrolledtext.ScrolledText(frame_ylog, wrap=tk.WORD, height=20, font=("Consolas", 10), bg="white", fg="black")
        self.txt_yaoce_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.txt_yaoce_log.tag_config("info", foreground="green")
        self.txt_yaoce_log.tag_config("error", foreground="red")
        self.txt_yaoce_log.tag_config("sys", foreground="blue")
        self.ylog("[SYS] 遥测接收转发模块已就绪，请先检查参数配置是否正确。", "sys")
        
    def ylog(self, msg, tag="sys"):
        self.txt_yaoce_log.insert(tk.END, msg + "\n", tag)
        self.txt_yaoce_log.see(tk.END)
        
    def start_yaoce(self):
        worker_cmd = [sys.executable]
        if not getattr(sys, 'frozen', False): worker_cmd.append(os.path.abspath(__file__))
        worker_cmd.extend(["--yaoceworker", self.yaoce_dir])
        
        self.btn_yaoce_start.config(state=tk.DISABLED)
        self.btn_yaoce_stop.config(state=tk.NORMAL)
        
        self.ylog("===========================================", "sys")
        self.ylog(f"[*] 启动底层遥测子进程... CMD={worker_cmd}", "sys")
        
        # UI端主动清空老日志，避免被旧数据污染或截断判定干扰
        log_file = os.path.join(APP_DIR, "yaoce_run.log")
        try:
            with open(log_file, "w", encoding="utf-8") as f: f.write("")
        except: pass

        self._yaoce_log_pos = 0
        try:
            self.yaoce_proc = subprocess.Popen(worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=APP_DIR, env=self._child_env())
            
            def poll_log():
                if not hasattr(self, 'yaoce_proc') or not self.yaoce_proc: return
                if os.path.exists(log_file):
                    try:
                        sz = os.path.getsize(log_file)
                        if sz < self._yaoce_log_pos: self._yaoce_log_pos = 0
                        with open(log_file, "r", encoding="utf-8") as f:
                            f.seek(self._yaoce_log_pos)
                            new_data = f.read()
                            self._yaoce_log_pos = f.tell()
                            if new_data:
                                for l in new_data.split('\n'):
                                    l = l.strip()
                                    if not l: continue
                                    tag = "sys"
                                    if "[SEND]" in l or "[TCP/UDP]" in l or "[RECV]" in l or "[OK]" in l or "[*]" in l: tag = "info"
                                    elif "[-]" in l: tag = "error"
                                    elif "[WARN]" in l: tag = "error"
                                    elif "[!]" in l or "Error" in l or "Exception" in l: tag = "error"
                                    self.ylog(l, tag)
                    except: pass
                
                if self.yaoce_proc.poll() is None:
                    self.root.after(200, poll_log)
                else:
                    self.ylog(f"[SYS] 转发引擎退出，退出码: {self.yaoce_proc.poll()}", "sys")
                    self.btn_yaoce_start.config(state=tk.NORMAL)
                    self.btn_yaoce_stop.config(state=tk.DISABLED)

            self.root.after(200, poll_log)
        except Exception as e:
            self.ylog(f"[!] 独立子进程启动致命失败: {e}", "error")
            self.stop_yaoce()


    def stop_yaoce(self):
        if hasattr(self, 'yaoce_proc') and self.yaoce_proc:
            try:
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.yaoce_proc.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
                self.ylog("[*] 发送强制终止指令...", "error")
            except: pass
            self.yaoce_proc = None
        self.btn_yaoce_start.config(state=tk.NORMAL)
        self.btn_yaoce_stop.config(state=tk.DISABLED)

    def _open_fields_window(self):
        top = tk.Toplevel(self.root)
        top.title("同步变量字段配置 (DDM 映射)")
        top.geometry("900x600")
        
        # 顶部操作栏
        frame_top = tk.Frame(top)
        frame_top.pack(fill=tk.X, padx=10, pady=5)
        
        btn_add = tk.Button(frame_top, text="+ 手动添加", command=self._add_field_manual, bg="#e0f7fa")
        btn_add.pack(side=tk.LEFT, padx=5)
        
        btn_parse = tk.Button(frame_top, text="⚡ 智能解析粘贴文本", command=self._parse_pasted_text, bg="#fff9c4")
        btn_parse.pack(side=tk.LEFT, padx=5)
        
        btn_clear = tk.Button(frame_top, text="🗑 清除所有字段", command=self._clear_fields, bg="#ffebee")
        btn_clear.pack(side=tk.LEFT, padx=5)
        
        btn_save = tk.Button(frame_top, text="💾 应用并关闭", command=lambda: [self._save_fields_cfg(), top.destroy()], bg="#e8f5e9", font=("", 9, "bold"))
        btn_save.pack(side=tk.RIGHT, padx=5)
        
        # 提示文本
        tk.Label(frame_top, text="双击某行的【同步】列可快速切换 ☑/☐", fg="gray").pack(side=tk.RIGHT, padx=10)
        
        # 表格
        cols = ("name", "type", "desc", "sync")
        self.tree = ttk.Treeview(top, columns=cols, show="headings", height=20)
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
        
        self.fmu_path_var = tk.StringVar(value=self.default_sim_fmu)
        tk.Entry(frame_file, textvariable=self.fmu_path_var, width=80).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(frame_file, text="浏览...", command=self.browse_file).pack(side=tk.LEFT, padx=5, pady=5)
        
        # --- 通信配置 ---
        frame_comm = ttk.LabelFrame(self.tab_sim, text="2. 通信网络设置")
        frame_comm.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(frame_comm, text="远程地址 (IP):").grid(row=0, column=0, padx=5, pady=5)
        self.ip_var = tk.StringVar(value=self.default_ip)
        tk.Entry(frame_comm, textvariable=self.ip_var, width=15).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(frame_comm, text="端口:").grid(row=0, column=2, padx=5, pady=5)
        self.port_var = tk.IntVar(value=self.default_port)
        tk.Entry(frame_comm, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=5, pady=5)
        
        # --- 初值设置 ---
        frame_init = ttk.LabelFrame(self.tab_sim, text="3. 初值与参数定义 (EPS_CJ)")
        frame_init.pack(fill=tk.X, padx=10, pady=5)
        
        self.cj_year = tk.IntVar(value=2026); self.cj_mon = tk.IntVar(value=3); self.cj_day = tk.IntVar(value=31)
        self.cj_hour = tk.IntVar(value=12); self.cj_min = tk.IntVar(value=19); self.cj_sec = tk.DoubleVar(value=0.0)
        
        # 时间备注
        tk.Label(frame_init, text="[时间初值] (年-月-日 时:分:秒):", fg="#0277bd").grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        time_inputs = [
            ("Year:", self.cj_year, 1, 0), ("Mon:", self.cj_mon, 1, 2), ("Day:", self.cj_day, 1, 4),
            ("Hour:", self.cj_hour, 2, 0), ("Min:", self.cj_min, 2, 2), ("Sec:", self.cj_sec, 2, 4),
        ]
        for label, var, r, c in time_inputs:
            tk.Label(frame_init, text=label).grid(row=r, column=c, padx=5, pady=2, sticky=tk.E)
            tk.Entry(frame_init, textvariable=var, width=8).grid(row=r, column=c+1, padx=2, sticky=tk.W)

        self.cj_table_a = tk.StringVar(value="1000, 3640; 2000, 3640")
        self.cj_table_b = tk.StringVar(value="1000, 3640; 2000, 3640")
        self.cj_table_fb = tk.StringVar(value="1000, 360, 184; 2000, 360, 184")
        self.cj_table_att = tk.StringVar(value="1000, 0, 3, 90; 2000, 0, 3, 90")
        
        tk.Label(frame_init, text="Table_A (太阳帆板A指令):").grid(row=3, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_a, width=50).grid(row=3, column=1, columnspan=5, sticky=tk.W)
        tk.Label(frame_init, text="Table_B (太阳帆板B指令):").grid(row=4, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_b, width=50).grid(row=4, column=1, columnspan=5, sticky=tk.W)
        tk.Label(frame_init, text="Table_FB (分流器状态):").grid(row=5, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_fb, width=50).grid(row=5, column=1, columnspan=5, sticky=tk.W)
        tk.Label(frame_init, text="Table_Att (姿态四元数):").grid(row=6, column=0, sticky=tk.E, pady=2)
        tk.Entry(frame_init, textvariable=self.cj_table_att, width=50).grid(row=6, column=1, columnspan=5, sticky=tk.W)
        
        tk.Label(frame_init, text="备注: 表格格式为 '时间, 值1, 值2; 时间, 值1, 值2'，时间按升序排列", fg="gray", font=("", 8)).grid(row=7, column=1, columnspan=3, sticky=tk.W)
        
        # PointSun checkbox
        self.cj_pointsun = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_init, text="Alpha轴对日定向 (PointSun)", variable=self.cj_pointsun, fg="#00695c").grid(row=7, column=4, columnspan=2, sticky=tk.W)

        # --- 策略参数 ---
        frame_params = ttk.LabelFrame(self.tab_sim, text="4. 仿真策略配置")
        frame_params.pack(fill=tk.X, padx=10, pady=5)
        
        self.step_var = tk.DoubleVar(value=0.02)
        self.rate_var = tk.DoubleVar(value=1.0)
        self.freq_var = tk.DoubleVar(value=50.0)
        self.time_var = tk.DoubleVar(value=86400.0)
        
        grid_params = [
            ("步长 (s):", self.step_var, 0, 0), ("仿真速率 (1x=物理):", self.rate_var, 0, 2),
            ("采样频率(Hz):", self.freq_var, 1, 0), ("自动停止(s):", self.time_var, 1, 2)
        ]
        for label, var, r, c in grid_params:
            tk.Label(frame_params, text=label).grid(row=r, column=c, padx=5, pady=5, sticky=tk.E)
            tk.Entry(frame_params, textvariable=var, width=12).grid(row=r, column=c+1, padx=5, pady=5, sticky=tk.W)

        # --- 进度条 ---
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(self.tab_sim, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=15, pady=5)
        self.progress_label = tk.Label(self.tab_sim, text="等待启动...", fg="gray", font=("微软雅黑", 8))
        self.progress_label.pack()

        # --- 控制按钮 ---
        frame_btn = tk.Frame(self.tab_sim)
        frame_btn.pack(fill=tk.X, padx=10, pady=10)
        self.btn_start = tk.Button(frame_btn, text="▶ 启动实时仿真", command=self.start_sim, bg="#e1f5fe", font=("微软雅黑", 10, "bold"), padx=15)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_fields = tk.Button(frame_btn, text="⚙ 变量配置", command=self._open_fields_window, bg="#f3e5f5", padx=10)
        self.btn_fields.pack(side=tk.LEFT, padx=5)
        
        self.is_initial_val = 0.0
        self.btn_initial = tk.Button(frame_btn, text="⚡ 同步信号 (0)", bg="#fff9c4", command=self.toggle_is_initial, padx=10)
        self.btn_initial.pack(side=tk.LEFT, padx=5)

        self.btn_stop = tk.Button(frame_btn, text="⏹ 停止仿真", command=self.stop_sim, bg="#ffebee", state=tk.DISABLED, padx=10)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="OS Ready")
        tk.Label(frame_btn, textvariable=self.status_var, fg="#666").pack(side=tk.RIGHT, padx=10)

        # --- 运行日志 ---
        frame_log = ttk.LabelFrame(self.tab_sim, text="实时运行状态与诊断")
        frame_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.txt_log = scrolledtext.ScrolledText(frame_log, wrap=tk.WORD, height=10, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.txt_log.tag_config("info", foreground="#1b5e20"); self.txt_log.tag_config("error", foreground="#b71c1c"); self.txt_log.tag_config("sys", foreground="#455a64")

    def _setup_orbit_tab(self):
        # 独立FMU路径选择
        frame_orbit_fmu = ttk.LabelFrame(self.tab_orbit, text="0. 轨道预示 FMU 模型")
        frame_orbit_fmu.pack(fill=tk.X, padx=10, pady=5)
        self.orbit_fmu_path_var = tk.StringVar(value=self.default_orbit_fmu)
        tk.Entry(frame_orbit_fmu, textvariable=self.orbit_fmu_path_var, width=72).pack(side=tk.LEFT, padx=5, pady=4)
        ttk.Button(frame_orbit_fmu, text="浏览...", command=self._browse_orbit_file).pack(side=tk.LEFT, padx=3)

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
            ("时间 Year:", self.year_var, 0, 0), ("Month:", self.mon_var, 0, 2), ("Day:", self.day_var, 0, 4),
            ("Hour:", self.hour_var, 1, 0), ("Min:", self.min_var, 1, 2), ("Sec:", self.sec_var, 1, 4),
            ("半长轴 a_MT (km):", self.a_mt_var, 2, 0), ("离心率 e_MT:", self.e_mt_var, 2, 2), ("轨道倾角 i_MT (rad):", self.i_mt_var, 2, 4),
            ("升交点 Ω_MT (rad):", self.OMEGA_mt_var, 3, 0), ("近地角 ω_MT (rad):", self.omega_mt_var, 3, 2), ("真近点角 f_MT (rad):", self.f_mt_var, 3, 4)
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
            ("计算步长 (s):", self.orbit_step, 0, 0), ("仿真速率 (1x=物理, 0=全速):", self.orbit_rate, 0, 2),
            ("采样频率 (Hz):", self.orbit_freq, 1, 0), ("计算时长 (s):", self.orbit_duration, 1, 2)
        ]
        for label, var, r, c in strats:
            tk.Label(frame_strat, text=label).grid(row=r, column=c, padx=5, pady=5, sticky=tk.E)
            tk.Entry(frame_strat, textvariable=var, width=15).grid(row=r, column=c+1, padx=5, sticky=tk.W)

        # --- 轨道计算进度条 ---
        self.orbit_progress_var = tk.DoubleVar(value=0.0)
        self.orbit_progress_bar = ttk.Progressbar(self.tab_orbit, variable=self.orbit_progress_var, maximum=100)
        self.orbit_progress_bar.pack(fill=tk.X, padx=15, pady=5)
        self.orbit_progress_label = tk.Label(self.tab_orbit, text="等待启动...", fg="gray", font=("微软雅黑", 8))
        self.orbit_progress_label.pack()

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
        
        self.txt_orbit_log = scrolledtext.ScrolledText(frame_olog, height=15, bg="#fafafa", font=("Consolas", 9))
        self.txt_orbit_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.txt_orbit_log.tag_config("info", foreground="#1b5e20")
        self.txt_orbit_log.tag_config("error", foreground="#b71c1c")
        self.txt_orbit_log.tag_config("sys", foreground="#455a64")
        self.olog("[SYS] 轨道预示模块就绪。", "sys")

    def browse_file(self):
        initial_dir = os.path.dirname(self.fmu_path_var.get().strip()) or os.path.join(APP_DIR, "FMU")
        f = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("FMU Files", "*.fmu")])
        if f:
            self.fmu_path_var.set(os.path.normpath(f))
            self._save_gui_config()
        
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
            "Table_FB": self.cj_table_fb.get(), "Table_Att": self.cj_table_att.get(),
            "PointSun": 1.0 if self.cj_pointsun.get() else 0.0
        }

    def start_sim(self):
        self._save_gui_config()
        fmu_path = self.fmu_path_var.get().strip()
        if not os.path.exists(fmu_path): self.olog(f"[!] 找不到文件 {fmu_path}", "error"); return
        if not fmu_path or not os.path.exists(fmu_path):
            from tkinter import messagebox
            messagebox.showerror("错误", "请先选择有效的 FMU 模型文件")
            return
        
        # 生成唯一会话 ID，防止陈旧 UDP 指令干扰
        self.current_sim_id = str(int(time.time()))
        
        sim_args = ["--step", str(self.step_var.get()), "--rate", str(self.rate_var.get()), 
                    "--freq", str(self.freq_var.get()), "--time", str(self.time_var.get()),
                    "--sim_id", self.current_sim_id,
                    "--ip", self.ip_var.get().strip(), "--port", str(self.port_var.get()),
                    "--params", json.dumps(self.get_cj_params()), "--control_port", str(CONTROL_PORT)]
        
        # 确保传入变量过滤配置
        sync_path = os.path.join(APP_DIR, "sync_fields.json")
        if os.path.exists(sync_path):
            sim_args.extend(["--sync_vars", sync_path])
        
        # 恢复使用基于内容的架构探测，确保兼容任何命名的 FMU
        arch_val = get_fmu_arch(fmu_path)
        fmu_bit = str(arch_val) if arch_val else ("32" if "32" in fmu_path else "64")
        
        # 兼容源码运行与打包运行
        if getattr(sys, 'frozen', False):
            worker_p = os.path.join(APP_DIR, "FmuWorker32.exe" if fmu_bit == "32" else "FmuSolver.exe")
            cmd = [worker_p]
            if fmu_bit == "64": cmd.append("--worker")
            cmd.extend([fmu_path] + sim_args)
        else:
            # 源码模式下使用 python 启动 fmu_player.py
            player_script = os.path.join(APP_DIR, "fmu_player.py")
            cmd = [sys.executable, player_script, fmu_path] + sim_args

        self.btn_start.config(state=tk.DISABLED); self.btn_stop.config(state=tk.NORMAL)
        self.progress_var.set(0); self.progress_label.config(text="正在启动...", fg="#01579b")
        self.txt_log.delete(1.0, tk.END)
        self.olog(f"[*] 启动仿真引擎 (ID: {self.current_sim_id}, Arch: {fmu_bit})...", "sys")
        
        try:
            self.worker_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=APP_DIR, env=self._child_env())
            self.root.after(2000, self.update_params) # 延迟2秒同步参数
            threading.Thread(target=self._read_worker_logs, daemon=True).start()
        except Exception as e:
            self.olog(f"[!] 启动失败: {e}", "error")
            self._reset_ui()

    def _read_worker_logs(self):
        if not self.worker_process: return
        total_t = self.time_var.get()
        for line in iter(self.worker_process.stdout.readline, ''):
            if not line: continue
            line_str = line.strip()
            
            # 进度条解析: [Live] [45%] Time: 123.4s | ...
            pct_match = re.search(r'\[(\d+)%\]', line_str)
            if pct_match:
                try:
                    pct_val = int(pct_match.group(1))
                    t_str = line_str.split("Time:")[1].split("s")[0] if "Time:" in line_str else "0.0"
                    t_val = float(t_str)
                    self.root.after(0, lambda v=pct_val, t=t_val: [
                        self.progress_var.set(v),
                        self.progress_label.config(text=f"仿真进度: {v}% (已运行 {t:.1f}s / 总计 {total_t:.0f}s)", fg="#01579b")
                    ])
                except: pass

            tag = "info" if "[OK]" in line else ("error" if "[!]" in line else "sys")
            self.root.after(0, self.log, line_str, tag)
        self.worker_process.stdout.close(); self.worker_process.wait(); self.root.after(0, self._reset_ui)

    def _reset_ui(self):
        self.btn_start.config(state=tk.NORMAL); self.btn_stop.config(state=tk.DISABLED); self.worker_process = None
        self.current_sim_id = None
        self.progress_var.set(0); self.progress_label.config(text="仿真停止", fg="gray")
        self.orbit_progress_var.set(0); self.orbit_progress_label.config(text="计算停止", fg="gray")

    def stop_sim(self):
        if self.worker_process:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # 必须带上 sim_id，Worker 才会响应退出指令
                msg = {"sim_id": getattr(self, 'current_sim_id', ""), "exit": True}
                sock.sendto(json.dumps(msg).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
            except: pass
            finally: sock.close()
            # 延迟杀掉进程
            self.root.after(500, self._terminate_worker)
        self._reset_ui()

    def _terminate_worker(self):
        if self.worker_process:
            try:
                import subprocess
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.worker_process.pid)], creationflags=0x08000000)
            except: pass

    def update_params(self):
        if not self.worker_process: return
        cmd = {
            "sim_id": getattr(self, 'current_sim_id', ""),
            "step_size": self.step_var.get(), 
            "sim_time": self.time_var.get(), 
            "sim_rate": self.rate_var.get(), 
            "sample_freq": self.freq_var.get()
        }
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: s.sendto(json.dumps(cmd).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
        except: pass
        finally: s.close()

    def toggle_is_initial(self):
        """脉冲式触发：自动 0 -> 1 -> 0"""
        def do_pulse():
            # 1. 变高并保持一会儿
            self.btn_initial.config(text="⚡ 同步中...", bg="#ffb74d", state=tk.DISABLED)
            self.send_ctrl_signal("Is_initial", 1.0)
            
            # 2. 0.5秒后恢复为低电平
            self.root.after(500, lambda: [
                self.send_ctrl_signal("Is_initial", 0.0),
                self.btn_initial.config(text="⚡ 同步信号 (脉冲触发)", bg="#fff9c4", state=tk.NORMAL)
            ])
        do_pulse()

    def send_ctrl_signal(self, name, val):
        if self.worker_process:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                msg = {"sim_id": getattr(self, 'current_sim_id', ""), name: val}
                s.sendto(json.dumps(msg).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
            except: pass
            finally: s.close()

    def run_orbit_precalc(self):
        self._save_gui_config()
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
        self.orbit_progress_var.set(0)
        self.orbit_progress_label.config(text="正在启动...", fg="#01579b")
        self.orbit_proc = None

        def run_thread():
            total_t = self.orbit_duration.get()
            try:
                self.orbit_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=APP_DIR, env=self._child_env())
                ready_file = None
                for line in iter(self.orbit_proc.stdout.readline, ''):
                    line_str = line.strip()
                    if not line_str: continue
                    
                    # 进度条解析: [Live] [45%] Time: 123.4s | ...
                    pct_match = re.search(r'\[(\d+)%\]', line_str)
                    if pct_match:
                        try:
                            pct_val = int(pct_match.group(1))
                            t_str = line_str.split("Time:")[1].split("s")[0] if "Time:" in line_str else "0.0"
                            t_val = float(t_str)
                            self.root.after(0, lambda v=pct_val, t=t_val: [
                                self.orbit_progress_var.set(v),
                                self.orbit_progress_label.config(text=f"计算进度: {v}% (已解析 {t:.0f}s / 总计 {total_t:.0f}s)", fg="#1b5e20")
                            ])
                        except: pass

                    if "[EXPORT_READY]" in line_str:
                        ready_file = line_str.replace("[EXPORT_READY]", "").strip()
                    tag = "info" if "[OK]" in line_str or "SUCCESS" in line_str else ("error" if "[!]" in line_str or "Error" in line_str or "Fatal" in line_str else "sys")
                    self.root.after(0, self.olog, line_str, tag)
                self.orbit_proc.stdout.close()
                rc = self.orbit_proc.wait()

                if ready_file and os.path.exists(ready_file):
                    with open(ready_file, 'r') as f:
                        self.orbit_data = json.load(f)
                    self.root.after(0, lambda: self.btn_export_txt.config(state=tk.NORMAL))
                    self.root.after(0, self.olog, f"[OK] 计算完成，共 {len(self.orbit_data)} 行数据。", "info")
                    
                    # --- 自动保存到 txt/Orbit_Pre.txt ---
                    try:
                        txt_dir = os.path.join(APP_DIR, "txt")
                        os.makedirs(txt_dir, exist_ok=True)
                        auto_save_p = os.path.join(txt_dir, "Orbit_Pre.txt")
                        self._save_to_orbit_txt(auto_save_p)
                        self.root.after(0, self.olog, f"[OK] 结果已自动同步至: {auto_save_p}", "info")
                    except Exception as e:
                        self.root.after(0, self.olog, f"[!] 自动保存失败: {e}", "error")
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

    def _save_to_orbit_txt(self, filepath):
        if not self.orbit_data: return
        with open(filepath, 'w') as out:
            # 兼容 FMU 内部 C++ Table 格式
            out.write("#1\ndouble table({},7)\n".format(len(self.orbit_data)))
            for row in self.orbit_data:
                # row[0] 是时间，row[1:] 是 6 根初值
                out.write("\t".join([f"{x:.5f}" for x in row[1:]]) + "\n")

    def export_orbit_txt(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="Orbit_Pre.txt")
        if not f: return
        try:
            self._save_to_orbit_txt(f)
            self.log(f"[OK] 导出成功: {f}", "info")
        except Exception as e:
            self.log(f"[!] 导出失败: {e}", "error")

if __name__ == "__main__":
    try:
        with open(os.path.join(APP_DIR, "sys_argv.log"), "a", encoding="utf-8") as f:
            f.write(f"sys.argv={sys.argv}\n")
    except: pass
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--worker", action="store_true")
        parser.add_argument("fmu_path")
        parser.add_argument("--ip", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8889)
        parser.add_argument("--sync_vars", default=None)
        parser.add_argument("--control_port", type=int, default=8898)
        parser.add_argument("--step", type=float, default=0.01)
        parser.add_argument("--rate", type=float, default=1.0)
        parser.add_argument("--freq", type=float, default=0.0)
        parser.add_argument("--time", type=float, default=float('inf'))
        parser.add_argument("--params", default=None)
        parser.add_argument("--sim_id", default=None)
        
        args = parser.parse_args()
        os.chdir(APP_DIR)
        
        init_params_dict = None
        if args.params:
            try: init_params_dict = json.loads(args.params)
            except: pass
            
        try: 
            from fmu_player import FMUPlayer
            player = FMUPlayer(args.fmu_path, args.ip, args.port, sim_id=args.sim_id, sync_vars_file=args.sync_vars, control_port=args.control_port)
            player.run(step_size=args.step, sim_time=args.time, sim_rate=args.rate, sample_freq=args.freq, init_params=init_params_dict)
        except Exception as e: 
            with open(os.path.join(APP_DIR, "worker_fatal.log"), "a", encoding="utf-8") as f:
                f.write(f"Worker Fatal Error: {e}\n")
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "--yaoceworker":
        import os
        import sys
        import builtins
        
        APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(APP_DIR, "yaoce_run.log")
        fatal_log = os.path.join(APP_DIR, "yaoce_fatal.log")
        
        try:
            with open(log_file, "w", encoding="utf-8") as f: f.write("")
        except Exception as e:
            with open(fatal_log, "a", encoding="utf-8") as f: f.write(f"Clear error: {e}\n")
        
        class FileOut:
            def __init__(self, prefix=""): self.p = prefix
            def write(self, text):
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        if text.strip() and self.p: f.write(self.p + text)
                        else: f.write(text)
                except Exception as e:
                    with open(fatal_log, "a", encoding="utf-8") as f: f.write(f"Write error: {e}\n")
            def flush(self): pass
            
        my_out = FileOut()
        sys.stdout = my_out
        sys.stderr = FileOut("[!ERR] ")
        
        def _my_print(*args, **kwargs):
            try:
                msg = " ".join(map(str, args)) + "\n"
                my_out.write(msg)
            except Exception as e:
                with open(fatal_log, "a") as f: f.write(f"Print error: {e}\n")
                
        builtins.print = _my_print

        yaoce_module_path = os.path.join(APP_DIR, "yaocetest")
        if yaoce_module_path not in sys.path: sys.path.append(yaoce_module_path)
        
        yaoce_config_dir = sys.argv[2] if len(sys.argv) > 2 else yaoce_module_path
        
        try:
            from yaocetest.main import YaoCeLinkLayerApp
            my_out.write(f"[SYS] Importing YaoCeLinkLayerApp successful. Config Dir: {yaoce_config_dir}\n")
            app = YaoCeLinkLayerApp(yaoce_config_dir)
            my_out.write("[SYS] App instantiated.\n")
            app.start()
        except Exception as e:
            my_out.write(f"[!] YaoCe Worker Error: {e}\n")
        sys.exit(0)
    else: root = tk.Tk(); FmuSolverGUI(root); root.mainloop()
