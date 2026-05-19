"""Fix all bad QTimer.singleShot(0, callable, arg1, arg2) calls."""
import re

with open('FmuLauncherUniversal.py', 'r', encoding='utf-8') as f:
    txt = f.read()

# Pattern: QTimer.singleShot(0, self.log,  line_str, tag)
# Replace:  QTimer.singleShot(0, lambda l=line_str, t=tag: self.log(l, t))
txt = re.sub(
    r'QTimer\.singleShot\(0,\s*self\.log,\s*line_str,\s*tag\)',
    'QTimer.singleShot(0, lambda l=line_str, t=tag: self.log(l, t))',
    txt
)

# Pattern: QTimer.singleShot(0, self.olog, line_str, tag)
txt = re.sub(
    r'QTimer\.singleShot\(0,\s*self\.olog,\s*line_str,\s*tag\)',
    'QTimer.singleShot(0, lambda l=line_str, t=tag: self.olog(l, t))',
    txt
)

# Pattern: QTimer.singleShot(0, self.olog, f"...", "info"/"error"/"sys")
# These have literal strings - convert to lambdas
def fix_olog_literal(m):
    msg = m.group(1)
    tag = m.group(2)
    return f'QTimer.singleShot(0, lambda: self.olog({msg}, {tag}))'

txt = re.sub(
    r'QTimer\.singleShot\(0,\s*self\.olog,\s*(f?"[^"]*"|f\'[^\']*\'),\s*("(?:info|error|sys)")\)',
    fix_olog_literal,
    txt
)

# Also fix QTimer.singleShot(0, self._reset_ui) - this is fine
# Fix also: _read_worker_logs final line calls
# self.root.after(0, self._reset_ui) -> QTimer.singleShot(0, self._reset_ui)  -- already correct

# Fix _reset_ui: the orbit_progress_bar and sim_progress setValue need int()
txt = txt.replace(
    'self.sim_progress.setValue(int(0))',
    'self.sim_progress.setValue(0)'
)
txt = txt.replace(
    'self.orbit_progress.setValue(int(0))',
    'self.orbit_progress.setValue(0)'
)

# Fix progress setValue calls that wrap pct_val (already int from regex match)
# self.sim_progress.setValue(int(pct_val))  -- fine, pct_val is int
# self.orbit_progress.setValue(int(pct_val)) -- fine

# Fix the _read_worker_logs progress update lambda
# Original pattern from backup:
# self.root.after(0, lambda v=pct_val, t=t_val: [
#     self.progress_var.set(v),
#     self.progress_label.config(...)
# ])
# After substitution, this became a broken multi-statement lambda
# Find and fix it
old_sim_update = (
    'QTimer.singleShot(0, lambda v=pct_val, t=t_val: [\n'
    '                        self.sim_progress.setValue(int(v)),\n'
    '                        self.sim_prog_lbl.setText(f\\'仿真进度: {v}% (已运行 {t:.1f}s / 总计 {total_t:.0f}s)\\')\n'
    '                    ])'
)
new_sim_update = (
    'def _upd_sim_prog(v=pct_val, t=t_val):\n'
    '                        self.sim_progress.setValue(int(v))\n'
    '                        self.sim_prog_lbl.setText(f"仿真进度: {v}% (已运行 {t:.1f}s / 总计 {total_t:.0f}s)")\n'
    '                    QTimer.singleShot(0, _upd_sim_prog)'
)

old_orbit_update = (
    'QTimer.singleShot(0, lambda v=pct_val, t=t_val: [\n'
    '                            self.orbit_progress.setValue(int(v)),\n'
    '                            self.orbit_prog_lbl.setText(f\\'计算进度: {v}% (已解析 {t:.0f}s / 总计 {total_t:.0f}s)\\')\n'
    '                        ])'
)
new_orbit_update = (
    'def _upd_orbit_prog(v=pct_val, t=t_val):\n'
    '                            self.orbit_progress.setValue(int(v))\n'
    '                            self.orbit_prog_lbl.setText(f"计算进度: {v}% (已解析 {t:.0f}s / 总计 {total_t:.0f}s)")\n'
    '                        QTimer.singleShot(0, _upd_orbit_prog)'
)

if old_sim_update in txt:
    txt = txt.replace(old_sim_update, new_sim_update)
    print("Fixed sim progress lambda")
if old_orbit_update in txt:
    txt = txt.replace(old_orbit_update, new_orbit_update)
    print("Fixed orbit progress lambda")

# Generic fix for any remaining [ list ] lambda pattern
# QTimer.singleShot(N, lambda ...: [...])
def fix_list_lambda(m):
    """Convert lambda: [a, b] to a proper def."""
    return m.group(0)  # leave for manual fix if not caught

with open('FmuLauncherUniversal.py', 'w', encoding='utf-8') as f:
    f.write(txt)

print("Done. Checking remaining bad QTimer calls:")
for i, l in enumerate(txt.splitlines(), 1):
    if 'QTimer.singleShot' in l and ('self.log,' in l or 'self.olog,' in l or 'self.ylog,' in l):
        print(f"  Line {i}: {l.strip()}")
print("Check complete.")
