"""
Assembles FmuLauncherUniversal.py from Part1 + Part2 + transformed business logic.
Run: python _build_launcher.py
"""
import re, os

SRC = "FmuLauncherUniversal_tkinter_backup.py"
P1  = "FmuLauncherUniversal.py"   # already written (Part 1)
P2  = "_part2.py"                  # already written (Part 2 UI)
OUT = "FmuLauncherUniversal.py"

# ── Substitution table (Tkinter -> Qt) ──
SUBS = [
    # variable accessors
    (r"self\.fmu_path_var\.get\(\)\.strip\(\)", "self.fmu_path_edit.text().strip()"),
    (r"self\.fmu_path_var\.get\(\)", "self.fmu_path_edit.text().strip()"),
    (r"self\.fmu_path_var\.set\(([^)]+)\)", r"self.fmu_path_edit.setText(\1)"),
    (r"self\.orbit_fmu_path_var\.get\(\)\.strip\(\)", "self.orbit_fmu_edit.text().strip()"),
    (r"self\.orbit_fmu_path_var\.get\(\)", "self.orbit_fmu_edit.text().strip()"),
    (r"self\.orbit_fmu_path_var\.set\(([^)]+)\)", r"self.orbit_fmu_edit.setText(\1)"),
    (r"self\.ip_var\.get\(\)\.strip\(\)", "self.ip_edit.text().strip()"),
    (r"self\.ip_var\.get\(\)", "self.ip_edit.text().strip()"),
    (r"self\.port_var\.get\(\)", "int(self.port_edit.text() or '12345')"),
    (r"self\.replace_dot_var\.get\(\)", "self.chk_replace_dot.isChecked()"),
    (r"self\.launch_visualizer_var\.get\(\)", "self.chk_auto_vis.isChecked()"),
    (r"self\.step_var\.get\(\)", "float(self.step_e.text() or '0.02')"),
    (r"self\.rate_var\.get\(\)", "float(self.rate_e.text() or '1.0')"),
    (r"self\.freq_var\.get\(\)", "float(self.freq_e.text() or '50.0')"),
    (r"self\.time_var\.get\(\)", "float(self.time_e.text() or '86400.0')"),
    (r"self\.orbit_step\.get\(\)", "float(self.o_step_e.text() or '10.0')"),
    (r"self\.orbit_rate\.get\(\)", "float(self.o_rate_e.text() or '0.0')"),
    (r"self\.orbit_freq\.get\(\)", "float(self.o_freq_e.text() or '0.1')"),
    (r"self\.orbit_duration\.get\(\)", "float(self.o_dur_e.text() or '86400.0')"),
    (r"self\.year_var\.get\(\)", "int(self.year_e.text() or '2026')"),
    (r"self\.mon_var\.get\(\)", "int(self.mon_e.text() or '1')"),
    (r"self\.day_var\.get\(\)", "int(self.day_e.text() or '1')"),
    (r"self\.hour_var\.get\(\)", "int(self.hour_e.text() or '0')"),
    (r"self\.min_var\.get\(\)", "int(self.min_e.text() or '0')"),
    (r"self\.sec_var\.get\(\)", "float(self.sec_e.text() or '0.0')"),
    (r"self\.a_mt_var\.get\(\)", "float(self.a_e.text() or '6766.71777')"),
    (r"self\.e_mt_var\.get\(\)", "float(self.ecc_e.text() or '0.0011')"),
    (r"self\.i_mt_var\.get\(\)", "float(self.inc_e.text() or '0.72653')"),
    (r"self\.OMEGA_mt_var\.get\(\)", "float(self.om_e.text() or '2.39969')"),
    (r"self\.omega_mt_var\.get\(\)", "float(self.w_e.text() or '1.34409')"),
    (r"self\.f_mt_var\.get\(\)", "float(self.f_e.text() or '1.00447')"),
    (r"self\.cj_year\.get\(\)", "int(self.cj_year_e.text() or '2026')"),
    (r"self\.cj_mon\.get\(\)", "int(self.cj_mon_e.text() or '3')"),
    (r"self\.cj_day\.get\(\)", "int(self.cj_day_e.text() or '31')"),
    (r"self\.cj_hour\.get\(\)", "int(self.cj_hour_e.text() or '12')"),
    (r"self\.cj_min\.get\(\)", "int(self.cj_min_e.text() or '19')"),
    (r"self\.cj_sec\.get\(\)", "float(self.cj_sec_e.text() or '0.0')"),
    (r"self\.cj_table_a\.get\(\)", "self.cj_ta_e.text()"),
    (r"self\.cj_table_b\.get\(\)", "self.cj_tb_e.text()"),
    (r"self\.cj_table_fb\.get\(\)", "self.cj_tfb_e.text()"),
    (r"self\.cj_table_att\.get\(\)", "self.cj_tatt_e.text()"),
    (r"self\.cj_pointsun\.get\(\)", "self.chk_pointsun.isChecked()"),
    # button states
    (r"self\.btn_start\.config\(state=tk\.DISABLED\)", "self.btn_start.setEnabled(False)"),
    (r"self\.btn_start\.config\(state=tk\.NORMAL\)", "self.btn_start.setEnabled(True)"),
    (r"self\.btn_stop\.config\(state=tk\.NORMAL\)", "self.btn_stop.setEnabled(True)"),
    (r"self\.btn_stop\.config\(state=tk\.DISABLED\)", "self.btn_stop.setEnabled(False)"),
    (r"self\.btn_run_orbit\.config\(state=tk\.DISABLED,\s*text=\"([^\"]+)\"\)", r'self.btn_run_orbit.setText("\1"); self.btn_run_orbit.setEnabled(False)'),
    (r"self\.btn_run_orbit\.config\(state=tk\.NORMAL,\s*text=\"([^\"]+)\"\)", r'self.btn_run_orbit.setText("\1"); self.btn_run_orbit.setEnabled(True)'),
    (r"self\.btn_stop_orbit\.config\(state=tk\.NORMAL\)", "self.btn_stop_orbit.setEnabled(True)"),
    (r"self\.btn_stop_orbit\.config\(state=tk\.DISABLED\)", "self.btn_stop_orbit.setEnabled(False)"),
    (r"self\.btn_export_txt\.config\(state=tk\.NORMAL\)", "self.btn_export.setEnabled(True)"),
    (r"self\.btn_yaoce_start\.config\(state=tk\.DISABLED\)", "self.btn_yaoce_start.setEnabled(False)"),
    (r"self\.btn_yaoce_start\.config\(state=tk\.NORMAL\)", "self.btn_yaoce_start.setEnabled(True)"),
    (r"self\.btn_yaoce_stop\.config\(state=tk\.NORMAL\)", "self.btn_yaoce_stop.setEnabled(True)"),
    (r"self\.btn_yaoce_stop\.config\(state=tk\.DISABLED\)", "self.btn_yaoce_stop.setEnabled(False)"),
    (r"self\.btn_initial\.config\(text=\"([^\"]+)\",\s*bg=\"[^\"]+\",\s*state=tk\.DISABLED\)", r'self.btn_initial.setText("\1"); self.btn_initial.setEnabled(False)'),
    (r"self\.btn_initial\.config\(text=\"([^\"]+)\",\s*bg=\"[^\"]+\",\s*state=tk\.NORMAL\)", r'self.btn_initial.setText("\1"); self.btn_initial.setEnabled(True)'),
    # progress
    (r"self\.progress_var\.set\(([^)]+)\)", r"self.sim_progress.setValue(int(\1))"),
    (r"self\.progress_label\.config\(text=([^,)]+)(?:,\s*fg=[^)]+)?\)", r"self.sim_prog_lbl.setText(\1)"),
    (r"self\.orbit_progress_var\.set\(([^)]+)\)", r"self.orbit_progress.setValue(int(\1))"),
    (r"self\.orbit_progress_label\.config\(text=([^,)]+)(?:,\s*fg=[^)]+)?\)", r"self.orbit_prog_lbl.setText(\1)"),
    # status
    (r"self\.status_var\.set\(([^)]+)\)", r"self.status_lbl.setText(\1)"),
    # root.after -> QTimer.singleShot
    (r"self\.root\.after\(0,\s*", "QTimer.singleShot(0, "),
    (r"self\.root\.after\(500,\s*", "QTimer.singleShot(500, "),
    (r"self\.root\.after\(2000,\s*", "QTimer.singleShot(2000, "),
    (r"self\.root\.after\(200,\s*", "QTimer.singleShot(200, "),
    # log methods (txt_log / txt_orbit_log -> QPlainTextEdit)
    (r"self\.txt_log\.delete\(1\.0,\s*tk\.END\)", "self.txt_log.clear()"),
    (r"self\.txt_log\.insert\(tk\.END,\s*msg\s*\+\s*\"\\n\",\s*tag\)", "_qt_log(self.txt_log, msg, tag)"),
    (r"self\.txt_log\.see\(tk\.END\)", ""),
    (r"self\.txt_orbit_log\.insert\(tk\.END,\s*msg\s*\+\s*\"\\n\",\s*tag\)", "_qt_log(self.txt_orbit_log, msg, tag)"),
    (r"self\.txt_orbit_log\.see\(tk\.END\)", ""),
    (r"self\.txt_yaoce_log\.insert\(tk\.END,\s*msg\s*\+\s*\"\\n\",\s*tag\)", "_qt_log(self.txt_yaoce_log, msg, tag)"),
    (r"self\.txt_yaoce_log\.see\(tk\.END\)", ""),
    # file dialogs
    (r"filedialog\.askopenfilename\(initialdir=([^,]+),\s*filetypes=\[.*?\]\)", r"QFileDialog.getOpenFileName(self, 'Open FMU', \1, 'FMU Files (*.fmu)')[0]"),
    (r"filedialog\.asksaveasfilename\(defaultextension=\"\.txt\",\s*initialfile=\"([^\"]+)\"\)", r"QFileDialog.getSaveFileName(self, 'Save', '\1', 'Text Files (*.txt)')[0]"),
    (r"filedialog\.askdirectory\([^)]+\)", r"QFileDialog.getExistingDirectory(self, 'Select Directory', APP_DIR)"),
    # messagebox
    (r"from tkinter import messagebox\s*\n\s*messagebox\.showerror\(\"([^\"]+)\",\s*\"([^\"]+)\"\)", r'QMessageBox.critical(self, "\1", "\2")'),
    (r"messagebox\.showerror\(\"([^\"]+)\",\s*\"([^\"]+)\"\)", r'QMessageBox.critical(self, "\1", "\2")'),
    # lbl_yaoce_dir
    (r"self\.lbl_yaoce_dir\.config\(text=([^)]+)\)", r"self.yaoce_dir_lbl.setText(\1)"),
    # remove tk imports that may leak through
    (r"import tkinter.*\n", ""),
    (r"from tkinter.*\n", ""),
    (r",\s*tk\.END", ""),
    (r"\btk\.(NORMAL|DISABLED|END|X|Y|BOTH|LEFT|RIGHT|TOP|BOTTOM|W|E|N|S)\b", r"'\1'"),
]

# ── Helper injected into output ──
QT_LOG_HELPER = '''
def _qt_log(widget, msg, tag="sys"):
    TAG_COLORS = {"info": "#28CD41", "error": "#FF3B30", "sys": "#86868B"}
    color = TAG_COLORS.get(tag, "#86868B")
    widget.appendHtml(f'<span style="color:{color};">{msg}</span>')
    widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())
'''

# ── Entry point replacement ──
QT_MAIN = '''
if __name__ == "__main__":
    try:
        with open(os.path.join(APP_DIR, "sys_argv.log"), "a", encoding="utf-8") as f:
            f.write(f"sys.argv={sys.argv}\\n")
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
        parser.add_argument("--time", type=float, default=float("inf"))
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
            player = FMUPlayer(args.fmu_path, args.ip, args.port, sim_id=args.sim_id,
                               sync_vars_file=args.sync_vars, control_port=args.control_port)
            player.run(step_size=args.step, sim_time=args.time, sim_rate=args.rate,
                       sample_freq=args.freq, init_params=init_params_dict)
        except Exception as e:
            with open(os.path.join(APP_DIR, "worker_fatal.log"), "a", encoding="utf-8") as f:
                f.write(f"Worker Fatal Error: {e}\\n")
        sys.exit(0)

    elif len(sys.argv) > 1 and sys.argv[1] == "--yaoceworker":
        APP_DIR_W = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        log_file  = os.path.join(APP_DIR_W, "yaoce_run.log")
        fatal_log = os.path.join(APP_DIR_W, "yaoce_fatal.log")
        try:
            with open(log_file, "w", encoding="utf-8") as f: f.write("")
        except: pass
        import builtins
        class FileOut:
            def __init__(self, prefix=""): self.p = prefix
            def write(self, text):
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write((self.p + text) if (text.strip() and self.p) else text)
                except: pass
            def flush(self): pass
        my_out = FileOut()
        sys.stdout = my_out
        sys.stderr = FileOut("[!ERR] ")
        def _my_print(*args, **kwargs):
            try: my_out.write(" ".join(map(str, args)) + "\\n")
            except: pass
        builtins.print = _my_print
        yaoce_mod = os.path.join(APP_DIR_W, "yaocetest")
        if yaoce_mod not in sys.path: sys.path.append(yaoce_mod)
        yaoce_cfg = sys.argv[2] if len(sys.argv) > 2 else yaoce_mod
        try:
            from yaocetest.main import YaoCeLinkLayerApp
            my_out.write(f"[SYS] Starting. Config: {yaoce_cfg}\\n")
            YaoCeLinkLayerApp(yaoce_cfg).start()
        except Exception as e:
            my_out.write(f"[!] YaoCe Worker Error: {e}\\n")
        sys.exit(0)

    else:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        window = FmuSolverGUI()
        window.show()
        sys.exit(app.exec())
'''

# ── Methods to extract from backup ──
METHODS = [
    "browse_file",
    "log",
    "olog",
    "ylog",
    "get_cj_params",
    "start_sim",
    "_read_worker_logs",
    "_launch_viz_manual",
    "_reset_ui",
    "stop_sim",
    "_terminate_worker",
    "update_params",
    "toggle_is_initial",
    "send_ctrl_signal",
    "run_orbit_precalc",
    "stop_orbit",
    "_save_to_orbit_txt",
    "export_orbit_txt",
    "start_yaoce",
    "stop_yaoce",
    "_browse_orbit_file",
]

def extract_methods(src_text, method_names):
    """Extract complete method bodies from a class in the source text."""
    lines = src_text.splitlines(keepends=True)
    collected = []
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        for name in method_names:
            if stripped.startswith(f"def {name}(self"):
                # collect until next def at same indent level or end
                indent = len(lines[i]) - len(lines[i].lstrip())
                block = [lines[i]]
                j = i + 1
                while j < len(lines):
                    if lines[j].strip() == "":
                        block.append(lines[j])
                        j += 1
                        continue
                    cur_indent = len(lines[j]) - len(lines[j].lstrip())
                    if cur_indent <= indent and lines[j].lstrip().startswith("def "):
                        break
                    block.append(lines[j])
                    j += 1
                collected.append("".join(block))
                i = j - 1
                break
        i += 1
    return "\n".join(collected)

def apply_subs(text):
    for pattern, repl in SUBS:
        text = re.sub(pattern, repl, text)
    return text

# ── Also fix the _browse_orbit_file method name ──
def fix_browse_orbit(text):
    return text.replace("def _browse_orbit_file(self)", "def _browse_orbit_fmu(self)")

def fix_misc(text):
    # Fix root.after lambdas that have lists
    text = text.replace("QTimer.singleShot(0, lambda v=pct_val, t=t_val: [\n",
                        "def _upd_sim(v=pct_val, t=t_val):\n")
    # Remove old tk.Tk root references
    text = text.replace("self.root.", "")
    # Fix any leftover tk. references
    text = re.sub(r'\btk\.(?!END|X|Y|BOTH|LEFT|RIGHT|TOP|BOTTOM|W|E|N|S)\w+', '', text)
    return text

def build():
    # Read parts
    p1 = open(P1, encoding="utf-8").read()
    p2 = open(P2, encoding="utf-8").read()
    backup = open(SRC, encoding="utf-8").read()

    # Extract & transform business logic
    logic = extract_methods(backup, METHODS)
    logic = apply_subs(logic)
    logic = fix_browse_orbit(logic)

    # Combine
    full = (
        p1.rstrip() + "\n\n" +
        QT_LOG_HELPER + "\n" +
        p2.rstrip() + "\n\n" +
        "    # ─── Business Logic ───\n" +
        logic + "\n\n" +
        QT_MAIN
    )

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"Done. Written to {OUT} ({len(full.splitlines())} lines)")

if __name__ == "__main__":
    build()
