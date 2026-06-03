
# ─── Main GUI Class ───
class FmuSolverGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker_process = None
        self.visualizer_process = None
        self.orbit_data = []
        self.orbit_proc = None
        self.current_sim_id = None
        self._yaoce_log_pos = 0
        self.gui_config_path = GUI_CONFIG_PATH
        self.gui_config = self._load_gui_config()
        self.default_sim_fmu   = self._resolve_sim_fmu()
        self.default_orbit_fmu = self._resolve_orbit_fmu()
        self.yaoce_dir = self._resolve_yaoce_dir()
        self.default_ip   = str(self.gui_config.get("ip", "127.0.0.1"))
        self.default_port = int(self.gui_config.get("port", 12345))
        self._setup_window()
        self._build_ui()

    def _load_gui_config(self):
        if os.path.exists(self.gui_config_path):
            try:
                with open(self.gui_config_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict): return d
            except: pass
        return {}

    def _save_gui_config(self):
        data = {
            "sim_fmu":    self.fmu_path_edit.text().strip(),
            "orbit_fmu":  self.orbit_fmu_edit.text().strip(),
            "yaoce_dir":  getattr(self, "yaoce_dir", ""),
            "ip":         self.ip_edit.text().strip(),
            "port":       self.port_edit.text().strip(),
            "replace_dot": self.chk_replace_dot.isChecked(),
        }
        try:
            with open(self.gui_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except: pass

    def _resolve_sim_fmu(self):
        a = auto_find_fmu(["MTLibrary_System_EPS_PD_EPS_CJ.fmu","FMU_Model1.fmu","TestFmu.fmu"],["eps","cj"])
        return a or _norm_existing(self.gui_config.get("sim_fmu")) or ""

    def _resolve_orbit_fmu(self):
        a = auto_find_fmu(["MTLibrary_System_EPS_PD_Orbit_Pre.fmu"],["orbit","pre"])
        return a or _norm_existing(self.gui_config.get("orbit_fmu")) or ""

    def _resolve_yaoce_dir(self):
        a = auto_find_yaoce_dir()
        return a or _norm_existing(self.gui_config.get("yaoce_dir")) or os.path.normpath(os.path.join(APP_DIR,"yaocetest"))

    def _child_env(self):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _setup_window(self):
        self.setWindowTitle("FmuSolver - Simulation Platform")
        self.resize(960, 800)
        self.setMinimumWidth(860)
        self.setStyleSheet(APP_QSS)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        vlay.addWidget(self._make_header())
        vlay.addWidget(divider())

        nav_wrap = QWidget()
        nav_wrap.setStyleSheet(f"background:{C_BG};")
        nav_h = QHBoxLayout(nav_wrap)
        nav_h.setContentsMargins(20, 10, 20, 6)
        self.seg = SegmentedControl(["  轨道预示计算", " 实时仿真控制", "  遥测接收转发"])
        nav_h.addWidget(self.seg)
        nav_h.addStretch()
        vlay.addWidget(nav_wrap)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{C_BG};")
        self.tab_orbit = QScrollArea(); self.tab_orbit.setWidgetResizable(True); self.tab_orbit.setFrameShape(QFrame.NoFrame)
        self.tab_sim   = QScrollArea(); self.tab_sim.setWidgetResizable(True);   self.tab_sim.setFrameShape(QFrame.NoFrame)
        self.tab_yaoce = QScrollArea(); self.tab_yaoce.setWidgetResizable(True); self.tab_yaoce.setFrameShape(QFrame.NoFrame)
        for t in [self.tab_orbit, self.tab_sim, self.tab_yaoce]:
            self.stack.addWidget(t)
        self.seg.tab_changed.connect(self.stack.setCurrentIndex)
        vlay.addWidget(self.stack, 1)

        self._build_orbit_tab()
        self._build_sim_tab()
        self._build_yaoce_tab()

    def _make_header(self):
        h = QFrame()
        h.setStyleSheet(f"background:{C_CARD}; border:none;")
        h.setFixedHeight(64)
        hl = QHBoxLayout(h)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("FmuSolver")
        title.setStyleSheet("font-size:18px; font-weight:700; color:#1D1D1F;")
        sub = QLabel("  Satellite Payload Simulation")
        sub.setStyleSheet(f"font-size:12px; color:{C_MUTED};")
        hl.addWidget(title)
        hl.addWidget(sub)
        hl.addStretch()
        self.led_dot = QLabel("●")
        self.led_dot.setStyleSheet("color:#AEAEB2; font-size:14px;")
        self.led_txt = QLabel("READY")
        self.led_txt.setStyleSheet(f"color:{C_MUTED}; font-size:11px; font-weight:600;")
        hl.addWidget(self.led_dot)
        hl.addWidget(self.led_txt)
        return h

    def _update_led(self, state):
        m = {"ready":("#AEAEB2",C_MUTED,"READY"), "running":(C_SUCCESS,C_SUCCESS,"RUNNING"),
             "error":(C_ERROR,C_ERROR,"ERROR"), "stopped":(C_WARNING,C_WARNING,"STOPPED")}
        dot, txt, label = m.get(state, ("#AEAEB2",C_MUTED,"READY"))
        self.led_dot.setStyleSheet(f"color:{dot}; font-size:14px;")
        self.led_txt.setStyleSheet(f"color:{txt}; font-size:11px; font-weight:600;")
        self.led_txt.setText(label)

    # ═══════════════════════════════════════
    #  TAB 1: Orbit Pre-calculation
    # ═══════════════════════════════════════
    def _build_orbit_tab(self):
        w = QWidget(); w.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(w); lay.setContentsMargins(16,12,16,16); lay.setSpacing(12)

        # Card 1: FMU path
        c1 = card(); cl1 = QVBoxLayout(c1); cl1.setContentsMargins(16,14,16,14); cl1.setSpacing(8)
        cl1.addWidget(lbl("1. 轨道预示 FMU 模型", obj="Title"))
        row = QHBoxLayout(); row.setSpacing(8)
        self.orbit_fmu_edit = field(text=self.default_orbit_fmu)
        b_browse = text_btn("浏览...")
        b_browse.clicked.connect(self._browse_orbit_fmu)
        row.addWidget(self.orbit_fmu_edit, 1)
        row.addWidget(b_browse)
        cl1.addLayout(row)
        lay.addWidget(c1)

        # Card 2: Orbital elements
        c2 = card(); cl2 = QVBoxLayout(c2); cl2.setContentsMargins(16,14,16,14); cl2.setSpacing(10)
        cl2.addWidget(lbl("2. 轨道初始根数设置", obj="Title"))

        self.year_e = field("2026","2026"); self.mon_e = field("4","4"); self.day_e = field("10","10")
        self.hour_e = field("8","8");  self.min_e = field("0","0");   self.sec_e = field("0.0","0.0")
        self.a_e = field("6766.71777","6766.71777"); self.ecc_e = field("0.00110","0.00110"); self.inc_e = field("0.72653","0.72653")
        self.om_e = field("2.39969","2.39969");   self.w_e = field("1.34409","1.34409"); self.f_e = field("1.00447","1.00447")

        g = QGridLayout(); g.setSpacing(8)
        rows_time = [("时间 Year:", self.year_e, "Month:", self.mon_e, "Day:", self.day_e),
                     ("Hour:", self.hour_e, "Min:", self.min_e, "Sec:", self.sec_e)]
        for r, row_data in enumerate(rows_time):
            for c in range(3):
                g.addWidget(lbl(row_data[c*2], obj="Muted"), r, c*3, Qt.AlignRight)
                g.addWidget(row_data[c*2+1], r, c*3+1)
        cl2.addLayout(g)

        g2 = QGridLayout(); g2.setSpacing(8)
        rows_orb = [("半长轴 a_MT (km):", self.a_e, "离心率 e_MT:", self.ecc_e, "轨道倾角 i_MT (rad):", self.inc_e),
                    ("升交点 Ω_MT (rad):", self.om_e, "近地角 ω_MT (rad):", self.w_e, "真近点角 f_MT (rad):", self.f_e)]
        for r, row_data in enumerate(rows_orb):
            for c in range(3):
                g2.addWidget(lbl(row_data[c*2], obj="Muted"), r, c*3, Qt.AlignRight)
                g2.addWidget(row_data[c*2+1], r, c*3+1)
        cl2.addLayout(g2)

        warn = lbl("⚠  计算年份受 FMU EOP 数据范围限制，年份将自动修正", obj="WarnPill")
        cl2.addWidget(warn)
        lay.addWidget(c2)

        # Card 3: Strategy
        c3 = card(); cl3 = QVBoxLayout(c3); cl3.setContentsMargins(16,14,16,14); cl3.setSpacing(10)
        cl3.addWidget(lbl("3. 离轨计算策略配置", obj="Title"))
        self.o_step_e = field("10.0","10.0"); self.o_rate_e = field("0.0","0.0")
        self.o_freq_e = field("0.1","0.1");   self.o_dur_e  = field("86400.0","86400.0")
        gs = QGridLayout(); gs.setSpacing(8)
        sd = [("计算步步 (s):", self.o_step_e, "仿真速率 (1x=物理, 0=全速):", self.o_rate_e),
              ("采样频率 (Hz):", self.o_freq_e, "计算时长 (s):", self.o_dur_e)]
        for r, (l1, e1, l2, e2) in enumerate(sd):
            gs.addWidget(lbl(l1, obj="Muted"), r, 0, Qt.AlignRight)
            gs.addWidget(e1, r, 1)
            gs.addWidget(lbl(l2, obj="Muted"), r, 2, Qt.AlignRight)
            gs.addWidget(e2, r, 3)
        cl3.addLayout(gs)
        lay.addWidget(c3)

        # Progress + buttons
        self.orbit_progress = QProgressBar(); self.orbit_progress.setMaximum(100); self.orbit_progress.setValue(0)
        lay.addWidget(self.orbit_progress)
        self.orbit_prog_lbl = lbl("等待启动...", obj="Muted"); self.orbit_prog_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.orbit_prog_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.btn_run_orbit  = btn("▶  开始预示解算")
        self.btn_stop_orbit = btn("■ 停止", False); self.btn_stop_orbit.setEnabled(False)
        self.btn_export     = btn("导出结果", False); self.btn_export.setEnabled(False)
        self.btn_run_orbit.clicked.connect(self.run_orbit_precalc)
        self.btn_stop_orbit.clicked.connect(self.stop_orbit)
        self.btn_export.clicked.connect(self.export_orbit_txt)
        btn_row.addWidget(self.btn_run_orbit)
        btn_row.addWidget(self.btn_stop_orbit)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # Log console
        lay.addWidget(lbl("轨道预示日志", obj="Title"))
        self.txt_orbit_log = QPlainTextEdit(); self.txt_orbit_log.setObjectName("Console")
        self.txt_orbit_log.setReadOnly(True); self.txt_orbit_log.setMinimumHeight(180)
        lay.addWidget(self.txt_orbit_log, 1)
        lay.addStretch()

        self.tab_orbit.setWidget(w)

    # ═══════════════════════════════════════
    #  TAB 2: Real-time Simulation Control
    # ═══════════════════════════════════════
    def _build_sim_tab(self):
        w = QWidget(); w.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(w); lay.setContentsMargins(16,12,16,16); lay.setSpacing(12)

        # Card 1: FMU path
        c1 = card(); cl1 = QVBoxLayout(c1); cl1.setContentsMargins(16,14,16,14); cl1.setSpacing(8)
        cl1.addWidget(lbl("1. 模型与路径配置", obj="Title"))
        row1 = QHBoxLayout(); row1.setSpacing(8)
        self.fmu_path_edit = field(text=self.default_sim_fmu)
        b_sim_browse = text_btn("浏览...")
        b_sim_browse.clicked.connect(self.browse_file)
        row1.addWidget(self.fmu_path_edit, 1); row1.addWidget(b_sim_browse)
        cl1.addLayout(row1)
        lay.addWidget(c1)

        # Card 2: Network
        c2 = card(); cl2 = QVBoxLayout(c2); cl2.setContentsMargins(16,14,16,14); cl2.setSpacing(10)
        cl2.addWidget(lbl("2. 通信网络设置", obj="Title"))
        row2 = QHBoxLayout(); row2.setSpacing(12)
        row2.addWidget(lbl("远程地址 (IP):", obj="Muted"))
        self.ip_edit = field(text=self.default_ip); self.ip_edit.setFixedWidth(160)
        row2.addWidget(self.ip_edit)
        row2.addWidget(lbl("端口:", obj="Muted"))
        self.port_edit = field(text=str(self.default_port)); self.port_edit.setFixedWidth(90)
        row2.addWidget(self.port_edit)
        row2.addStretch()
        cl2.addLayout(row2)
        self.chk_replace_dot = QCheckBox("将变量名中的 '.' 转换为 '_' (兼容模式)")
        self.chk_replace_dot.setChecked(self.gui_config.get("replace_dot", False))
        self.chk_replace_dot.setStyleSheet(f"color:{C_WARNING};")
        cl2.addWidget(self.chk_replace_dot)
        lay.addWidget(c2)

        # Card 3: Init params (EPS_CJ)
        c3 = card(); cl3 = QVBoxLayout(c3); cl3.setContentsMargins(16,14,16,14); cl3.setSpacing(10)
        cl3.addWidget(lbl("3. 初值与参数定义 (EPS_CJ)", obj="Title"))
        cl3.addWidget(lbl("时间初值 (年-月-日 时:分:秒)", obj="Muted"))

        self.cj_year_e = field("2026","2026"); self.cj_mon_e = field("3","3"); self.cj_day_e = field("31","31")
        self.cj_hour_e = field("12","12");     self.cj_min_e = field("19","19"); self.cj_sec_e = field("0.0","0.0")
        gt = QGridLayout(); gt.setSpacing(8)
        trows = [("Year:", self.cj_year_e, "Mon:", self.cj_mon_e, "Day:", self.cj_day_e),
                 ("Hour:", self.cj_hour_e, "Min:", self.cj_min_e, "Sec:", self.cj_sec_e)]
        for r, row_data in enumerate(trows):
            for c in range(3):
                gt.addWidget(lbl(row_data[c*2], obj="Muted"), r, c*3, Qt.AlignRight)
                gt.addWidget(row_data[c*2+1], r, c*3+1)
        cl3.addLayout(gt)

        self.cj_ta_e  = field(text="1000, 3640; 2000, 3640")
        self.cj_tb_e  = field(text="1000, 3640; 2000, 3640")
        self.cj_tfb_e = field(text="1000, 360, 184; 2000, 360, 184")
        self.cj_tatt_e= field(text="1000, 0, 3, 90; 2000, 0, 3, 90")
        for lbl_text, edit in [("Table_A (太阳帆板A指令):", self.cj_ta_e),
                                ("Table_B (太阳帆板B指令):", self.cj_tb_e),
                                ("Table_FB (分流器状态):", self.cj_tfb_e),
                                ("Table_Att (姿态四元数):", self.cj_tatt_e)]:
            row = QHBoxLayout(); row.setSpacing(8)
            row.addWidget(lbl(lbl_text, obj="Muted"))
            row.addWidget(edit, 1)
            cl3.addLayout(row)

        note_row = QHBoxLayout()
        note_row.addWidget(lbl("备注: 数据序列格式为 '时间, 值1, 值2; ...' 按时间升序排列", obj="Muted"))
        self.chk_pointsun = QCheckBox("Alpha轴对日定向 (PointSun)")
        self.chk_pointsun.setStyleSheet(f"color:{C_SUCCESS};")
        note_row.addStretch(); note_row.addWidget(self.chk_pointsun)
        cl3.addLayout(note_row)
        lay.addWidget(c3)

        # Card 4: Strategy
        c4 = card(); cl4 = QVBoxLayout(c4); cl4.setContentsMargins(16,14,16,14); cl4.setSpacing(10)
        cl4.addWidget(lbl("4. 仿真策略配置", obj="Title"))
        self.step_e = field("0.02","0.02"); self.rate_e = field("1.0","1.0")
        self.freq_e = field("50.0","50.0"); self.time_e = field("86400.0","86400.0")
        gs4 = QGridLayout(); gs4.setSpacing(8)
        sp = [("步长 (s):", self.step_e, "仿真速率 (1x=物理):", self.rate_e),
              ("采样频率(Hz):", self.freq_e, "停止 (s):", self.time_e)]
        for r, (l1, e1, l2, e2) in enumerate(sp):
            gs4.addWidget(lbl(l1, obj="Muted"), r, 0, Qt.AlignRight)
            gs4.addWidget(e1, r, 1)
            gs4.addWidget(lbl(l2, obj="Muted"), r, 2, Qt.AlignRight)
            gs4.addWidget(e2, r, 3)
        cl4.addLayout(gs4)
        lay.addWidget(c4)

        # Progress
        self.sim_progress = QProgressBar(); self.sim_progress.setMaximum(100); self.sim_progress.setValue(0)
        lay.addWidget(self.sim_progress)
        self.sim_prog_lbl = lbl("等待启动...", obj="Muted"); self.sim_prog_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.sim_prog_lbl)

        # Button bar
        btn_bar = QHBoxLayout(); btn_bar.setSpacing(10)
        self.btn_start = btn("▶ 启动仿真")
        self.chk_auto_vis = QCheckBox("自动开启看板")
        self.chk_auto_vis.setChecked(True)
        self.btn_fields  = btn("变量配置", False)
        self.btn_initial = btn("⚡ 同步 (0)", False)
        self.btn_stop    = danger_btn("■ 停止"); self.btn_stop.setEnabled(False)
        self.btn_viz     = btn("看板", False)
        self.btn_out     = btn("输出包", False)
        self.status_lbl  = lbl("就绪", obj="Muted")

        self.btn_start.clicked.connect(self.start_sim)
        self.btn_fields.clicked.connect(self._open_fields)
        self.btn_initial.clicked.connect(self.toggle_is_initial)
        self.btn_stop.clicked.connect(self.stop_sim)
        self.btn_viz.clicked.connect(self._launch_viz_manual)
        self.btn_out.clicked.connect(lambda: os.startfile(os.path.join(APP_DIR,"..","FmuSolver_Package")))

        for w2 in [self.btn_start, self.chk_auto_vis, self.btn_fields,
                   self.btn_initial, self.btn_stop, self.btn_viz, self.btn_out]:
            btn_bar.addWidget(w2)
        btn_bar.addStretch()
        btn_bar.addWidget(self.status_lbl)
        lay.addLayout(btn_bar)

        # Log console
        lay.addWidget(lbl("实时运行状态与诊断", obj="Title"))
        self.txt_log = QPlainTextEdit(); self.txt_log.setObjectName("Console")
        self.txt_log.setReadOnly(True); self.txt_log.setMinimumHeight(160)
        lay.addWidget(self.txt_log, 1)
        lay.addStretch()

        self.tab_sim.setWidget(w)

    # ═══════════════════════════════════════
    #  TAB 3: Yaoce Relay
    # ═══════════════════════════════════════
    def _build_yaoce_tab(self):
        w = QWidget(); w.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(w); lay.setContentsMargins(16,12,16,16); lay.setSpacing(12)

        # Config card
        c1 = card(); cl1 = QVBoxLayout(c1); cl1.setContentsMargins(16,14,16,14); cl1.setSpacing(10)
        cl1.addWidget(lbl("1. 配置文件与过滤白名单检查", obj="Title"))
        self.yaoce_dir_lbl = lbl(f"当前配置读取目录: {self.yaoce_dir}", obj="Muted")
        cl1.addWidget(self.yaoce_dir_lbl)

        row = QHBoxLayout(); row.setSpacing(8)
        b_dir   = btn("更改目录", False)
        b_cfg   = text_btn("打开 config.ini")
        b_xml   = text_btn("打开 ParamFilter.xml")
        b_logs  = text_btn("打开日志文件夹")
        b_dir.clicked.connect(self._choose_yaoce_dir)
        b_cfg.clicked.connect(lambda: self._open_yaoce_file("config.ini"))
        b_xml.clicked.connect(lambda: self._open_yaoce_file("ParamFilter.xml"))
        b_logs.clicked.connect(self._open_yaoce_logs)
        for bw in [b_dir, b_cfg, b_xml, b_logs]: row.addWidget(bw)
        row.addStretch()
        cl1.addLayout(row)
        lay.addWidget(c1)

        # Control buttons
        ctrl = QHBoxLayout(); ctrl.setSpacing(10)
        self.btn_yaoce_start = btn("启动遥测引擎")
        self.btn_yaoce_stop  = danger_btn("停止服务"); self.btn_yaoce_stop.setEnabled(False)
        self.btn_yaoce_start.clicked.connect(self.start_yaoce)
        self.btn_yaoce_stop.clicked.connect(self.stop_yaoce)
        ctrl.addWidget(self.btn_yaoce_start); ctrl.addWidget(self.btn_yaoce_stop); ctrl.addStretch()
        lay.addLayout(ctrl)

        # Log
        lay.addWidget(lbl("2. 转发服务实时调试日志", obj="Title"))
        self.txt_yaoce_log = QPlainTextEdit(); self.txt_yaoce_log.setObjectName("Console")
        self.txt_yaoce_log.setReadOnly(True); self.txt_yaoce_log.setMinimumHeight(300)
        lay.addWidget(self.txt_yaoce_log, 1)
        lay.addStretch()
        self.tab_yaoce.setWidget(w)
        self.ylog("[SYS] 遥测接收转发模块已就绪，请先检查参数配置是否正确。", "sys")

    # ─── Yaoce helpers ───
    def _choose_yaoce_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择遥测配置文件目录 (需包含 config.ini)", APP_DIR)
        if d:
            self.yaoce_dir = os.path.normpath(d)
            self.yaoce_dir_lbl.setText(f"当前配置读取目录: {self.yaoce_dir}")
            self._save_gui_config()

    def _open_yaoce_file(self, name):
        p = os.path.join(self.yaoce_dir, name)
        if os.path.exists(p): os.startfile(p)
        else: self.ylog(f"[!] {p} 不存在!", "error")

    def _open_yaoce_logs(self):
        log_dir = os.path.join(self.yaoce_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)

    def _open_yaoce_logs(self):
        log_dir = os.path.join(self.yaoce_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)

    def _open_fields(self):
        sync_path = os.path.join(APP_DIR, "sync_fields.json")
        dlg = FieldsDialog(sync_path, self)
        dlg.exec()
