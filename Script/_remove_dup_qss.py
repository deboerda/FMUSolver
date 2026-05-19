"""Remove the orphaned old QSS block from FmuLauncherUniversal.py"""
with open('FmuLauncherUniversal.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the duplicate: after the new APP_QSS closing """, there's leftover CSS
# The new QSS ends with:  """  followed by a blank line
# Then the old block starts at "# --- Low-level helpers" which was wrongly placed
# We need to remove everything from the second QSS fragment up to actual helpers

content = ''.join(lines)

# The new QSS ends with:
marker_end = '"""\n\n# \u2500\u2500\u2500 Low-level helpers (unchanged) \u2500\u2500\u2500\n'
# Find the SECOND occurrence of the helpers marker
idx1 = content.find('# \u2500\u2500\u2500 Low-level helpers')
idx2 = content.find('# \u2500\u2500\u2500 Low-level helpers', idx1 + 1)

if idx2 == -1:
    print("No duplicate found - maybe already clean")
else:
    # Find the closing """ before idx2
    close_qss = content.rfind('"""\n', 0, idx2)
    print(f"Cutting from char {close_qss} to {idx2}")
    # Cut: keep everything up to and including the """\n, skip to idx2
    content = content[:close_qss + 4] + '\n' + content[idx2:]
    with open('FmuLauncherUniversal.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Done. Lines now: {len(content.splitlines())}")
