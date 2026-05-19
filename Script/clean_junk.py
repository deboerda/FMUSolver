with open('c:/Spaceship/FMUSOLVER/Script/FmuLauncherUniversal.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# I want to keep everything up to the FIRST self.setStyleSheet(qss)
# and skip everything until the FIRST _setup_window

new_lines = []
found_first_qss = False
skip = False
for i, line in enumerate(lines):
    if not found_first_qss:
        new_lines.append(line)
        if 'self.setStyleSheet(qss)' in line:
            found_first_qss = True
            skip = True
    elif skip:
        if 'def _setup_window(self):' in line:
            skip = False
            new_lines.append('\n') # add a newline for spacing
            new_lines.append(line)
    else:
        new_lines.append(line)

with open('c:/Spaceship/FMUSOLVER/Script/FmuLauncherUniversal.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
