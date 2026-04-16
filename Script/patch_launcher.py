import os
import re

target_file = r"C:\Spaceship\FmuLauncherUniversal.py"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add tab_fields to create_widgets
new_create_widgets = """        self.tab_sim = ttk.Frame(self.notebook)
        self.tab_orbit = ttk.Frame(self.notebook)
        self.tab_data = ttk.Frame(self.notebook)
        self.tab_fields = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_fields, text=" 字段配置 ")
        self.notebook.add(self.tab_sim, text=" 实时仿真控制 ")
        self.notebook.add(self.tab_orbit, text=" 轨道预示计算 ")
        self.notebook.add(self.tab_data, text=" 数据结果展示 ")
        
        self._setup_fields_tab()
        self._setup_sim_tab()"""

content = re.sub(
    r'self\.tab_sim = ttk\.Frame\(self\.notebook\).*?self\._setup_sim_tab\(\)',
    new_create_widgets,
    content,
    flags=re.DOTALL
)

# 2. Add _setup_fields_tab method right before _setup_sim_tab
setup_fields_method = """    def _setup_fields_tab(self):
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
            lines = content.split('\\n')
            import re
            added = 0
            for line in lines:
                line = line.strip()
                if not line: continue
                # 兼容 Modelica 和 普通名字
                m = re.search(r'(?:output\\s+)?(?:(Real|Integer|Boolean|String)\\s+)?([a-zA-Z0-9_\\.]+)(?:\\[(\\d+)\\])?(.*)', line)
                if m:
                    var_type = m.group(1) or 'Real'
                    base_name = m.group(2)
                    size = int(m.group(3)) if m.group(3) else 1
                    desc_match = re.search(r'\\"([^\\"]+)\\"', m.group(4))
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

    def _setup_sim_tab(self):"""

content = content.replace("    def _setup_sim_tab(self):", setup_fields_method.replace('json. ভবিষ্যৎdump', 'json.dump'))

# 3. Update start_sim cmd.extend
old_extend = 'cmd.extend(["--worker", fmu_path, "--ip", self.ip_var.get(), "--port", str(self.port_var.get())] + sim_args)'
new_extend = 'cmd.extend(["--worker", fmu_path, "--ip", self.ip_var.get(), "--port", str(self.port_var.get()), "--sync_vars", getattr(self, "sync_cfg_path", "sync_fields.json")] + sim_args)'
content = content.replace(old_extend, new_extend)

old_worker_cmd = 'cmd = [worker_p, fmu_path, "--ip", self.ip_var.get(), "--port", str(self.port_var.get())] + sim_args'
new_worker_cmd = 'cmd = [worker_p, fmu_path, "--ip", self.ip_var.get(), "--port", str(self.port_var.get()), "--sync_vars", getattr(self, "sync_cfg_path", "sync_fields.json")] + sim_args'
content = content.replace(old_worker_cmd, new_worker_cmd)

# 4. End __main__ part
old_main = """        parser.add_argument("--worker", action="store_true"); parser.add_argument("fmu_path"); parser.add_argument("--ip", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8889)
        args = parser.parse_args(); os.chdir(APP_DIR)
        try: from fmu_player import FMUPlayer; FMUPlayer(args.fmu_path, remote_ip=args.ip, remote_port=args.port).run()"""

new_main = """        parser.add_argument("--worker", action="store_true"); parser.add_argument("fmu_path"); parser.add_argument("--ip", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8889); parser.add_argument("--sync_vars", default=None)
        args = parser.parse_args(); os.chdir(APP_DIR)
        try: from fmu_player import FMUPlayer; FMUPlayer(args.fmu_path, remote_ip=args.ip, remote_port=args.port, sync_vars_file=args.sync_vars).run()"""

content = content.replace(old_main, new_main)

with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] FmuLauncherUniversal.py fully patched!")
