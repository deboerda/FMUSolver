with open('c:/Spaceship/FMUSOLVER/Script/DataVisualizerPython.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_on_table_changed = False
lines_to_move = []

for line in lines:
    if 'def on_table_item_changed(self, item):' in line:
        in_on_table_changed = True
        new_lines.append(line)
        continue
    
    if in_on_table_changed:
        if line.strip() == '' or line.startswith('        if') or line.startswith('            '):
            new_lines.append(line)
        elif 'self.left_panel.setMinimumWidth' in line or 'splitter.addWidget' in line or 'self.dock_area = DockArea()' in line or 'main_layout.addWidget(splitter)' in line or 'self.create_dock_internal' in line or 'splitter.setStretchFactor' in line:
            lines_to_move.append(line)
        elif 'def ' in line:
            in_on_table_changed = False
            new_lines.append(line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

# Now find the end of setup_ui and insert the moved lines
final_lines = []
for line in new_lines:
    final_lines.append(line)
    if 'self.table.itemChanged.connect(self.on_table_item_changed)' in line:
        final_lines.append('        left_layout.addWidget(self.table)\n')
        for m_line in lines_to_move:
            # Adjust indentation if needed, but they are already at 8 spaces
            final_lines.append(m_line)

# Remove the duplicated left_layout.addWidget(self.table) if it exists
# (It might be in both places now)

with open('c:/Spaceship/FMUSOLVER/Script/DataVisualizerPython.py', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)
