import re

with open('FmuLauncherUniversal.py','r',encoding='utf-8') as f:
    txt = f.read()

# 1. Fix broken lambda in toggle_is_initial
old = ('QTimer.singleShot(500, lambda: [\n'
       '                self.send_ctrl_signal("Is_initial", 0.0),\n'
       '                self.btn_initial.setText("\u26a1 \u540c\u6b65\u4fe1\u53f7 (\u8109\u51b2\u89e6\u53d1)"); self.btn_initial.setEnabled(True)\n'
       '            ])')
new = ('QTimer.singleShot(500, lambda: [\n'
       '                self.send_ctrl_signal("Is_initial", 0.0) or\n'
       '                self.btn_initial.setText("\u26a1 \u540c\u6b65 (0)") or\n'
       '                self.btn_initial.setEnabled(True)\n'
       '            ])')
txt = txt.replace(old, new)

# 2. Fix any remaining root.after calls
txt = re.sub(r'self\.root\.after\((\d+),\s*', r'QTimer.singleShot(\1, ', txt)
txt = re.sub(r'self\.root\.after\(0,\s*', 'QTimer.singleShot(0, ', txt)

# 3. Fix _reset_ui residual label configs
txt = re.sub(r"self\.orbit_progress_label\.config\([^)]+\)", 'self.orbit_prog_lbl.setText("\u8ba1\u7b97\u505c\u6b62")', txt)
txt = re.sub(r"self\.progress_label\.config\([^)]+\)", 'self.sim_prog_lbl.setText("\u4eff\u771f\u505c\u6b62")', txt)

# 4. QTimer singleShot lambda lists with or-chaining for single-expression lambdas
# (already done above)

with open('FmuLauncherUniversal.py','w',encoding='utf-8') as f:
    f.write(txt)

print("patch done, lines:", len(txt.splitlines()))
