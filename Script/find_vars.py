import fmpy
import sys

# Ensure stdout handles utf-8 gracefully if possible, or just ignore errors
# by redirecting via io
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

md = fmpy.read_model_description(r'C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu')
matched = []
for v in md.modelVariables:
    name = v.name.lower()
    if ('orbit' in name or 'element' in name or 'a_mt' in name or 'a_' in name or 'e_' in name or 'i_' in name or 'omega' in name or 'f_' in name or 'day' in name or 'jd' in name):
        if v.causality == 'local':
            matched.append(f"{v.name} ({v.causality}) - {getattr(v, 'description', '')}")

with open(r'C:\Spaceship\matched_vars.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(matched))
print("Done")
