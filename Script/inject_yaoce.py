import os
import re

target_file = r"C:\Spaceship\FMUSOLVER\Script\FmuLauncherUniversal.py"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Widgets Creation
old_widgets = """        self.tab_sim = ttk.Frame(self.notebook)
        self.tab_orbit = ttk.Frame(self.notebook)
        self.tab_data = ttk.Frame(self.notebook)
        self.tab_fields = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_fields, text=" 字段配置 ")
        self.notebook.add(self.tab_sim, text=" 实时仿真控制 ")
        self.notebook.add(self.tab_orbit, text=" 轨道预示计算 ")
        self.notebook.add(self.tab_data, text=" 数据结果展示 ")
        
        self._setup_fields_tab()"""

new_widgets = """        self.tab_sim = ttk.Frame(self.notebook)
        self.tab_orbit = ttk.Frame(self.notebook)
        self.tab_data = ttk.Frame(self.notebook)
        self.tab_fields = ttk.Frame(self.notebook)
        self.tab_yaoce = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_yaoce, text=" 遥测接收转发 ")
        self.notebook.add(self.tab_fields, text=" 同步字段配置 ")
        self.notebook.add(self.tab_sim, text=" 实时仿真控制 ")
        self.notebook.add(self.tab_orbit, text=" 轨道预示计算 ")
        self.notebook.add(self.tab_data, text=" 数据结果展示 ")
        
        self._setup_yaoce_tab()
        self._setup_fields_tab()"""

content = content.replace(old_widgets, new_widgets)

# 2. Add _setup_yaoce_tab method
yaoce_method = """    def _setup_yaoce_tab(self):
        # 1. 配置文件检查区域
        frame_cfg = ttk.LabelFrame(self.tab_yaoce, text="1. 配置文件与过滤白名单检查 (支持进厂断网环境查验)")
        frame_cfg.pack(fill=tk.X, padx=10, pady=5)
        
        self.yaoce_dir = os.path.join(APP_DIR, "yaocetest")
        lbl_dir = tk.Label(frame_cfg, text=f"当前配置读取目录: {self.yaoce_dir}", fg="#455a64")
        lbl_dir.pack(side=tk.TOP, anchor=tk.W, padx=5, pady=2)
        
        btn_frame = tk.Frame(frame_cfg)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        def open_config():
            cfg_path = os.path.join(self.yaoce_dir, "config.ini")
            if os.path.exists(cfg_path): os.startfile(cfg_path)
            else: self.ylog(f"[!] {cfg_path} 不存在! (请将 yaocetest 文件夹放置于 exe 旁)", "error")
            
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
        self.txt_yaoce_log = scrolledtext.ScrolledText(frame_ylog, wrap=tk.WORD, height=20, font=("Consolas", 10), bg="#1e1e1e", fg="#e0e0e0")
        self.txt_yaoce_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.txt_yaoce_log.tag_config("info", foreground="#81c784")
        self.txt_yaoce_log.tag_config("error", foreground="#e57373")
        self.txt_yaoce_log.tag_config("sys", foreground="#64b5f6")
        self.ylog("[SYS] 遥测接收转发模块已就绪，请先检查参数配置是否正确。", "sys")
        
    def ylog(self, msg, tag="sys"):
        self.txt_yaoce_log.insert(tk.END, msg + "\\n", tag)
        self.txt_yaoce_log.see(tk.END)
        
    def start_yaoce(self):
        worker_cmd = [sys.executable]
        if not getattr(sys, 'frozen', False):
            worker_cmd.append(os.path.abspath(__file__))
        worker_cmd.append("--yaoceworker")
        
        self.btn_yaoce_start.config(state=tk.DISABLED)
        self.btn_yaoce_stop.config(state=tk.NORMAL)
        
        self.ylog("===========================================", "sys")
        self.ylog(f"[*] 启动底层遥测子进程... CMD={worker_cmd}", "sys")
        try:
            self.yaoce_proc = subprocess.Popen(worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=APP_DIR)
            threading.Thread(target=self._yaoce_log_reader, daemon=True).start()
        except Exception as e:
            self.ylog(f"[!] 独立子进程启动致命失败: {e}", "error")
            self.stop_yaoce()

    def _yaoce_log_reader(self):
        if not hasattr(self, 'yaoce_proc') or not self.yaoce_proc: return
        for line in iter(self.yaoce_proc.stdout.readline, ''):
            if not line: continue
            l = line.strip()
            tag = "sys"
            if "[SEND]" in l or "[OK]" in l or "[*]" in l: tag = "info"
            elif "[!]" in l or "Error" in l or "Exception" in l: tag = "error"
            self.root.after(0, self.ylog, l, tag)
            
        self.yaoce_proc.stdout.close()
        rc = self.yaoce_proc.wait()
        self.root.after(0, self.ylog, f"[SYS] 转发引擎退出，退出码: {rc}", "sys")
        self.root.after(0, lambda: self.btn_yaoce_start.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_yaoce_stop.config(state=tk.DISABLED))

    def stop_yaoce(self):
        if hasattr(self, 'yaoce_proc') and self.yaoce_proc:
            try:
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.yaoce_proc.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
                self.ylog("[*] 发送强制终止指令...", "error")
            except: pass
            self.yaoce_proc = None
        self.btn_yaoce_start.config(state=tk.NORMAL)
        self.btn_yaoce_stop.config(state=tk.DISABLED)

    def _setup_fields_tab(self):"""

content = content.replace("    def _setup_fields_tab(self):", yaoce_method)

# 3. Add to __main__ switch
old_main = """    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        import argparse; parser = argparse.ArgumentParser()
        parser.add_argument("--worker", action="store_true"); parser.add_argument("fmu_path"); parser.add_argument("--ip", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8889); parser.add_argument("--sync_vars", default=None)
        args = parser.parse_args(); os.chdir(APP_DIR)
        try: from fmu_player import FMUPlayer; FMUPlayer(args.fmu_path, remote_ip=args.ip, remote_port=args.port, sync_vars_file=args.sync_vars).run()
        except: pass
        sys.exit(0)
    else: root = tk.Tk(); FmuSolverGUI(root); root.mainloop()"""

new_main = """    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        import argparse; parser = argparse.ArgumentParser()
        parser.add_argument("--worker", action="store_true"); parser.add_argument("fmu_path"); parser.add_argument("--ip", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8889); parser.add_argument("--sync_vars", default=None)
        args = parser.parse_args(); os.chdir(APP_DIR)
        try: from fmu_player import FMUPlayer; FMUPlayer(args.fmu_path, remote_ip=args.ip, remote_port=args.port, sync_vars_file=args.sync_vars).run()
        except: pass
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "--yaoceworker":
        import builtins
        # Flush print calls to surface them to GUI realtime
        _old_print = builtins.print
        def _flush_print(*args, **kwargs):
            kwargs['flush'] = True
            _old_print(*args, **kwargs)
        builtins.print = _flush_print
        
        yaoce_path = os.path.join(APP_DIR, "yaocetest")
        if yaoce_path not in sys.path: sys.path.append(yaoce_path)
        try:
            from yaocetest.main import YaoCeLinkLayerApp
            app = YaoCeLinkLayerApp(yaoce_path)
            app.start()
        except Exception as e:
            print(f"[!] YaoCe Worker Error: {e}")
        sys.exit(0)
    else: root = tk.Tk(); FmuSolverGUI(root); root.mainloop()"""

content = content.replace(old_main, new_main)

with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] FmuLauncherUniversal.py with YaoCe correctly patched!")
